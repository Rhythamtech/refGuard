from typing import List, Literal
from decimal import Decimal
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage
from .tools.llm import get_llm, get_llm_with_structured_output, get_vision_llm_with_structured_output
from .tools.helper import regex_classify, check_regex_guardrails
from .tools.db import (
    is_customer_fraud, last_refunds, get_order_details,
    get_account_age_days, check_duplicate_refund, create_refund_request,
    create_review_queue_entry, save_refund_decision, get_customer_profile,
    save_refund_rejection, save_fraud_history,
)
from .state import RefundState, IntentOutput, EvidenceAnalysisSchema
from .prompt import (
    INTENT_PROMPT, EVIDENCE_ANALYSIS_PROMPT, ELIGIBILITY_AGENT_SYSTEM_PROMPT,
    GENERAL_SUPPORT_PROMPT,
)
from .tools.eligibility_tools import grep_policy, read_policy_section, evaluate_eligibility
import backend.agents.tools.eligibility_tools as et_module


def days_since_delivered(delivered_at: str) -> int:
    """
    Returns the number of days since the order was delivered.
    """
    delivered_date = datetime.strptime(delivered_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - delivered_date).days

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
    Classifies the intent of the request.
    """
    regex_intent = regex_classify(state["request"].reason)
    
    if regex_intent is not None:
        result = regex_intent
    else:
        try:
            history_lines = []
            for msg in state.get("chat_history", [])[:-1]:
                role = "Customer" if msg["role"] == "user" else "Assistant"
                history_lines.append(f"{role}: {msg['content']}")
            chat_history_str = "\n".join(history_lines) if history_lines else "No previous history."

            chain = INTENT_PROMPT | get_llm_with_structured_output(IntentOutput)
            result = await chain.ainvoke({
                "chat_history": chat_history_str,
                "message": state["request"].reason,
                "context": f"order_item_id hint: {state['request'].order_item_id}"
            })
        except Exception:
            result = IntentOutput(
                intent="refund_related",
                confidence=0.5,
                reason_category="fallback_generic",
                order_id=None
            )

    intent_type = result.intent

    if intent_type in ["wrong_item", "missing_item", "damaged", "quality", "request_refund", "cancel_order", "late_delivery"]:
        intent_type = "refund_related"
    elif intent_type in ["refund_inquiry"]:
        intent_type = "general_support"
    
    order_item_id = result.order_item_id or state["request"].order_item_id
    
    unrelated_count = state.get("unrelated_msg_count", 0)
    if intent_type == "unrelated":
        unrelated_count += 1
    
    return {
        "intent": intent_type,
        "intent_label": result.intent,
        "extracted_order_item_id": order_item_id,
        "unrelated_msg_count": unrelated_count,
        "audit_log": state["audit_log"] + [{
            "step": "classify_intent",
            "result": result.model_dump(),
            "ts": datetime.now(timezone.utc).isoformat()
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
                "ts": datetime.now(timezone.utc).isoformat()
            }]
        }   

    is_fraud = await is_customer_fraud(customer_id)

    if is_fraud:
        fraud_score += 1
        signals.append("fraudulent_customer")

        recent_refunds = await last_refunds(customer_id=customer_id, days=30)
        if recent_refunds > 5:
            signals.append("high_refund_frequency")
        elif recent_refunds > 3:
            signals.append("moderate_refund_frequency")

        account_age = await get_account_age_days(customer_id=customer_id)
        if account_age < 7:
            signals.append("new_customer")

        already_refunded = await check_duplicate_refund(order_item_id)
        if already_refunded:
            signals.append("duplicate_refund")

        refund_req_id = state.get("refund_request_id")
        if refund_req_id:
            await save_fraud_history(
                refund_request_id=int(refund_req_id),
                fraud_score=float(fraud_score),
                flagged_rules=signals,
            )

        return {
            "fraud_score": fraud_score,
            "fraud_signals": signals,
            "decision": "reject",
            "audit_log": state["audit_log"] + [{
                "step": "fraud_detection", "result": {
                    "is_fraud": True, "reason": "customer is fraudulent"
                },
                "ts": datetime.now(timezone.utc).isoformat()
            }]
        }   
    
    else :
        recent_refunds = await last_refunds(customer_id=customer_id, days=30)
        account_age = await get_account_age_days(customer_id=customer_id)

        if recent_refunds > 5:
            fraud_score += 0.35
            signals.append("high_refund_frequency")
        elif recent_refunds > 3:
            fraud_score += 0.15
            signals.append("moderate_refund_frequency")

        
        if account_age < 7:
            signals.append("new_customer")

        already_refunded = await check_duplicate_refund(order_item_id)

        if already_refunded:
            fraud_score += 1
            signals.append("duplicate_refund")

        if state["request"].evidence_urls:
            evidence_result = await analyze_evidence_images_with_llm(state["request"].evidence_urls, state["request"].reason)
            
            if evidence_result["fraud_score"] > 0.6:  
                fraud_score += 0.3
                signals.append("evidence_suspicious")

        fraud_score = min(fraud_score, 1.0)
        decision = "approve" if fraud_score < 0.3 else ("human_review" if fraud_score < 0.7 else "reject")

        refund_req_id = state.get("refund_request_id")
        if refund_req_id:
            await save_fraud_history(
                refund_request_id=int(refund_req_id),
                fraud_score=float(fraud_score),
                flagged_rules=signals,
            )

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
                "ts": datetime.now(timezone.utc).isoformat()
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
                "ts": datetime.now(timezone.utc).isoformat()
            }]
        }

    try:
        order_data = await get_order_details(state["request"].order_id)
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
                    "ts": datetime.now(timezone.utc).isoformat()
                }]
            }

    except Exception as e:
        return {
            "error": f"Order lookup failed: {str(e)}",
            "audit_log": state["audit_log"] + [{
                "step": "lookup_order",
                "result": {"success": False, "error": str(e), "order_id": state["request"].order_id},
                "ts": datetime.now(timezone.utc).isoformat()
            }]
        }

    # Extract customer_id, total_amount, status for the precise audit log
    customer_id = order_data.customer_id if hasattr(order_data, "customer_id") else order_data.get("customer_id")
    total_amount = order_data.total_amount if hasattr(order_data, "total_amount") else order_data.get("total_amount")
    status = order_data.status if hasattr(order_data, "status") else order_data.get("status")

    refund_request_id = state.get("refund_request_id")
    if not refund_request_id and state.get("intent") == "refund_related":
        refund_request_id = await create_refund_request(
            order_id=state["request"].order_id,
            customer_id=state["request"].customer_id,
            order_item_id=state.get("extracted_order_item_id") or state["request"].order_item_id,
            reason=state["request"].reason,
            intent=state.get("intent_label") or "refund_related"
        )

    return {
        "order_data": order_data,
        "refund_request_id": refund_request_id,
        "audit_log": state["audit_log"] + [{
            "step": "lookup_order",
            "result": {
                "success": True,
                "order_id": state["request"].order_id,
                "customer_id": customer_id,
                "total_amount": float(total_amount) if total_amount is not None else None,
                "status": status
            },
            "ts": datetime.now(timezone.utc).isoformat()
        }]
    }

async def check_eligibility_node(state: RefundState) -> dict:
    """
    Pre-flight deterministic rules (applied before LLM)
    Everything else is forwarded to the LLM ReAct agent.
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
                "ts": datetime.now(timezone.utc).isoformat()
            }]
        }

    order_item_id = state["request"].order_item_id
    items = order_data.get("items", [])
    order_status = order_data.get("status", "") or ""
    shipment_status = order_data.get("shipment_status", "") or ""
    delivered_at = order_data.get("delivered_at")

   
    _in_transit_statuses = {"shipped", "in_transit", "in transit"}

    # Rule: out_for_delivery → reject (cannot cancel once out for delivery)
    if order_status.lower() == "out_for_delivery" or shipment_status.lower() == "out_for_delivery":
        return {
            "is_eligible": False,
            "eligibility_reason": "Order cannot be cancelled once out for delivery.",
            "policy_context": "Additional Refund Rules – Shipped Orders",
            "decision": "reject",
            "response_message": (
                "We're unable to process your refund request because your order is already "
                "out for delivery and cannot be cancelled at this stage. "
                "Please wait for delivery and then contact support if there is an issue."
            ),
            "refund_amount": Decimal(0),
            "audit_log": state["audit_log"] + [{
                "step": "check_eligibility",
                "result": {
                    "is_eligible": False,
                    "reason": "Out for delivery – cannot cancel",
                    "policy_sections": ["Additional Refund Rules – Shipped Orders"],
                    "order_item_id": order_item_id
                },
                "ts": datetime.now(timezone.utc).isoformat()
            }]
        }

    # Rule: cancelled + not shipped → approve_refund
    if order_status.lower() == "cancelled" and shipment_status.lower() in ("", "not_shipped", "not shipped"):
        return {
            "is_eligible": True,
            "eligibility_reason": "Order was cancelled before shipment – full refund approved.",
            "policy_context": "Additional Refund Rules – Order Cancellation",
            "decision": "approve",
            "audit_log": state["audit_log"] + [{
                "step": "check_eligibility",
                "result": {
                    "is_eligible": True,
                    "reason": "Cancelled before shipment",
                    "policy_sections": ["Additional Refund Rules – Order Cancellation"],
                    "order_item_id": order_item_id
                },
                "ts": datetime.now(timezone.utc).isoformat()
            }]
        }

    # Rule: cancelled + already shipped/in_transit → human_review
    if order_status.lower() == "cancelled" and shipment_status.lower() in _in_transit_statuses:
        return {
            "is_eligible": True,
            "eligibility_reason": "Order was cancelled after shipment – requires human review.",
            "policy_context": "Additional Refund Rules – Order Cancellation",
            "decision": "human_review",
            "audit_log": state["audit_log"] + [{
                "step": "check_eligibility",
                "result": {
                    "is_eligible": True,
                    "reason": "Cancelled after shipment – human review required",
                    "policy_sections": ["Additional Refund Rules – Order Cancellation"],
                    "order_item_id": order_item_id
                },
                "ts": datetime.now(timezone.utc).isoformat()
            }]
        }

    # Rule: shipped / in_transit (active, not cancelled) → human_review
    if order_status.lower() in _in_transit_statuses or shipment_status.lower() in _in_transit_statuses:
        return {
            "is_eligible": True,
            "eligibility_reason": "Order is currently in transit – requires human review before any refund action.",
            "policy_context": "Additional Refund Rules – Shipped Orders",
            "decision": "human_review",
            "audit_log": state["audit_log"] + [{
                "step": "check_eligibility",
                "result": {
                    "is_eligible": True,
                    "reason": "Order in transit – human review required per policy",
                    "policy_sections": ["Additional Refund Rules – Shipped Orders"],
                    "order_item_id": order_item_id
                },
                "ts": datetime.now(timezone.utc).isoformat()
            }]
        }

    # For all other statuses, delegate to the LLM ReAct agent
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
            days = (datetime.now(timezone.utc) - delivered_at).days

    # Construct complete structured order context for the agent
    order_context = {
        "current_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "customer_id": state["request"].customer_id,
        "order_id": state["request"].order_id,
        "order_item_id": order_item_id,
        "request_reason": state["request"].reason,
        "intent": state.get("intent"),
        "order_status": order_status,
        "shipment_status": shipment_status,
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

    # Reset the context variable
    et_module._final_verdict.set(None)

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

            print(f"\n--- ReAct Step {step} ---")
            print(f"LLM Response content: {response.content}")
            print(f"LLM Tool calls: {response.tool_calls}")

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
                    # Call the underlying function directly to propagate ContextVar in the same thread/context
                    result = evaluate_eligibility.func(
                        is_eligible=tool_args.get("is_eligible"),
                        reason=tool_args.get("reason"),
                        policy_sections=tool_args.get("policy_sections")
                    )
                else:
                    result = f"Unknown tool: {tool_name}"

                print(f"Tool {tool_name} args: {tool_args}")
                print(f"Tool result: {result}")

                messages.append({
                    "role": "tool",
                    "name": tool_name,
                    "tool_call_id": tool_id,
                    "content": str(result)
                })

                if tool_name == "evaluate_eligibility":
                    break

            if et_module._final_verdict.get() is not None:
                break

            step += 1

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "is_eligible": True,
            "eligibility_reason": "LLM evaluation failed; escalating to human review",
            "decision": "human_review",
            "audit_log": state["audit_log"] + [{
                "step": "check_eligibility",
                "result": {
                    "is_eligible": True,
                    "reason": "LLM evaluation failed; escalating to human review",
                    "policy_sections": ["1. Eligibility for Refunds"],
                    "order_item_id": order_item_id
                },
                "ts": datetime.now(timezone.utc).isoformat()
            }]
        }

    verdict = et_module._final_verdict.get()
    if verdict is None:
        # Fallback to human review if LLM failed to call evaluate_eligibility tool
        return {
            "is_eligible": True,
            "eligibility_reason": "LLM evaluation failed to return a verdict; escalating to human review",
            "decision": "human_review",
            "policy_context": "1. Eligibility for Refunds",
            "audit_log": state["audit_log"] + [{
                "step": "check_eligibility",
                "result": {
                    "is_eligible": True,
                    "reason": "LLM evaluation failed to return a verdict; escalating to human review",
                    "policy_sections": ["1. Eligibility for Refunds"],
                    "order_item_id": order_item_id
                },
                "ts": datetime.now(timezone.utc).isoformat()
            }]
        }

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
                "ts": datetime.now(timezone.utc).isoformat()
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
            "ts": datetime.now(timezone.utc).isoformat()
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

    refund_request_id = state.get("refund_request_id")
    if not refund_request_id:
        refund_request_id = await create_refund_request(
            order_id=order_id,
            customer_id=customer_id,
            order_item_id=order_item_id,
            reason=state["request"].reason,
            intent=state.get("intent", "refund_related")
        )

    current_audit_log = state["audit_log"] + [{
        "step": "human_review",
        "result": {
            "fraud_score": fraud_score,
            "fraud_signals": fraud_signals,
            "order_id": order_id,
            "order_item_id": order_item_id,
            "customer_id": customer_id,
        },
        "ts": datetime.now(timezone.utc).isoformat(),
    }]

    review_id = await create_review_queue_entry(
        refund_request_id=int(refund_request_id),
        fraud_score=fraud_score,
        signals=fraud_signals,
        audit_log=current_audit_log,
    )

    return {
        "decision": "human_review",
        "review_id": review_id,
        "refund_request_id": refund_request_id,
        "audit_log": current_audit_log,
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
            

    current_audit_log = state["audit_log"] + [{
        "step": "process_refund",
        "result": {
            "review": evidence_review,
            "refund_amount": float(refund_amount),
        },
        "ts": datetime.now(timezone.utc).isoformat(),
    }]

    refund_request_id = state.get("refund_request_id")
    if not refund_request_id:
        refund_request_id = await create_refund_request(
            order_id=state["request"].order_id,
            customer_id=state["request"].customer_id,
            order_item_id=state["request"].order_item_id,
            reason=state["request"].reason,
            intent=state.get("intent", "refund_related")
        )

    refund_decision_id = await save_refund_decision(
        refund_request_id=int(refund_request_id),
        review=evidence_review,
        amount=float(refund_amount),
        audit_log=current_audit_log,
    )

    return {
        "refund_id": refund_decision_id,
        "refund_request_id": refund_request_id,
        "refund_amount": refund_amount,
        "response_message": (
            f"Your refund of ₹{refund_amount:.2f} has been approved. "
            "It will be credited to your original payment method within 5–10 business days."
        ),
        "audit_log": current_audit_log,
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

        refund_req_id = state.get("refund_request_id")
        if refund_req_id:
            current_audit_log = state["audit_log"] + [{
                "step": "generate_response",
                "result": {"decision": decision, "message": message},
                "ts": datetime.now(timezone.utc).isoformat(),
            }]
            await save_refund_rejection(
                refund_request_id=int(refund_req_id),
                review=reason,
                audit_log=current_audit_log,
            )

    return {
        "response_message": message,
        "chat_history": state.get("chat_history", []) + [{"role": "assistant", "content": message}],
        "audit_log": state["audit_log"] + [{
            "step": "generate_response",
            "result": {"decision": decision, "message": message},
            "ts": datetime.now(timezone.utc).isoformat(),
        }],
    }


async def general_support_node(state: RefundState) -> dict:
    """
    Handles general customer support queries with guardrails.
    """
    query = state["request"].reason or ""

    unrelated_count = state.get("unrelated_msg_count", 0)
    if unrelated_count >= 3:
        refusal_message = (
            "I have repeatedly informed you that I can only assist with e-commerce queries. "
            "Since we are unable to stay on topic, I must stop responding. "
            "Please start a new request if you have order or refund inquiries."
        )
        return {
            "response_message": refusal_message,
            "decision": "support",
            "chat_history": state.get("chat_history", []) + [{"role": "assistant", "content": refusal_message}],
            "audit_log": state["audit_log"] + [{
                "step": "general_support",
                "result": {"message": refusal_message, "blocked_due_to_unrelated_limit": True},
                "ts": datetime.now(timezone.utc).isoformat()
            }]
        }

    if check_regex_guardrails(query):
        refusal_message = (
            "I can only assist with e-commerce-related queries, including order status, delivery updates, "
            "product information, account support, and refund requests. If you need help with any of these, "
            "I'll be happy to assist. Unfortunately, I cannot help with topics outside of customer support."
        )
        return {
            "response_message": refusal_message,
            "decision": "support",
            "chat_history": state.get("chat_history", []) + [{"role": "assistant", "content": refusal_message}],
            "audit_log": state["audit_log"] + [{
                "step": "general_support",
                "result": {"message": refusal_message, "refused": True},
                "ts": datetime.now(timezone.utc).isoformat()
            }]
        }

    customer_data = await get_customer_profile(state["request"].customer_id)
    
    history_lines = []
    for msg in state.get("chat_history", [])[:-1]:
        role = "Customer" if msg["role"] == "user" else "Assistant"
        history_lines.append(f"{role}: {msg['content']}")
    chat_history_str = "\n".join(history_lines) if history_lines else "No previous history."

    chain = GENERAL_SUPPORT_PROMPT | get_llm()
    
    response = await chain.ainvoke({
        "chat_history": chat_history_str,
        "order_data": state.get("order_data"),
        "customer_data": customer_data,
        "unrelated_msg_count": state.get("unrelated_msg_count", 0),
        "query": query
    })
    
    message = response.content

    return {
        "response_message": message,
        "decision": "support",
        "chat_history": state.get("chat_history", []) + [{"role": "assistant", "content": message}],
        "audit_log": state["audit_log"] + [{
            "step": "general_support",
            "result": {"message": message},
            "ts": datetime.now(timezone.utc).isoformat()
        }]
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
        "chat_history": state.get("chat_history", []) + [{"role": "assistant", "content": message}],
        "audit_log": state["audit_log"] + [{
            "step": "error",
            "result": {"internal_error": internal_error},
            "ts": datetime.now(timezone.utc).isoformat(),
        }],
    }