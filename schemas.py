from pydantic import BaseModel, Field
from typing import List, Union, Literal, Optional, Dict, Any


class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ImageURL(BaseModel):
    type: Literal["image_url"] = "image_url"
    image_url: Dict[str, Any]


ContentItem = Union[TextContent, ImageURL]


class Message(BaseModel):
    role: Literal["user", "system", "assistant", "tool"]
    content: Optional[Union[str, List[ContentItem]]] = None # Allow None for tool calls
    name: Optional[str] = None
    tool_calls: Optional[List[dict]] = None
    tool_call_id: Optional[str] = None


class ToolFunction(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: dict


class Tool(BaseModel):
    type: Literal["function"] = "function"
    function: ToolFunction


class CompletionRequest(BaseModel):
    model: Literal[
        "openai/gpt-4o-mini",
        "google/gemini-2.0-flash-001",
        "deepseek/deepseek-v3-0324",
        "meta/llama-3-3-70b-instruct",
        "anthropic/claude-3-7-sonnet",
        "anthropic/claude-3-5-sonnet",
    ] = Field(..., description="مدل هوش مصنوعی مورد استفاده")

    messages: List[Message] = Field(..., min_length=1, description="لیست پیام‌های گفتگو") # Changed min_items to min_length for Pydantic V2

    # پارامترهای مشترک
    max_tokens: Optional[int] = Field(
        None, gt=1, le=4096, description="حداکثر توکن خروجی"
    )
    temperature: Optional[float] = Field(
        None, ge=0.0, le=2.0, description="درجه خلاقیت"
    )
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="نمونه‌گیری هسته‌ای")
    stop: Optional[Union[str, List[str]]] = Field(None, description="توکن‌های توقف")
    frequency_penalty: Optional[float] = Field(
        None, ge=-2.0, le=2.0, description="جریمه تکرار"
    )
    presence_penalty: Optional[float] = Field(
        None, ge=-2.0, le=2.0, description="جریمه حضور"
    )
    seed: Optional[int] = Field(None, description="مقدار ثابت برای تصادفی‌سازی")

    # پارامترهای ویژه مدل‌ها
    web_search_options: Optional[dict] = Field(None, description="تنظیمات جستجوی وب")
    logit_bias: Optional[dict] = Field(None, description="انحراف لاجیت")
    logprobs: Optional[bool] = Field(None, description="نمایش احتمالات")
    top_logprobs: Optional[int] = Field(None, description="تعداد احتمالات برتر")
    response_format: Optional[dict] = Field(None, description="فرمت پاسخ")
    structured_outputs: Optional[dict] = Field(None, description="خروجی ساختاریافته")
    tools: Optional[List[Tool]] = Field(None, description="ابزارهای قابل استفاده")
    tool_choice: Optional[Union[str, dict]] = Field(None, description="انتخاب ابزار")

    # برای استریمینگ
    stream: Optional[bool] = Field(False, description="فعال‌سازی استریمینگ")


class ChatCompletionResponse(BaseModel):
    id: str = Field(..., description="شناسه منحصر به فرد")
    object: Literal["chat.completion"] = Field(..., description="نوع شیء")
    created: int = Field(..., description="زمان ایجاد")
    model: str = Field(..., description="مدل استفاده شده")
    choices: List[dict] = Field(..., description="لیست انتخاب‌ها")
    usage: Optional[dict] = Field(None, description="اطلاعات مصرف توکن")
