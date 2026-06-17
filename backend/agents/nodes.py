from typing import List, Literal
from decimal import Decimal
from datetime import datetime
from langchain_core.messages import HumanMessage
from .tools.llm import get_llm, get_llm_with_structured_output, get_vision_llm_with_structured_output
from .tools.helper import regex_classify
from .tools.db import (
    is_customer_fraud, last_refunds, get_order_details,
    get_account_age_days, check_duplicate_refund, create_refund_request,
    create_review_queue_entry, save_refund_decision,
)
from .state import RefundState, IntentOutput, EvidenceAnalysisSchema
from .prompt import INTENT_PROMPT, EVIDENCE_ANALYSIS_PROMPT, ELIGIBILITY_AGENT_SYSTEM_PROMPT
from .tools.eligibility_tools import grep_policy, read_policy_section, evaluate_eligibility
import backend.agents.tools.eligibility_tools as et_module


def days_since_delivered(delivered_at: str) -> int:
    """
    Returns the number of days since the order was delivered.
    """
    delivered_date = datetime.strptime(delivered_at, "%Y-%m-%d %H:%M:%S")
    return (datetime.utcnow() - delivered_date).days

async def analyze_evidence_images_with_llm(evidence_urls: List[str], user_message: str)->dict:
    """
    Analyzes evidence images using a vision-capable LLM.
    """

    messages = []
    messages.append({"type": "text", "text": user_message})
    for url in evidence_urls:
        messages.append({"type": "image_url", "image_url": {"url": url}})

    message = HumanMessage(content=messages)

    try:
        chain = EVIDENCE_ANALYSIS_PROMPT | get_vision_llm_with_structured_output(EvidenceAnalysisSchema)
        result = await chain.ainvoke(message)

        return {
            "fraud_score": result.fraud_score,
            "signals": result.signals,
            "review": result.review
        }
    except Exception:
        return {
            "fraud_score": 0.5,
            "signals": ["vision_analysis_unavailable"],
            "review": "Evidence analysis failed due to service unavailability."
        }

def compute_refund_amount(state: RefundState) -> Decimal:
    """
    Shared helper: find the order item and compute unit_price * quantity.
    Falls back to 0 if the item cannot be located.
    """
    order_item_id = state["request"].order_item_id
    order_data = state.get("order_data")
    if not order_data:
        return Decimal(0)

    items = order_data.get("items", [])
    for item in items:
        item_id = str(item.get("order_item_id", ""))
        if item_id == str(order_item_id):
            unit_price = Decimal(str(item.get("unit_price", 0)))
            quantity = int(item.get("quantity", 1))
            return unit_price * quantity

    return Decimal(0)

# Nodes 
async def classify_intent_node(state: RefundState) -> dict:
    """
    Classifies the intent of the refund request.
    """
    regex_intent = regex_classify(state["request"].reason)
    
    if regex_intent is not None:
        result = regex_intent
    else:
        try:
            chain = INTENT_PROMPT | get_llm_with_structured_output(IntentOutput)
            result = await chain.ainvoke({
                "message": state["request"].reason,
                "context": f"order_item_id hint: {state['request'].order_item_id}"
            })
        except Exception:
            result = IntentOutput(
                intent="request_refund",
                confidence=0.5,
                reason_category="fallback_generic",
                order_id=None
            )

    intent = result.intent
    order_item_id = result.order_item_id or state["request"].order_item_id
    
    refund_request_id = create_refund_request(
        order_id=state["request"].order_id,
        customer_id=state["request"].customer_id,
        order_item_id=order_item_id,
        reason=state["request"].reason,
        intent=intent
    )
    
    return {
        "refund_request_id": refund_request_id,
        "intent": intent,
        "extracted_order_item_id": order_item_id,
        "audit_log": state["audit_log"] + [{
            "step": "classify_intent",
            "result": result.dict(),
            "ts": datetime.utcnow().isoformat()
        }]
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

async def lookup_order_node(state: RefundState) -> dict: 
    """
    Looks up order data in the database.
    """
    if state.get("order_data") is not None:
        return {
            "audit_log": state["audit_log"] + [{
                "step": "lookup_order",
                "result": {"success": True, "cached": True, "order_id": state["request"].order_id},
                "ts": datetime.utcnow().isoformat()
            }]
        }

    try:
        order_data = get_order_details(state["request"].order_id)
        if not order_data:
            return {
                "is_eligible": False,
                "eligibility_reason": "Order not found",
                "decision": "reject",
                "response_message": "Order not found",
                "refund_amount": Decimal(0),
                "audit_log": state["audit_log"] + [{
                    "step": "lookup_order",
                    "result": {"success": False, "reason": "Order not found", "order_id": state["request"].order_id},
                    "ts": datetime.utcnow().isoformat()
                }]
            }

    except Exception as e:
        return {
            "error": f"Order lookup failed: {str(e)}",
            "audit_log": state["audit_log"] + [{
                "step": "lookup_order",
                "result": {"success": False, "error": str(e), "order_id": state["request"].order_id},
                "ts": datetime.utcnow().isoformat()
            }]
        }

    # Extract customer_id, total_amount, status for the precise audit log
    customer_id = order_data.customer_id if hasattr(order_data, "customer_id") else order_data.get("customer_id")
    total_amount = order_data.total_amount if hasattr(order_data, "total_amount") else order_data.get("total_amount")
    status = order_data.status if hasattr(order_data, "status") else order_data.get("status")

    return {
        "order_data": order_data,
        "audit_log": state["audit_log"] + [{
            "step": "lookup_order",
            "result": {
                "success": True,
                "order_id": state["request"].order_id,
                "customer_id": customer_id,
                "total_amount": float(total_amount) if total_amount is not None else None,
                "status": status
            },
            "ts": datetime.utcnow().isoformat()
        }]
    }

async def check_eligibility_node(state: RefundState) -> dict:
    """
    Checks if the refund request is eligible for a refund using an LLM agent.
    """
    order_data = state.get("order_data")
    if not order_data:
        return {
            "is_eligible": False,
            "eligibility_reason": "Order not found or not loaded",
            "decision": "reject",
            "response_message": "Order not found or not loaded",
            "refund_amount": Decimal(0),
            "audit_log": state["audit_log"] + [{
                "step": "check_eligibility",
                "result": {"is_eligible": False, "reason": "Order not found or not loaded"},
                "ts": datetime.utcnow().isoformat()
            }]
        }

    order_item_id = state["request"].order_item_id
    items = order_data.get("items", [])
    status = order_data.get("status")
    delivered_at = order_data.get("delivered_at")

    # Find the specific order item requested
    matched_item = None
    for item in items:
        if str(item.get("order_item_id", "")) == str(order_item_id):
            matched_item = item
            break

    # Calculate days since delivery if delivered_at is available
    days = None
    if delivered_at:
        if isinstance(delivered_at, str):
            days = days_since_delivered(delivered_at)
        else:
            days = (datetime.utcnow() - delivered_at).days

    # Construct complete structured order context for the agent
    order_context = {
        "customer_id": state["request"].customer_id,
        "order_id": state["request"].order_id,
        "order_item_id": order_item_id,
        "request_reason": state["request"].reason,
        "intent": state.get("intent"),
        "order_status": status,
        "delivered_at": str(delivered_at) if delivered_at else None,
        "days_since_delivery": days,
        "matched_item": {
            "product_name": matched_item.get("product_name") if matched_item else None,
            "product_category": matched_item.get("product_category") if matched_item else None,
            "item_status": matched_item.get("status") if matched_item else None,
            "return_window_days": matched_item.get("return_window_days") if matched_item else None,
            "unit_price": float(matched_item.get("unit_price", 0)) if matched_item else 0.0,
            "quantity": matched_item.get("quantity") if matched_item else 1
        } if matched_item else None,
        "fraud_score": state.get("fraud_score"),
        "fraud_signals": state.get("fraud_signals", [])
    }

    # Reset the global verdict registry
    et_module._final_verdict = None

    try:
        # Initialize ReAct agent execution
        llm = get_llm()
        tools = [grep_policy, read_policy_section, evaluate_eligibility]
        llm_with_tools = llm.bind_tools(tools)

        messages = [
            ("system", ELIGIBILITY_AGENT_SYSTEM_PROMPT),
            ("human", f"Verify the refund eligibility of this request under the store refund policies.\n\nOrder Context:\n{order_context}")
        ]

        # Run ReAct step loop
        max_steps = 10
        step = 0
        while step < max_steps:
            response = await llm_with_tools.ainvoke(messages)
            messages.append(response)

            if not response.tool_calls:
                # Prompt the LLM to submit a final verdict via evaluate_eligibility if it stopped early
                messages.append(("human", "You must conclude the evaluation by calling the `evaluate_eligibility` tool with the structured verdict. Please call `evaluate_eligibility` now."))
                step += 1
                continue

            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                tool_id = tc["id"]

                # Invoke the appropriate tool
                if tool_name == "grep_policy":
                    result = grep_policy.invoke(tool_args)
                elif tool_name == "read_policy_section":
                    result = read_policy_section.invoke(tool_args)
                elif tool_name == "evaluate_eligibility":
                    result = evaluate_eligibility.invoke(tool_args)
                else:
                    result = f"Unknown tool: {tool_name}"

                messages.append({
                    "role": "tool",
                    "name": tool_name,
                    "tool_call_id": tool_id,
                    "content": str(result)
                })

                if tool_name == "evaluate_eligibility":
                    break

            if et_module._final_verdict is not None:
                break

            step += 1

    except Exception as e:
        # Log LLM execution failure in internal trace (silently fallback)
        pass

    # Retrieve the agent's final verdict or run the fallback engine
    verdict = et_module._final_verdict
    if verdict is None:
        # Safety Fallback Engine (replicates standard policy constraints)
        is_eligible = True
        reason = None

        if matched_item and matched_item.get("status") == "refunded":
            is_eligible = False
            reason = "This order has already been refunded."
        else:
            return_window_days = matched_item.get("return_window_days") if matched_item else None
            if return_window_days is not None and days is not None:
                if days > return_window_days:
                    is_eligible = False
                    reason = f"Order is {days} days old, outside the {return_window_days}-day return window."

        verdict = et_module.EligibilityVerdict(
            is_eligible=is_eligible,
            reason=reason or "Eligible for refund",
            policy_sections=["1. Eligibility for Refunds"]
        )

    # Return structured state updates based on the verdict
    if not verdict.is_eligible:
        return {
            "is_eligible": False,
            "eligibility_reason": verdict.reason,
            "policy_context": ", ".join(verdict.policy_sections),
            "decision": "reject",
            "response_message": verdict.reason,
            "refund_amount": Decimal(0),
            "audit_log": state["audit_log"] + [{
                "step": "check_eligibility",
                "result": {
                    "is_eligible": False,
                    "reason": verdict.reason,
                    "policy_sections": verdict.policy_sections,
                    "order_item_id": order_item_id
                },
                "ts": datetime.utcnow().isoformat()
            }]
        }

    return {
        "is_eligible": True,
        "eligibility_reason": None,
        "policy_context": ", ".join(verdict.policy_sections),
        "audit_log": state["audit_log"] + [{
            "step": "check_eligibility",
            "result": {
                "is_eligible": True,
                "reason": verdict.reason,
                "policy_sections": verdict.policy_sections,
                "order_item_id": order_item_id
            },
            "ts": datetime.utcnow().isoformat()
        }]
    }



async def human_review_node(state: RefundState) -> dict:
    """
    Marks the refund request as pending human review.
    """

    order_item_id = state["request"].order_item_id
    order_id = state["request"].order_id
    customer_id = state["request"].customer_id
    fraud_score = state.get("fraud_score") or 0.0
    fraud_signals = state.get("fraud_signals") or []

    review_id = create_review_queue_entry(
        refund_request_id=int(state["refund_request_id"]),
        fraud_score=fraud_score,
        signals=fraud_signals,
    )

    return {
        "decision": "human_review",
        "review_id": review_id,
        "audit_log": state["audit_log"] + [{
            "step": "human_review",
            "result": {
                "review_id": review_id,
                "fraud_score": fraud_score,
                "fraud_signals": fraud_signals,
                "order_id": order_id,
                "order_item_id": order_item_id,
                "customer_id": customer_id,
            },
            "ts": datetime.utcnow().isoformat(),
        }],
    }




async def process_refund_node(state: RefundState) -> dict:
    """
    Executes the refund for auto-approved cases.
    Computes the refund amount from the matched order item, writes an approved record to refund_decision, and sets the response message.
    """
    refund_amount = compute_refund_amount(state)

    evidence_review = ""
    if state["request"].evidence_urls:
        evidence_result = await analyze_evidence_images_with_llm(state["request"].evidence_urls, state["request"].reason)
        evidence_review = evidence_result["review"]
            

    refund_decision_id = save_refund_decision(
        refund_request_id=int(state["refund_request_id"]),
        review=evidence_review,
        amount=float(refund_amount),
    )

    return {
        "refund_id": refund_decision_id,
        "refund_amount": refund_amount,
        "response_message": (
            f"Your refund of ₹{refund_amount:.2f} has been approved. "
            "It will be credited to your original payment method within 5–10 business days."
        ),
        "audit_log": state["audit_log"] + [{
            "step": "process_refund",
            "result": {
                "refund_id": refund_decision_id,
                "review": evidence_review,
                "refund_amount": float(refund_amount),
            },
            "ts": datetime.utcnow().isoformat(),
        }],
    }


async def generate_response_node(state: RefundState) -> dict:
    """
    Produces the final customer-facing response message.
    """
    decision = state.get("decision")

    if decision == "approve":
        refund_amount = state.get("refund_amount", Decimal(0))
        message = (
            f"Great news! Your refund of ₹{refund_amount:.2f} has been approved. "
            "It will be credited to your original payment method within 5–10 business days."
        )

    elif decision == "human_review":
        review_id = state.get("review_id")
        message = (
            "Your refund request is currently under review by our support team. "
            "We'll get back to you within 24 hours with an update. "
            f"Your reference ID is: {review_id}."
        )

    else:  # reject
        reason = state.get("eligibility_reason")
        if not reason:
            signals = state.get("fraud_signals") or []
            reason = (
                "your request could not be verified against our refund policy"
                if signals else
                "your request does not meet the refund eligibility criteria"
            )
        message = (
            f"We're unable to process your refund request at this time because {reason}. "
            "If you believe this is an error, please contact our support team."
        )

    return {
        "response_message": message,
        "audit_log": state["audit_log"] + [{
            "step": "generate_response",
            "result": {"decision": decision, "message": message},
            "ts": datetime.utcnow().isoformat(),
        }],
    }


async def error_node(state: RefundState) -> dict:
    """
    Handles unexpected pipeline failures gracefully.

    Reads the error set in state, logs it internally, and returns a
    user-safe message that does not expose internal details.
    """
    internal_error = state.get("error", "unknown error")
    message = (
        "We encountered an issue processing your refund request. "
        "Please try again or contact our support team for assistance."
    )

    return {
        "decision": "reject",
        "response_message": message,
        "audit_log": state["audit_log"] + [{
            "step": "error",
            "result": {"internal_error": internal_error},
            "ts": datetime.utcnow().isoformat(),
        }],
    }