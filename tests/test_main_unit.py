import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from main import ConnectionManager, logger
from main import (
    get_sync_initial_cache_maxsize,
    get_sync_dynamic_customer_limit_str,
    get_sync_dynamic_business_limit_str,
    get_sync_dynamic_default_limit_str
)
import httpx
import json

from main import _handle_chat_completions_request, APIKeyDetails, CompletionRequest, cache
from errors import UpstreamServiceDownError, UpstreamTimeoutError, UpstreamResponseError, GeneralProxyError
from link import LIARA_BASE_URLS
from utils import generate_cache_key


@pytest.fixture
def manager():
    return ConnectionManager()

@pytest.mark.asyncio
async def test_connection_manager_connect(manager: ConnectionManager):
    websocket_mock = AsyncMock()
    connection_id = "test_conn_1"
    await manager.connect(websocket_mock, connection_id)
    websocket_mock.accept.assert_awaited_once()
    assert connection_id in manager.active_connections
    assert manager.active_connections[connection_id] is websocket_mock

@pytest.mark.asyncio
async def test_connection_manager_disconnect_assuming_async(manager: ConnectionManager):
    websocket_mock = AsyncMock()
    connection_id = "test_conn_2"
    await manager.connect(websocket_mock, connection_id)
    assert connection_id in manager.active_connections
    await manager.disconnect(connection_id)
    assert connection_id not in manager.active_connections

@pytest.mark.asyncio
async def test_connection_manager_disconnect_non_existent_assuming_async(manager: ConnectionManager):
    await manager.disconnect("non_existent_id")
    assert "non_existent_id" not in manager.active_connections

@pytest.mark.asyncio
async def test_connection_manager_send_message(manager: ConnectionManager):
    websocket_mock = AsyncMock()
    connection_id = "test_conn_3"
    message_text = "Hello, WebSocket!"
    await manager.connect(websocket_mock, connection_id)
    await manager.send_message(connection_id, message_text)
    websocket_mock.send_text.assert_awaited_once_with(message_text)

@pytest.mark.asyncio
async def test_connection_manager_send_message_connection_not_active(manager: ConnectionManager):
    connection_id = "test_conn_4_disconnected"
    websocket_mock = AsyncMock()
    await manager.connect(websocket_mock, connection_id)
    await manager.disconnect(connection_id)
    await manager.send_message(connection_id, "This should not be sent.")
    websocket_mock.send_text.assert_not_awaited()

@pytest.mark.asyncio
async def test_connection_manager_send_message_exception_during_send(manager: ConnectionManager, mocker):
    websocket_mock = AsyncMock()
    websocket_mock.send_text.side_effect = Exception("Network Error")
    connection_id = "test_conn_5_error"
    message_text = "Test message"
    mock_logger_error = mocker.patch("main.logger.error")
    await manager.connect(websocket_mock, connection_id)
    await manager.send_message(connection_id, message_text)
    websocket_mock.send_text.assert_awaited_once_with(message_text)
    mock_logger_error.assert_called_once()
    args, _ = mock_logger_error.call_args
    expected_log_message_part = f"Error sending message to {connection_id}: Network Error"
    assert expected_log_message_part in args[0]

@pytest.mark.asyncio
async def test_connection_manager_multiple_connections_assuming_async_disconnect(manager: ConnectionManager):
    ws1_mock = AsyncMock()
    id1 = "conn1"
    ws2_mock = AsyncMock()
    id2 = "conn2"
    await manager.connect(ws1_mock, id1)
    await manager.connect(ws2_mock, id2)
    assert id1 in manager.active_connections
    assert id2 in manager.active_connections
    await manager.send_message(id1, "msg1")
    ws1_mock.send_text.assert_awaited_once_with("msg1")
    ws2_mock.send_text.assert_not_awaited()
    await manager.send_message(id2, "msg2")
    ws2_mock.send_text.assert_awaited_once_with("msg2")
    await manager.disconnect(id1)
    assert id1 not in manager.active_connections
    assert id2 in manager.active_connections
    await manager.disconnect(id2)
    assert id2 not in manager.active_connections

# --- Tests for Dynamic Configuration Functions ---
def test_get_sync_initial_cache_maxsize(mocker):
    mocker.patch("psutil.virtual_memory", return_value=mocker.Mock(total=8 * (1024**3)))
    assert get_sync_initial_cache_maxsize() == 2000
    mocker.patch("psutil.virtual_memory", return_value=mocker.Mock(total=4 * (1024**3)))
    assert get_sync_initial_cache_maxsize() == 1000
    mocker.patch("psutil.virtual_memory", return_value=mocker.Mock(total=2 * (1024**3)))
    assert get_sync_initial_cache_maxsize() == 500
    mocker.patch("psutil.virtual_memory", side_effect=Exception("Test Error"))
    mock_logger_warning = mocker.patch("main.logger.warning")
    assert get_sync_initial_cache_maxsize() == 500
    mock_logger_warning.assert_called_once_with("Could not determine system memory for cache sizing, defaulting to 500. Error: Test Error")

def test_get_sync_dynamic_customer_limit_str(mocker):
    mock_os_cpu_count = mocker.patch("os.cpu_count", return_value=4)
    mock_psutil_cpu_percent = mocker.patch("psutil.cpu_percent", return_value=50)
    assert get_sync_dynamic_customer_limit_str() == "200/minute"
    mock_os_cpu_count.assert_called_once()
    mock_psutil_cpu_percent.assert_called_once_with(interval=0.1)
    mock_psutil_cpu_percent.return_value = 95
    assert get_sync_dynamic_customer_limit_str() == "150/minute"
    mock_os_cpu_count.return_value = 1
    mock_psutil_cpu_percent.return_value = 50
    assert get_sync_dynamic_customer_limit_str() == "100/minute"
    mock_os_cpu_count.side_effect = Exception("Test CPU Count Error")
    mock_logger_warning = mocker.patch("main.logger.warning")
    assert get_sync_dynamic_customer_limit_str() == "100/minute"
    mock_logger_warning.assert_called_with("Could not determine dynamic rate limit for v1, defaulting to 100/minute. Error: Test CPU Count Error")

def test_get_sync_dynamic_business_limit_str(mocker):
    mock_os_cpu_count = mocker.patch("os.cpu_count", return_value=4)
    mock_psutil_cpu_percent = mocker.patch("psutil.cpu_percent", return_value=50)
    assert get_sync_dynamic_business_limit_str() == "2000/minute"
    mock_psutil_cpu_percent.return_value = 95
    assert get_sync_dynamic_business_limit_str() == "1500/minute"
    mock_os_cpu_count.return_value = 1
    mock_psutil_cpu_percent.return_value = 50
    assert get_sync_dynamic_business_limit_str() == "1000/minute"
    mock_psutil_cpu_percent.side_effect = Exception("Test CPU Percent Error")
    mock_logger_warning = mocker.patch("main.logger.warning")
    assert get_sync_dynamic_business_limit_str() == "1000/minute"
    mock_logger_warning.assert_called_with("Could not determine dynamic rate limit for v2, defaulting to 1000/minute. Error: Test CPU Percent Error")

def test_get_sync_dynamic_default_limit_str(mocker):
    mock_os_cpu_count = mocker.patch("os.cpu_count", return_value=2)
    mock_psutil_cpu_percent = mocker.patch("psutil.cpu_percent", return_value=50)
    assert get_sync_dynamic_default_limit_str() == "100/minute"
    mock_psutil_cpu_percent.return_value = 90
    assert get_sync_dynamic_default_limit_str() == "80/minute"
    mock_os_cpu_count.return_value = None
    mock_psutil_cpu_percent.return_value = 30
    assert get_sync_dynamic_default_limit_str() == "100/minute"
    mocker.patch("os.cpu_count", side_effect=Exception("Generic Error"))
    mock_logger_warning = mocker.patch("main.logger.warning")
    assert get_sync_dynamic_default_limit_str() == "100/minute"
    mock_logger_warning.assert_called_with("Could not determine dynamic default rate limit, defaulting to 100/minute. Error: Generic Error")

# --- End Tests for Dynamic Configuration Functions ---

# --- Common Mocking Setup for httpx.AsyncClient for _handle_chat_completions_request ---
def mock_httpx_async_client(mocker, post_return_value=None, post_side_effect=None):
    mock_response_from_post = post_return_value

    mock_managed_client = AsyncMock() # This is the 'client' from 'async with ... as client'
    if post_side_effect:
        mock_managed_client.post = AsyncMock(side_effect=post_side_effect)
    else:
        mock_managed_client.post.return_value = mock_response_from_post

    mock_client_constructor_result = AsyncMock() # Return value of httpx.AsyncClient()
    mock_client_constructor_result.__aenter__.return_value = mock_managed_client

    mocker.patch("httpx.AsyncClient", return_value=mock_client_constructor_result)
    return mock_managed_client # Return this to assert calls on client.post

# --- Tests for _handle_chat_completions_request ---
@pytest.fixture(autouse=True)
def clear_cache_before_each_test():
    cache.clear()

@pytest.mark.asyncio
async def test_handle_chat_completions_success_first_url(mocker):
    mock_response_data = {"id": "chatcmpl-123", "choices": [{"message": {"role": "assistant", "content": "Hello there"}}]}
    mock_resp_obj = MagicMock(spec=httpx.Response)
    mock_resp_obj.status_code = 200
    mock_resp_obj.json = MagicMock(return_value=mock_response_data)
    mock_resp_obj.text = json.dumps(mock_response_data)

    mock_managed_client = mock_httpx_async_client(mocker, post_return_value=mock_resp_obj)

    api_key_details: APIKeyDetails = ("cust-valid-key", "v1_customer")
    body = CompletionRequest(model="openai/gpt-4o-mini", messages=[{"role": "user", "content": "Hi"}])

    response_json_response = await _handle_chat_completions_request(api_key_details, body)

    assert response_json_response.status_code == 200
    assert json.loads(response_json_response.body.decode()) == mock_response_data
    mock_managed_client.post.assert_awaited_once()

    expected_cache_key = generate_cache_key(body.model_dump(exclude_unset=True))
    assert expected_cache_key in cache
    assert cache[expected_cache_key] == mock_response_data

@pytest.mark.asyncio
async def test_handle_chat_completions_success_second_url_after_timeout(mocker):
    if len(LIARA_BASE_URLS) < 2: pytest.skip("Test requires at least two LIARA_BASE_URLS")

    mock_response_data = {"id": "chatcmpl-456", "choices": [{"message": {"role": "assistant", "content": "Secondary success"}}]}
    mock_successful_resp_obj = MagicMock(spec=httpx.Response)
    mock_successful_resp_obj.status_code = 200
    mock_successful_resp_obj.json = MagicMock(return_value=mock_response_data)
    mock_successful_resp_obj.text = json.dumps(mock_response_data)

    mock_post_side_effects = [httpx.TimeoutException("Simulated timeout"), mock_successful_resp_obj]
    mock_managed_client = mock_httpx_async_client(mocker, post_side_effect=mock_post_side_effects)

    api_key_details: APIKeyDetails = ("cust-valid-key", "v1_customer")
    body = CompletionRequest(model="openai/gpt-4o-mini", messages=[{"role": "user", "content": "Hi"}])

    response_json_response = await _handle_chat_completions_request(api_key_details, body)

    assert response_json_response.status_code == 200
    assert json.loads(response_json_response.body.decode()) == mock_response_data
    assert mock_managed_client.post.await_count == 2

    first_call_args = mock_managed_client.post.await_args_list[0]
    second_call_args = mock_managed_client.post.await_args_list[1]
    assert LIARA_BASE_URLS[0] in first_call_args[0][0]
    assert LIARA_BASE_URLS[1] in second_call_args[0][0]

    expected_cache_key = generate_cache_key(body.model_dump(exclude_unset=True))
    assert expected_cache_key in cache
    assert cache[expected_cache_key] == mock_response_data

@pytest.mark.asyncio
async def test_handle_chat_completions_all_urls_fail_timeout(mocker):
    if not LIARA_BASE_URLS: pytest.skip("Test requires at least one LIARA_BASE_URL")

    mock_managed_client = mock_httpx_async_client(mocker, post_side_effect=httpx.TimeoutException("Simulated timeout"))

    api_key_details: APIKeyDetails = ("cust-valid-key", "v1_customer")
    body = CompletionRequest(model="openai/gpt-4o-mini", messages=[{"role": "user", "content": "Hi"}])

    with pytest.raises(UpstreamTimeoutError):
        await _handle_chat_completions_request(api_key_details, body)

    assert mock_managed_client.post.await_count == len(LIARA_BASE_URLS)
    assert len(cache) == 0

@pytest.mark.asyncio
async def test_handle_chat_completions_all_urls_fail_connect_error(mocker):
    if not LIARA_BASE_URLS: pytest.skip("Test requires at least one LIARA_BASE_URL")

    mock_managed_client = mock_httpx_async_client(mocker, post_side_effect=httpx.ConnectError("Simulated connect error"))

    api_key_details: APIKeyDetails = ("cust-valid-key", "v1_customer")
    body = CompletionRequest(model="openai/gpt-4o-mini", messages=[{"role": "user", "content": "Hi"}])

    with pytest.raises(UpstreamServiceDownError):
        await _handle_chat_completions_request(api_key_details, body)
    assert mock_managed_client.post.await_count == len(LIARA_BASE_URLS)

@pytest.mark.asyncio
async def test_handle_chat_completions_all_urls_fail_upstream_response_error(mocker):
    if not LIARA_BASE_URLS: pytest.skip("Test requires at least one LIARA_BASE_URL")

    mock_err_resp_obj = MagicMock(spec=httpx.Response)
    mock_err_resp_obj.status_code = 500
    mock_err_resp_obj.text = "Internal Server Error from Upstream"

    mock_managed_client = mock_httpx_async_client(mocker, post_return_value=mock_err_resp_obj)

    api_key_details: APIKeyDetails = ("cust-valid-key", "v1_customer")
    body = CompletionRequest(model="openai/gpt-4o-mini", messages=[{"role": "user", "content": "Hi"}])

    with pytest.raises(UpstreamResponseError) as excinfo:
        await _handle_chat_completions_request(api_key_details, body)

    assert excinfo.value.status_code == 502
    assert "status: 500" in excinfo.value.detail
    assert "Internal Server Error from Upstream" in excinfo.value.detail
    assert mock_managed_client.post.await_count == len(LIARA_BASE_URLS)

@pytest.mark.asyncio
async def test_handle_chat_completions_cache_hit(mocker):
    mock_response_data = {"id": "chatcmpl-789", "choices": [{"message": {"role": "assistant", "content": "Cached Hello"}}]}
    api_key_details: APIKeyDetails = ("cust-valid-key", "v1_customer")
    body = CompletionRequest(model="openai/gpt-4o-mini", messages=[{"role": "user", "content": "Cache me"}])
    expected_cache_key = generate_cache_key(body.model_dump(exclude_unset=True))

    cache[expected_cache_key] = mock_response_data

    # We still need to mock httpx.AsyncClient in case cache is missed, but its post shouldn't be called
    mock_managed_client = mock_httpx_async_client(mocker, post_return_value=MagicMock()) # Dummy return that would fail if called
    mock_logger_info = mocker.patch("main.logger.info")

    response_json_response = await _handle_chat_completions_request(api_key_details, body)

    assert response_json_response.status_code == 200
    assert json.loads(response_json_response.body.decode()) == mock_response_data
    mock_managed_client.post.assert_not_awaited()

    logged_cache_hit = False
    for call_args in mock_logger_info.call_args_list:
        if f"Cache hit for key: {expected_cache_key}" in call_args[0][0]:
            logged_cache_hit = True; break
    assert logged_cache_hit

@pytest.mark.asyncio
async def test_handle_chat_completions_mixed_errors_then_success(mocker):
    if len(LIARA_BASE_URLS) < 3:
        pytest.skip("Test requires at least three LIARA_BASE_URLS to simulate mixed errors then success")

    mock_response_data = {"id": "chatcmpl-xyz", "choices": [{"message": {"role": "assistant", "content": "Finally success"}}]}

    mock_err_resp_obj = MagicMock(spec=httpx.Response)
    mock_err_resp_obj.status_code = 503
    mock_err_resp_obj.text = "Service Unavailable for second URL"

    mock_succ_resp_obj = MagicMock(spec=httpx.Response)
    mock_succ_resp_obj.status_code = 200
    mock_succ_resp_obj.json = MagicMock(return_value=mock_response_data)
    mock_succ_resp_obj.text = json.dumps(mock_response_data)

    mock_post_side_effects = [
        httpx.TimeoutException("Simulated timeout for first URL"),
        mock_err_resp_obj,
        mock_succ_resp_obj
    ]
    mock_managed_client = mock_httpx_async_client(mocker, post_side_effect=mock_post_side_effects)

    api_key_details: APIKeyDetails = ("cust-valid-key", "v1_customer")
    body = CompletionRequest(model="openai/gpt-4o-mini", messages=[{"role": "user", "content": "Retry test"}])

    response_json_response = await _handle_chat_completions_request(api_key_details, body)

    assert response_json_response.status_code == 200
    assert json.loads(response_json_response.body.decode()) == mock_response_data
    assert mock_managed_client.post.await_count == 3

    assert LIARA_BASE_URLS[0] in mock_managed_client.post.await_args_list[0][0][0]
    assert LIARA_BASE_URLS[1] in mock_managed_client.post.await_args_list[1][0][0]
    assert LIARA_BASE_URLS[2] in mock_managed_client.post.await_args_list[2][0][0]

    expected_cache_key = generate_cache_key(body.model_dump(exclude_unset=True))
    assert expected_cache_key in cache
    assert cache[expected_cache_key] == mock_response_data
# --- End Tests for _handle_chat_completions_request ---
