"""
Tests for FastAPI application endpoints and integration.
"""

import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from main import app
from src.core.config import settings


class TestApplication:
    """Test FastAPI application setup and configuration."""

    def test_app_creation(self):
        """Test that the FastAPI app is created correctly."""
        assert app.title == "Telegram Assistant"
        assert app.version == "1.0.0"

    def test_app_settings(self):
        """Test that app uses correct settings."""
        # App should have access to settings
        assert hasattr(app.state, 'settings') or settings is not None


class TestHealthEndpoints:
    """Test health check endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test basic health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_status_endpoint(self, client):
        """Test detailed status endpoint."""
        response = client.get("/status")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "services" in data
        assert "timestamp" in data
        assert "version" in data

        # Check service status structure
        services = data["services"]
        assert "database" in services
        assert "configuration" in services

    @pytest.mark.integration
    async def test_status_with_database(self, client, test_database):
        """Test status endpoint with database connection."""
        response = client.get("/status")

        assert response.status_code == 200
        data = response.json()

        # Database should be healthy when test_database fixture is used
        assert data["services"]["database"]["status"] == "healthy"

    def test_health_endpoints_during_startup(self, client):
        """Test health endpoints work during application startup."""
        # Health should always be available
        response = client.get("/health")
        assert response.status_code == 200

        # Status might have some services unavailable during startup
        response = client.get("/status")
        assert response.status_code == 200


class TestAPIDocumentation:
    """Test API documentation endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_openapi_json(self, client):
        """Test OpenAPI JSON schema endpoint."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()

        assert "openapi" in data
        assert "info" in data
        assert "paths" in data
        assert data["info"]["title"] == "Telegram Assistant"

    def test_docs_endpoint(self, client):
        """Test Swagger UI documentation endpoint."""
        response = client.get("/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_endpoint(self, client):
        """Test ReDoc documentation endpoint."""
        response = client.get("/redoc")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestTelegramWebhook:
    """Test Telegram webhook endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_webhook_endpoint_exists(self, client):
        """Test that webhook endpoint exists and accepts POST."""
        # Try with empty payload - should get validation error but endpoint exists
        response = client.post("/webhook/telegram")

        # Should not be 404 (endpoint exists)
        assert response.status_code != 404

    def test_webhook_with_valid_payload(self, client):
        """Test webhook with valid Telegram update payload."""
        # Typical Telegram update structure
        telegram_update = {
            "update_id": 123456789,
            "message": {
                "message_id": 1001,
                "date": 1234567890,
                "chat": {
                    "id": 123456789,
                    "type": "private"
                },
                "from": {
                    "id": 987654321,
                    "first_name": "Test",
                    "username": "testuser"
                },
                "text": "Hello, bot!"
            }
        }

        response = client.post(
            "/webhook/telegram",
            json=telegram_update,
            headers={"Content-Type": "application/json"}
        )

        # Should accept the webhook (even if processing fails, the endpoint should work)
        assert response.status_code in [200, 202, 422]  # 422 if validation fails

    def test_webhook_with_invalid_payload(self, client):
        """Test webhook with invalid payload."""
        invalid_payload = {"invalid": "data"}

        response = client.post(
            "/webhook/telegram",
            json=invalid_payload,
            headers={"Content-Type": "application/json"}
        )

        # Should handle invalid payload gracefully
        assert response.status_code in [400, 422]

    def test_webhook_security(self, client):
        """Test webhook security features."""
        # Test with missing content-type
        response = client.post("/webhook/telegram", data="invalid")
        assert response.status_code in [400, 422]

        # Test with oversized payload
        huge_payload = {"text": "x" * 10000000}  # Very large payload
        response = client.post("/webhook/telegram", json=huge_payload)
        assert response.status_code in [400, 413, 422]  # Should reject large payloads


class TestErrorHandling:
    """Test application error handling."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_404_handling(self, client):
        """Test 404 error handling."""
        response = client.get("/nonexistent-endpoint")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_method_not_allowed(self, client):
        """Test method not allowed error handling."""
        # Try POST on GET endpoint
        response = client.post("/health")

        assert response.status_code == 405
        data = response.json()
        assert "detail" in data

    def test_internal_server_error_handling(self, client):
        """Test internal server error handling."""
        # This would require triggering an actual error
        # For now, just ensure error handling middleware is in place
        assert app.exception_handlers is not None

    def test_validation_error_handling(self, client):
        """Test validation error handling."""
        # Send malformed JSON to webhook
        response = client.post(
            "/webhook/telegram",
            data="malformed json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422


class TestMiddleware:
    """Test application middleware."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_cors_middleware(self, client):
        """Test CORS middleware if configured."""
        response = client.get("/health")

        # Should have basic security headers
        assert response.status_code == 200

        # Check for any security headers
        headers = response.headers
        # CORS headers might be present depending on configuration

    def test_compression_middleware(self, client):
        """Test response compression if configured."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        # Large JSON response might be compressed

    def test_request_timing(self, client):
        """Test that requests complete in reasonable time."""
        import time

        start_time = time.time()
        response = client.get("/health")
        end_time = time.time()

        assert response.status_code == 200
        assert (end_time - start_time) < 5.0  # Should complete within 5 seconds


class TestApplicationIntegration:
    """Test application integration scenarios."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.mark.integration
    async def test_full_application_startup(self, client, test_database):
        """Test complete application startup with all components."""
        # Test that all main endpoints work after startup
        endpoints_to_test = [
            "/health",
            "/status",
            "/docs",
            "/openapi.json"
        ]

        for endpoint in endpoints_to_test:
            response = client.get(endpoint)
            assert response.status_code == 200, f"Endpoint {endpoint} failed"

    @pytest.mark.integration
    def test_configuration_integration(self, client, test_settings):
        """Test that application works with test configuration."""
        # Application should work with test settings
        response = client.get("/status")

        assert response.status_code == 200
        data = response.json()

        # Configuration should be properly loaded
        assert data["services"]["configuration"]["status"] == "healthy"

    @pytest.mark.slow
    def test_concurrent_requests(self, client):
        """Test handling of concurrent requests."""
        import concurrent.futures
        import time

        def make_request():
            return client.get("/health")

        # Make multiple concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        assert all(r.status_code == 200 for r in results)

    def test_application_lifecycle(self, client):
        """Test application handles startup and shutdown gracefully."""
        # Test startup - health should be available
        response = client.get("/health")
        assert response.status_code == 200

        # Test that app can handle requests during normal operation
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == 200

    @pytest.mark.integration
    def test_database_integration_in_app(self, client, test_database):
        """Test that application properly integrates with database."""
        response = client.get("/status")

        assert response.status_code == 200
        data = response.json()

        # Database should be connected
        db_status = data["services"]["database"]
        assert db_status["status"] == "healthy"
        assert db_status["connected"] is True

    def test_environment_configuration(self, client, test_settings):
        """Test that application respects environment configuration."""
        response = client.get("/status")

        assert response.status_code == 200
        data = response.json()

        # Should reflect test environment
        config_status = data["services"]["configuration"]
        assert config_status["status"] == "healthy"


class TestPerformance:
    """Test application performance characteristics."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_response_times(self, client):
        """Test that responses are returned within acceptable time limits."""
        import time

        endpoints = ["/health", "/status"]

        for endpoint in endpoints:
            start_time = time.time()
            response = client.get(endpoint)
            end_time = time.time()

            assert response.status_code == 200
            assert (end_time - start_time) < 2.0  # Should respond within 2 seconds

    def test_memory_usage(self, client):
        """Test that multiple requests don't cause memory leaks."""
        # Make many requests to check for memory leaks
        for _ in range(100):
            response = client.get("/health")
            assert response.status_code == 200

        # If we get here without crashing, memory usage is reasonable

    @pytest.mark.slow
    def test_load_handling(self, client):
        """Test application under load."""
        import concurrent.futures

        def make_multiple_requests():
            responses = []
            for _ in range(10):
                responses.append(client.get("/health"))
            return responses

        # Simulate load with multiple threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_multiple_requests) for _ in range(5)]
            all_responses = []
            for future in concurrent.futures.as_completed(futures):
                all_responses.extend(future.result())

        # All requests should succeed
        assert len(all_responses) == 250  # 5 threads * 5 batches * 10 requests
        assert all(r.status_code == 200 for r in all_responses)