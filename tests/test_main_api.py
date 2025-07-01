import pytest
import httpx # Added import
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, ANY # ANY for flexible matching in assertions

# Import the FastAPI app instance from main.py
# Also import specific items that might be useful for mocking or setup
from main import app, cache, LIARA_BASE_URLS
from schemas import CompletionRequest # For constructing request bodies
from errors import (
    UpstreamServiceDownError,
    UpstreamTimeoutError,
    UpstreamResponseError,
    GeneralProxyError
)

# Use pytest-asyncio for async test functions if needed, though TestClient handles sync calls to async endpoints.
# For direct async operations within tests (e.g. if not using TestClient for some part), mark tests with @pytest.mark.asyncio

@pytest.fixture(scope="module")
def client():
    # Create a TestClient instance using your FastAPI app
    with TestClient(app) as c:
        yield c

@pytest.fixture(autouse=True)
def clear_cache_and_reset_mocks(mocker):
    """Clears the cache before each test and resets global mocks if any."""
    cache.clear()
    # If LIARA_BASE_URLS could change or needs mocking for specific tests:
    # mocker.patch('main.LIARA_BASE_URLS', ["mock_url_1", "mock_url_2"])


VALID_API_KEY = "test-api-key"
DEFAULT_HEADERS = {"Authorization": f"Bearer {VALID_API_KEY}"}

MINIMAL_REQUEST_PAYLOAD = {
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello"}],
}

# --- Test Cases ---

def test_chat_completions_missing_api_key(client: TestClient):
    response = client.post("/api/v1/chat/completions", json=MINIMAL_REQUEST_PAYLOAD)
    assert response.status_code == 401
    assert "API Key is required" in response.json()["detail"]

def test_chat_completions_invalid_bearer_token(client: TestClient):
    response = client.post(
        "/api/v1/chat/completions",
        json=MINIMAL_REQUEST_PAYLOAD,
        headers={"Authorization": f"Invalid {VALID_API_KEY}"}
    )
    assert response.status_code == 401 # Or 403 depending on how strict the "Bearer" check is
                                      # Current code raises 401 for "not api_key.startswith("Bearer ")"
    assert "API Key is required" in response.json()["detail"] # Check specific message


def test_chat_completions_successful_first_try(client: TestClient, mocker):
    mock_response_data = {"id": "123", "choices": [{"message": {"content": "Success"}}]}

    # Mock httpx.AsyncClient.post
    mock_post = AsyncMock(return_value=AsyncMock(status_code=200, json=lambda: mock_response_data))
    mocker.patch("httpx.AsyncClient.post", new=mock_post)

    response = client.post("/api/v1/chat/completions", headers=DEFAULT_HEADERS, json=MINIMAL_REQUEST_PAYLOAD)

    assert response.status_code == 200
    assert response.json() == mock_response_data
    mock_post.assert_awaited_once_with(
        f"{LIARA_BASE_URLS[0]}/chat/completions", # Assumes it tries the first URL
        headers=ANY, # Could be more specific if needed
        json=MINIMAL_REQUEST_PAYLOAD # Pydantic model_dump(exclude_unset=True) would be used
    )
    # Check cache (optional here, more specific tests for caching below)
    cache_key_data = CompletionRequest(**MINIMAL_REQUEST_PAYLOAD).model_dump(exclude_unset=True)
    from utils import generate_cache_key
    expected_cache_key = generate_cache_key(cache_key_data)
    assert expected_cache_key in cache
    assert cache[expected_cache_key] == mock_response_data


def test_chat_completions_cache_hit(client: TestClient, mocker):
    mock_response_data = {"id": "cached_123", "choices": [{"message": {"content": "Cached data"}}]}
    cache_key_data = CompletionRequest(**MINIMAL_REQUEST_PAYLOAD).model_dump(exclude_unset=True)
    from utils import generate_cache_key
    cache_key = generate_cache_key(cache_key_data)
    cache[cache_key] = mock_response_data # Pre-populate cache

    mock_post = AsyncMock() # This should NOT be called if cache hits
    mocker.patch("httpx.AsyncClient.post", new=mock_post)

    response = client.post("/api/v1/chat/completions", headers=DEFAULT_HEADERS, json=MINIMAL_REQUEST_PAYLOAD)

    assert response.status_code == 200
    assert response.json() == mock_response_data
    mock_post.assert_not_awaited() # Crucial: external API was not called


def test_chat_completions_fallback_behavior(client: TestClient, mocker):
    if len(LIARA_BASE_URLS) < 2:
        pytest.skip("Fallback test requires at least two LIARA_BASE_URLS")

    success_response_data = {"id": "fallback_success", "choices": [{"message": {"content": "Fallback success"}}]}

    # Simulate first URL failing, second succeeding
    mock_post = AsyncMock(side_effect=[
        httpx.ConnectError("Connection failed to first server"),
        AsyncMock(status_code=200, json=lambda: success_response_data) # Successful response from second server
    ])
    mocker.patch("httpx.AsyncClient.post", new=mock_post)

    response = client.post("/api/v1/chat/completions", headers=DEFAULT_HEADERS, json=MINIMAL_REQUEST_PAYLOAD)

    assert response.status_code == 200
    assert response.json() == success_response_data
    assert mock_post.await_count == 2 # Called for both URLs

    # Verify calls were made to the correct URLs in order
    assert mock_post.await_args_list[0][0][0] == f"{LIARA_BASE_URLS[0]}/chat/completions"
    assert mock_post.await_args_list[1][0][0] == f"{LIARA_BASE_URLS[1]}/chat/completions"

    # Check caching of the successful fallback response
    cache_key_data = CompletionRequest(**MINIMAL_REQUEST_PAYLOAD).model_dump(exclude_unset=True)
    from utils import generate_cache_key
    expected_cache_key = generate_cache_key(cache_key_data)
    assert expected_cache_key in cache
    assert cache[expected_cache_key] == success_response_data


def test_chat_completions_all_servers_fail(client: TestClient, mocker):
    # Simulate all configured URLs failing
    failures = [httpx.ConnectError(f"Connection failed to server {i}") for i, _ in enumerate(LIARA_BASE_URLS)]
    if not failures: # Handle case with no LIARA_BASE_URLS, though unlikely
        failures = [httpx.ConnectError("Connection failed")]

    mock_post = AsyncMock(side_effect=failures)
    mocker.patch("httpx.AsyncClient.post", new=mock_post)

    response = client.post("/api/v1/chat/completions", headers=DEFAULT_HEADERS, json=MINIMAL_REQUEST_PAYLOAD)

    # Expecting the error from the last failed server, which is UpstreamServiceDownError
    assert response.status_code == UpstreamServiceDownError().status_code # 503
    # The detail will be specific to the last URL tried if LIARA_BASE_URLS is not empty
    if LIARA_BASE_URLS:
        last_url_specific_detail = UpstreamServiceDownError(detail=f"Could not connect to AI service endpoint: {LIARA_BASE_URLS[-1]}. It may be temporarily down.").detail
        assert response.json()["detail"] == last_url_specific_detail
    else:
        # If LIARA_BASE_URLS is empty, a generic UpstreamServiceDownError is raised before the loop.
        assert response.json()["detail"] == UpstreamServiceDownError(detail="All AI service endpoints are currently unavailable or failed.").detail

    assert mock_post.await_count == len(LIARA_BASE_URLS) if LIARA_BASE_URLS else 0 # No calls if empty


def test_chat_completions_liara_returns_error_status(client: TestClient, mocker):
    # Simulate Liara returning a non-200 status code that is not an httpx exception
    # For example, a 400 or 500 from Liara itself
    liara_error_response_text = "Liara specific error"
    liara_status_code = 429 # e.g. rate limit from Liara

    mock_post = AsyncMock(return_value=AsyncMock(status_code=liara_status_code, text=liara_error_response_text))
    mocker.patch("httpx.AsyncClient.post", new=mock_post)
    mock_logger_error = mocker.patch("main.logger.error")


    response = client.post("/api/v1/chat/completions", headers=DEFAULT_HEADERS, json=MINIMAL_REQUEST_PAYLOAD)

    # The current code in main.py, if a non-200 is received from Liara, it logs the error
    # and then tries the next Liara server. If all servers return non-200 (but not httpx exceptions),
    # it will eventually raise the 502 "All upstream servers are unavailable".
    # Let's test this behavior.
    # If only one LIARA_BASE_URLS, it will try it, get UpstreamResponseError, and raise that.

    expected_error = UpstreamResponseError(
        liara_status_code=liara_status_code,
        liara_detail=liara_error_response_text
    )
    assert response.status_code == expected_error.status_code # 502
    assert response.json()["detail"] == expected_error.detail

    # Check that logger.warning (now used for this case) was called for each attempt
    mock_logger_warning = mocker.patch("main.logger.warning") # Changed from error to warning in main.py

    # Re-run the request post-patching the logger to warning, if main.py changed the log level
    # For this test, we assume the logger level change is already in main.py
    # The logger call count should be for each server that was tried.

    # To accurately test logger calls, it's better to reset and re-run if the logger itself is part of the test.
    # However, main.py's logger.warning for this case is what we expect.
    # The number of calls to httpx.post would be len(LIARA_BASE_URLS).
    # The number of calls to logger.warning about "Upstream service at {url} returned error" would be len(LIARA_BASE_URLS).

    # Let's re-patch logger.warning and re-run the client call to be certain about call counts.
    mocker.stopall() # Stop previous mocks
    mock_post_rerun = AsyncMock(return_value=AsyncMock(status_code=liara_status_code, text=liara_error_response_text))
    mocker.patch("httpx.AsyncClient.post", new=mock_post_rerun)
    mock_logger_warning_rerun = mocker.patch("main.logger.warning")

    response_rerun = client.post("/api/v1/chat/completions", headers=DEFAULT_HEADERS, json=MINIMAL_REQUEST_PAYLOAD)
    assert response_rerun.status_code == expected_error.status_code

    assert mock_logger_warning_rerun.call_count == len(LIARA_BASE_URLS) if LIARA_BASE_URLS else 0
    if LIARA_BASE_URLS:
        # Example: check the log message for the first call
        first_log_call_args = mock_logger_warning_rerun.call_args_list[0][0][0]
        assert f"Upstream service at {LIARA_BASE_URLS[0]} returned error: {liara_status_code} - {liara_error_response_text}" in first_log_call_args


def test_chat_completions_liara_http_status_error_exception(client: TestClient, mocker):
    # Simulate Liara returning an error that httpx raises as HTTPStatusError
    # (e.g. via response.raise_for_status() if that was used, but here it's direct status check)
    # The current code catches httpx.HTTPStatusError specifically.

    # This test is similar to the one above, as the current code doesn't use raise_for_status()
    # on the client.post, but checks response.status_code.
    # The specific httpx.HTTPStatusError catch block in main.py might be less likely to be hit
    # with client.post unless the Liara server itself behaves in a way that triggers it in httpx.
    # Let's simulate it as if it was an httpx.HTTPStatusError

    mock_request = mocker.MagicMock() # Mock request object for HTTPStatusError
    mock_response_for_exception = mocker.MagicMock(status_code=503) # Mock response for HTTPStatusError

    http_status_error = httpx.HTTPStatusError(
        "Service Unavailable",
        request=mock_request,
        response=mock_response_for_exception
    )

    # This will apply to all calls to LIARA_BASE_URLS
    mock_post = AsyncMock(side_effect=http_status_error)
    mocker.patch("httpx.AsyncClient.post", new=mock_post)
    mock_logger_error = mocker.patch("main.logger.error")

    response = client.post("/api/v1/chat/completions", headers=DEFAULT_HEADERS, json=MINIMAL_REQUEST_PAYLOAD)

    # The HTTPStatusError is caught, logged, and then the endpoint returns a 502.
    # This seems a bit off, it should perhaps return the status from the HTTPStatusError,
    # or a generic 502 but with a detail indicating upstream failure.
    # The refactored main.py will catch this, log it, and then raise an UpstreamResponseError.
    expected_error = UpstreamResponseError(
        liara_status_code=mock_response_for_exception.status_code, # 503
        liara_detail="Service Unavailable" # This is from the HTTPStatusError message
    )

    assert response.status_code == expected_error.status_code # 502 (from UpstreamResponseError)
    assert response.json()["detail"] == expected_error.detail

    # Logger should be called for each server attempt. If HTTPStatusError is raised by the first one,
    # and it's configured to continue, it would log for each.
    # In the refactored main.py, httpx.HTTPStatusError is caught, last_exception is set, and it continues.
    # So, it will be called for each server if they all raise this.
    assert mock_logger_error.call_count == len(LIARA_BASE_URLS) if LIARA_BASE_URLS else 0
    if LIARA_BASE_URLS:
        first_log_call_args = mock_logger_error.call_args_list[0][0][0]
        assert f"HTTPStatusError from upstream service {LIARA_BASE_URLS[0]}: {http_status_error.response.status_code}" in first_log_call_args


# Example for a more complex payload if needed for other tests
COMPLEX_REQUEST_PAYLOAD = {
    "model": "google/gemini-2.0-flash-001",
    "messages": [
        {"role": "user", "content": "Describe this image"},
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "http://example.com/image.png"}}]}
    ],
    "temperature": 0.5,
    "max_tokens": 100
}

# Could add tests for rate limiting if a reliable way to control time/state for slowapi is feasible in tests.
# Often, rate limiting is tested more at an e2e level or by disabling it for certain unit/integration tests.

# Test with a different model from the allowed list
def test_chat_completions_different_valid_model(client: TestClient, mocker):
    payload = {
        "model": "google/gemini-2.0-flash-001", # Different valid model
        "messages": [{"role": "user", "content": "Hello Gemini"}],
    }
    mock_response_data = {"id": "gemini_123", "choices": [{"message": {"content": "Response from Gemini"}}]}
    mock_post = AsyncMock(return_value=AsyncMock(status_code=200, json=lambda: mock_response_data))
    mocker.patch("httpx.AsyncClient.post", new=mock_post)

    response = client.post("/api/v1/chat/completions", headers=DEFAULT_HEADERS, json=payload)

    assert response.status_code == 200
    assert response.json() == mock_response_data
    mock_post.assert_awaited_once_with(
        f"{LIARA_BASE_URLS[0]}/chat/completions",
        headers=ANY,
        json=payload
    )
    cache_key_data = CompletionRequest(**payload).model_dump(exclude_unset=True)
    from utils import generate_cache_key
    expected_cache_key = generate_cache_key(cache_key_data)
    assert expected_cache_key in cache
    assert cache[expected_cache_key] == mock_response_data

# Test for invalid Pydantic model (e.g. wrong field type for a required field)
def test_chat_completions_invalid_payload_schema(client: TestClient):
    invalid_payload = {
        "model": "openai/gpt-4o-mini",
        "messages": "this-should-be-a-list-of-messages" # Invalid type for messages
    }
    response = client.post("/api/v1/chat/completions", headers=DEFAULT_HEADERS, json=invalid_payload)
    assert response.status_code == 422 # Unprocessable Entity for Pydantic validation errors
    # Check for a more generic Pydantic validation error message
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert len(detail) > 0
    assert detail[0]["loc"] == ["body", "messages"] # Location of the error
    assert "Input should be a valid list" in detail[0]["msg"] # More specific error message


def test_chat_completions_invalid_model_name(client: TestClient):
    invalid_payload = {
        "model": "non_existent_model/gpt-10",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    response = client.post("/api/v1/chat/completions", headers=DEFAULT_HEADERS, json=invalid_payload)
    assert response.status_code == 422
    assert any("Input should be " in err["msg"] and "openai/gpt-4o-mini" in err["msg"] for err in response.json()["detail"])


# TODO: Add tests for rate limiting (might be complex to unit test reliably)
# TODO: Add tests for specific headers being passed through (e.g. Content-Type, Accept)
# TODO: Add tests for the `exclude_unset=True` behavior in model_dump if critical path relies on it heavily for external API
#       (current tests implicitly cover it as MINIMAL_REQUEST_PAYLOAD is used for mock call assertion)

# A note on testing the LIARA_BASE_URLS loop:
# The tests `test_chat_completions_fallback_behavior` and `test_chat_completions_all_servers_fail`
# cover the iteration. If LIARA_BASE_URLS is empty, the code currently would loop 0 times,
# then immediately raise HTTPException(502, "All upstream servers are unavailable").
# This is implicitly tested by `test_chat_completions_all_servers_fail` if LIARA_BASE_URLS is patched to be empty.

def test_chat_completions_empty_liara_base_urls(client: TestClient, mocker):
    mocker.patch("main.LIARA_BASE_URLS", []) # Patch to be an empty list

    mock_post = AsyncMock() # This should not be called
    mocker.patch("httpx.AsyncClient.post", new=mock_post)

    response = client.post("/api/v1/chat/completions", headers=DEFAULT_HEADERS, json=MINIMAL_REQUEST_PAYLOAD)

    expected_error = UpstreamServiceDownError(detail="All AI service endpoints are currently unavailable or failed.")
    assert response.status_code == expected_error.status_code # 503
    assert response.json()["detail"] == expected_error.detail
    mock_post.assert_not_awaited() # Ensure no attempt to call httpx.post

    # Also ensure cache is not hit or populated under these conditions
    cache_key_data = CompletionRequest(**MINIMAL_REQUEST_PAYLOAD).model_dump(exclude_unset=True)
    from utils import generate_cache_key
    expected_cache_key = generate_cache_key(cache_key_data)
    assert expected_cache_key not in cache

# Test that the `utils.get_headers` function is called with the correct API key
def test_get_headers_is_called_correctly(client: TestClient, mocker):
    mock_get_headers = mocker.patch("main.get_headers", return_value={"Authorization": f"Bearer {VALID_API_KEY}", "X-Custom": "Test"})
    mock_post = AsyncMock(return_value=AsyncMock(status_code=200, json=lambda: {}))
    mocker.patch("httpx.AsyncClient.post", new=mock_post)

    client.post("/api/v1/chat/completions", headers=DEFAULT_HEADERS, json=MINIMAL_REQUEST_PAYLOAD)

    mock_get_headers.assert_called_once_with(VALID_API_KEY)
    # And check that the headers from get_headers were used in the actual post
    mock_post.assert_awaited_once_with(
        ANY, # URL
        headers=mock_get_headers.return_value, # Check that the mocked headers were used
        json=ANY
    )

# Test the structure of request_data sent to Liara
def test_request_data_structure_sent_to_liara(client: TestClient, mocker):
    # This test ensures that body.model_dump(exclude_unset=True) works as expected
    # and the resulting data is passed to httpx.AsyncClient.post

    # Use a more complex payload where exclude_unset would matter
    payload_with_optional_set = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.8, # This is set
        "max_tokens": None # This is explicitly set to None, Pydantic V2 model_dump(exclude_none=False) would include it
                           # exclude_unset=True should include it if it was part of the input.
                           # If it was not in input, exclude_unset=True would exclude it.
                           # Let's assume it's part of the input.
    }
    # Pydantic V2: model_dump(exclude_unset=True) will include 'max_tokens': None if it was provided in the input.
    # If max_tokens was not in payload_with_optional_set, exclude_unset=True would skip it.
    # The default for max_tokens in schema is None. If input provides None, it's considered "set".

    expected_json_to_liara = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.8,
        "max_tokens": None # This should be included as it's explicitly set in payload
    }


    mock_post = AsyncMock(return_value=AsyncMock(status_code=200, json=lambda: {}))
    mocker.patch("httpx.AsyncClient.post", new=mock_post)

    client.post("/api/v1/chat/completions", headers=DEFAULT_HEADERS, json=payload_with_optional_set)

    mock_post.assert_awaited_once_with(
        ANY, headers=ANY, json=expected_json_to_liara
    )

    # Case 2: max_tokens is not provided in input, so exclude_unset=True should exclude it
    payload_without_optional = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.8,
        # max_tokens is not set here
    }
    expected_json_to_liara_without_optional = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.8,
        # max_tokens should be absent
    }

    # Reset mock for a new call
    mock_post.reset_mock()
    mocker.patch("httpx.AsyncClient.post", new=mock_post) # Re-patch if needed, or ensure reset_mock is enough

    client.post("/api/v1/chat/completions", headers=DEFAULT_HEADERS, json=payload_without_optional)

    mock_post.assert_awaited_once_with(
        ANY, headers=ANY, json=expected_json_to_liara_without_optional
    )

# --- WebSocket Test Cases ---

VALID_WS_CONFIG_PAYLOAD = {
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello stream"}],
    "stream": True # Explicitly set for clarity, though main.py forces it
}

@pytest.mark.asyncio # Needs asyncio for websocket_connect
async def test_websocket_chat_successful_stream(client: TestClient, mocker):

    async def mock_aiter_text():
        yield "data: {\"id\":\"1\", \"choices\":[{\"delta\":{\"content\":\"Hello\"}}]}\n\n"
        yield "data: {\"id\":\"1\", \"choices\":[{\"delta\":{\"content\":\" World\"}}]}\n\n"
        yield "data: [DONE]\n\n"

    mock_stream_response = AsyncMock(status_code=200)
    mock_stream_response.aiter_text = mock_aiter_text # Assign the async generator

    # The context manager for client.stream needs to be an AsyncMock too
    mock_stream_context_manager = AsyncMock()
    mock_stream_context_manager.__aenter__.return_value = mock_stream_response
    mock_stream_context_manager.__aexit__ = AsyncMock(return_value=None) # Ensure __aexit__ is async

    # Refined mocking for the stream method itself
    patched_httpx_stream_method = mocker.patch("httpx.AsyncClient.stream", new_callable=AsyncMock)
    patched_httpx_stream_method.return_value = mock_stream_context_manager # stream() returns the context manager

    received_messages = []
    with client.websocket_connect("/ws/v1/chat/completions") as websocket:
        websocket.send_json({"api_key": VALID_API_KEY})
        websocket.send_json(VALID_WS_CONFIG_PAYLOAD)

        while True:
            try:
                data = websocket.receive_json() # Removed timeout
                received_messages.append(data)
            except Exception as e:
                break

    # The main.py sends raw text chunks, not JSON objects for each stream part.
    # Let's re-evaluate the receive loop based on main.py:
    # async for chunk in response.aiter_text():
    #     if chunk.strip():
    #         await manager.send_message(connection_id, chunk)
    # So, client should receive text.

    patched_httpx_stream_method.reset_mock() # Use the patched method here
    # mock_stream_context_manager's __aenter__ still points to mock_stream_response, which is fine.
    # No need to re-patch "httpx.AsyncClient.stream" if patched_httpx_stream_method is the same object
    # that was patched originally and we are just resetting its call history.
    # If a new mock object was created for mocker.patch, then it would need re-patching.
    # mocker.patch returns the mock object, so patched_httpx_stream_method is that mock.

    full_received_text = ""
    with client.websocket_connect("/ws/v1/chat/completions") as websocket:
        websocket.send_json({"api_key": VALID_API_KEY})
        websocket.send_json(VALID_WS_CONFIG_PAYLOAD)

        # Collect messages until a known termination or timeout
        # The server doesn't explicitly close the connection after streaming in the current code.
        # It relies on the client to know when the stream is done (e.g. via [DONE] marker).
        # We'll receive a few messages and check.
        for _ in range(3): # Expecting 3 chunks from mock_aiter_text
             full_received_text += websocket.receive_text() # Removed timeout

    assert "data: {\"id\":\"1\", \"choices\":[{\"delta\":{\"content\":\"Hello\"}}]}\n\n" in full_received_text
    assert "data: {\"id\":\"1\", \"choices\":[{\"delta\":{\"content\":\" World\"}}]}\n\n" in full_received_text
    assert "data: [DONE]\n\n" in full_received_text

    patched_httpx_stream_method.assert_called_once_with(
        "POST",
        f"{LIARA_BASE_URLS[0]}/chat/completions", # Assumes first URL
        headers=ANY,
        json={**VALID_WS_CONFIG_PAYLOAD, "stream": True} # main.py forces stream:True
    )


@pytest.mark.asyncio
async def test_websocket_chat_missing_api_key(client: TestClient):
    with client.websocket_connect("/ws/v1/chat/completions") as websocket:
        websocket.send_json({}) # Send empty JSON, missing api_key
        response = websocket.receive_json() # Removed timeout
        assert response == {"error": "API Key is required"}

@pytest.mark.asyncio
async def test_websocket_chat_invalid_json_auth(client: TestClient):
    with client.websocket_connect("/ws/v1/chat/completions") as websocket:
        websocket.send_text("this is not json")
        response = websocket.receive_json() # Removed timeout
        assert response == {"error": "Invalid JSON message format received from client."}

@pytest.mark.asyncio
async def test_websocket_chat_invalid_json_config(client: TestClient):
    with client.websocket_connect("/ws/v1/chat/completions") as websocket:
        websocket.send_json({"api_key": VALID_API_KEY})
        websocket.send_text("this is not json for config")
        response = websocket.receive_json() # Removed timeout
        assert response == {"error": "Invalid JSON message format received from client."}


@pytest.mark.asyncio
async def test_websocket_chat_upstream_error(client: TestClient, mocker):
    # Simulate upstream server returning an error status code
    mock_stream_response = AsyncMock(status_code=500, text="Upstream server error")
    # mock_stream_response.aiter_text = lambda: (_ for _ in ()).throw(Exception("Should not be called")) # Make aiter_text raise if called

    async def mock_aiter_text_empty(): # Async generator that yields nothing
        if False: # pragma: no cover
             yield
    mock_stream_response.aiter_text = mock_aiter_text_empty


    mock_stream_context_manager = AsyncMock()
    mock_stream_context_manager.__aenter__.return_value = mock_stream_response
    mock_stream_context_manager.__aexit__ = AsyncMock(return_value=None) # Ensure async

    patched_httpx_stream_method = mocker.patch("httpx.AsyncClient.stream", new_callable=AsyncMock)
    patched_httpx_stream_method.return_value = mock_stream_context_manager

    with client.websocket_connect("/ws/v1/chat/completions") as websocket:
        websocket.send_json({"api_key": VALID_API_KEY})
        websocket.send_json(VALID_WS_CONFIG_PAYLOAD)

        response = websocket.receive_json() # Removed timeout
        # Based on the refactored main.py, this will be the detail of an UpstreamResponseError
        expected_error_detail = UpstreamResponseError(
            upstream_status_code=500,
            upstream_error_message="Upstream server error" # The .text from the mock response
        ).detail
        assert response == {"error": expected_error_detail}


@pytest.mark.asyncio
async def test_websocket_chat_all_servers_fail_connect_error(client: TestClient, mocker):
    if not LIARA_BASE_URLS:
        pytest.skip("Requires LIARA_BASE_URLS to be non-empty")

    failures = [httpx.ConnectError(f"Connection failed to server {i}") for i, _ in enumerate(LIARA_BASE_URLS)]

    patched_httpx_stream_method = mocker.patch("httpx.AsyncClient.stream", new_callable=AsyncMock)
    patched_httpx_stream_method.side_effect = failures

    with client.websocket_connect("/ws/v1/chat/completions") as websocket:
        websocket.send_json({"api_key": VALID_API_KEY})
        websocket.send_json(VALID_WS_CONFIG_PAYLOAD)

        response = websocket.receive_json() # Removed timeout
        # Expecting the error from the last failed server
        last_url = LIARA_BASE_URLS[-1].split('/')[2] # Get hostname for detail message
        expected_error_detail = UpstreamServiceDownError(
            detail=f"Could not connect to AI service endpoint: {last_url}. It may be temporarily down."
        ).detail
        assert response == {"error": expected_error_detail}

    assert patched_httpx_stream_method.call_count == len(LIARA_BASE_URLS)

@pytest.mark.asyncio
async def test_websocket_chat_fallback_behavior_ws(client: TestClient, mocker):
    if len(LIARA_BASE_URLS) < 2:
        pytest.skip("Fallback test requires at least two LIARA_BASE_URLS")

    async def mock_aiter_text_success():
        yield "data: {\"id\":\"fallback_ws\", \"choices\":[{\"delta\":{\"content\":\"Success from fallback\"}}]}\n\n"
        yield "data: [DONE]\n\n"

    mock_success_stream_response = AsyncMock(status_code=200)
    mock_success_stream_response.aiter_text = mock_aiter_text_success

    mock_success_context_manager = AsyncMock()
    mock_success_context_manager.__aenter__.return_value = mock_success_stream_response
    mock_success_context_manager.__aexit__.return_value = None

    # Side effect: first call raises ConnectError, second call returns success_manager
    patched_httpx_stream_method = mocker.patch("httpx.AsyncClient.stream", new_callable=AsyncMock)
    patched_httpx_stream_method.side_effect = [
        httpx.ConnectError("Connection failed to first ws server"),
        mock_success_context_manager
    ]

    full_received_text = ""
    with client.websocket_connect("/ws/v1/chat/completions") as websocket:
        websocket.send_json({"api_key": VALID_API_KEY})
        websocket.send_json(VALID_WS_CONFIG_PAYLOAD)

        for _ in range(2): # Expecting 2 chunks from mock_aiter_text_success
             full_received_text += websocket.receive_text() # Removed timeout

    assert "Success from fallback" in full_received_text
    assert "data: [DONE]\n\n" in full_received_text
     assert patched_httpx_stream_method.call_count == 2
    # Check call arguments if necessary
     first_call_args = patched_httpx_stream_method.call_args_list[0]
     second_call_args = patched_httpx_stream_method.call_args_list[1]
    assert first_call_args[0][1] == f"{LIARA_BASE_URLS[0]}/chat/completions" # URL is second arg for stream method
    assert second_call_args[0][1] == f"{LIARA_BASE_URLS[1]}/chat/completions"

# Test general exception during streaming (not ConnectError or HTTP status error from httpx.stream directly)
@pytest.mark.asyncio
async def test_websocket_chat_general_exception_during_streaming_loop(client: TestClient, mocker):
    # This simulates an error occurring inside the `async for chunk in response.aiter_text()` loop
    # or some other unexpected error after connection to Liara is established.

    async def mock_aiter_text_raising_exception():
        yield "data: chunk1\n\n"
        raise Exception("Something broke mid-stream") # Simulate error during iteration

    mock_stream_response = AsyncMock(status_code=200)
    mock_stream_response.aiter_text = mock_aiter_text_raising_exception

    mock_stream_context_manager = AsyncMock()
    mock_stream_context_manager.__aenter__.return_value = mock_stream_response
    mock_stream_context_manager.__aexit__ = AsyncMock(return_value=None) # Ensure async // Or mock it to raise an error too if relevant

    patched_httpx_stream_method = mocker.patch("httpx.AsyncClient.stream", new_callable=AsyncMock)
    patched_httpx_stream_method.return_value = mock_stream_context_manager
    mock_logger_error = mocker.patch("main.logger.error") # To check if general WebSocket error is logged

    with client.websocket_connect("/ws/v1/chat/completions") as websocket:
        websocket.send_json({"api_key": VALID_API_KEY})
        websocket.send_json(VALID_WS_CONFIG_PAYLOAD)

        # First message should be received
        received_chunk1 = websocket.receive_text() # Removed timeout
        assert "data: chunk1\n\n" == received_chunk1

        # Next, an error message should be sent by the server's exception handler
        error_response = websocket.receive_json() # Removed timeout
        assert "error" in error_response
        # The error message in main.py's websocket_chat for this scenario is:
        # GeneralProxyError(detail=f"An unexpected problem occurred while streaming from AI service: {url.split('/')[2]}.")
        # where url is the first (and only, in this test setup) Liara URL.
        expected_url_part = LIARA_BASE_URLS[0].split('/')[2]
        expected_detail = GeneralProxyError(detail=f"An unexpected problem occurred while streaming from AI service: {expected_url_part}.").detail
        assert error_response["error"] == expected_detail

    mock_logger_error.assert_called_once()
    # The log message in main.py for this case is:
    # logger.error(f"WS: Unexpected error with AI service at {url.split('/')[2]} during stream: {str(e)}", exc_info=True)
    assert f"WS: Unexpected error with AI service at {expected_url_part} during stream: Something broke mid-stream" in mock_logger_error.call_args[0][0]
