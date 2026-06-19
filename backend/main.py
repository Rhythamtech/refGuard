import os
import sys
from pathlib import Path

# Setup system path so absolute imports work when running from different directories
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from typing import List, Optional, Literal
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from backend.agents.graph import workflow
from backend.agents.state import RefundRequest
from backend.agents.tools.db import (
    get_customer_by_email,
    get_admin_by_email,
    get_customer_profile,
    get_customer_orders,
    get_order_details,
    get_customer_refund_history,
    get_review_queue,
    get_refund_logs,
    get_admin_stats,
    get_all_customers_summary,
    resolve_review_decision,
    clear_all_logs,
)


from contextlib import asynccontextmanager


load_dotenv()

compiled_graph = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global compiled_graph
    async with AsyncSqliteSaver.from_conn_string("checkpoints.db") as checkpointer:
        app.state.checkpointer = checkpointer
        compiled_graph = workflow.compile(checkpointer=checkpointer)
        app.state.graph = compiled_graph
        yield

app = FastAPI(title="Refund Guard AI API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex="https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# JWT helper functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, os.getenv("SECRET_KEY"), algorithm=os.getenv("ALGORITHM"))
    return encoded_jwt

def decode_token(token: str):
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=[os.getenv("ALGORITHM")])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user(token: str = Depends(oauth2_scheme)):
    return decode_token(token)

def get_current_customer(user: dict = Depends(get_current_user)):
    if user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Not authorized as a customer")
    return user

def get_current_admin(user: dict = Depends(get_current_user)):
    if user.get("role") not in ["admin", "supervisor", "agent"]:
        raise HTTPException(status_code=403, detail="Not authorized as an admin staff")
    return user


# Pydantic Schemas
class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    name: str
    id: int

class SubmitRefundPayload(BaseModel):
    order_id: str
    order_item_id: str
    reason: str
    evidence_urls: List[str] = []

class RefundSubmissionResponse(BaseModel):
    refund_request_id: int
    decision: str
    refund_amount: float
    message: str
    review_id: Optional[int] = None

class QueueDecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]

# Routes
@app.get("/health")
def health_check():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.post("/auth/customer/login", response_model=TokenResponse)
async def customer_login(payload: LoginRequest):
    user = await get_customer_by_email(payload.email)
    # Support both raw password comparison and MD5 hash comparison
    password_match = False
    if user:
        db_hash = user.get("password_hash")
        input_hash = hashlib.md5(payload.password.encode()).hexdigest()
        if db_hash == payload.password or db_hash == input_hash:
            password_match = True
            
    if not user or not password_match:
        raise HTTPException(status_code=400, detail="Invalid email or password")
    
    access_token = create_access_token(
        data={"sub": str(user["id"]), "role": "customer", "email": user["email"]}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": "customer",
        "name": user["full_name"],
        "id": user["id"]
    }


@app.post("/auth/admin/login", response_model=TokenResponse)
async def admin_login(payload: LoginRequest):
    user = await get_admin_by_email(payload.email)
    password_match = False
    if user:
        db_hash = user.get("password_hash")
        input_hash = hashlib.md5(payload.password.encode()).hexdigest()
        if db_hash == payload.password or db_hash == input_hash:
            password_match = True
            
    if not user or not password_match:
        raise HTTPException(status_code=400, detail="Invalid email or password")
    
    access_token = create_access_token(
        data={"sub": str(user["id"]), "role": user["role"], "email": user["email"]}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user["role"],
        "name": user["name"],
        "id": user["id"]
    }


@app.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    user_id = user["sub"]
    if user["role"] == "customer":
        profile = await get_customer_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Customer not found")
        profile["role"] = "customer"
        return profile
    else:
        # Admin
        admin = await get_admin_by_email(user["email"])
        if not admin:
            raise HTTPException(status_code=404, detail="Admin user not found")
        return {
            "id": admin["id"],
            "name": admin["name"],
            "email": admin["email"],
            "role": admin["role"]
        }


# Customer Portal Routes
@app.get("/customer/profile")
async def customer_profile(user: dict = Depends(get_current_customer)):
    profile = await get_customer_profile(user["sub"])
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.get("/customer/orders")
async def customer_orders(user: dict = Depends(get_current_customer)):
    return await get_customer_orders(user["sub"])


@app.get("/customer/orders/{order_id}")
async def customer_order_detail(order_id: str, user: dict = Depends(get_current_customer)):
    order = await get_order_details(order_id)
    if not order or str(order.get("customer_id")) != str(user["sub"]):
        raise HTTPException(status_code=404, detail="Order not found or access denied")
    return order


@app.get("/customer/refunds")
async def customer_refunds(user: dict = Depends(get_current_customer)):
    return await get_customer_refund_history(user["sub"])


# Refund Pipeline Routes
@app.post("/refund/submit", response_model=RefundSubmissionResponse)
async def submit_refund(payload: SubmitRefundPayload, user: dict = Depends(get_current_customer)):
    global compiled_graph
    if not compiled_graph:
        raise HTTPException(status_code=500, detail="Workflow graph not compiled")

    # Verify order belongs to customer
    order = await get_order_details(payload.order_id)
    if not order or str(order.get("customer_id")) != str(user["sub"]):
        raise HTTPException(status_code=400, detail="Invalid order or unauthorized access")

    # Match order item
    matched_item = None
    for item in order.get("items", []):
        if str(item.get("order_item_id")) == str(payload.order_item_id):
            matched_item = item
            break
    
    if not matched_item:
        raise HTTPException(status_code=400, detail="Item not found in order")

    # Prepare RefundRequest for LangGraph pipeline
    request = RefundRequest(
        customer_id=str(user["sub"]),
        order_id=payload.order_id,
        order_item_id=payload.order_item_id,
        reason=payload.reason,
        evidence_urls=payload.evidence_urls
    )

    # Execute graph
    # Generate a stable thread ID per user/order/item
    thread_id = f"refund-{user['sub']}-{payload.order_id}-{payload.order_item_id}"
    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Check for previous state to retrieve chat_history
        state_info = await compiled_graph.aget_state(config)
        previous_history = state_info.values.get("chat_history", []) if state_info.values else []
        new_history = previous_history + [{"role": "user", "content": payload.reason}]

        # Initialize graph state
        initial_state = {
            "request": request,
            "chat_history": new_history,
            "audit_log": state_info.values.get("audit_log", []) if state_info.values else [],
            "unrelated_msg_count": state_info.values.get("unrelated_msg_count", 0) if state_info.values else 0,
            "order_data": state_info.values.get("order_data") if state_info.values else None,
            "refund_request_id": state_info.values.get("refund_request_id") if state_info.values else None,
        }

        # Run graph steps asynchronously until completion
        async for _ in compiled_graph.astream(initial_state, config):
            pass

        # Fetch final state
        state_info = await compiled_graph.aget_state(config)
        final_state = state_info.values

        # Form response
        decision = final_state.get("decision", "reject")
        refund_amount = float(final_state.get("refund_amount") or 0.0)
        message = final_state.get("response_message") or "Your request could not be processed at this time."
        refund_req_id = final_state.get("refund_request_id") or 0
        review_id = final_state.get("review_id")

        return {
            "refund_request_id": refund_req_id,
            "decision": decision,
            "refund_amount": refund_amount,
            "message": message,
            "review_id": review_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline processing failed: {str(e)}")


# Admin Management Routes
@app.get("/admin/stats")
async def admin_stats(user: dict = Depends(get_current_admin)):
    return await get_admin_stats()


@app.get("/admin/logs")
async def admin_logs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_admin)
):
    return await get_refund_logs(limit, offset)


@app.delete("/admin/logs")
async def admin_clear_logs(user: dict = Depends(get_current_admin)):
    success = await clear_all_logs()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to clear logs")
    return {"ok": True}


@app.get("/admin/queue")
async def admin_queue(user: dict = Depends(get_current_admin)):
    return await get_review_queue()


@app.post("/admin/queue/{review_id}/decide")
async def admin_decide(
    review_id: int,
    payload: QueueDecisionRequest,
    user: dict = Depends(get_current_admin)
):
    admin_id = int(user["sub"])
    decision = payload.decision
    db_decision = "approved" if decision == "approved" else "rejected"

    try:
        success = await resolve_review_decision(review_id, db_decision, admin_id)
        if not success:
            raise HTTPException(status_code=404, detail="Review task not found or already decided")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process decision: {str(e)}")


@app.get("/admin/customers")
async def admin_customers(user: dict = Depends(get_current_admin)):
    return await get_all_customers_summary()
