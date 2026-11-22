"""Asynchronous client for the unoserver XML-RPC API."""

import asyncio
import xmlrpc.client


class UnoserverError(Exception):
    """unoserver could not convert the document."""


class UnoserverTimeout(UnoserverError):
    """unoserver did not answer within the timeout."""


class UnoserverUnavailable(UnoserverError):
    """unoserver could not be reached."""


class _TimeoutTransport(xmlrpc.client.Transport):
    def __init__(self, timeout: float) -> None:
        super().__init__()
        self._timeout = timeout

    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = self._timeout
        return connection


class UnoserverClient:
    def __init__(self, url: str, timeout: float, attempts: int = 4, backoff_seconds: float = 5) -> None:
        self.url = url
        self.timeout = timeout
        self.attempts = attempts
        self.backoff_seconds = backoff_seconds

    async def convert(self, content: bytes, convert_to: str) -> bytes:
        """Convert a document, retrying while LibreOffice is still starting up."""
        for attempt in range(self.attempts):
            if attempt:
                await asyncio.sleep(self.backoff_seconds * attempt)
            try:
                return await asyncio.to_thread(self._convert, content, convert_to)
            except TimeoutError as exc:
                raise UnoserverTimeout from exc
            except (xmlrpc.client.Fault, xmlrpc.client.ProtocolError) as exc:
                raise UnoserverError from exc
            except OSError:
                continue
        raise UnoserverUnavailable

    def _convert(self, content: bytes, convert_to: str) -> bytes:
        transport = _TimeoutTransport(self.timeout)
        with xmlrpc.client.ServerProxy(self.url, transport=transport, allow_none=True) as proxy:
            result = proxy.convert(None, xmlrpc.client.Binary(content), None, convert_to, None, [], True, None, None)
        if not isinstance(result, xmlrpc.client.Binary) or not result.data:
            raise UnoserverError("unoserver returned no document")
        return result.data
