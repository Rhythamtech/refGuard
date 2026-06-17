from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from .state import RefundState
from .nodes import (
    classify_intent_node,
    lookup_order_node,
    check_eligibility_node,
    fraud_detection_node,
    human_review_node,
    process_refund_node,
    generate_response_node,
    error_node,
)

# Routing functions
def route_after_lookup(state: RefundState) -> str:
    if state.get("error"):
        return "error"
    if not state.get("order_data"):
        return "error"
    return "check_eligibility"

def route_after_eligibility(state: RefundState) -> str:
    if state.get("error"):
        return "error"
    if state.get("is_eligible") is False:
        return "generate_response"
    return "fraud_detection"

def route_after_fraud(state: RefundState) -> str:
    if state.get("error"):
        return "error"
    decision = state.get("decision")
    if decision == "approve":
        return "process_refund"
    elif decision == "human_review":
        return "human_review"
    else:  # reject
        return "generate_response"


# Initialize the state-driven workflow
workflow = StateGraph(RefundState)

# Add all nodes
workflow.add_node("classify_intent", classify_intent_node)
workflow.add_node("lookup_order", lookup_order_node)
workflow.add_node("check_eligibility", check_eligibility_node)
workflow.add_node("fraud_detection", fraud_detection_node)
workflow.add_node("human_review", human_review_node)
workflow.add_node("process_refund", process_refund_node)
workflow.add_node("generate_response", generate_response_node)
workflow.add_node("error", error_node)

# Wire the nodes
workflow.add_edge(START, "classify_intent")
workflow.add_edge("classify_intent", "lookup_order")

# Conditional transitions
workflow.add_conditional_edges(
    "lookup_order",
    route_after_lookup,
    {
        "error": "error",
        "check_eligibility": "check_eligibility"
    }
)

workflow.add_conditional_edges(
    "check_eligibility",
    route_after_eligibility,
    {
        "error": "error",
        "generate_response": "generate_response",
        "fraud_detection": "fraud_detection"
    }
)

workflow.add_conditional_edges(
    "fraud_detection",
    route_after_fraud,
    {
        "error": "error",
        "process_refund": "process_refund",
        "human_review": "human_review",
        "generate_response": "generate_response"
    }
)

# Human review flows directly to generate_response to show the customer the pending status.
workflow.add_edge("human_review", "generate_response")

# Terminating nodes
workflow.add_edge("process_refund", "generate_response")
workflow.add_edge("generate_response", END)
workflow.add_edge("error", END)

# Compile graph with MemorySaver checkpointer
checkpointer = MemorySaver()
graph = workflow.compile(checkpointer=checkpointer)
