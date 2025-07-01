import asyncio
import pytest
from unittest.mock import AsyncMock # Changed from MagicMock for async methods

# Assuming ConnectionManager is in main.py and accessible for import
from main import ConnectionManager, logger # Import logger for mocking if needed

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
    """
    This test assumes that ConnectionManager.disconnect is an `async def` method.
    If `main.py` has a synchronous `disconnect` with `async with self.lock`,
    that's a bug in `main.py` which will likely cause a RuntimeError.
    """
    websocket_mock = AsyncMock()
    connection_id = "test_conn_2"

    await manager.connect(websocket_mock, connection_id)
    assert connection_id in manager.active_connections

    await manager.disconnect(connection_id)
    assert connection_id not in manager.active_connections

@pytest.mark.asyncio
async def test_connection_manager_disconnect_non_existent_assuming_async(manager: ConnectionManager):
    """ Assumes disconnect is async """
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
    """ Assumes disconnect is async """
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
    # The exception is part of the formatted string in args[0]
    expected_log_message_part = f"Error sending message to {connection_id}: Network Error"
    assert expected_log_message_part in args[0]
    # Ensure the logged message also contains the specific exception string,
    # which is already covered by the above if the side_effect was just Exception("Network Error")
    # If the exception object itself was passed as a second arg to logger.error, then args[1] would be valid.
    # assert "Network Error" in str(args[0]) # This is redundant due to the f-string check


@pytest.mark.asyncio
async def test_connection_manager_multiple_connections_assuming_async_disconnect(manager: ConnectionManager):
    """ Assumes disconnect is async """
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
