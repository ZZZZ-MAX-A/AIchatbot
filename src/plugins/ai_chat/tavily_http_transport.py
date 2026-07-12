from __future__ import annotations

import asyncio
import json
import socket
import ssl
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any, Mapping, Protocol

import httpcore
from httpcore._backends.auto import AutoBackend

from .external_read_security import (
    ExternalReadPolicyCategory,
    ExternalReadPolicyError,
    canonicalize_external_host,
    validate_external_read_addresses,
    validate_external_read_endpoint,
)
from .tavily_search import TAVILY_ALLOWED_HOSTS, TavilyHttpResponse


TAVILY_MAX_REQUEST_BYTES = 4_096


class TavilyAddressResolver(Protocol):
    async def resolve(self, host: str, port: int) -> tuple[str, ...]: ...


class SystemTavilyAddressResolver:
    async def resolve(self, host: str, port: int) -> tuple[str, ...]:
        loop = asyncio.get_running_loop()
        records = await loop.getaddrinfo(
            host,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
        addresses: list[str] = []
        for _family, _type, _proto, _canonical_name, socket_address in records:
            address = str(socket_address[0])
            if address not in addresses:
                addresses.append(address)
        return tuple(addresses)


class _PinnedNetworkStream(httpcore.AsyncNetworkStream):
    def __init__(
        self,
        stream: httpcore.AsyncNetworkStream,
        *,
        expected_server_hostname: str,
    ) -> None:
        self._stream = stream
        self._expected_server_hostname = expected_server_hostname

    async def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        return await self._stream.read(max_bytes, timeout=timeout)

    async def write(self, buffer: bytes, timeout: float | None = None) -> None:
        await self._stream.write(buffer, timeout=timeout)

    async def aclose(self) -> None:
        await self._stream.aclose()

    async def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> httpcore.AsyncNetworkStream:
        received_hostname = canonicalize_external_host(server_hostname or "")
        if received_hostname != self._expected_server_hostname:
            await self.aclose()
            raise OSError("Tavily TLS server hostname did not match the pinned host")
        tls_stream = await self._stream.start_tls(
            ssl_context,
            server_hostname=self._expected_server_hostname,
            timeout=timeout,
        )
        return _PinnedNetworkStream(
            tls_stream,
            expected_server_hostname=self._expected_server_hostname,
        )

    def get_extra_info(self, info: str) -> Any:
        return self._stream.get_extra_info(info)


class _PinnedNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(
        self,
        *,
        expected_host: str,
        expected_port: int,
        pinned_address: str,
        delegate: httpcore.AsyncNetworkBackend,
    ) -> None:
        self._expected_host = expected_host
        self._expected_port = expected_port
        self._pinned_address = pinned_address
        self._delegate = delegate

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ) -> httpcore.AsyncNetworkStream:
        received_host = canonicalize_external_host(host)
        if received_host != self._expected_host or port != self._expected_port:
            raise OSError("Tavily connection target did not match the pinned endpoint")
        stream = await self._delegate.connect_tcp(
            self._pinned_address,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )
        return _PinnedNetworkStream(
            stream,
            expected_server_hostname=self._expected_host,
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options=None,
    ) -> httpcore.AsyncNetworkStream:
        raise OSError("Tavily transport does not support Unix sockets")

    async def sleep(self, seconds: float) -> None:
        await self._delegate.sleep(seconds)


class TavilyConnectionPool(Protocol):
    def stream(
        self,
        method,
        url,
        *,
        headers=None,
        content=None,
        extensions=None,
    ) -> AbstractAsyncContextManager[httpcore.Response]: ...

    async def __aenter__(self) -> "TavilyConnectionPool": ...

    async def __aexit__(self, exc_type, exc, traceback) -> None: ...


ConnectionPoolFactory = Callable[
    [httpcore.AsyncNetworkBackend, ssl.SSLContext],
    TavilyConnectionPool,
]


def _default_pool_factory(
    backend: httpcore.AsyncNetworkBackend,
    ssl_context: ssl.SSLContext,
) -> TavilyConnectionPool:
    return httpcore.AsyncConnectionPool(
        ssl_context=ssl_context,
        max_connections=1,
        max_keepalive_connections=0,
        keepalive_expiry=0.0,
        http1=True,
        http2=False,
        retries=0,
        network_backend=backend,
    )


def _safe_headers(headers: Mapping[str, str]) -> list[tuple[bytes, bytes]]:
    if not isinstance(headers, Mapping):
        raise ValueError("Tavily headers must be a mapping")
    output: list[tuple[bytes, bytes]] = []
    for raw_name, raw_value in headers.items():
        if not isinstance(raw_name, str) or not isinstance(raw_value, str):
            raise ValueError("Tavily headers must contain text keys and values")
        try:
            name = raw_name.strip().encode("ascii")
            value = raw_value.strip().encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("Tavily headers must be ASCII") from exc
        if not name or any(character in name for character in b"\r\n:"):
            raise ValueError("Tavily header name is unsafe")
        if any(character in value for character in b"\r\n"):
            raise ValueError("Tavily header value is unsafe")
        lowered_name = name.lower()
        if lowered_name in {
            b"host",
            b"content-length",
            b"transfer-encoding",
            b"connection",
            b"proxy-authorization",
        }:
            raise ValueError("Tavily transport-owned header cannot be overridden")
        if lowered_name == b"accept-encoding" and value.lower() != b"identity":
            raise ValueError("Tavily response compression must stay disabled")
        output.append((name, value))
    lowered = {name.lower() for name, _value in output}
    if b"accept-encoding" not in lowered:
        output.append((b"Accept-Encoding", b"identity"))
    return output


def _response_header(headers: list[tuple[bytes, bytes]], name: bytes) -> str:
    lowered_name = name.lower()
    values = [
        value.decode("latin-1")
        for header_name, value in headers
        if header_name.lower() == lowered_name
    ]
    return ",".join(values)


class PinnedTavilyHttpTransport:
    def __init__(
        self,
        *,
        resolver: TavilyAddressResolver | None = None,
        backend_factory: Callable[[], httpcore.AsyncNetworkBackend] | None = None,
        pool_factory: ConnectionPoolFactory | None = None,
    ) -> None:
        self._resolver = resolver or SystemTavilyAddressResolver()
        self._backend_factory = backend_factory or AutoBackend
        self._pool_factory = pool_factory or _default_pool_factory

    async def post_json(
        self,
        endpoint: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, object],
        timeout_seconds: int,
        max_response_bytes: int,
    ) -> TavilyHttpResponse:
        validated_endpoint = validate_external_read_endpoint(
            endpoint,
            allowed_hosts=TAVILY_ALLOWED_HOSTS,
        )
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int):
            raise ValueError("Tavily timeout must be an integer")
        if not 1 <= timeout_seconds <= 15:
            raise ValueError("Tavily timeout must be between 1 and 15 seconds")
        if isinstance(max_response_bytes, bool) or not isinstance(
            max_response_bytes,
            int,
        ):
            raise ValueError("Tavily response budget must be an integer")
        if not 1 <= max_response_bytes <= 262_144:
            raise ValueError("Tavily response budget is invalid")
        if not isinstance(json_body, Mapping):
            raise ValueError("Tavily request body must be a mapping")
        request_body = json.dumps(
            dict(json_body),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(request_body) > TAVILY_MAX_REQUEST_BYTES:
            raise ValueError("Tavily request body exceeds the local budget")
        request_headers = _safe_headers(headers)

        try:
            resolved = await self._resolver.resolve(validated_endpoint.source_host, 443)
            public_addresses = validate_external_read_addresses(resolved)
            pinned_address = public_addresses[0]
            backend = _PinnedNetworkBackend(
                expected_host=validated_endpoint.source_host,
                expected_port=443,
                pinned_address=pinned_address,
                delegate=self._backend_factory(),
            )
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
            timeout = float(timeout_seconds)
            extensions = {
                "timeout": {
                    "connect": timeout,
                    "read": timeout,
                    "write": timeout,
                    "pool": timeout,
                }
            }
            async with self._pool_factory(backend, ssl_context) as pool:
                async with pool.stream(
                    "POST",
                    validated_endpoint.base_url,
                    headers=request_headers,
                    content=request_body,
                    extensions=extensions,
                ) as response:
                    content_encoding = _response_header(
                        response.headers,
                        b"content-encoding",
                    ).strip().lower()
                    if content_encoding not in {"", "identity"}:
                        raise ExternalReadPolicyError(
                            ExternalReadPolicyCategory.INVALID_PROVIDER_RESPONSE,
                            "Tavily response compression is unsupported",
                        )
                    content_length = _response_header(
                        response.headers,
                        b"content-length",
                    ).strip()
                    if content_length:
                        try:
                            declared_length = int(content_length)
                        except ValueError as exc:
                            raise ExternalReadPolicyError(
                                ExternalReadPolicyCategory.INVALID_PROVIDER_RESPONSE,
                                "Tavily Content-Length is invalid",
                            ) from exc
                        if declared_length < 0:
                            raise ExternalReadPolicyError(
                                ExternalReadPolicyCategory.INVALID_PROVIDER_RESPONSE,
                                "Tavily Content-Length is invalid",
                            )
                        if declared_length > max_response_bytes:
                            raise ExternalReadPolicyError(
                                ExternalReadPolicyCategory.RESPONSE_TOO_LARGE,
                                "Tavily response exceeded the byte budget",
                            )

                    body = bytearray()
                    async for chunk in response.aiter_stream():
                        body.extend(chunk)
                        if len(body) > max_response_bytes:
                            raise ExternalReadPolicyError(
                                ExternalReadPolicyCategory.RESPONSE_TOO_LARGE,
                                "Tavily response exceeded the byte budget",
                            )
                    return TavilyHttpResponse(
                        status_code=response.status,
                        content_type=_response_header(
                            response.headers,
                            b"content-type",
                        ),
                        body=bytes(body),
                    )
        except ExternalReadPolicyError:
            raise
        except httpcore.TimeoutException as exc:
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.REQUEST_TIMEOUT,
                "Tavily request timed out",
            ) from exc
        except Exception as exc:
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.PROVIDER_UNAVAILABLE,
                "Tavily transport failed",
            ) from exc
