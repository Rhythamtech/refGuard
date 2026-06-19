import sys
from pathlib import Path
import asyncio
import pytest
from datetime import datetime, timedelta, timezone
import os

# Add paths to sys.path for import resolution
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent))

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from backend.agents.graph import workflow
from backend.agents.state import RefundRequest
from backend.agents.tools.db import get_db_conn

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()


def get_decision_style(decision: str) -> tuple[str, str]:
    """Returns (border_color, emoji) based on decision value."""
    decision = (decision or "").lower()
    if "approved" in decision or "approve" == decision:
        return "green", "✅"
    elif "rejected" in decision or "reject" == decision or "invalid" in decision:
        return "red", "❌"
    elif "review" in decision or "pending" in decision or "escalat" in decision or "human_review" == decision:
        return "yellow", "🔍"
    else:
        return "blue", "ℹ️"


def print_result(case_title: str, final_state: dict):
    decision = final_state.get("decision", "N/A")
    border_color, emoji = get_decision_style(decision)

    # ── Main Info Table ──────────────────────────────────────────
    info_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    info_table.add_column("Field", style="bold cyan", min_width=20)
    info_table.add_column("Value", style="white")

    is_eligible = final_state.get("is_eligible")
    eligible_display = (
        Text("Yes", style="bold green") if is_eligible
        else Text("No", style="bold red") if is_eligible is not None
        else Text("N/A", style="dim")
    )

    fraud_score = final_state.get("fraud_score")
    fraud_display = Text(
        str(fraud_score) if fraud_score is not None else "N/A",
        style="bold red" if (fraud_score or 0) > 0.6 else "bold yellow" if (fraud_score or 0) > 0.3 else "bold green"
    )

    info_table.add_row("Final Decision", Text(str(decision), style=f"bold {border_color}"))
    info_table.add_row("Is Eligible", eligible_display)
    info_table.add_row("Eligibility Reason", str(final_state.get("eligibility_reason") or "N/A"))
    info_table.add_row("Policy Context", str(final_state.get("policy_context") or "N/A"))
    info_table.add_row("Fraud Score", fraud_display)
    info_table.add_row("Fraud Signals", str(final_state.get("fraud_signals") or "None"))
    info_table.add_row("Refund Amount", str(final_state.get("refund_amount") or "N/A"))
    info_table.add_row("Response Message", str(final_state.get("response_message") or "N/A"))

    # ── Audit Log Table ──────────────────────────────────────────
    audit_table = Table(
        title="Audit Log",
        box=box.ROUNDED,
        border_style="dim",
        show_lines=True,
        title_style="bold magenta",
        header_style="bold magenta",
    )
    audit_table.add_column("Step", style="cyan", min_width=25)
    audit_table.add_column("Result", style="white")

    for entry in final_state.get("audit_log", []):
        audit_table.add_row(
            str(entry.get("step", "—")),
            str(entry.get("result", "—"))
        )

    from rich.padding import Padding

    content = Padding(info_table, (0, 1))
    console.print()
    console.print(Panel(
        content,
        title=f"[bold]{emoji}  {case_title}[/bold]",
        border_style=border_color,
        expand=True,
        subtitle=f"[dim]Decision: {decision}[/dim]"
    ))
    console.print(audit_table)
    console.rule(style="dim")


async def run_case(graph, case_title: str, request: RefundRequest):
    config = {"configurable": {"thread_id": case_title}}
    initial_state = {"request": request, "audit_log": []}

    async for event in graph.astream(initial_state, config):
        pass

    state_info = await graph.aget_state(config)
    final_state = state_info.values
    print_result(case_title, final_state)
    return final_state


@pytest.fixture(scope="function")
async def graph():
    db_name = "test_checkpoints.db"
    # Clean up any leftover db file from previous runs
    if os.path.exists(db_name):
        try:
            os.remove(db_name)
        except Exception:
            pass

    async with AsyncSqliteSaver.from_conn_string(db_name) as checkpointer:
        compiled_graph = workflow.compile(checkpointer=checkpointer)
        yield compiled_graph

    if os.path.exists(db_name):
        try:
            os.remove(db_name)
        except Exception:
            pass


@pytest.fixture(scope="function")
async def db_conn():
    async with await get_db_conn() as db:
        # 1. Backup original delivery dates for orders 1, 4, 13
        async with db.execute("SELECT id, delivered_at FROM orders WHERE id IN (1, 4, 13)") as cursor:
            rows = await cursor.fetchall()
            original_delivery_dates = {row["id"]: row["delivered_at"] for row in rows}

        # 2. Backup original item status for order_items 16
        async with db.execute("SELECT id, item_status FROM order_items WHERE id = 16") as cursor:
            row = await cursor.fetchone()
            original_item_status = row["item_status"] if row else None

        # 3. Robust clean up of existing test/orphaned records to ensure a clean run
        await db.execute("DELETE FROM refund_decision WHERE refund_request_id IN (SELECT id FROM refund_request WHERE customer_id IN ('1', '4', '13', 1, 4, 13))")
        await db.execute("DELETE FROM refund_decision WHERE refund_request_id NOT IN (SELECT id FROM refund_request)")
        await db.execute("DELETE FROM fraud_history WHERE refund_request_id IN (SELECT id FROM refund_request WHERE customer_id IN ('1', '4', '13', 1, 4, 13))")
        await db.execute("DELETE FROM fraud_history WHERE refund_request_id NOT IN (SELECT id FROM refund_request)")
        await db.execute("DELETE FROM refund_request WHERE customer_id IN ('1', '4', '13', 1, 4, 13)")
        await db.commit()

        yield db

        # Teardown:
        # Restore order delivery dates
        for order_id, delivered_at in original_delivery_dates.items():
            await db.execute("UPDATE orders SET delivered_at = ? WHERE id = ?", (delivered_at, order_id))
        
        # Restore order item status
        if original_item_status is not None:
            await db.execute("UPDATE order_items SET item_status = ? WHERE id = 16", (original_item_status,))
            
        # Clean up any leftover test/orphaned entries
        await db.execute("DELETE FROM refund_decision WHERE refund_request_id IN (SELECT id FROM refund_request WHERE customer_id IN ('1', '4', '13', 1, 4, 13))")
        await db.execute("DELETE FROM refund_decision WHERE refund_request_id NOT IN (SELECT id FROM refund_request)")
        await db.execute("DELETE FROM fraud_history WHERE refund_request_id IN (SELECT id FROM refund_request WHERE customer_id IN ('1', '4', '13', 1, 4, 13))")
        await db.execute("DELETE FROM fraud_history WHERE refund_request_id NOT IN (SELECT id FROM refund_request)")
        await db.execute("DELETE FROM refund_request WHERE customer_id IN ('1', '4', '13', 1, 4, 13)")
        await db.execute("DELETE FROM refund_request WHERE reason = 'Mock reason'")
        await db.commit()


@pytest.fixture(autouse=True)
async def rate_limit_delay():
    yield
    # Sleep to avoid rate limiting with LLM calls
    await asyncio.sleep(8)


@pytest.mark.asyncio
async def test_case_1_auto_approved_refund(graph, db_conn):
    # Case 1: Auto-Approved Refund (Eligible, Low Fraud)
    recent_date = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    await db_conn.execute("UPDATE orders SET delivered_at = ? WHERE id = 13", (recent_date,))
    await db_conn.execute("UPDATE order_items SET item_status = 'delivered' WHERE id = 16")
    await db_conn.commit()

    request = RefundRequest(
        customer_id="13", order_id="13", order_item_id="16",
        reason="My SanDisk pen drive is not working at all. I would like a refund.",
        evidence_urls=[]
    )
    
    final_state = await run_case(graph, "1. Auto-Approved Refund (Eligible, Low Fraud)", request)
    
    assert final_state.get("decision") == "approve"
    assert final_state.get("is_eligible") is True
    assert final_state.get("refund_amount") == 1199.0
    assert final_state.get("fraud_score") == 0


@pytest.mark.asyncio
async def test_case_2_auto_rejected_refund_outside_window(graph, db_conn):
    # Case 2: Auto-Rejected Refund (Outside Return Window)
    old_date = (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m-%d %H:%M:%S")
    await db_conn.execute("UPDATE orders SET delivered_at = ? WHERE id = 13", (old_date,))
    await db_conn.commit()

    request = RefundRequest(
        customer_id="13", order_id="13", order_item_id="16",
        reason="The item is defective. Requesting refund.",
        evidence_urls=[]
    )
    
    final_state = await run_case(graph, "2. Auto-Rejected Refund (Outside Return Window)", request)
    
    assert final_state.get("decision") == "reject"
    assert final_state.get("is_eligible") is False


@pytest.mark.asyncio
async def test_case_3_human_review_escalated_refund(graph, db_conn):
    # Case 3: Human Review / Escalated Refund (No pause, direct pending info response)
    recent_date = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    await db_conn.execute("UPDATE orders SET delivered_at = ? WHERE id = 13", (recent_date,))
    
    # Insert 6 mock refund requests to trigger high refund frequency signals
    for _ in range(6):
        await db_conn.execute(
            "INSERT INTO refund_request (customer_id, order_item_id, reason, reason_category, requested_refund_amount) "
            "VALUES (13, 16, 'Mock reason', 'quality', 1199.00)"
        )
    await db_conn.commit()

    request = RefundRequest(
        customer_id="13", order_id="13", order_item_id="16",
        reason="The item is defective and does not work. Requesting refund.",
        evidence_urls=[]
    )
    
    final_state = await run_case(graph, "3. Human Review / Escalated Refund (No pause, direct pending info response)", request)
    
    assert final_state.get("decision") == "human_review"
    assert final_state.get("is_eligible") is True
    assert final_state.get("fraud_score") == 0.35
    assert "high_refund_frequency" in final_state.get("fraud_signals", [])


@pytest.mark.asyncio
async def test_case_4_non_returnable_product_category(graph, db_conn):
    # Case 4: Non-Returnable Product Category (Beauty Product)
    recent_date = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    await db_conn.execute("UPDATE orders SET delivered_at = ? WHERE id = 4", (recent_date,))
    await db_conn.commit()

    request = RefundRequest(
        customer_id="4", order_id="4", order_item_id="7",
        reason="I changed my mind. The seal is not broken.",
        evidence_urls=[]
    )
    
    final_state = await run_case(graph, "4. Non-Returnable Product Category (Beauty Product)", request)
    
    assert final_state.get("decision") == "reject"
    assert final_state.get("is_eligible") is False


@pytest.mark.asyncio
async def test_case_5_missing_invalid_order_id(graph, db_conn):
    # Case 5: Missing / Invalid Order ID
    request = RefundRequest(
        customer_id="13", order_id="99999", order_item_id="16",
        reason="I did not receive my item.",
        evidence_urls=[]
    )
    
    final_state = await run_case(graph, "5. Missing / Invalid Order ID", request)
    
    assert final_state.get("decision") == "reject"
    assert final_state.get("is_eligible") is False


@pytest.mark.asyncio
async def test_case_6_duplicate_refund_request(graph, db_conn):
    # Case 6: Duplicate Refund Request (Already Refunded)
    recent_date = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    await db_conn.execute("UPDATE orders SET delivered_at = ? WHERE id = 1", (recent_date,))
    await db_conn.commit()

    request = RefundRequest(
        customer_id="1", order_id="1", order_item_id="2",
        reason="The speaker is broken.",
        evidence_urls=[]
    )
    
    final_state = await run_case(graph, "6. Duplicate Refund Request (Already Refunded)", request)
    
    assert final_state.get("decision") == "reject"
    assert final_state.get("is_eligible") is False