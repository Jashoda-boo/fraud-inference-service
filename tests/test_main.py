import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.agents import fraud_agent_workflow

# Initialize the simulated FastAPI test client cleanly
client = TestClient(app)

# --- Test 1: FastAPI Endpoint Validation ---
def test_predict_fraud_high_risk():
    """Ensure high-risk scores trigger the LangGraph agent mesh successfully."""
    payload = {
        "transaction_id": "tx_999",
        "user_id": "usr_1102",  # Triggers the mock fallback inside our app logic
        "amount": 1500.00,
        "merchant_category": "retail",
        "device_id": "dev_ios_99"
    }
    
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["transaction_id"] == "tx_999"
    assert data["is_fraud"] is True
    assert "status" in data

# --- Test 2: Isolated LangGraph Workflow State Validation ---
def test_langgraph_workflow_execution():
    """Ensure the state updates correctly across all 3 agent graph nodes."""
    initial_state = {
        "transaction_id": "tx_test_123",
        "user_id": "usr_1102",
        "fraud_probability": 0.85,
        "collected_features": {},
        "risk_notes": [],
        "final_decision": "",
        "audit_log_draft": ""
    }
    
    # Run the compiled graph manually with a mock initial state payload
    output_state = fraud_agent_workflow.invoke(initial_state)
    
    # Verify Agent 1 collected behavioral context features
    assert "device_velocity_24h" in output_state["collected_features"]
    
    # Verify Agent 2 rendered a forensic risk decision based on the context
    assert output_state["final_decision"] in ["CONFIRMED_FRAUD_BLOCK_ACCOUNT", "FALSE_POSITIVE_RELEASE"]
    
    # Verify Agent 3 properly drafted a compliance audit logging string
    assert "Audit for Tx" in output_state["audit_log_draft"]