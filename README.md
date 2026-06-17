# Refund Guard AI

Refund Guard is an intelligent, agentic refund decision system designed for quick-commerce and e-commerce platforms. Powered by **LangGraph** and **LangChain**, it automates eligibility checks, evaluates fraud risk, coordinates support queue escalations, and executes refund decisions securely.

---

## System Architecture

The application is structured into four functional layers:
1. **Presentation Layer**: Handles incoming API requests (FastAPI) and WebSocket events.
2. **Orchestration Layer**: Manages the multi-agent execution flow using a state-driven LangGraph pipeline.
3. **Agent Layer**: Hosts specialized agent nodes (Intent Classifier, Eligibility Auditor, Fraud Detector, and Response Generator) equipped with tool access.
4. **Data Layer**: Directs state transitions and data persistence via SQLite (for orders, refund requests, and audit logs) and local vector-retrieval for policy lookups.

---

## Agent Workflow (LangGraph State Machine)

The refund evaluation follows a deterministic, stateful workflow modeled in `backend/agents/graph.py`:

```mermaid
flowchart TD
    START([Start]) --> classify_intent[Classify Intent]
    classify_intent --> lookup_order[Lookup Order]
    
    lookup_order -->|Order Found| check_eligibility[Check Eligibility]
    lookup_order -->|Order Missing / Error| error[Error Handler]
    
    check_eligibility -->|Eligible| fraud_detection[Fraud Detection]
    check_eligibility -->|Not Eligible| generate_response[Generate Response]
    
    fraud_detection -->|Score < 0.3 / Approve| process_refund[Process Refund]
    fraud_detection -->|0.3 <= Score < 0.7 / Review| human_review[Human Review]
    fraud_detection -->|Score >= 0.7 / Reject| generate_response
    
    human_review --> generate_response
    process_refund --> generate_response
    
    generate_response --> END([End])
    error --> END
```

### Flow Node Descriptions:
- **Classify Intent**: Analyzes customer free-text query to extract the intent category and targets.
- **Lookup Order**: Retrieves order, item metadata, and delivery dates from the SQLite database.
- **Check Eligibility**: Cross-references order timelines and items against `refund-policy.md` utilizing RAG/grep tools.
- **Fraud Detection**: Computes a fraud score based on customer history, duplicate attempts, and evidence validation.
- **Process Refund**: Dynamically calculates the final credit amount and writes approved refund decisions.
- **Human Review**: Marks suspicious or boundary claims as `pending_review` in the database to be resolved by support agents.
- **Generate Response**: Constructs context-appropriate, customer-friendly status messages.

---

## Database Schema & ER Diagram

The database runs on SQLite (`mock.db`). The entity-relationship design supports full audit trails and historical analysis for fraud detection.

### Visual ER Diagram
Below is the visual database mapping of the entities:

![ER Diagram](ER_DIAGRAM.png)

### Logical ER Model (Mermaid Diagram)

```mermaid
erDiagram
    customer ||--o{ orders : "places"
    customer ||--o{ refund_request : "submits"
    products ||--o{ order_items : "contains"
    orders ||--|{ order_items : "has"
    order_items ||--o{ refund_request : "referenced_by"
    refund_request ||--o{ refund_decision : "resolves_into"
    refund_request ||--o{ fraud_history : "flagged_in"
    admin_user ||--o{ refund_decision : "decides"

    customer {
        integer id PK
        varchar full_name
        varchar email UK
        varchar phone_number
        text address
        varchar password_hash
        timestamp created_at
        timestamp updated_at
    }

    products {
        integer id PK
        varchar title
        text description
        varchar category
        varchar subcategory
        decimal price
        boolean is_returnable
        integer return_window_days
        timestamp created_at
        timestamp updated_at
    }

    orders {
        integer id PK
        timestamp ordered_at
        integer customer_id FK
        varchar status
        decimal total_amount
        text shipping_address
        varchar payment_method
        timestamp delivered_at
    }

    order_items {
        integer id PK
        integer order_id FK
        integer product_id FK
        integer quantity
        decimal unit_price
        decimal total_price
        varchar item_status
    }

    refund_request {
        integer id PK
        integer customer_id FK
        integer order_item_id FK
        text reason
        varchar reason_category
        varchar attachment_url
        varchar status
        decimal requested_refund_amount
        timestamp created_at
        timestamp resolved_at
    }

    refund_decision {
        integer id PK
        integer refund_request_id FK
        varchar decision
        integer decision_by FK
        decimal refunded_amount
        text review
        timestamp created_at
        timestamp decided_at
    }

    fraud_history {
        integer id PK
        integer refund_request_id FK
        decimal fraud_score
        text flagged_rules
        timestamp created_at
    }

    admin_user {
        integer id PK
        varchar name
        varchar email UK
        varchar password_hash
        varchar role
        timestamp last_login
        timestamp created_at
    }
```

---

## How to Set Up & Run Tests

### 1. Configure Environment
Copy `.env.example` to `.env` and fill in your OpenAI API credentials:
```bash
cp .env.example .env
```
Ensure `.env` contains:
```env
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_KEY=your-openai-api-key
OPENAI_VISION_MODEL=gpt-4o-mini
```

### 2. Activate Environment
Initialize and activate your virtual environment:
```bash
source .venv/bin/activate
```

### 3. Run the Verification Suite
Execute the main script to run through the test scenarios (Auto-Approve, Auto-Reject, Escalated Human Review, Non-Returnable Category, Missing Order ID, and Duplicate Request):
```bash
uv run backend/main.py
```
This runs the entire LangGraph workflow state machine, performs DB mocks, cleans up temporary request data, and displays structured step-by-step audit logs in the terminal.
