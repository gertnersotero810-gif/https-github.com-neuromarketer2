from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.agents.anomaly_state import AnomalyState
from app.agents.nodes.detection_node import detection_node
from app.agents.nodes.verification_node import verification_node
from app.agents.nodes.hitl_gate_node import hitl_gate_node
from app.db.session import AsyncSessionLocal
from app.core.llm_provider import LLMProvider

async def detection_node_wrapper(state: AnomalyState) -> AnomalyState:
    """
    Wrapper for detection_node that retrieves an existing db session
    from state or creates a new one from AsyncSessionLocal.
    """
    # Try to extract db session if it's stored in state
    db = state.get("db") if isinstance(state, dict) else None
    
    if db is not None:
        # Run using the provided session
        return await detection_node(state, db)
    else:
        # Create a new session with context
        async with AsyncSessionLocal() as session:
            # We don't commit since detection node is read-only (no DML)
            return await detection_node(state, session)

def build_anomaly_graph(llm: LLMProvider):
    """
    Builds and compiles the anomaly detection LangGraph with memory checkpointer.
    """
    graph = StateGraph(AnomalyState)
    
    # Add nodes
    graph.add_node("detection", detection_node_wrapper)
    
    async def verification_node_wrapper(state: AnomalyState) -> AnomalyState:
        return await verification_node(state, llm)
    
    graph.add_node("verification", verification_node_wrapper)
    
    async def hitl_gate_node_wrapper(state: AnomalyState) -> AnomalyState:
        return await hitl_gate_node(state)
        
    graph.add_node("hitl_gate", hitl_gate_node_wrapper)
    
    # Define routing
    graph.set_entry_point("detection")
    graph.add_edge("detection", "verification")
    
    def route_after_verification(state: AnomalyState):
        if state.get("error"):
            return "end"
        return "hitl_gate"
        
    graph.add_conditional_edges(
        "verification",
        route_after_verification,
        {
            "end": END,
            "hitl_gate": "hitl_gate"
        }
    )
    
    graph.add_edge("hitl_gate", END)
    
    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


