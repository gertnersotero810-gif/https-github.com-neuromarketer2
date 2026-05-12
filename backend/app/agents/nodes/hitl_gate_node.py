from app.agents.anomaly_state import AnomalyState


async def hitl_gate_node(state: AnomalyState) -> AnomalyState:
    dangerous = [
        a for a in state["verified_anomalies"]
        if a.get("budget_change_pct", 0) > 20 or a.get("fraud", False)
    ]

    if dangerous:
        return {
            **state,
            "pending_approval": True,
            "approval_payload": {
                "anomalies": dangerous,
                "requires_action": True,
            },
        }

    return {**state, "pending_approval": False}
