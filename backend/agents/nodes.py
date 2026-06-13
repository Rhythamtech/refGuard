from .tools.llm  import get_llm_with_structured_output
from .tools.helper import regex_classify
from datetime import datetime
from .state import RefundState, IntentOutput
from .prompt import INTENT_PROMPT


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