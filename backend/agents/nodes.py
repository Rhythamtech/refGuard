from typing import List, Literal
from decimal import Decimal
from datetime import datetime
from langchain_core.messages import HumanMessage
from .tools.llm import get_llm_with_structured_output, get_vision_llm_with_structured_output
from .tools.helper import regex_classify
from .tools.db import is_customer_fraud, last_refunds, get_order_details, get_account_age_days, check_duplicate_refund
from .state import RefundState, IntentOutput, EvidenceAnalysisSchema
from .prompt import INTENT_PROMPT, EVIDENCE_ANALYSIS_PROMPT


def days_since_delivered(delivered_at: str) -> int:
    """
    Returns the number of days since the order was delivered.
    """
    delivered_date = datetime.strptime(delivered_at, "%Y-%m-%d %H:%M:%S")
    return (datetime.utcnow() - delivered_date).days

async def classify_intent_node(state: RefundState) -> dict:
    """
    Classifies the intent of the refund request.
    """

    regex_intent = regex_classify(state["request"].reason)
    if regex_intent is not None: 
        return {
            "intent": regex_intent.intent,
            "extracted_order_item_id": regex_intent.order_item_id or state["request"].order_item_id,
            "audit_log": state["audit_log"] + [{
                "step": "classify_intent", "result": regex_intent.dict(),
                "ts": datetime.utcnow().isoformat()
            }]
        }
    else: 
        chain = INTENT_PROMPT | get_llm_with_structured_output(IntentOutput)
        result = await chain.ainvoke({
            "message": state["request"].reason,
            "context": f"order_item_id hint: {state['request'].order_item_id}"
        })
        return {
            "intent": result.intent,
            "extracted_order_item_id": result.order_item_id or state["request"].order_item_id,
            "audit_log": state["audit_log"] + [{
                "step": "classify_intent", "result": result.dict(),
                "ts": datetime.utcnow().isoformat()
            }]
        }    


async def analyze_evidence_images_with_llm(evidence_urls: List[str], user_message: str)->dict:
    """
    Analyzes evidence images using a vision-capable LLM.
    """

    messages = []
    messages.append({"type": "text", "text": user_message})
    for url in evidence_urls:
        messages.append({"type": "image_url", "image_url": {"url": url}})

    message = HumanMessage(content=messages)

    chain = EVIDENCE_ANALYSIS_PROMPT | get_vision_llm_with_structured_output(EvidenceAnalysisSchema) 
    result = await chain.ainvoke(message)

    return {
        "fraud_score": result.fraud_score,
        "signals": result.signals
    }

async def fraud_detection_node(state: RefundState) -> dict: 
    """
    Detects fraudulent refund requests.
    """

    fraud_score = 0
    signals = []
    customer_id = state["request"].customer_id
    order_id = state["request"].order_id
    order_item_id = state["request"].order_item_id

    if customer_id is None or order_id is None:
        return {
            "audit_log": state["audit_log"] + [{
                "step": "fraud_detection", "result": {
                    "is_fraud": False, "reason": "customer_id or order_id is None"
                },
                "ts": datetime.utcnow().isoformat()
            }]
        }   

    is_fraud =  is_customer_fraud(customer_id)

    if is_fraud:
        fraud_score += 1

        return {
            "fraud_score": fraud_score,
            "fraud_signals": signals,
            "decision": "reject",
            "audit_log": state["audit_log"] + [{
                "step": "fraud_detection", "result": {
                    "is_fraud": True, "reason": "customer is fraudulent"
                },
                "ts": datetime.utcnow().isoformat()
            }]
        }   
    
    else :
        recent_refunds = last_refunds(customer_id=customer_id, days=30)
        account_age = get_account_age_days(customer_id=customer_id)

        if recent_refunds > 5:
            fraud_score += 0.35
            signals.append("high_refund_frequency")
        elif recent_refunds > 3:
            fraud_score += 0.15
            signals.append("moderate_refund_frequency")

        
        if account_age < 7:
            signals.append("new_customer")

        already_refunded = check_duplicate_refund(order_item_id)

        if already_refunded:
            fraud_score += 1
            signals.append("duplicate_refund")

        if state["request"].evidence_urls:
            evidence_result = await analyze_evidence_images_with_llm(state["request"].evidence_urls, state["request"].reason)
            
            if evidence_result["fraud_score"] < 0.4:  
                fraud_score += 0.3
                signals.append("evidence_mismatch")

        fraud_score = min(fraud_score, 1.0)
        decision = "approve" if fraud_score < 0.3 else ("human_review" if fraud_score < 0.7 else "reject")

        return {
            "fraud_score": fraud_score,
            "fraud_signals": signals,
            "decision": decision,
            "audit_log": state["audit_log"] + [{
                "step": "fraud_detection", "result": {
                    "fraud_score": fraud_score,
                    "signals": signals,
                    "decision": decision
                },
                "ts": datetime.utcnow().isoformat()
            }]
        }   


def lookup_order_node(state: RefundState) -> dict: 
    """
    Looks up order data in the database.
    """
    if state["order_data"] is not None:
        return {}

    try:
        order_data = get_order_details(state["request"].order_id)
        if not order_data:
            return {
                "is_eligible": False,
                "eligibility_reason": "Order not found",
                "decision": "reject",
                "response_message": "Order not found",
                "refund_amount": Decimal(0)
            }

    except Exception as e:
        return {"error": f"Order lookup failed: {str(e)}"}

    return {
        "order_data": order_data
    }


def check_eligibility_node(state: RefundState) -> dict:
    """
    Checks if the refund request is eligible for a refund.
    """
    order_data = state.get("order_data")
    if not order_data:
        return {
            "is_eligible": False,
            "eligibility_reason": "Order not found or not loaded",
            "decision": "reject",
            "response_message": "Order not found or not loaded",
            "refund_amount": Decimal(0)
        }

    order_item_id = state["request"].order_item_id

    items = order_data.items if hasattr(order_data, "items") else order_data.get("items", [])
    status = order_data.status if hasattr(order_data, "status") else order_data.get("status")
    delivered_at = order_data.delivered_at if hasattr(order_data, "delivered_at") else order_data.get("delivered_at")

    def is_item_refunded(items_list, item_id):
        for item in items_list:
            if item.get("order_item_id") == item_id:
                return item.get("status") == "refunded"
        return False

    def get_return_window_days(items_list, item_id):
        for item in items_list:
            if item.get("order_item_id") == item_id:
                return item.get("return_window_days")
        return None

    if is_item_refunded(items, order_item_id) and status == "refunded":
        return {
            "is_eligible": False,
            "eligibility_reason": "This order has already been refunded.",
            "decision": "reject",
            "response_message": "This order has already been refunded.",
            "refund_amount": Decimal(0)
        }

    return_window_days = get_return_window_days(items, order_item_id)
    if return_window_days is not None and delivered_at:
        if isinstance(delivered_at, str):
            days = days_since_delivered(delivered_at)
        else:
            days = (datetime.utcnow() - delivered_at).days

        if days > return_window_days:
            return {
                "is_eligible": False,
                "eligibility_reason": f"Order is {days} days old, outside the {return_window_days}-day return window.",
                "decision": "reject",
                "response_message": f"Order is {days} days old, outside the {return_window_days}-day return window.",
                "refund_amount": Decimal(0)
            }

    return {
        "is_eligible": True,
        "eligibility_reason": None
    }