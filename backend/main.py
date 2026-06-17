import sys
from pathlib import Path
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta

# Adjust Python path to allow running directly from workspace root
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent))

from backend.agents.graph import graph
from backend.agents.state import RefundRequest
from backend.agents.tools.db import cursor, conn

def print_result(case_title: str, final_state: dict):
    print("=" * 60)
    print(f"CASE: {case_title}")
    print("=" * 60)
    print(f"Final Decision:   {final_state.get('decision')}")
    print(f"Is Eligible:      {final_state.get('is_eligible')}")
    print(f"Eligibility Rsn:  {final_state.get('eligibility_reason')}")
    print(f"Policy Context:   {final_state.get('policy_context')}")
    print(f"Fraud Score:      {final_state.get('fraud_score')}")
    print(f"Fraud Signals:    {final_state.get('fraud_signals')}")
    print(f"Refund Amount:    {final_state.get('refund_amount')}")
    print(f"Response Msg:     {final_state.get('response_message')}")
    print("Audit Log Steps:")
    for entry in final_state.get("audit_log", []):
        step_name = entry.get('step')
        result_info = entry.get('result')
        print(f" - {step_name} -> {result_info}")
    print("-" * 60)
    print()

async def run_case(case_title: str, request: RefundRequest):
    config = {"configurable": {"thread_id": case_title}}
    initial_state = {
        "request": request,
        "audit_log": []
    }
    
    # Stream the graph execution to run all nodes
    async for event in graph.astream(initial_state, config):
        pass
    
    state_info = await graph.aget_state(config)
    final_state = state_info.values
    print_result(case_title, final_state)
    return final_state

async def main():
    print("Starting Refund Guard Agent Workflow Verification...\n")
    
    # Save the original state of the database so we can restore it at the end
    cursor.execute("SELECT id, delivered_at FROM orders")
    original_delivery_dates = {row["id"]: row["delivered_at"] for row in cursor.fetchall()}
    
    try:
        # Case 1: Auto-Approved Refund
        # Order 13, item 16. Delivered at a recent date.
        recent_date = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE orders SET delivered_at = ? WHERE id = 13", (recent_date,))
        cursor.execute("UPDATE order_items SET item_status = 'delivered' WHERE id = 16")
        conn.commit()
        
        request1 = RefundRequest(
            customer_id="13",
            order_id="13",
            order_item_id="16",
            reason="My SanDisk pen drive is not working at all. I would like a refund.",
            evidence_urls=[]
        )
        await run_case("1. Auto-Approved Refund (Eligible, Low Fraud)", request1)
        
        # Case 2: Auto-Rejected Refund (Outside Return Window)
        # Order 13, item 16. Delivered at an old date.
        old_date = (datetime.utcnow() - timedelta(days=100)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE orders SET delivered_at = ? WHERE id = 13", (old_date,))
        conn.commit()
        
        request2 = RefundRequest(
            customer_id="13",
            order_id="13",
            order_item_id="16",
            reason="The item is defective. Requesting refund.",
            evidence_urls=[]
        )
        await run_case("2. Auto-Rejected Refund (Outside Return Window)", request2)
        
        # Case 3: Human Review / Escalated Refund
        # Order 13, item 16. Recent delivery but customer has 6 recent refund requests.
        cursor.execute("UPDATE orders SET delivered_at = ? WHERE id = 13", (recent_date,))
        for i in range(6):
            cursor.execute(
                "INSERT INTO refund_request (customer_id, order_item_id, reason, reason_category, requested_refund_amount) "
                "VALUES (13, 16, 'Mock reason', 'quality', 1199.00)"
            )
        conn.commit()
        
        request3 = RefundRequest(
            customer_id="13",
            order_id="13",
            order_item_id="16",
            reason="The item has scratches all over. Requesting refund.",
            evidence_urls=[]
        )
        await run_case("3. Human Review / Escalated Refund (No pause, direct pending info response)", request3)
        
        # Clean up mock refund requests
        cursor.execute("DELETE FROM refund_request WHERE reason = 'Mock reason'")
        conn.commit()
        
        # Case 4: Edge Case - Non-Returnable Product Category
        # Order 4, item 7. Beauty & Personal Care category (non-returnable under policy section 3).
        cursor.execute("UPDATE orders SET delivered_at = ? WHERE id = 4", (recent_date,))
        conn.commit()
        
        request4 = RefundRequest(
            customer_id="4",
            order_id="4",
            order_item_id="7",
            reason="I changed my mind. The seal is not broken.",
            evidence_urls=[]
        )
        await run_case("4. Non-Returnable Product Category (Beauty Product)", request4)
        
        # Case 5: Edge Case - Missing Order ID
        # Invalid order ID 99999.
        request5 = RefundRequest(
            customer_id="13",
            order_id="99999",
            order_item_id="16",
            reason="I did not receive my item.",
            evidence_urls=[]
        )
        await run_case("5. Missing / Invalid Order ID", request5)
        
        # Case 6: Edge Case - Duplicate Refund Request
        # Order 1, item 2 (already has an approved refund decision).
        cursor.execute("UPDATE orders SET delivered_at = ? WHERE id = 1", (recent_date,))
        conn.commit()
        
        request6 = RefundRequest(
            customer_id="1",
            order_id="1",
            order_item_id="2",
            reason="The speaker is broken.",
            evidence_urls=[]
        )
        await run_case("6. Duplicate Refund Request (Already Refunded)", request6)
        
    finally:
        # Restore original delivery dates
        print("Restoring database state...")
        for order_id, delivered_at in original_delivery_dates.items():
            cursor.execute("UPDATE orders SET delivered_at = ? WHERE id = ?", (delivered_at, order_id))
        conn.commit()
        print("Database state restored successfully.")

if __name__ == "__main__":
    asyncio.run(main())
