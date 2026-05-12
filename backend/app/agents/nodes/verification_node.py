import json
from app.agents.anomaly_state import AnomalyState
from app.core.llm_provider import LLMProvider


async def verification_node(state: AnomalyState, llm: LLMProvider) -> AnomalyState:
    if not state["candidates"]:
        return state

    try:
        context = json.dumps(state["candidates"], default=str)[:1000]
        prompt = f"""Analyze these marketing anomalies and respond ONLY in JSON:
{context}

Respond with exactly this JSON structure:
{{"verified": bool, "action": "reduce_budget|pause_campaign|investigate|no_action", "budget_change_pct": float, "fraud": bool, "reasoning": "string max 200 chars"}}"""

        response = await llm.complete(
            messages=[{"role": "user", "content": prompt}],
            tenant_id=state["tenant_id"],
            operation="anomaly_verify",
            response_format={"type": "json_object"},
            temperature=0.0,
        )

        # КРИТИЧНО: всегда response.content, никогда response напрямую
        data = json.loads(response.content)

        if data.get("verified", False):
            enriched = [{**c, **data} for c in state["candidates"]]
            return {**state, "verified_anomalies": enriched}

        return {**state, "verified_anomalies": []}

    except Exception as e:
        return {**state, "error": str(e), "verified_anomalies": []}
