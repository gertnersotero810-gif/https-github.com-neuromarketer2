from langgraph.graph import StateGraph, END
from app.agents.anomaly_state import AnomalyState
from app.agents.nodes.detection_node import detection_node
from app.db.session import AsyncSessionLocal

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

def create_anomaly_graph():
    """
    Builds and compiles the anomaly detection LangGraph.
    Currently a simple workflow: START -> detection -> END.
    """
    graph = StateGraph(AnomalyState)
    
    # Add nodes
    graph.add_node("detection", detection_node_wrapper)
    
    # Define routing
    graph.set_entry_point("detection")
    graph.add_edge("detection", END)
    
    return graph.compile()

# Compile the graph object
anomaly_graph = create_anomaly_graph()
