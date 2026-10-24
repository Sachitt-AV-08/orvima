import anyio
import httpx


class _SyncASGIClient:
    """Sync shim over httpx's async ASGI transport.

    starlette's TestClient differs across versions: older ones hand
    ``app=`` to ``httpx.Client``, which modern httpx rejects with:
    ``TypeError: Client.__init__() got an unexpected keyword argument 'app'``.
    Driving the app via ``httpx.ASGITransport`` (under anyio) avoids the
    constructor mismatch and works regardless of installed starlette/httpx
    versions.
    """

    def __init__(self, app, base_url: str = "http://testserver"):
        self.app = app
        self.base_url = base_url

    def _request(self, method, path, **kwargs):
        async def _run():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app),
                base_url=self.base_url,
            ) as client:
                return await client.request(method, path, **kwargs)

        return anyio.run(_run)

    def get(self, *args, **kwargs):
        return self._request("GET", *args, **kwargs)

    def post(self, *args, **kwargs):
        return self._request("POST", *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self._request("DELETE", *args, **kwargs)

    def put(self, *args, **kwargs):
        return self._request("PUT", *args, **kwargs)


TestClient = _SyncASGIClient
TestClient.__test__ = False
