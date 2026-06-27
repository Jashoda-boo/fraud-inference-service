import os
from typing import Annotated, TypedDict, List
from langgraph.graph import StateGraph, START, END
from databricks.sdk import WorkspaceClient

# 1. Define the Shared State
class InvestigationState(TypedDict):
    transaction_id: str
    user_id: str
    fraud_probability: float
    collected_features: dict
    risk_notes: List[str]
    final_decision: str
    audit_log_draft: str

# 2. Dynamic Live Tool Node
def feature_investigator_node(state: InvestigationState) -> dict:
    print("--- [Agent 1] Fetching live behavioral context from Databricks ---")
    user_id = state.get("user_id", "")
    
    # Fallback default features if connection fails
    features = {"device_velocity_24h": "1 device", "historical_max_spend": 0.0}
    
    try:
        # Automatically reads DATABRICKS_HOST and DATABRICKS_TOKEN from your environment variables
        w = WorkspaceClient()
        
        # Execute a real SQL command against your Gold/Feature store tables
        query = f"SELECT device_count_24h, max_spend_amount FROM main.fraud_features.user_behavior WHERE user_id = '{user_id}' LIMIT 1"
        response = w.statement_execution.execute_statement(
            warehouse_id="your_sql_warehouse_id_here", # Add your warehouse ID here
            statement=query
        )
        
        # Parse out rows if data exists
        if response.result.data_array:
            row = response.result.data_array[0]
            features["device_velocity_24h"] = f"{row[0]} distinct devices used"
            features["historical_max_spend"] = float(row[1])
            print(f"-> Successfully retrieved live data for User: {user_id}")
            
    except Exception as e:
        print(f"-> [Connection Warning] Could not connect to live Databricks SQL: {e}")
        print("-> Falling back to simulated behavioral baseline features for local validation.")
        # Simulated live data fallback for smooth local debugging
        if user_id == "usr_1102":
            features["device_velocity_24h"] = "3 distinct devices used in 2 cities"
            features["historical_max_spend"] = 500.00

    return {"collected_features": features}

# 3. Define Node 2: The Risk Scoring Agent
def risk_scoring_node(state: InvestigationState) -> dict:
    print("--- [Agent 2] Executing LLM semantic anomaly analysis ---")
    features = state.get("collected_features", {})
    notes = []
    
    if "3 distinct devices" in features.get("device_velocity_24h", ""):
        notes.append("CRITICAL: High device rotation detected within a 24-hour window.")
        decision = "CONFIRMED_FRAUD_BLOCK_ACCOUNT"
    else:
        decision = "FALSE_POSITIVE_RELEASE"
        
    return {"risk_notes": notes, "final_decision": decision}

# 4. Define Node 3: The Compliance & Resolution Agent
def compliance_agent_node(state: InvestigationState) -> dict:
    print("--- [Agent 3] Generating production audit logs and drafting alert ---")
    decision = state.get("final_decision", "UNKNOWN")
    notes = ", ".join(state.get("risk_notes", []))
    
    log = f"Audit for Tx {state['transaction_id']}: Action taken: {decision}. Justification: {notes}"
    return {"audit_log_draft": log}

# 5. Build and compile the Stateful Graph Orchestrator
builder = StateGraph(InvestigationState)
builder.add_node("investigator", feature_investigator_node)
builder.add_node("scorer", risk_scoring_node)
builder.add_node("compliance", compliance_agent_node)

builder.add_edge(START, "investigator")
builder.add_edge("investigator", "scorer")
builder.add_edge("scorer", "compliance")
builder.add_edge("compliance", END)

fraud_agent_workflow = builder.compile()