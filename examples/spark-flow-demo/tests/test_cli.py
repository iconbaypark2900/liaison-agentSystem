"""Tests for spark-flow-demo CLI."""

import json
import sys
from unittest.mock import patch, Mock

from spark_flow_demo.cli import check_ollama_api, check_model_installed


def test_check_model_installed():
    """Test model status checking."""
    # Test with all models installed
    models = ["qwen3.6:latest", "qwen3-coder:30b", "gpt-oss:20b", "nemotron-3-nano:30b-a3b-q4_K_M"]
    expected_models = ["qwen3.6:latest", "qwen3-coder:30b", "gpt-oss:20b", "nemotron-3-nano:30b-a3b-q4_K_M"]
    
    result = check_model_installed(models, expected_models)
    assert result["qwen3.6:latest"] is True
    assert result["qwen3-coder:30b"] is True
    assert result["gpt-oss:20b"] is True
    assert result["nemotron-3-nano:30b-a3b-q4_K_M"] is True
    
    # Test with some models missing
    models = ["qwen3.6:latest", "gpt-oss:20b"]
    result = check_model_installed(models, expected_models)
    assert result["qwen3.6:latest"] is True
    assert result["qwen3-coder:30b"] is False
    assert result["gpt-oss:20b"] is True
    assert result["nemotron-3-nano:30b-a3b-q4_K_M"] is False


def test_check_ollama_api_success():
    """Test successful Ollama API check."""
    # Mock successful API response
    mock_response = Mock()
    mock_response.read.return_value = b'{"models": [{"name": "qwen3.6:latest"}, {"name": "qwen3-coder:30b"}]}'
    
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_urlopen.return_value = mock_response
        reachable, models = check_ollama_api()
        assert reachable is True
        assert "qwen3.6:latest" in models
        assert "qwen3-coder:30b" in models


def test_check_ollama_api_failure():
    """Test failed Ollama API check."""
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_urlopen.side_effect = Exception("Network error")
        # The function should catch the exception and return False, empty list
        reachable, models = check_ollama_api()
        assert reachable is False
        assert models == []


def test_check_ollama_api_malformed_json():
    """Test malformed JSON in Ollama API response."""
    # Mock response with malformed JSON
    mock_response = Mock()
    mock_response.read.return_value = b'{"invalid": json}'  # Invalid JSON
    
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_urlopen.return_value = mock_response
        reachable, models = check_ollama_api()
        assert reachable is False
        assert models == []


def test_check_ollama_api_missing_models_key():
    """Test missing models key in Ollama API response."""
    # Mock response with data but no models key
    mock_response = Mock()
    mock_response.read.return_value = b'{"other": "data"}'  # No models key
    
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_urlopen.return_value = mock_response
        reachable, models = check_ollama_api()
        assert reachable is True
        assert models == []