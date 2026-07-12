from __future__ import annotations

import unittest

from pure_ai_chat_loader import load_external_read_security_module


class ExternalReadSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.security = load_external_read_security_module()

    def assert_policy_error(self, category, callback) -> None:
        with self.assertRaises(self.security.ExternalReadPolicyError) as raised:
            callback()
        self.assertEqual(raised.exception.category, category)

    def test_query_normalizes_whitespace_and_control_characters(self):
        query = self.security.normalize_external_read_query(
            "  Python\nasyncio\t在 2026 年的公开资料  "
        )

        self.assertEqual(query, "Python asyncio 在 2026 年的公开资料")

    def test_query_rejects_empty_non_text_and_over_limit_values(self):
        invalid = self.security.ExternalReadPolicyCategory.INVALID_QUERY
        cases = (
            "",
            " \n\t ",
            "a" * (self.security.EXTERNAL_READ_MAX_QUERY_CHARS + 1),
            None,
        )
        for value in cases:
            with self.subTest(value_type=type(value).__name__):
                self.assert_policy_error(
                    invalid,
                    lambda value=value: self.security.normalize_external_read_query(value),
                )

    def test_query_rejects_urls_local_paths_and_secrets(self):
        cases = (
            ("查询 https://example.com/private", "invalid_query"),
            ("读取 file:///etc/passwd", "invalid_query"),
            (r"分析 D:\AIchatbot\.env", "sensitive_query"),
            (r"读取 \\server\share\secret.txt", "sensitive_query"),
            ("读取 /etc/passwd", "sensitive_query"),
            ("api_key=super-secret-value", "sensitive_query"),
            ("API key = super-secret-value", "sensitive_query"),
            ("token=super-secret-value", "sensitive_query"),
            ("Authorization: Bearer abcdefghijklmnop", "sensitive_query"),
            ("Cookie: session=abcdef", "sensitive_query"),
            ("检查 sk-abcdefghijklmnop", "sensitive_query"),
            (
                "检查 eyJabcdefghijk.abcdefghijklmnop.qrstuvwxyzABCDE",
                "sensitive_query",
            ),
        )
        for query, category in cases:
            with self.subTest(query=query):
                self.assert_policy_error(
                    self.security.ExternalReadPolicyCategory(category),
                    lambda query=query: self.security.normalize_external_read_query(query),
                )

    def test_query_rejects_high_confidence_personal_data_but_not_plain_identifiers(self):
        sensitive = self.security.ExternalReadPolicyCategory.SENSITIVE_QUERY
        rejected = (
            "查询邮箱 owner@example.com 的公开记录",
            "查询手机号：13800138000",
            "查询电话 +86 13900139000",
            "查询 QQ号：123456789",
            "查询身份证号：11010519491231002X",
        )
        for query in rejected:
            with self.subTest(query=query):
                self.assert_policy_error(
                    sensitive,
                    lambda query=query: self.security.normalize_external_read_query(query),
                )

        accepted = (
            "RFC 9110 的缓存语义",
            "CVE-2026-12345 修复状态",
            "产品型号 123456789",
        )
        for query in accepted:
            with self.subTest(query=query):
                self.assertEqual(
                    self.security.normalize_external_read_query(query),
                    query,
                )

    def test_endpoint_accepts_only_exact_allowlisted_https_host(self):
        endpoint = self.security.validate_external_read_endpoint(
            "https://search.example.com/v1/search",
            allowed_hosts=("SEARCH.EXAMPLE.COM.",),
        )

        self.assertEqual(endpoint.source_host, "search.example.com")
        self.assertEqual(endpoint.base_url, "https://search.example.com/v1/search")

    def test_endpoint_rejects_unsafe_shapes(self):
        unsafe = self.security.ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT
        cases = (
            "http://search.example.com/v1/search",
            "https://user:pass@search.example.com/v1/search",
            "https://search.example.com:8443/v1/search",
            "https://search.example.com/v1/search?token=secret",
            "https://search.example.com/v1/search#fragment",
            "https://evil.example.com/v1/search",
            "https://search.example.com.evil.test/v1/search",
            "https://search.example.com\\@evil.test/v1/search",
            "https://search.example.com/v1/\nsearch",
            "not a URL",
            "",
        )
        for endpoint in cases:
            with self.subTest(endpoint=endpoint):
                self.assert_policy_error(
                    unsafe,
                    lambda endpoint=endpoint: self.security.validate_external_read_endpoint(
                        endpoint,
                        allowed_hosts=("search.example.com",),
                    ),
                )

    def test_endpoint_rejects_allowlisted_non_public_ip_literal(self):
        self.assert_policy_error(
            self.security.ExternalReadPolicyCategory.UNSAFE_RESOLVED_ADDRESS,
            lambda: self.security.validate_external_read_endpoint(
                "https://127.0.0.1/search",
                allowed_hosts=("127.0.0.1",),
            ),
        )

    def test_resolved_addresses_accept_only_public_ipv4_and_ipv6(self):
        addresses = self.security.validate_external_read_addresses(
            ("8.8.8.8", "2606:4700:4700::1111", "8.8.8.8")
        )

        self.assertEqual(addresses, ("8.8.8.8", "2606:4700:4700::1111"))

    def test_resolved_addresses_reject_private_reserved_and_metadata_ranges(self):
        unsafe = self.security.ExternalReadPolicyCategory.UNSAFE_RESOLVED_ADDRESS
        addresses = (
            "127.0.0.1",
            "0.0.0.0",
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",
            "100.64.0.1",
            "224.0.0.1",
            "255.255.255.255",
            "::1",
            "::",
            "fe80::1",
            "fc00::1",
            "ff02::1",
        )
        for address in addresses:
            with self.subTest(address=address):
                self.assert_policy_error(
                    unsafe,
                    lambda address=address: self.security.validate_external_read_addresses(
                        (address,)
                    ),
                )

    def test_resolved_addresses_reject_empty_and_invalid_results(self):
        unsafe = self.security.ExternalReadPolicyCategory.UNSAFE_RESOLVED_ADDRESS
        for addresses in ((), ("not-an-ip",)):
            with self.subTest(addresses=addresses):
                self.assert_policy_error(
                    unsafe,
                    lambda addresses=addresses: self.security.validate_external_read_addresses(
                        addresses
                    ),
                )

    def test_default_budget_matches_first_external_read_contract(self):
        budget = self.security.ExternalReadBudget()

        self.assertEqual(budget.max_results, 3)
        self.assertEqual(budget.max_response_bytes, 262_144)
        self.assertEqual(budget.timeout_seconds, 10)
        self.assertEqual(budget.external_request_count, 1)
        self.assertEqual(budget.redirect_count, 0)
        self.assertEqual(budget.retry_count, 0)

    def test_budget_rejects_expansion_and_non_integer_values(self):
        invalid = self.security.ExternalReadPolicyCategory.INVALID_BUDGET
        cases = (
            {"max_results": 0},
            {"max_results": 4},
            {"max_results": True},
            {"max_response_bytes": 0},
            {"max_response_bytes": 262_145},
            {"timeout_seconds": 0},
            {"timeout_seconds": 16},
            {"external_request_count": 2},
            {"redirect_count": 1},
            {"retry_count": 1},
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                self.assert_policy_error(
                    invalid,
                    lambda arguments=arguments: self.security.ExternalReadBudget(**arguments),
                )


if __name__ == "__main__":
    unittest.main()
