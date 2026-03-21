from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None


class ToolParameter(BaseModel):
    type: str
    description: str
    enum: Optional[List[str]] = None


class ToolFunction(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class Tool(BaseModel):
    type: str = "function"
    function: ToolFunction


class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function: Dict[str, Any]


class ChatCompletionRequest(BaseModel):
    messages: List[Message]
    model: Optional[str] = None
    provider: Optional[str] = None  # openai, anthropic, groq, gemini, etc.
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[Union[str, Dict]] = None

    # Context injection options
    inject_memory: bool = False
    inject_cognitive: bool = False
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    
    # User custom API keys (BYOK - Bring Your Own Key)
    # Keys: openai, anthropic, google, groq
    user_api_keys: Optional[Dict[str, str]] = None


class ChatCompletionChoice(BaseModel):
    index: int
    message: Message
    finish_reason: str
    tool_calls: Optional[List[ToolCall]] = None


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Usage


class StreamChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    delta: Dict[str, Any]
    finish_reason: Optional[str] = None


class AgentRouteQueryRequest(BaseModel):
    message: str
    context: Optional[List[Dict[str, Any]]] = None
    preferred_provider: Optional[str] = None
    user_api_keys: Optional[Dict[str, str]] = None
    images: Optional[List[Dict[str, Any]]] = None


# Agent Models
class AgentAction(BaseModel):
    tool: str
    tool_input: Dict[str, Any]
    log: str


class AgentFinish(BaseModel):
    return_values: Dict[str, Any]
    log: str


class AgentStep(BaseModel):
    action: AgentAction
    observation: str


class AgentRequest(BaseModel):
    task: str
    tools: List[Tool]
    max_iterations: int = 10
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None


class AgentResponse(BaseModel):
    result: str
    steps: List[AgentStep]
    total_tokens: int
