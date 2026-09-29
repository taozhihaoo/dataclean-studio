import httpx
from fastapi.testclient import TestClient

from app.main import create_app


class TestHealth:
    def test_health(self, client: TestClient):
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert body["version"]

    def test_health_async_client(self, data_dir):
        import asyncio

        async def check():
            from app.config import get_settings

            get_settings.cache_clear()
            app = create_app()
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
                async with app.router.lifespan_context(app):
                    response = await ac.get("/health")
                    assert response.status_code == 200
                    assert response.json()["status"] == "ok"

        asyncio.run(check())

    def test_unknown_api_route_uniform_404(self, client: TestClient):
        response = client.get("/api/definitely/not/here")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    def test_method_not_allowed_uniform(self, client: TestClient):
        response = client.delete("/health")
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "method_not_allowed"

    def test_no_traceback_in_errors(self, client: TestClient):
        """Malformed JSON body must produce a clean error, never a traceback."""
        response = client.post(
            "/api/jobs/aaaaaaaaaaaa/transform",
            content=b"{this is not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code in (400, 422)
        assert "Traceback" not in response.text
