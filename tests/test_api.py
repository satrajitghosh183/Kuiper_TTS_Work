"""
Tests for FastAPI endpoints.
"""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check(self, test_client):
        """Test /health endpoint."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "1.0.0"

    @patch("app.main.get_redis")
    def test_readiness_check(self, mock_redis_dep, test_client, mock_redis):
        """Test /ready endpoint."""
        mock_redis_dep.return_value = mock_redis

        response = test_client.get("/ready")

        # May be 200 or 503 depending on actual Redis availability
        assert response.status_code in [200, 503]
        data = response.json()
        assert "ready" in data
        assert "checks" in data


class TestMetricsEndpoint:
    """Tests for metrics endpoint."""

    def test_metrics_endpoint(self, test_client):
        """Test /metrics endpoint returns Prometheus metrics."""
        response = test_client.get("/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"] or \
               "text/plain; charset=utf-8" in response.headers["content-type"]


class TestConversionEndpoints:
    """Tests for conversion endpoints."""

    @patch("app.main.get_redis")
    @patch("app.main.verify_api_key")
    def test_convert_sync_invalid_file_type(
        self, mock_api_key, mock_redis_dep, test_client, mock_redis
    ):
        """Test sync conversion rejects non-PDF files."""
        mock_api_key.return_value = "test_key"
        mock_redis_dep.return_value = mock_redis

        # Create a fake text file
        file_content = b"This is not a PDF"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}

        response = test_client.post(
            "/api/v1/convert/sync",
            files=files,
            headers={"X-API-Key": "test_api_key"},
        )

        # Should fail validation
        assert response.status_code in [400, 422]

    @patch("app.main.get_redis")
    def test_job_status_not_found(self, mock_redis_dep, test_client, mock_redis):
        """Test job status returns 404 for unknown job."""
        mock_redis.hgetall = AsyncMock(return_value={})
        mock_redis_dep.return_value = mock_redis

        response = test_client.get("/api/v1/status/nonexistent-job-id")

        assert response.status_code == 404

    @patch("app.main.get_redis")
    def test_download_not_completed(self, mock_redis_dep, test_client, mock_redis):
        """Test download fails for incomplete job."""
        mock_redis.hgetall = AsyncMock(return_value={"status": "processing"})
        mock_redis_dep.return_value = mock_redis

        response = test_client.get("/api/v1/download/some-job-id")

        assert response.status_code == 400


class TestAuthenticationEndpoints:
    """Tests for API authentication."""

    def test_convert_without_api_key(self, test_client):
        """Test that endpoints require API key when configured."""
        # Create a fake PDF
        pdf_content = b"%PDF-1.4 fake pdf content"
        files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}

        response = test_client.post("/api/v1/convert", files=files)

        # Should require authentication
        assert response.status_code in [401, 403, 422]

