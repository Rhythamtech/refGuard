from typing import TypedDict, Optional, Literal, List
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal

class EvidenceAnalysisSchema(BaseModel):
    fraud_score: float
    signals: List[str]
    review : str

class IntentOutput(BaseModel):
    intent: str          
    order_item_id: str | None = None
    order_id: str | None = None
    reason_category: str 
    confidence: float

class RefundRequest(BaseModel):
    customer_id: str
    order_id : str
    order_item_id: str
    reason: str
    evidence_urls: List[str] = [] 

class OrderData(BaseModel):
    order_id: str
    customer_id: str
    items: List[dict]
    total_amount: Decimal
    delivered_at: Optional[datetime]
    status: str
    payment_method: str

class RefundResponse(BaseModel):
    refund_id: Optional[str]
    decision: Literal["approved", "rejected", "pending_review"]
    refund_amount: Optional[Decimal]
    message: str
    estimated_credit_time: Optional[str]


class RefundState(TypedDict):
    # Input
    request: RefundRequest

    # Populated by nodes
    intent: Optional[Literal["refund", "exchange", "inquiry", "cancel"]]
    extracted_order_item_id: Optional[str]
    order_data: Optional[OrderData]
    refund_request_id : Optional[int]

    # Eligibility
    is_eligible: Optional[bool]
    eligibility_reason: Optional[str]
    policy_context: Optional[str]  # RAG-retrieved policy text

    # Fraud
    fraud_score: Optional[float]   # 0.0 → 1.0
    fraud_signals: List[str]       # list of triggered signals

    # Decision
    decision: Optional[Literal["approve", "reject", "human_review"]]
    human_decision: Optional[Literal["approve", "reject"]]
    review_id: Optional[int]          # refund_decision PK when decision=pending_review

    # Output
    refund_id: Optional[str]
    refund_amount: Optional[Decimal]
    response_message: Optional[str]
    error: Optional[str]
    audit_log: List[dict]         