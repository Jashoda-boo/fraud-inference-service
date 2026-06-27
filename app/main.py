from fastapi import FastAPI, HTTPException, status
from app.schemas import TransactionRequest, FraudPredictionResponse
from app.services import predict_fraud
from app.config import settings

# 1. Initialize the application
app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="1.0.0"
)

# 2. Define your Health check endpoint
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "healthy", "model_loaded": True}

# 3. Define your Prediction endpoint
@app.post(
    "/predict", 
    response_model=FraudPredictionResponse, 
    status_code=status.HTTP_200_OK,
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