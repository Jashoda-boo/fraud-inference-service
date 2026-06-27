import pandas as pd
from app.schemas import TransactionRequest
from app.agents import fraud_agent_workflow  # Import our compiled graph agent team

# ... keep your get_model() function exactly the same ...

def predict_fraud(request: TransactionRequest) -> dict:
    # 1. Standard model inference thresholding
    fraud_prob = 0.85 if request.amount > 1000 else 0.12
    is_fraud = fraud_prob >= 0.75
    
    status = "APPROVED"
    
    # 2. Trigger LangGraph Agent Investigation if flagged!
    if is_fraud:
        status = "FLAGGED_FOR_AUDIT"
        
        # Initialize the state dictionary to feed into the graph network
        initial_state = {
            "transaction_id": request.transaction_id,
            "user_id": request.user_id,
            "fraud_probability": fraud_prob,
            "collected_features": {},
            "risk_notes": [],
            "final_decision": "",
            "audit_log_draft": ""
        }
        
        # Run the multi-agent crew synchronously
        final_output = fraud_agent_workflow.invoke(initial_state)
        
        # Print out the autonomous findings to the console log
        print("\n=== Agent Investigation Complete ===")
        print(f"Final Decision: {final_output['final_decision']}")
        print(f"Generated Audit Trail: {final_output['audit_log_draft']}\n")
        
        # Override standard status with the agent's granular decision output
        status = final_output['final_decision']

    return {
        "transaction_id": request.transaction_id,
        "user_id": request.user_id,
        "fraud_probability": fraud_prob,
        "is_fraud": is_fraud,
        "status": status
    }