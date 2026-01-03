"""
Configuration management for FastAPI service
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    database_url: Optional[str] = Field(
        default=None,
        alias="DATABASE_URL"
    )
    db_host: str = Field(default="mariadb", alias="DB_HOST")
    db_port: int = Field(default=3306, alias="DB_PORT")
    db_user: str = Field(default="forex_user", alias="DB_USER")
    db_password: str = Field(default="forex_password", alias="DB_PASSWORD")
    db_name: str = Field(default="db_forex", alias="DB_NAME")
    
    # MLflow
    mlflow_tracking_uri: str = Field(
        default="http://mlflow:5000",
        alias="MLFLOW_TRACKING_URI"
    )
    
    # API
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # Kill switch file path (shared with trading server)
    kill_switch_file: str = Field(
        default="/app/logs/kill_switch.flag",
        alias="KILL_SWITCH_FILE"
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields from environment (like SERVER_IP, SERVER_PORT)
    )
    
    @property
    def get_database_url(self) -> str:
        """Get database URL, constructing it if not provided"""
        if self.database_url:
            return self.database_url
        return f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()
