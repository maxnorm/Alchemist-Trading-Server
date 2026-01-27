"""
Configuration management for FastAPI service
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings"""

    # Database
    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    db_host: str = Field(alias="DB_HOST")
    db_port: int = Field(alias="DB_PORT")
    db_user: str = Field(alias="DB_USER")
    db_password: str = Field(alias="DB_PASSWORD")
    db_name: str = Field(alias="DB_NAME")

    # MLflow
    mlflow_tracking_uri: str = Field(alias="MLFLOW_TRACKING_URI")

    # API
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    # API Versioning
    api_version: str = Field(default="v1", alias="API_VERSION")
    api_base_path: str = Field(default="/api", alias="API_BASE_PATH")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Kill switch file path (shared with trading server)
    kill_switch_file: str = Field(
        default="/app/logs/kill_switch.flag", alias="KILL_SWITCH_FILE"
    )

    # Public MT5 server coordinates for EA configuration
    mt5_server_public_host: Optional[str] = Field(
        default=None, alias="MT5_SERVER_PUBLIC_HOST"
    )
    mt5_server_public_port: Optional[int] = Field(
        default=None, alias="MT5_SERVER_PUBLIC_PORT"
    )

    # Trading Server URL for health checks
    trading_server_host: str = Field(default="server", alias="TRADING_SERVER_HOST")
    trading_server_port: int = Field(default=8080, alias="TRADING_SERVER_PORT")

    # Clerk Configuration
    clerk_secret_key: Optional[str] = Field(default=None, alias="CLERK_SECRET_KEY")
    clerk_publishable_key: Optional[str] = Field(
        default=None, alias="CLERK_PUBLISHABLE_KEY"
    )

    # Clerk User Seeding (for local development)
    clerk_seed_enabled: bool = Field(default=False, alias="CLERK_SEED_ENABLED")
    clerk_seed_email: str = Field(default="dev@localhost.com", alias="CLERK_SEED_EMAIL")
    clerk_seed_password: str = Field(default="dev123", alias="CLERK_SEED_PASSWORD")
    clerk_seed_roles: str = Field(default="admin,user", alias="CLERK_SEED_ROLES")

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields from environment (like SERVER_IP, SERVER_PORT)
    )

    @property
    def get_database_url(self) -> str:
        """Get database URL, constructing it if not provided"""
        if self.database_url:
            return self.database_url
        return f"postgresql+psycopg2://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def api_prefix(self) -> str:
        """Get the full API prefix (e.g., /api/v1)"""
        return f"{self.api_base_path}/{self.api_version}"

    @property
    def trading_server_url(self) -> str:
        """Get the trading server base URL"""
        return f"http://{self.trading_server_host}:{self.trading_server_port}"


settings = Settings()
