__init__.py

import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # API App Settings
    APP_NAME: str = "Real-Time Fraud Inference Service"
    ENVIRONMENT: str = "development"  # development, staging, production
    DEBUG: bool = True

    # MLflow Model Registry Configuration
    # If using Databricks managed MLflow, this is usually 'databricks'
    MLFLOW_TRACKING_URI: str = "databricks"
    # Name of your registered model in the MLflow Registry
    MLFLOW_MODEL_NAME: str = "fraud_detection_model"
    # Stage or version to pull (e.g., 'Production', 'Staging', or specific version '1')
    MLFLOW_MODEL_STAGE: str = "Production"

    # Databricks / Feature Store Credentials
    # Pydantic will automatically look for these exact environment variables
    DATABRICKS_HOST: str = "https://your-databricks-instance.cloud.databricks.com"
    DATABRICKS_TOKEN: str = "dapi_mock_token_for_local_dev"

    # System configuration to handle local or containerized environments
    model_config = SettingsConfigDict(
        env_file=".env",           # Automatically parses a .env file if it exists
        env_file_encoding="utf-8",
        extra="ignore"             # Ignores extra environment variables not defined here
    )

    @property
    def model_uri(self) -> str:
        """Dynamically generates the MLflow model URI string."""
        return f"models:/{self.MLFLOW_MODEL_NAME}/{self.MLFLOW_MODEL_STAGE}"

# Instantiate the settings object to be imported across the app
settings = Settings()