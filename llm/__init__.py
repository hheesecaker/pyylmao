from __future__ import annotations

from pyylmao.generated_commands import (
    Attachment,
    GeneratedLLMModel,
    GeneratedLLMResponse,
    GeneratedTool,
    GeneratedToolRegistry,
    MessageEvent,
    Toolbox,
    get_model,
    get_tools,
)

model = get_model
_pyylmao_api = True

__all__ = [
    "Attachment",
    "GeneratedLLMModel",
    "GeneratedLLMResponse",
    "GeneratedTool",
    "GeneratedToolRegistry",
    "MessageEvent",
    "Toolbox",
    "get_model",
    "model",
    "get_tools",
]
