from langchain_core.prompts import ChatPromptTemplate

INTENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a refund intent classifier for a quick-commerce platform.
Extract: intent type, order ID, reason category, and confidence.
Reason categories: wrong_item | missing_item | not_delivered | damaged | quality | refund_inquiry | request_refund | cancel_order | late_delivery | other
Return valid JSON matching the IntentOutput schema."""),
    ("human", "Customer message: {message}\nContext: {context}")
])


EVIDENCE_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an evidence analyzer for a quick-commerce platform.
You will be given details of evidence uploaded by a customer, and their message. Analyze it and determine the likelihood of fraud, or any anomalies.
Extract: fraud_score, signals
fraud_Score must be between 0.0 to 1.0 , 1.0 being highest
signals should be a list of strings describing the fraud indicators
review should be a string describing the review of the evidence (one-liner)
Return valid JSON matching the EvidenceAnalysisSchema schema."""),
    ("human", "Evidence details: {messages}")
])