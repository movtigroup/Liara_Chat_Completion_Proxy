import pytest
from pydantic import ValidationError
from schemas import (
    TextContent,
    ImageURL,
    Message,
    Tool,
    ToolFunction,
    CompletionRequest,
    ChatCompletionResponse,
)

# General valid model examples
VALID_TEXT_CONTENT = {"type": "text", "text": "Hello"}
VALID_IMAGE_URL_CONTENT = {"type": "image_url", "image_url": {"url": "http://example.com/image.png"}}
VALID_USER_MESSAGE_TEXT = {"role": "user", "content": "What is the weather?"}
VALID_USER_MESSAGE_MULTI = {
    "role": "user",
    "content": [
        VALID_TEXT_CONTENT,
        VALID_IMAGE_URL_CONTENT
    ]
}
VALID_ASSISTANT_MESSAGE = {"role": "assistant", "content": "It's sunny."}
VALID_TOOL_FUNCTION = {"name": "get_weather", "description": "Gets weather", "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}}
VALID_TOOL = {"type": "function", "function": VALID_TOOL_FUNCTION}

VALID_COMPLETION_REQUEST_MINIMAL = {
    "model": "openai/gpt-4o-mini",
    "messages": [VALID_USER_MESSAGE_TEXT]
}

VALID_CHAT_COMPLETION_RESPONSE = {
    "id": "chatcmpl-123",
    "object": "chat.completion",
    "created": 1677652288,
    "model": "openai/gpt-4o-mini",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hello there!",
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 9, "completion_tokens": 12, "total_tokens": 21},
}


# Test Cases for TextContent
def test_text_content_valid():
    content = TextContent(**VALID_TEXT_CONTENT)
    assert content.type == "text"
    assert content.text == "Hello"

def test_text_content_invalid_type():
    with pytest.raises(ValidationError):
        TextContent(type="invalid", text="Hello")

# Test Cases for ImageURL
def test_image_url_valid():
    content = ImageURL(**VALID_IMAGE_URL_CONTENT)
    assert content.type == "image_url"
    assert content.image_url["url"] == "http://example.com/image.png"

def test_image_url_invalid_type():
    with pytest.raises(ValidationError):
        ImageURL(type="invalid", image_url={"url": "http://example.com/image.png"})

# Test Cases for Message
def test_message_valid_text():
    msg = Message(**VALID_USER_MESSAGE_TEXT)
    assert msg.role == "user"
    assert msg.content == "What is the weather?"

def test_message_valid_multi_content():
    msg = Message(**VALID_USER_MESSAGE_MULTI)
    assert msg.role == "user"
    assert len(msg.content) == 2
    assert isinstance(msg.content[0], TextContent)
    assert isinstance(msg.content[1], ImageURL)

def test_message_invalid_role():
    with pytest.raises(ValidationError):
        Message(role="invalid_role", content="Hello")

def test_message_tool_call():
    msg_data = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "call_123",
            "type": "function",
            "function": {"name": "get_weather", "arguments": "{\"location\": \"Boston\"}"}
        }]
    }
    msg = Message(**msg_data)
    assert msg.role == "assistant"
    assert msg.tool_calls[0]["id"] == "call_123"

def test_message_tool_response():
    msg_data = {
        "role": "tool",
        "tool_call_id": "call_123",
        "content": "{\"temperature\": \"22C\"}"
    }
    msg = Message(**msg_data)
    assert msg.role == "tool"
    assert msg.tool_call_id == "call_123"
    assert msg.content == "{\"temperature\": \"22C\"}"


# Test Cases for Tool & ToolFunction
def test_tool_function_valid():
    func = ToolFunction(**VALID_TOOL_FUNCTION)
    assert func.name == "get_weather"

def test_tool_valid():
    tool = Tool(**VALID_TOOL)
    assert tool.type == "function"
    assert tool.function.name == "get_weather"

# Test Cases for CompletionRequest
def test_completion_request_valid_minimal():
    req = CompletionRequest(**VALID_COMPLETION_REQUEST_MINIMAL)
    assert req.model == "openai/gpt-4o-mini"
    assert len(req.messages) == 1

def test_completion_request_valid_full():
    full_request_data = {
        **VALID_COMPLETION_REQUEST_MINIMAL,
        "max_tokens": 100,
        "temperature": 0.5,
        "top_p": 0.9,
        "stop": ["\n"],
        "frequency_penalty": 0.1,
        "presence_penalty": 0.2,
        "seed": 123,
        "tools": [VALID_TOOL],
        "tool_choice": "auto",
        "stream": False
    }
    req = CompletionRequest(**full_request_data)
    assert req.max_tokens == 100
    assert req.temperature == 0.5
    assert req.tools[0].function.name == "get_weather"

def test_completion_request_invalid_model():
    with pytest.raises(ValidationError):
        CompletionRequest(model="invalid/model", messages=[VALID_USER_MESSAGE_TEXT])

def test_completion_request_missing_messages():
    with pytest.raises(ValidationError):
        CompletionRequest(model="openai/gpt-4o-mini", messages=[]) # Empty list is not allowed by Field(...)

def test_completion_request_invalid_temperature():
    with pytest.raises(ValidationError):
        CompletionRequest(**VALID_COMPLETION_REQUEST_MINIMAL, temperature=3.0) # > 2.0

def test_completion_request_invalid_max_tokens():
    with pytest.raises(ValidationError):
        CompletionRequest(**VALID_COMPLETION_REQUEST_MINIMAL, max_tokens=0) # <=1
    with pytest.raises(ValidationError):
        CompletionRequest(**VALID_COMPLETION_REQUEST_MINIMAL, max_tokens=5000) # >4096


# Test Cases for ChatCompletionResponse
def test_chat_completion_response_valid():
    resp = ChatCompletionResponse(**VALID_CHAT_COMPLETION_RESPONSE)
    assert resp.id == "chatcmpl-123"
    assert resp.model == "openai/gpt-4o-mini"
    assert len(resp.choices) == 1
    assert resp.choices[0]["message"]["content"] == "Hello there!"
    assert resp.usage["total_tokens"] == 21

def test_chat_completion_response_missing_fields():
    with pytest.raises(ValidationError):
        ChatCompletionResponse(id="123", object="chat.completion", created=123, model="gpt-4") # Missing choices

def test_chat_completion_response_stream_chunk_like():
    # This model is for the full response, not stream chunks directly.
    # Stream chunks would be different and typically parsed piece by piece.
    # However, we can test a choice that might look like a delta from a stream.
    stream_choice = {
        "index": 0,
        "delta": {"role": "assistant", "content": "Hello"},
        "finish_reason": None
    }
    response_data = {
        "id": "chatcmpl-stream-123",
        "object": "chat.completion.chunk", # Note: object type is different for chunks
        "created": 1677652288,
        "model": "openai/gpt-4o-mini",
        "choices": [stream_choice]
        # No 'usage' in stream chunks typically
    }
    # Our ChatCompletionResponse is not designed for 'chat.completion.chunk'
    # This test is more conceptual for choice structure.
    # If we were to validate chunks, we'd need a different Pydantic model.

    # For the existing ChatCompletionResponse, this would fail on 'object' and 'delta' vs 'message'
    with pytest.raises(ValidationError):
         ChatCompletionResponse(**response_data)

    # Let's adapt it to fit the existing model, pretending it's a non-streamed single message
    adapted_choice = {
        "index": 0,
        "message": {"role": "assistant", "content": "Hello"},
        "finish_reason": None
    }
    adapted_response_data = {
        "id": "chatcmpl-stream-123",
        "object": "chat.completion", # Correct object type for this model
        "created": 1677652288,
        "model": "openai/gpt-4o-mini",
        "choices": [adapted_choice]
    }
    resp = ChatCompletionResponse(**adapted_response_data)
    assert resp.choices[0]["message"]["content"] == "Hello"

# Example of how to test specific model constraints if they were more complex
# For example, if a field had a regex:
# class MyModel(BaseModel):
#   phone: str = Field(regex=r"^\+?[0-9]{10,15}$")
#
# def test_my_model_phone_valid():
#   MyModel(phone="+12345678901")
#
# def test_my_model_phone_invalid():
#   with pytest.raises(ValidationError):
#       MyModel(phone="123")
#
# (This is just a comment, no actual regex field in current schemas to test like this)
# The current schemas mostly rely on type annotations and standard Pydantic validations (Literal, Optional, basic types, simple gt/le)
# which are implicitly tested by the above cases.
# For example, `max_tokens: Optional[int] = Field(None, gt=1, le=4096)` is tested by:
# - `test_completion_request_valid_full` (valid value)
# - `test_completion_request_invalid_max_tokens` (invalid values outside gt/le range)
# - Omitting it (valid due to Optional)
