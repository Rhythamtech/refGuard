import sys
from pathlib import Path
import asyncio
from datetime import datetime, timedelta, timezone

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
    if "approved" in decision:
        return "green", "✅"
    elif "rejected" in decision or "invalid" in decision:
        return "red", "❌"
    elif "review" in decision or "pending" in decision or "escalat" in decision:
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

    # ── Combine into a Panel ─────────────────────────────────────
    from rich.columns import Columns
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

    with console.status(f"[bold cyan]Running: {case_title}...[/bold cyan]"):
        async for event in graph.astream(initial_state, config):
            pass

    state_info = await graph.aget_state(config)
    final_state = state_info.values
    print_result(case_title, final_state)
    return final_state


async def main():
    console.rule("[bold blue]🚀 Refund Guard Agent Workflow Verification[/bold blue]")
    console.print()

    db_path = Path(__file__).parent.parent / "mock.db"

    async with AsyncSqliteSaver.from_conn_string("checkpoints.db") as checkpointer:
        graph = workflow.compile(checkpointer=checkpointer)

        async with await get_db_conn() as db:
            async with db.execute("SELECT id, delivered_at FROM orders") as cursor:
                rows = await cursor.fetchall()
                original_delivery_dates = {row["id"]: row["delivered_at"] for row in rows}

            try:
                # Case 1: Auto-Approved Refund
                recent_date = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
                await db.execute("UPDATE orders SET delivered_at = ? WHERE id = 13", (recent_date,))
                await db.execute("UPDATE order_items SET item_status = 'delivered' WHERE id = 16")
                await db.commit()
                request1 = RefundRequest(
                    customer_id="13", order_id="13", order_item_id="16",
                    reason="My SanDisk pen drive is not working at all. I would like a refund.",
                    evidence_urls=[]
                )
                await run_case(graph, "1. Auto-Approved Refund (Eligible, Low Fraud)", request1)

                # Case 2: Auto-Rejected Refund (Outside Return Window)
                old_date = (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m-%d %H:%M:%S")
                await db.execute("UPDATE orders SET delivered_at = ? WHERE id = 13", (old_date,))
                await db.commit()
                request2 = RefundRequest(
                    customer_id="13", order_id="13", order_item_id="16",
                    reason="The item is defective. Requesting refund.",
                    evidence_urls=[]
                )
                await run_case(graph, "2. Auto-Rejected Refund (Outside Return Window)", request2)

                # Case 3: Human Review / Escalated Refund
                await db.execute("UPDATE orders SET delivered_at = ? WHERE id = 13", (recent_date,))
                for i in range(6):
                    await db.execute(
                        "INSERT INTO refund_request (customer_id, order_item_id, reason, reason_category, requested_refund_amount) "
                        "VALUES (13, 16, 'Mock reason', 'quality', 1199.00)"
                    )
                await db.commit()
                request3 = RefundRequest(
                    customer_id="13", order_id="13", order_item_id="16",
                    reason="The item has scratches all over. Requesting refund.",
                    evidence_urls=[]
                )
                await run_case(graph, "3. Human Review / Escalated Refund (No pause, direct pending info response)", request3)
                await db.execute("DELETE FROM refund_request WHERE reason = 'Mock reason'")
                await db.commit()

                # Case 4: Non-Returnable Product Category
                await db.execute("UPDATE orders SET delivered_at = ? WHERE id = 4", (recent_date,))
                await db.commit()
                request4 = RefundRequest(
                    customer_id="4", order_id="4", order_item_id="7",
                    reason="I changed my mind. The seal is not broken.",
                    evidence_urls=[]
                )
                await run_case(graph, "4. Non-Returnable Product Category (Beauty Product)", request4)

                # Case 5: Missing / Invalid Order ID
                request5 = RefundRequest(
                    customer_id="13", order_id="99999", order_item_id="16",
                    reason="I did not receive my item.",
                    evidence_urls=[]
                )
                await run_case(graph, "5. Missing / Invalid Order ID", request5)

                # Case 6: Duplicate Refund Request
                await db.execute("UPDATE orders SET delivered_at = ? WHERE id = 1", (recent_date,))
                await db.commit()
                request6 = RefundRequest(
                    customer_id="1", order_id="1", order_item_id="2",
                    reason="The speaker is broken.",
                    evidence_urls=[]
                )
                await run_case(graph, "6. Duplicate Refund Request (Already Refunded)", request6)

            finally:
                console.print()
                console.rule("[bold yellow]🔄 Restoring Database State...[/bold yellow]")
                for order_id, delivered_at in original_delivery_dates.items():
                    await db.execute("UPDATE orders SET delivered_at = ? WHERE id = ?", (delivered_at, order_id))
                await db.commit()
                console.print("[bold green]✔ Database state restored successfully.[/bold green]")
                console.rule()


if __name__ == "__main__":
    asyncio.run(main())