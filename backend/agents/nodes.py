from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel
from .tools.llm  import get_llm_with_structured_output
from .tools.helper import regex_classify
from datetime import datetime, timedelta
from .state import RefundState, IntentOutput


INTENTS = [
    "wrong_item",
    "missing_item",
    "not_delivered",
    "damaged",
    "quality",
    "refund_inquiry",
    "request_refund",
    "cancel_order",
    "late_delivery",
]


INTENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a refund intent classifier for a quick-commerce platform.
Extract: intent type, order ID, reason category, and confidence.
Reason categories: damaged | wrong_item | quality | not_delivered | missing_item | other
Return valid JSON matching the IntentOutput schema."""),
    ("human", "Customer message: {message}\nContext: {context}")
])

async def classify_intent_node(state: RefundState) -> dict:

    regex_intent = regex_classify(state["request"].reason)
    if regex_intent is not None: 
        return {
            "intent": regex_intent.intent,
            "extracted_order_id": regex_intent.order_id or state["request"].order_id,
            "audit_log": state["audit_log"] + [{
                "step": "classify_intent", "result": regex_intent.dict(),
                "ts": datetime.utcnow().isoformat()
            }]
        }
    else: 
        chain = INTENT_PROMPT | get_llm_with_structured_output(IntentOutput)
        result = await chain.ainvoke({
            "message": state["request"].reason,
            "context": f"order_id hint: {state['request'].order_id}"
        })
        return {
            "intent": result.intent,
            "extracted_order_id": result.order_id or state["request"].order_id,
            "audit_log": state["audit_log"] + [{
                "step": "classify_intent", "result": result.dict(),
                "ts": datetime.utcnow().isoformat()
            }]
        }    