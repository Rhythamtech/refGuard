from langchain_core.prompts import ChatPromptTemplate

INTENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a refund intent classifier for a quick-commerce platform.
Extract: intent type, order ID, reason category, and confidence.
Reason categories: wrong_item | missing_item | not_delivered | damaged | quality | refund_inquiry | request_refund | cancel_order | late_delivery | other
Return valid JSON matching the IntentOutput schema."""),
    ("human", "Customer message: {message}\nContext: {context}")
])
