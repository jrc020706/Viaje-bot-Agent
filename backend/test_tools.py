"""
Unit Tests for ViajeBot Tools
Simple tests to validate core functionality without external dependencies.
"""

import pytest
from unittest.mock import Mock, patch
from tools import currency_converter, web_search, _currency_rates


# ---------------------------------------------------------------------------
# Test 1: Currency Converter - Basic functionality
# ---------------------------------------------------------------------------
def test_currency_converter_basic():
    """Test currency converter returns proper format."""
    # Mock the API response
    mock_response = Mock()
    mock_response.json.return_value = {
        "result": "success",
        "rates": {"EUR": 0.92, "COP": 4100.0}
    }
    
    with patch('tools.requests.get', return_value=mock_response):
        result = currency_converter(100, "USD", "EUR")
        
        # Verify the result contains expected format
        assert "100.00" in result
        assert "USD" in result
        assert "EUR" in result
        assert "Rate:" in result


def test_currency_converter_invalid_currency():
    """Test currency converter handles invalid currency codes."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "result": "success",
        "rates": {"EUR": 0.92}
    }
    
    with patch('tools.requests.get', return_value=mock_response):
        result = currency_converter(100, "USD", "XXX")
        
        # Should return error message for invalid currency
        assert "not recognized" in result.lower() or "error" in result.lower()


def test_currency_converter_api_failure():
    """Test currency converter handles API failures gracefully."""
    mock_response = Mock()
    mock_response.json.return_value = {"result": "failure"}
    
    with patch('tools.requests.get', return_value=mock_response):
        result = currency_converter(100, "USD", "EUR")
        
        # Should return error message
        assert "error" in result.lower() or "could not" in result.lower()


# ---------------------------------------------------------------------------
# Test 2: Web Search - Basic functionality
# ---------------------------------------------------------------------------
def test_web_search_basic():
    """Test web search returns formatted results."""
    mock_results = [
        {
            "title": "Test Result 1",
            "body": "This is a test search result.",
            "href": "https://example.com/1"
        },
        {
            "title": "Test Result 2",
            "body": "Another test result.",
            "href": "https://example.com/2"
        }
    ]
    
    with patch('tools._ddg_text_search', return_value=mock_results):
        result = web_search("test query")
        
        # Verify results are formatted correctly
        assert "Test Result 1" in result
        assert "This is a test search result." in result
        assert "https://example.com/1" in result


def test_web_search_no_results():
    """Test web search handles no results gracefully."""
    with patch('tools._ddg_text_search', return_value=[]):
        result = web_search("test query")
        
        # Should return appropriate message
        assert "no search results" in result.lower()


def test_web_search_error():
    """Test web search handles errors gracefully."""
    with patch('tools._ddg_text_search', side_effect=Exception("Network error")):
        result = web_search("test query")
        
        # Should return error message
        assert "error" in result.lower()


# ---------------------------------------------------------------------------
# Test 3: Currency Rates Cache
# ---------------------------------------------------------------------------
def test_currency_rates_cache():
    """Test that currency rates are cached to avoid repeated API calls."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "result": "success",
        "rates": {"EUR": 0.92}
    }
    
    with patch('tools.requests.get', return_value=mock_response) as mock_get:
        # First call
        _currency_rates("USD")
        # Second call (should use cache)
        _currency_rates("USD")
        
        # Should only call API once due to caching
        assert mock_get.call_count == 1


# ---------------------------------------------------------------------------
# Test 4: Tool Decorator Validation
# ---------------------------------------------------------------------------
def test_currency_converter_tool_signature():
    """Test that currency converter tool has correct signature."""
    # Verify the tool can be called with expected parameters
    assert callable(currency_converter)
    
    # Check that it has the expected docstring
    assert "Convert monetary amounts" in currency_converter.description


def test_web_search_tool_signature():
    """Test that web search tool has correct signature."""
    # Verify the tool can be called with expected parameters
    assert callable(web_search)
    
    # Check that it has the expected docstring
    assert "Search the web" in web_search.description


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
