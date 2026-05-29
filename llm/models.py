from __future__ import annotations

from pyylmao.generated_commands import (
    Attachment,
    GeneratedLLMModel,
    GeneratedLLMResponse,
    get_model,
)

Model = GeneratedLLMModel
Response = GeneratedLLMResponse
model = get_model

__all__ = [
    "Attachment",
    "GeneratedLLMModel",
    "GeneratedLLMResponse",
    "Model",
    "Response",
    "get_model",
    "model",
]
