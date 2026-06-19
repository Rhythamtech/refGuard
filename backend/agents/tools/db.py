import aiosqlite
import pathlib
from datetime import datetime
from backend.agents.state import RefundRequest

DB_PATH = pathlib.Path(__file__).parent.parent.parent.parent / "mock.db"

class DBConnectionContext:
    def __init__(self, conn):
        self.conn = conn
    async def __aenter__(self):
        return self.conn
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.conn.close()

async def get_db_conn():
    conn = await aiosqlite.connect(DB_PATH, timeout=30.0)
    conn.row_factory = aiosqlite.Row
    await conn.create_function("now", 0, lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return DBConnectionContext(conn)


async def is_customer_fraud(customer_id: str) -> bool:
    query_string = """
        SELECT 
        COUNT(*) as fraud_count
        FROM fraud_history fh
        JOIN refund_request rr ON fh.refund_request_id = rr.id
        WHERE rr.customer_id = ? AND fh.fraud_score >= 0.95
    """
    async with await get_db_conn() as conn:
        async with conn.execute(query_string, (customer_id,)) as cursor:
            result = await cursor.fetchone()
            if result is None or result[0] == 0:
                return False
            return True

async def last_refunds(customer_id: str, days: int) -> int:
    query_string = """
        SELECT 
        COUNT(*) as refund_count
        FROM refund_request
        WHERE customer_id = ? AND created_at >= datetime('now', ?)
    """
    async with await get_db_conn() as conn:
        async with conn.execute(query_string, (customer_id, f"-{days} days")) as cursor:
            result = await cursor.fetchone()
            if result is None:
                return 0
            return result[0]

async def get_account_age_days(customer_id: str) -> int:
    query_string = """
        SELECT 
        (strftime('%s', 'now') - strftime('%s', created_at)) / 86400 as age_days
        FROM customer
        WHERE id = ?
    """
    async with await get_db_conn() as conn:
        async with conn.execute(query_string, (customer_id,)) as cursor:
            result = await cursor.fetchone()
            if result is None:
                return 0
            return result[0]

async def check_duplicate_refund(order_item_id: str) -> bool:
    query_string = """
        SELECT rd.decision FROM refund_decision rd
        JOIN  refund_request rr
        ON rd.refund_request_id = rr.id
        WHERE rr.order_item_id = ?
        """
    async with await get_db_conn() as conn:
        async with conn.execute(query_string, (order_item_id,)) as cursor:
            result = await cursor.fetchone()
            if result is None:
                return False
            if result["decision"] == "approved":
                return True
            return False

async def get_order_details(order_id: str):
    query_string = """
        SELECT 
            id as order_id, 
            customer_id, 
            total_amount, 
            delivered_at, 
            status, 
            payment_method
        FROM orders
        WHERE id = ?
    """
    query_item_string = """
        SELECT 
            oi.id as order_item_id,
            unit_price,
            quantity,
            item_status AS status,
            p.title AS product_name,
            p.category AS product_category,
            p.return_window_days AS return_window_days
        FROM order_items oi
        JOIN products p
        ON oi.product_id = p.id
        WHERE order_id = ?
    """
    async with await get_db_conn() as conn:
        async with conn.execute(query_string, (order_id,)) as cursor:
            result = await cursor.fetchone()
        if result is None:
            return {}
        async with conn.execute(query_item_string, (order_id,)) as cursor:
            result_items = await cursor.fetchall()
            
    result_items = [dict(row) for row in result_items]
    result_dict = dict(result)
    result_dict["items"] = result_items
    return result_dict

async def create_refund_request(order_id: str, customer_id: str, order_item_id: str, reason: str, intent: str):
    async with await get_db_conn() as conn:
        async with conn.execute("SELECT total_price FROM order_items WHERE id = ?", (order_item_id,)) as cursor:
            row = await cursor.fetchone()
        amount = row["total_price"] if row else 0.0

        query = """
            INSERT INTO refund_request (customer_id, order_item_id, reason, reason_category, requested_refund_amount)
            VALUES (?, ?, ?, ?, ?)
        """
        async with conn.execute(query, (customer_id, order_item_id, reason, intent, amount)) as cursor:
            lastrowid = cursor.lastrowid
        await conn.commit()
    return lastrowid

def format_audit_logs(audit_log: list | None) -> str:
    if not audit_log:
        return "No audit logs recorded."
    
    formatted_steps = []
    for entry in audit_log:
        step = entry.get("step", "unknown")
        result = entry.get("result", {})
        ts = entry.get("ts", "")
        time_str = ""
        if ts:
            try:
                time_str = f" @ {ts.split('T')[1][:8]}"
            except Exception:
                pass
        
        res_parts = []
        if isinstance(result, dict):
            for k, v in result.items():
                res_parts.append(f"{k}={v}")
            res_str = ", ".join(res_parts)
        else:
            res_str = str(result)
            
        formatted_steps.append(f"• {step.upper()}{time_str}: {res_str}")
        
    return "\n".join(formatted_steps)

async def create_review_queue_entry(
    refund_request_id: int,
    fraud_score: float,
    signals: list[str],
    audit_log: list | None = None,
) -> int:
    flagged_rules = ", ".join(signals) if signals else ""
    review_content = f"fraud_score={fraud_score:.2f} signals=[{flagged_rules}]"
    if audit_log:
        audit_str = format_audit_logs(audit_log)
        review_content += f"\n\nAI Audit Log:\n{audit_str}"
        
    async with await get_db_conn() as conn:
        async with conn.execute(
            """
            INSERT INTO refund_decision (refund_request_id, decision, review)
            VALUES (?, 'pending_review', ?)
            """,
            (refund_request_id, review_content),
        ) as cursor:
            lastrowid = cursor.lastrowid
        await conn.execute(
            """
            UPDATE refund_request
            SET status = 'escalated'
            WHERE id = ?
            """,
            (refund_request_id,),
        )
        await conn.commit()
    return lastrowid

async def resolve_review_decision(
    review_id: int,
    decision: str,
    decided_by: int,
) -> bool:
    async with await get_db_conn() as conn:
        async with conn.execute(
            """
            SELECT refund_request_id, rr.requested_refund_amount
            FROM refund_decision rd
            JOIN refund_request rr ON rd.refund_request_id = rr.id
            WHERE rd.id = ? AND rd.decision = 'pending_review'
            """,
            (review_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return False

        req_id = row["refund_request_id"]
        amount = float(row["requested_refund_amount"]) if decision == "approved" else 0.0
        review_text = f"Human Approved by Admin ID: {decided_by}" if decision == "approved" else f"Human Rejected by Admin ID: {decided_by}"

        await conn.execute(
            """
            UPDATE refund_decision
            SET decision = ?,
                decision_by = ?,
                refunded_amount = ?,
                review = ?,
                decided_at = datetime('now')
            WHERE id = ?
            """,
            (decision, decided_by, amount, review_text, review_id),
        )
        await conn.execute(
            """
            UPDATE refund_request
            SET status = ?,
                resolved_at = datetime('now')
            WHERE id = ?
            """,
            (decision, req_id),
        )
        await conn.commit()
        return True

async def save_refund_decision(
    refund_request_id: int,
    review: str,
    amount: float,
    decided_by: int | None = None,
    audit_log: list | None = None,
) -> int:
    final_review = review
    if audit_log:
        audit_str = format_audit_logs(audit_log)
        final_review = f"{review}\n\nAI Audit Log:\n{audit_str}" if review else f"AI Audit Log:\n{audit_str}"

    async with await get_db_conn() as conn:
        async with conn.execute(
            """
            INSERT INTO refund_decision (refund_request_id, decision, decision_by, refunded_amount, review, decided_at)
            VALUES (?, 'approved', ?, ?, ?, datetime('now'))
            """,
            (refund_request_id, decided_by, amount, final_review),
        ) as cursor:
            lastrowid = cursor.lastrowid
        await conn.execute(
            """
            UPDATE refund_request
            SET status = 'approved',
                resolved_at = datetime('now')
            WHERE id = ?
            """,
            (refund_request_id,),
        )
        await conn.commit()
    return lastrowid

async def save_refund_rejection(
    refund_request_id: int,
    review: str,
    decided_by: int | None = None,
    audit_log: list | None = None,
) -> int:
    final_review = review
    if audit_log:
        audit_str = format_audit_logs(audit_log)
        final_review = f"{review}\n\nAI Audit Log:\n{audit_str}" if review else f"AI Audit Log:\n{audit_str}"

    async with await get_db_conn() as conn:
        async with conn.execute(
            """
            INSERT INTO refund_decision (refund_request_id, decision, decision_by, refunded_amount, review, decided_at)
            VALUES (?, 'rejected', ?, 0.0, ?, datetime('now'))
            """,
            (refund_request_id, decided_by, final_review),
        ) as cursor:
            lastrowid = cursor.lastrowid
        await conn.execute(
            """
            UPDATE refund_request
            SET status = 'rejected',
                resolved_at = datetime('now')
            WHERE id = ?
            """,
            (refund_request_id,),
        )
        await conn.commit()
    return lastrowid

async def save_fraud_history(
    refund_request_id: int,
    fraud_score: float,
    flagged_rules: list[str],
) -> int:
    rules_str = ", ".join(flagged_rules) if flagged_rules else ""
    async with await get_db_conn() as conn:
        async with conn.execute(
            """
            INSERT INTO fraud_history (refund_request_id, fraud_score, flagged_rules, created_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (refund_request_id, fraud_score, rules_str),
        ) as cursor:
            lastrowid = cursor.lastrowid
        await conn.commit()
    return lastrowid

async def get_customer_by_email(email: str):
    async with await get_db_conn() as conn:
        async with conn.execute("SELECT * FROM customer WHERE email = ?", (email,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_admin_by_email(email: str):
    async with await get_db_conn() as conn:
        async with conn.execute("SELECT * FROM admin_user WHERE email = ?", (email,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_customer_profile(customer_id: str):
    async with await get_db_conn() as conn:
        async with conn.execute("SELECT id, full_name, email, phone_number, address, created_at FROM customer WHERE id = ?", (customer_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_customer_orders(customer_id: str):
    async with await get_db_conn() as conn:
        async with conn.execute("""
            SELECT o.id as order_id, o.ordered_at, o.status, o.total_amount, o.payment_method, o.delivered_at,
                   (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as item_count
            FROM orders o
            WHERE o.customer_id = ?
            ORDER BY o.ordered_at DESC
        """, (customer_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_customer_refund_history(customer_id: str):
    async with await get_db_conn() as conn:
        async with conn.execute("""
            SELECT rr.id, rr.order_item_id, rr.reason, rr.reason_category, rr.status, rr.requested_refund_amount, rr.created_at,
                   rd.decision, rd.refunded_amount, rd.review, rd.decided_at,
                   p.title as product_name
            FROM refund_request rr
            LEFT JOIN refund_decision rd ON rr.id = rd.refund_request_id
            JOIN order_items oi ON rr.order_item_id = oi.id
            JOIN products p ON oi.product_id = p.id
            WHERE rr.customer_id = ?
            ORDER BY rr.created_at DESC
        """, (customer_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_review_queue():
    async with await get_db_conn() as conn:
        async with conn.execute("""
            SELECT rd.id as review_id, rd.refund_request_id, rd.review, rd.created_at as review_created_at,
                   rr.customer_id, rr.order_item_id, rr.reason, rr.reason_category, rr.requested_refund_amount,
                   rr.created_at as request_created_at, c.full_name as customer_name
            FROM refund_decision rd
            JOIN refund_request rr ON rd.refund_request_id = rr.id
            JOIN customer c ON rr.customer_id = c.id
            WHERE rd.decision = 'pending_review'
            ORDER BY rd.created_at DESC
        """) as cursor:
            rows = await cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            review_str = d.get("review") or ""
            fraud_score = 0.5
            signals = []
            try:
                if "fraud_score=" in review_str:
                    score_part = review_str.split("fraud_score=")[1].split(" ")[0]
                    fraud_score = float(score_part)
                if "signals=[" in review_str:
                    sig_part = review_str.split("signals=[")[1].split("]")[0]
                    signals = [s.strip() for s in sig_part.split(",") if s.strip()]
            except Exception:
                pass
            d["fraud_score"] = fraud_score
            d["signals"] = signals
            result.append(d)
        return result

async def get_refund_logs(limit: int = 20, offset: int = 0):
    async with await get_db_conn() as conn:
        async with conn.execute("""
            SELECT rd.id, rd.refund_request_id, rd.decision, rd.refunded_amount, rd.review, rd.created_at, rd.decided_at,
                   rr.customer_id, rr.order_item_id, rr.reason, c.full_name as customer_name
            FROM refund_decision rd
            JOIN refund_request rr ON rd.refund_request_id = rr.id
            JOIN customer c ON rr.customer_id = c.id
            ORDER BY rd.created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_admin_stats():
    async with await get_db_conn() as conn:
        async with conn.execute("SELECT COUNT(*) FROM refund_decision WHERE decision != 'pending_review'") as cursor:
            total_processed = (await cursor.fetchone())[0] or 0
        async with conn.execute("SELECT COUNT(*) FROM refund_decision WHERE decision = 'approved'") as cursor:
            approved_count = (await cursor.fetchone())[0] or 0
        async with conn.execute("SELECT COUNT(*) FROM refund_decision WHERE decision = 'rejected'") as cursor:
            rejected_count = (await cursor.fetchone())[0] or 0
        async with conn.execute("SELECT COUNT(*) FROM refund_decision WHERE decision = 'pending_review'") as cursor:
            pending_count = (await cursor.fetchone())[0] or 0
        
        success_rate = 0.0
        if (approved_count + rejected_count) > 0:
            success_rate = (approved_count / (approved_count + rejected_count)) * 100.0
            
        async with conn.execute("""
            SELECT AVG(strftime('%s', decided_at) - strftime('%s', created_at)) 
            FROM refund_decision 
            WHERE decision != 'pending_review' AND decided_at IS NOT NULL AND created_at IS NOT NULL
        """) as cursor:
            avg_res = (await cursor.fetchone())[0]
        avg_resolution_seconds = float(avg_res) if avg_res is not None else 0.0
        
        if avg_resolution_seconds < 0:
            avg_resolution_seconds = 0.0

        return {
            "total_processed": total_processed,
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "pending_count": pending_count,
            "success_rate": round(success_rate, 1),
            "avg_resolution_seconds": round(avg_resolution_seconds, 1)
        }

async def get_all_customers_summary():
    async with await get_db_conn() as conn:
        async with conn.execute("""
            SELECT c.id, c.full_name, c.email, c.created_at,
                   (SELECT COUNT(*) FROM refund_request WHERE customer_id = c.id) as refund_requests_count,
                   (SELECT SUM(refunded_amount) FROM refund_decision rd 
                    JOIN refund_request rr ON rd.refund_request_id = rr.id 
                    WHERE rr.customer_id = c.id AND rd.decision = 'approved') as total_refunded_amount
            FROM customer c
            ORDER BY c.id ASC
        """) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def clear_all_logs():
    async with await get_db_conn() as conn:
        await conn.execute("DELETE FROM refund_decision WHERE decision != 'pending_review'")
        await conn.execute("""
            DELETE FROM refund_request 
            WHERE id NOT IN (
                SELECT refund_request_id 
                FROM refund_decision 
                WHERE decision = 'pending_review'
            )
        """)
        await conn.execute("""
            DELETE FROM fraud_history
            WHERE refund_request_id NOT IN (
                SELECT id FROM refund_request
            )
        """)
        await conn.commit()
        return True