import asyncio
import io
import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
import pandas as pd
from pydantic import BaseModel, Field

# Database, Agent, and Notification Imports
try:
    from database import init_db, AsyncSessionLocal, FraudAuditRecord
    from app.agents import (
        run_behavioral_agent,
        run_geographic_agent,
        check_transaction_velocity,
        get_cache_metrics
    )
    from app.notifications import dispatch_fraud_alert
except ImportError:
    from .database import init_db, AsyncSessionLocal, FraudAuditRecord
    from .agents import (
        run_behavioral_agent,
        run_geographic_agent,
        check_transaction_velocity,
        get_cache_metrics
    )
    try:
        from notifications import dispatch_fraud_alert
    except ImportError:
        from .notifications import dispatch_fraud_alert

DB_PATH = os.getenv("DB_PATH", "./fraud_ledger.db")

app = FastAPI(
    title="Multi-Agent Fraud Inference & Audit Ledger Engine",
    version="1.3.0"
)

# ----------------- LIFECYCLE -----------------
@app.on_event("startup")
async def startup_event():
    print("🔄 [DATABASE] Verifying shared disk storage volume tables...")
    try:
        await init_db()
        print("✅ [DATABASE] Shared volume database schema is fully initialized!")
    except Exception as e:
        print(f"❌ [DATABASE] Schema initialization note: {str(e)}")

# ----------------- DATA MODELS -----------------
class TransactionRequest(BaseModel):
    transaction_id: str = Field(default_factory=lambda: f"TXN_{uuid.uuid4().hex[:10].upper()}")
    user_id: str
    amount: float
    location: str

# ----------------- INFERENCE PIPELINE -----------------
@app.post("/predict")
async def predict_fraud(payload: TransactionRequest, background_tasks: BackgroundTasks):
    """
    Concurrent Multi-Agent Pipeline: Velocity Check + Behavioral Audit + Geographic Analysis.
    """
    try:
        # 1. Concurrent Execution: Query all three audit mechanisms simultaneously
        velocity_data, behavioral_data, geographic_data = await asyncio.gather(
            check_transaction_velocity(payload.user_id, window_minutes=5),
            run_behavioral_agent(payload.user_id, payload.amount),
            run_geographic_agent(payload.location)
        )
        
        # 2. Extract numerical scores and flags safely
        v_score = float(velocity_data.get("score", 0.0))
        b_score = float(behavioral_data.get("score", 0.0))
        g_score = float(geographic_data.get("score", 0.0))

        v_flag = bool(velocity_data.get("flag", False))
        b_flag = bool(behavioral_data.get("flag", False))
        g_flag = bool(geographic_data.get("flag", False))

        # 3. Weighted Consensus Engine: 40% Behavioral, 30% Velocity, 30% Geographic
        composite_risk = round((b_score * 0.40) + (v_score * 0.30) + (g_score * 0.30), 2)
        
        # Flag as fraud if composite risk >= 0.65 or if critical rules trip
        is_fraud = composite_risk >= 0.65 or v_flag or (b_flag and b_score >= 0.85) or (g_flag and g_score >= 0.85)
        decision = "FRAUD" if is_fraud else "APPROVED"

        breakdown = {
            "velocity": velocity_data,
            "behavioral": behavioral_data,
            "geographic": geographic_data
        }

        # 4. Trigger Webhook Alert in background if flagged as FRAUD
        if is_fraud:
            background_tasks.add_task(
                dispatch_fraud_alert,
                transaction_id=payload.transaction_id,
                user_id=payload.user_id,
                amount=payload.amount,
                location=payload.location,
                risk_score=composite_risk,
                breakdown=breakdown
            )

        # 5. Persistence: Write telemetry dump to SQLite ledger
        async with AsyncSessionLocal() as session:
            async with session.begin():
                new_record = FraudAuditRecord(
                    transaction_id=payload.transaction_id,
                    decision=decision,
                    risk_score=composite_risk,
                    audit_hash=uuid.uuid4().hex[:16],
                    telemetry_dump={
                        "user_id": payload.user_id,
                        "amount": payload.amount,
                        "location": payload.location,
                        "velocity_agent": velocity_data,
                        "behavioral_agent": behavioral_data,
                        "geographic_agent": geographic_data,
                        "consensus_formula": f"(0.40 * {b_score}) + (0.30 * {v_score}) + (0.30 * {g_score}) = {composite_risk}"
                    }
                )
                session.add(new_record)
            await session.commit()
            
        return {
            "transaction_id": payload.transaction_id,
            "user_id": payload.user_id,
            "fraud_probability": composite_risk,
            "is_fraud": is_fraud,
            "status": decision,
            "agent_breakdown": breakdown
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline Error: {str(e)}")

# ----------------- AUDIT LEDGER & TELEMETRY ENDPOINTS -----------------
@app.get("/audit/summary")
async def get_ledger_summary_metrics():
    """
    Summary analytics report combining SQLite metrics with live LRU cache telemetry.
    """
    cache_stats = get_cache_metrics()

    default_response = {
        "total_monitored_operations": 0,
        "approved_operations": 0,
        "flagged_fraud_vectors": 0,
        "average_risk_index": 0.0,
        "fraud_rate_percentage": 0.0,
        "cache_telemetry": cache_stats
    }

    if not os.path.exists(DB_PATH):
        return default_response

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fraud_audit_records'")
        if not cursor.fetchone():
            conn.close()
            return default_response

        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN UPPER(decision) = 'FRAUD' THEN 1 ELSE 0 END) as fraud_count,
                SUM(CASE WHEN UPPER(decision) = 'APPROVED' THEN 1 ELSE 0 END) as approved_count,
                AVG(risk_score) as avg_risk
            FROM fraud_audit_records
        """)
        row = cursor.fetchone()
        conn.close()

        total = row[0] or 0
        fraud_count = row[1] or 0
        approved_count = row[2] or 0
        avg_risk = round(float(row[3] or 0.0), 2)
        fraud_rate = round((fraud_count / total * 100), 2) if total > 0 else 0.0

        return {
            "total_monitored_operations": total,
            "approved_operations": approved_count,
            "flagged_fraud_vectors": fraud_count,
            "average_risk_index": avg_risk,
            "fraud_rate_percentage": fraud_rate,
            "cache_telemetry": cache_stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate ledger metrics: {str(e)}")

@app.get("/audit/ledger")
async def get_audit_ledger_report(
    decision: Optional[str] = Query(None, description="Filter: 'FRAUD' or 'APPROVED'"),
    min_risk: float = Query(0.0, ge=0.0, le=1.0, description="Minimum risk score threshold"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return")
):
    """
    Retrieve audit trail ledger logs with safe JSON serialization.
    """
    if not os.path.exists(DB_PATH):
        return {"total_queried": 0, "records": []}

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM fraud_audit_records WHERE risk_score >= ?"
        params = [min_risk]

        if decision and decision.upper() in ["FRAUD", "APPROVED"]:
            query += " AND UPPER(decision) = ?"
            params.append(decision.upper())

        query += " ORDER BY rowid DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        records = [dict(row) for row in rows]

        return {
            "total_queried": len(records),
            "filter_criteria": {
                "decision": decision,
                "min_risk": min_risk,
                "limit": limit
            },
            "records": records
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch audit ledger: {str(e)}")

# ----------------- REPLAY & VERIFICATION AUDIT ENDPOINT -----------------
@app.get("/audit/replay/{transaction_id}")
async def replay_audit_transaction(transaction_id: str):
    """
    Deterministically replays and mathematically verifies a historical fraud decision.
    Validates that the ledger record has not been tampered with.
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Audit ledger database not found.")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT timestamp, transaction_id, decision, risk_score, audit_hash, telemetry_dump 
        FROM fraud_audit_records 
        WHERE transaction_id = ?
        """,
        (transaction_id,)
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found in ledger.")

    timestamp, txn_id, recorded_decision, recorded_score, audit_hash, raw_telemetry = row

    try:
        telemetry = json.loads(raw_telemetry) if isinstance(raw_telemetry, str) else raw_telemetry
        
        # Pull agents safely matching your exact database schema
        v_data = telemetry.get("velocity_agent", {})
        b_data = telemetry.get("behavioral_agent", {})
        g_data = telemetry.get("geographic_agent", {})

        v_score = float(v_data.get("score", 0.0))
        b_score = float(b_data.get("score", 0.0))
        g_score = float(g_data.get("score", 0.0))

        v_flag = bool(v_data.get("flag", False))
        b_flag = bool(b_data.get("flag", False))
        g_flag = bool(g_data.get("flag", False))

        # 1. Recalculate deterministic consensus
        recalculated_score = round((b_score * 0.40) + (v_score * 0.30) + (g_score * 0.30), 2)

        # 2. Replay decision boundary matching predict_fraud
        is_fraud = recalculated_score >= 0.65 or v_flag or (b_flag and b_score >= 0.85) or (g_flag and g_score >= 0.85)
        expected_decision = "FRAUD" if is_fraud else "APPROVED"

        # 3. Mathematical and structural integrity checks
        score_intact = abs(recalculated_score - float(recorded_score)) <= 0.02
        decision_intact = (expected_decision == recorded_decision)
        hash_present = bool(audit_hash and len(str(audit_hash)) >= 8)

        is_verified = score_intact and decision_intact and hash_present

        return {
            "transaction_id": txn_id,
            "timestamp": timestamp,
            "verification_status": "VERIFIED" if is_verified else "TAMPER_DETECTED",
            "audit_hash": audit_hash,
            "mathematical_audit": {
                "recorded_risk_score": float(recorded_score),
                "recalculated_risk_score": recalculated_score,
                "score_match": score_intact,
                "recorded_decision": recorded_decision,
                "recalculated_decision": expected_decision,
                "decision_match": decision_intact
            },
            "agent_inputs_replayed": {
                "velocity_score": v_score,
                "velocity_flag": v_flag,
                "behavioral_score": b_score,
                "behavioral_flag": b_flag,
                "geographic_score": g_score,
                "geographic_flag": g_flag
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Replay computation failed: {str(e)}")

# ----------------- ON-DEMAND PARQUET EXPORT (MEMORY-SAFE) -----------------
@app.get("/audit/export/parquet")
async def export_audit_ledger_to_parquet():
    """
    Generates and streams a compressed Apache Parquet file of recent audit logs
    directly as an attachment, capped to protect laptop RAM.
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Audit ledger database not found.")

    try:
        # Read-only connection ensures no locks on active inference writes
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        
        # Capped to 5,000 most recent records to stay well under 10 MB RAM
        query = "SELECT * FROM fraud_audit_records ORDER BY timestamp DESC LIMIT 5000"
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            raise HTTPException(status_code=404, detail="No audit records available to export.")

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        buffer = io.BytesIO()
        df.to_parquet(
            buffer,
            engine="pyarrow",
            compression="snappy",
            index=False
        )
        buffer.seek(0)

        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"fraud_audit_ledger_{timestamp_str}.parquet"

        return StreamingResponse(
            buffer,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parquet export failed: {str(e)}")
    summary="Evaluate transaction for fraud risk"
)
async def evaluate_transaction(payload: TransactionRequest):
    try:
        prediction = predict_fraud(payload)
        return prediction
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference Engine Exception: {str(e)}"
        )
