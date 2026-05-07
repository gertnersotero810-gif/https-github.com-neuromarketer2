import pytest
import respx
import uuid
from httpx import Response
from sqlalchemy.future import select

from app.db.session import AsyncSessionLocal
from app.models.tenant import Tenant
from app.models.usage_log import UsageLog
from app.core.llm_providers.openai_provider import OpenAIProvider

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

@pytest.mark.asyncio
async def test_usage_logged_on_complete():
    database_url = os.environ.get(
        "DATABASE_URL", 
        "postgresql+asyncpg://neuro:secret@localhost:5432/neuromarketer"
    )
    engine = create_async_engine(database_url)
    TestingSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with TestingSessionLocal() as db_session:
        # Create test tenant
        tenant = Tenant(name="Test LLM Tenant", slug=f"test-llm-{uuid.uuid4().hex[:8]}")
        db_session.add(tenant)
        await db_session.flush()

        # Mock OpenAI API
        mock_response = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4o-mini",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "pong",
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }

        with respx.mock(assert_all_called=True) as respx_mock:
            route = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
                return_value=Response(200, json=mock_response)
            )

            provider = OpenAIProvider(
                api_key="test-key",
                model="gpt-4o-mini",
                base_url="https://api.openai.com/v1",
                db=db_session
            )

            response = await provider.complete(
                messages=[{"role": "user", "content": "ping"}],
                tenant_id=str(tenant.id),
                operation="test_operation"
            )

            assert response.content == "pong"
            assert response.usage.total_tokens == 30

        # Verify database log
        result = await db_session.execute(
            select(UsageLog).where(UsageLog.operation == "test_operation")
        )
        logs = result.scalars().all()
        
        assert len(logs) == 1
        log = logs[0]
        assert log.prompt_tokens == 10
        assert log.completion_tokens == 20
        assert log.total_tokens == 30
        assert log.cost_usd > 0
        assert log.model == "gpt-4o-mini"
        assert str(log.tenant_id) == str(tenant.id)
