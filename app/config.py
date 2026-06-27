from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Real-Time Fraud Inference Service"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    MLFLOW_TRACKING_URI: str = "databricks"
    MLFLOW_MODEL_NAME: str = "fraud_detection_model"
    # Change this from "Production" to your Unity Catalog alias name (e.g., "champion")
    MLFLOW_MODEL_ALIAS: str = "champion" 

    @property
    def model_uri(self) -> str:
        """Dynamically generates a Unity Catalog compatible model URI using @ notation."""
        return f"models:/{self.MLFLOW_MODEL_NAME}@{self.MLFLOW_MODEL_ALIAS}"

settings = Settings()