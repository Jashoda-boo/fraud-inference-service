from pydantic import BaseModel, Field

class TransactionRequest(BaseModel):
    transaction_id: str = Field(..., example="tx_987654")
    user_id: str = Field(..., example="usr_1102")
    amount: float = Field(..., gt=0, example=250.50)
    merchant_category: str = Field(..., example="retail")
    device_id: str = Field(..., example="dev_ios_99")

class FraudPredictionResponse(BaseModel):
    transaction_id: str
    user_id: str
    fraud_probability: float = Field(..., example=0.87)
    is_fraud: bool
    status: str