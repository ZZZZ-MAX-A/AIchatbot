from __future__ import annotations

import asyncio
import json
import ssl
import unittest
from contextlib import asynccontextmanager

import httpcore

from pure_ai_chat_loader import load_tavily_search_modules


class FakeResolver:
    def __init__(self, addresses=("93.184.216.34",)) -> None:
        self.addresses = addresses
        self.calls = []

    async def resolve(self, host, port):
        self.calls.append((host, port))
        return self.addresses


class FakeStream(httpcore.AsyncNetworkStream):
    def __init__(self) -> None:
        self.tls_calls = []
        self.closed = False

    async def read(self, max_bytes, timeout=None):
        return b""

    async def write(self, buffer, timeout=None):
        return None

    async def aclose(self):
        self.closed = True

    async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        self.tls_calls.append((ssl_context, server_hostname, timeout))
        return self

    def get_extra_info(self, info):
        return None


class FakeBackend(httpcore.AsyncNetworkBackend):
    def __init__(self) -> None:
        self.connect_calls = []
        self.stream = FakeStream()

    async def connect_tcp(
        self,
        host,
        port,
        timeout=None,
        local_address=None,
        socket_options=None,
    ):
        self.connect_calls.append(
            (host, port, timeout, local_address, socket_options)
        )
        return self.stream

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise AssertionError("Unix sockets must not be used")

    async def sleep(self, seconds):
        return None


class ChunkedResponse(httpcore.Response):
    def __init__(self, status, headers, chunks) -> None:
        async def content():
            for chunk in chunks:
                yield chunk

        super().__init__(status, headers=headers, content=content())


class FakePool:
    def __init__(self, response) -> None:
        self.response = response
        self.calls = []
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.exited = True

    @asynccontextmanager
    async def stream(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        try:
            yield self.response
        finally:
            await self.response.aclose()


class TavilyPinnedHttpTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        modules = load_tavily_search_modules()
        cls.security = modules["security"]
        cls.tavily_http = modules["tavily_http"]

    def make_transport(self, response, *, resolver=None, delegate=None):
        resolver = resolver or FakeResolver()
        delegate = delegate or FakeBackend()
        pools = []

        def pool_factory(backend, ssl_context):
            self.assertIsInstance(ssl_context, ssl.SSLContext)
            self.assertTrue(ssl_context.check_hostname)
            self.assertEqual(ssl_context.verify_mode, ssl.CERT_REQUIRED)
            pool = FakePool(response)
            pool.pinned_backend = backend
            pools.append(pool)
            return pool

        transport = self.tavily_http.PinnedTavilyHttpTransport(
            resolver=resolver,
            backend_factory=lambda: delegate,
            pool_factory=pool_factory,
        )
        return transport, resolver, delegate, pools

    def call(self, transport, *, max_response_bytes=262_144, headers=None):
        return asyncio.run(
            transport.post_json(
                "https://api.tavily.com/search",
                headers=headers
                or {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": "Bearer tvly-test",
                },
                json_body={
                    "query": "公开中文问题",
                    "search_depth": "basic",
                    "max_results": 3,
                },
                timeout_seconds=10,
                max_response_bytes=max_response_bytes,
            )
        )

    def test_transport_validates_dns_pins_tcp_and_sends_one_post(self):
        body = json.dumps({"results": []}).encode("utf-8")
        response = ChunkedResponse(
            200,
            [
                (b"Content-Type", b"application/json"),
                (b"Content-Length", str(len(body)).encode()),
            ],
            [body[:4], body[4:]],
        )
        transport, resolver, delegate, pools = self.make_transport(response)

        result = self.call(transport)

        self.assertEqual(resolver.calls, [("api.tavily.com", 443)])
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, "application/json")
        self.assertEqual(result.body, body)
        self.assertEqual(len(pools), 1)
        pool = pools[0]
        self.assertTrue(pool.entered)
        self.assertTrue(pool.exited)
        self.assertEqual(len(pool.calls), 1)
        method, url, request = pool.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://api.tavily.com/search")
        self.assertIn((b"Accept-Encoding", b"identity"), request["headers"])
        self.assertIn(b'"search_depth":"basic"', request["content"])
        self.assertEqual(request["extensions"]["timeout"]["connect"], 10.0)

        pinned = pool.pinned_backend
        stream = asyncio.run(
            pinned.connect_tcp("api.tavily.com", 443, timeout=10.0)
        )
        self.assertEqual(delegate.connect_calls[0][0], "93.184.216.34")
        tls_stream = asyncio.run(
            stream.start_tls(
                ssl.create_default_context(),
                server_hostname="api.tavily.com",
                timeout=10.0,
            )
        )
        self.assertIsNotNone(tls_stream)
        self.assertEqual(delegate.stream.tls_calls[0][1], "api.tavily.com")

    def test_transport_rejects_non_public_dns_before_creating_pool(self):
        response = ChunkedResponse(200, [], [b"{}"])
        resolver = FakeResolver(("127.0.0.1",))
        transport, _resolver, _delegate, pools = self.make_transport(
            response,
            resolver=resolver,
        )

        with self.assertRaises(self.security.ExternalReadPolicyError) as raised:
            self.call(transport)

        self.assertEqual(
            raised.exception.category,
            self.security.ExternalReadPolicyCategory.UNSAFE_RESOLVED_ADDRESS,
        )
        self.assertEqual(pools, [])

    def test_pinned_backend_rejects_host_port_and_tls_sni_changes(self):
        delegate = FakeBackend()
        backend = self.tavily_http._PinnedNetworkBackend(
            expected_host="api.tavily.com",
            expected_port=443,
            pinned_address="93.184.216.34",
            delegate=delegate,
        )
        for host, port in (("example.com", 443), ("api.tavily.com", 80)):
            with self.subTest(host=host, port=port):
                with self.assertRaises(OSError):
                    asyncio.run(backend.connect_tcp(host, port))
        stream = asyncio.run(backend.connect_tcp("api.tavily.com", 443))
        with self.assertRaises(OSError):
            asyncio.run(
                stream.start_tls(
                    ssl.create_default_context(),
                    server_hostname="example.com",
                )
            )
        self.assertTrue(delegate.stream.closed)

    def test_transport_rejects_declared_and_streamed_oversize_responses(self):
        cases = (
            ChunkedResponse(
                200,
                [(b"Content-Length", b"65")],
                [b"{}"],
            ),
            ChunkedResponse(
                200,
                [],
                [b"x" * 40, b"y" * 25],
            ),
        )
        for response in cases:
            with self.subTest(headers=response.headers):
                transport, _resolver, _delegate, _pools = self.make_transport(
                    response
                )
                with self.assertRaises(self.security.ExternalReadPolicyError) as raised:
                    self.call(transport, max_response_bytes=64)
                self.assertEqual(
                    raised.exception.category,
                    self.security.ExternalReadPolicyCategory.RESPONSE_TOO_LARGE,
                )

    def test_transport_rejects_compression_and_invalid_content_length(self):
        cases = (
            ChunkedResponse(
                200,
                [(b"Content-Encoding", b"gzip")],
                [b"compressed"],
            ),
            ChunkedResponse(
                200,
                [(b"Content-Length", b"invalid")],
                [b"{}"],
            ),
        )
        for response in cases:
            transport, _resolver, _delegate, _pools = self.make_transport(response)
            with self.assertRaises(self.security.ExternalReadPolicyError) as raised:
                self.call(transport)
            self.assertEqual(
                raised.exception.category,
                self.security.ExternalReadPolicyCategory.INVALID_PROVIDER_RESPONSE,
            )

    def test_transport_rejects_header_injection_before_dns(self):
        cases = (
            {"Authorization": "Bearer safe\r\nInjected: bad"},
            {"Host": "example.com"},
            {"Content-Length": "1"},
            {"Transfer-Encoding": "chunked"},
            {"Proxy-Authorization": "Basic secret"},
            {"Accept-Encoding": "gzip"},
        )
        for headers in cases:
            with self.subTest(headers=headers):
                response = ChunkedResponse(200, [], [b"{}"])
                transport, resolver, _delegate, pools = self.make_transport(response)
                with self.assertRaises(ValueError):
                    self.call(transport, headers=headers)
                self.assertEqual(resolver.calls, [])
                self.assertEqual(pools, [])


if __name__ == "__main__":
    unittest.main()
