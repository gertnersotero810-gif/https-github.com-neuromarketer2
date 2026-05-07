import uuid
import httpx
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm_provider import LLMProvider, LLMResponse, UsageInfo
from app.models.usage_log import UsageLog

class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        db: AsyncSession
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.db = db

    async def complete(
        self,
        messages: List[Dict[str, str]],
        tenant_id: str,
        operation: str,
        response_format: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7
    ) -> LLMResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        
        if response_format:
            payload["response_format"] = response_format

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        # Parse response
        content = data["choices"][0]["message"]["content"]
        usage_data = data.get("usage", {})
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", 0)
        returned_model = data.get("model", self.model)

        # Calculate cost based on token pricing
        # For gpt-4o-mini:
        # prompt: $0.150 / 1M tokens
        # completion: $0.600 / 1M tokens
        input_cost = prompt_tokens * 0.15 / 1_000_000
        output_cost = completion_tokens * 0.60 / 1_000_000
        cost_usd = input_cost + output_cost

        # Log usage to database
        log = UsageLog(
            tenant_id=uuid.UUID(tenant_id),
            model=returned_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=Decimal(str(cost_usd)),
            operation=operation
        )
        self.db.add(log)
        await self.db.flush()

        return LLMResponse(
            content=content,
            usage=UsageInfo(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            ),
            model=returned_model
        )
