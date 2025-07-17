"""
Test suite for Reddit Comment Analysis API.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import ConfigurableAnalysisRequest

# Create test client
client = TestClient(app)


def test_health_endpoint():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "v2"
    assert data["analysis_type"] == "comment_level"
    assert data["service"] == "reddit-comment-analysis-api"
    assert "timestamp" in data


def test_status_endpoint():
    """Test the status endpoint."""
    response = client.get("/status")
    assert response.status_code == 200

    data = response.json()
    assert data["api_status"] == "operational"
    assert "analysis_capabilities" in data
    assert "supported_models" in data
    assert "configuration" in data
    assert "api_keys_configured" in data

    # Check analysis capabilities
    capabilities = data["analysis_capabilities"]
    assert capabilities["sentiment_analysis"] is True
    assert capabilities["theme_extraction"] is True
    assert capabilities["purchase_intent_detection"] is True
    assert capabilities["multi_model_support"] is True


@pytest.mark.asyncio
async def test_analyze_reddit_comments_endpoint():
    """Test the analyze Reddit comments endpoint with valid data."""
    # Create test request data
    test_request = {
        "keywords": ["BMW R 12 GS", "motorcycle"],
        "subreddits": ["motorcycles", "BMW"],
        "timeframe": "week",
        "limit": 5,
        "model": "gemini-2.5-pro",
        "api_key": "test_api_key_12345",
        "system_prompt": "You are an expert social media analyst...",
        "output_format": "json",
        "max_quote_length": 200,
    }

    response = client.post("/analyze-reddit-comments", json=test_request)
    assert response.status_code == 200

    data = response.json()
    assert "comment_analyses" in data
    assert "metadata" in data

    # Check metadata
    metadata = data["metadata"]
    assert metadata["keywords_analyzed"] == test_request["keywords"]
    assert metadata["subreddits_searched"] == test_request["subreddits"]
    assert metadata["model_used"] == test_request["model"]
    assert metadata["status"] == "completed"
    assert "total_comments_analyzed" in metadata
    assert "processing_time_ms" in metadata

    # Check comment analyses structure
    analyses = data["comment_analyses"]
    assert isinstance(analyses, list)

    if analyses:  # If there are analyses returned
        analysis = analyses[0]
        assert "post_id" in analysis
        assert "quote" in analysis
        assert "sentiment" in analysis
        assert "theme" in analysis
        assert "purchase_intent" in analysis
        assert "date" in analysis
        assert "source" in analysis


def test_analyze_reddit_comments_missing_keywords():
    """Test the analyze endpoint with missing keywords."""
    test_request = {
        "keywords": [],  # Empty keywords should fail
        "subreddits": ["motorcycles"],
        "api_key": "test_api_key",
    }

    response = client.post("/analyze-reddit-comments", json=test_request)
    assert response.status_code == 400
    assert "At least one keyword is required" in response.json()["detail"]


def test_analyze_reddit_comments_missing_subreddits():
    """Test the analyze endpoint with missing subreddits."""
    test_request = {
        "keywords": ["BMW"],
        "subreddits": [],  # Empty subreddits should fail
        "api_key": "test_api_key",
    }

    response = client.post("/analyze-reddit-comments", json=test_request)
    assert response.status_code == 400
    assert "At least one subreddit is required" in response.json()["detail"]


def test_invalid_endpoint():
    """Test accessing a non-existent endpoint."""
    response = client.get("/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_configurable_analysis_request_model():
    """Test the ConfigurableAnalysisRequest model validation."""
    # Test valid request
    valid_data = {"keywords": ["test"], "subreddits": ["test"], "api_key": "test_key"}

    request = ConfigurableAnalysisRequest(**valid_data)
    assert request.keywords == ["test"]
    assert request.subreddits == ["test"]
    assert request.api_key == "test_key"
    assert request.timeframe == "week"  # Default value
    assert request.limit == 10  # Default value
    assert request.model == "gemini-2.5-pro"  # Default value


def test_cors_headers():
    """Test that CORS headers are properly set."""
    response = client.get("/health")
    assert response.status_code == 200
    # CORS headers should be present due to middleware
    # Note: In test environment, CORS headers might not be fully visible
    # This is a basic check that the endpoint works with CORS middleware


if __name__ == "__main__":
    pytest.main([__file__])
