from setup_database import SqliteOrderDB

conn, cursor = SqliteOrderDB().connect_to_db()

def is_customer_fraud(customer_id: str) -> bool:
    """
    Returns True if the customer has been marked as fraud, False otherwise.
    """
    query_string = """
        SELECT 
        COUNT(*) as fraud_count
        FROM fraud_history fh
        JOIN refund_request rr ON fh.refund_request_id = rr.id
        WHERE rr.customer_id = ?
    """

    cursor.execute(query_string, (customer_id,))
    result = cursor.fetchone()

    if result is None:
        return False
    
    return True


def last_refunds(customer_id: str, days: int) -> int:
    """
    Returns the number of refunds the customer has received in the last n days.
    """
    query_string = """
        SELECT 
        COUNT(*) as refund_count
        FROM refund_request
        WHERE customer_id = ? AND created_at >= datetime('now', ?)
    """

    cursor.execute(query_string, (customer_id, f"-{days} days"))
    result = cursor.fetchone()

    if result is None:
        return 0
    
    return result[0]


def get_account_age_days(customer_id: str) -> int:
    """
    Returns the age of the customer's account in days.
    """

    query_string = """
        SELECT 
        (strftime('%s', 'now') - strftime('%s', created_at)) / 86400 as age_days
        FROM customer
        WHERE id = ?
    """
    
    cursor.execute(query_string, (customer_id,))
    result = cursor.fetchone()
    
    if result is None:
        return 0
    
    return result[0]

def check_duplicate_refund(order_item_id: str) -> bool:
    """
    Returns True if the order item has already been refunded, False otherwise.
    """
    query_string = """
        SELECT rd.decision FROM refund_decision rd
        JOIN  refund_request rr
        ON rd.refund_request_id = rr.id
        WHERE rr.order_item_id = ?
        """
    cursor.execute(query_string, (order_item_id,))
    result = cursor.fetchone()

    if result is None:
        return False
    if result["decision"] == "approved":
        return True
    
    return False   

def get_order_details(order_id: str):

    """
    Returns a dictionary with the following structure:
    {
        "order_id": str,
        "customer_id": str,
        "items": List[dict],
        "total_amount": Decimal,
        "delivered_at": Optional[datetime],
        "status": str,
        "payment_method": str
    }
    """
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
            id as order_item_id,
            unit_price,
            quantity,
            item_status AS status,
            p.name AS product_name,
            p.category AS product_category,
            p.return_window_days AS return_window_days
        FROM order_items oi
        JOIN products p
        ON oi.product_id = p.id
        WHERE order_id = ?
    """

    cursor.execute(query_string, (order_id,))
    result = cursor.fetchone()

    cursor.execute(query_item_string, (order_id,))
    result_items = cursor.fetchall()

    # Convert result to list of dictionaries
    result_items = [dict(row) for row in result_items]

    if result is None:
        return 0
    
    # Convert result to dictionary
    result_dict = dict(result)
    result_dict["items"] = result_items
    
    return result_dict