from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class UsageInfo:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

@dataclass
class LLMResponse:
    content: str
    usage: UsageInfo
    model: str

class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: List[Dict[str, str]],
        tenant_id: str,
        operation: str,
        response_format: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7
    ) -> LLMResponse:
        pass
