import pytest
from utils import get_headers, generate_cache_key

def test_get_headers():
    api_key = "test_api_key"
    headers = get_headers(api_key)
    expected_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    assert headers == expected_headers

def test_get_headers_caching():
    # Test that lru_cache is working
    api_key = "another_api_key"
    headers1 = get_headers(api_key)
    headers2 = get_headers(api_key)
    assert headers1 is headers2  # Should be the same object due to caching

    # Test with a different key
    api_key_different = "different_key"
    headers_different = get_headers(api_key_different)
    assert headers_different is not headers1

    # Clear the cache for this specific function for other tests if needed
    get_headers.cache_clear()

def test_generate_cache_key_simple():
    request_data = {"message": "hello", "model": "gpt-4"}
    key1 = generate_cache_key(request_data)

    # Same data should produce the same key
    request_data_same = {"message": "hello", "model": "gpt-4"}
    key2 = generate_cache_key(request_data_same)
    assert key1 == key2
    assert len(key1) == 64 # SHA256 produces 64 hex characters

def test_generate_cache_key_order_agnostic():
    # The function sorts keys, so order shouldn't matter
    request_data1 = {"message": "hello", "model": "gpt-4"}
    request_data2 = {"model": "gpt-4", "message": "hello"}
    key1 = generate_cache_key(request_data1)
    key2 = generate_cache_key(request_data2)
    assert key1 == key2

def test_generate_cache_key_different_data():
    request_data1 = {"message": "hello", "model": "gpt-4"}
    request_data2 = {"message": "goodbye", "model": "gpt-4"}
    key1 = generate_cache_key(request_data1)
    key2 = generate_cache_key(request_data2)
    assert key1 != key2

def test_generate_cache_key_nested_data():
    request_data1 = {"messages": [{"role": "user", "content": "Hi"}], "model": "gpt-3.5"}
    key1 = generate_cache_key(request_data1)

    request_data_same = {"messages": [{"role": "user", "content": "Hi"}], "model": "gpt-3.5"}
    key2 = generate_cache_key(request_data_same)
    assert key1 == key2

    request_data_different_content = {"messages": [{"role": "user", "content": "Hello"}], "model": "gpt-3.5"}
    key3 = generate_cache_key(request_data_different_content)
    assert key1 != key3

    request_data_different_role = {"messages": [{"role": "assistant", "content": "Hi"}], "model": "gpt-3.5"}
    key4 = generate_cache_key(request_data_different_role)
    assert key1 != key4

def test_generate_cache_key_empty_dict():
    request_data = {}
    key = generate_cache_key(request_data)
    assert len(key) == 64

def test_generate_cache_key_with_none_values():
    # json.dumps converts None to null
    request_data1 = {"param1": None, "param2": "value"}
    key1 = generate_cache_key(request_data1)

    request_data2 = {"param2": "value", "param1": None}
    key2 = generate_cache_key(request_data2)
    assert key1 == key2

    request_data3 = {"param1": "None", "param2": "value"} # "None" as string
    key3 = generate_cache_key(request_data3)
    assert key1 != key3
