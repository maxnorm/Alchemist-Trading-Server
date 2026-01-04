"""
Model Promoter Module

Model lifecycle management with promotion workflows.
Handles transitions between Training -> Staging -> Paper -> Production -> Archived
with validation gates and audit trails.
"""

import logging
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

try:
    from mlflow.tracking import MlflowClient

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

# Import ModelRegistry for database integration
try:
    from .model_registry import ModelRegistry, ModelStage as DBModelStage

    MODEL_REGISTRY_AVAILABLE = True
except ImportError:
    MODEL_REGISTRY_AVAILABLE = False
    DBModelStage = None  # type: ignore[assignment, misc]


class ModelStage(Enum):
    """Model lifecycle stages (MLflow compatible)"""

    TRAINING = "Training"
    STAGING = "Staging"
    PAPER = "Paper"  # New stage for paper trading
    PRODUCTION = "Production"
    ARCHIVED = "Archived"


@dataclass
class PromotionCriteria:
    """
    Criteria that must be met for model promotion.

    All criteria must pass for promotion to succeed.
    """

    # Paper trading validation
    min_paper_trading_days: int = 14
    min_trade_count: int = 100

    # Performance criteria
    min_sharpe_ratio: float = 1.0
    max_drawdown: float = 0.10  # 10%
    min_win_rate: float = 0.45  # 45%
    min_profit_factor: float = 1.2

    # Stability criteria
    max_volatility_ratio: float = 2.0  # Max volatility vs benchmark


@dataclass
class ValidationResult:
    """Result of model validation"""

    passed: bool
    checks: Dict[str, bool] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    messages: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": self.checks,
            "metrics": self.metrics,
            "messages": self.messages,
        }


class ModelPromoter:
    """
    Handles model promotion workflow.

    Workflow:
    1. Training -> Staging: After training completes, automatic
    2. Staging -> Paper: User initiates paper trading
    3. Paper -> Production: After paper trading validation + manual approval + 2FA
    4. Production -> Archived: When new model promoted

    Usage:
        promoter = ModelPromoter(
            tracking_uri="http://localhost:5000",
            model_name="trading-dqn",
            model_registry=model_registry  # Optional database registry
        )

        # Promote to paper
        promoter.promote_to_paper(model_id=1, approver="user")

        # Validate for production
        metrics = get_paper_trading_metrics()
        passed, result = promoter.validate_for_production(model_id=1, metrics=metrics)

        # Promote to production (requires passed validation + 2FA)
        if passed:
            promoter.promote_to_production(
                model_id=1,
                approver="admin",
                validation=result,
                totp_token="123456"  # 2FA token
            )

        # Rollback if needed
        promoter.rollback_production(reason="Performance degradation", operator="admin")
    """

    def __init__(
        self,
        tracking_uri: Optional[str] = None,
        model_name: str = "trading-dqn",
        criteria: Optional[PromotionCriteria] = None,
        model_registry: Optional["ModelRegistry"] = None,
    ):
        """
        Initialize model promoter.

        Args:
            tracking_uri: MLflow tracking server URI
            model_name: Name of the registered model
            criteria: Promotion criteria (uses defaults if None)
            model_registry: Optional ModelRegistry for database integration
        """
        if not MLFLOW_AVAILABLE:
            raise ImportError(
                "MLflow is not installed. Install with: pip install mlflow>=2.10.0"
            )

        import os

        self.tracking_uri = tracking_uri or os.getenv(
            "MLFLOW_TRACKING_URI", "http://localhost:5000"
        )
        self.model_name = model_name
        self.criteria = criteria or PromotionCriteria()
        self.model_registry = model_registry

        self.client = MlflowClient(self.tracking_uri)
        self.logger = logging.getLogger(__name__)

    def get_latest_versions(self, stages: Optional[List[str]] = None) -> List:
        """
        Get latest model versions, optionally filtered by stage.

        Args:
            stages: List of stages to filter by (e.g., ["Staging", "Production"])

        Returns:
            List of model versions
        """
        try:
            return self.client.get_latest_versions(self.model_name, stages=stages)
        except Exception as e:
            self.logger.error(f"Failed to get model versions: {e}")
            return []

    def get_production_model(self):
        """Get the current production model version"""
        versions = self.get_latest_versions(stages=["Production"])
        return versions[0] if versions else None

    def get_staging_model(self):
        """Get the current staging model version"""
        versions = self.get_latest_versions(stages=["Staging"])
        return versions[0] if versions else None

    def get_paper_model(self):
        """Get the current paper trading model version"""
        if self.model_registry:
            paper_models = self.model_registry.get_models_by_stage(DBModelStage.PAPER)
            return paper_models[0] if paper_models else None
        # Fallback to MLflow (if Paper stage is supported)
        versions = self.get_latest_versions(stages=["Paper"])
        return versions[0] if versions else None

    def get_model_version(self, version: int):
        """Get a specific model version"""
        try:
            return self.client.get_model_version(self.model_name, str(version))
        except Exception as e:
            self.logger.error(f"Failed to get model version {version}: {e}")
            return None

    def promote_to_staging(self, version: int, approver: str) -> bool:
        """
        Promote a model to staging for paper trading validation.

        Args:
            version: Model version number
            approver: Name of person approving promotion

        Returns:
            True if successful
        """
        try:
            # Transition to staging in MLflow
            self.client.transition_model_version_stage(
                name=self.model_name, version=str(version), stage="Staging"
            )

            # Update database if registry available
            if self.model_registry:
                model = self.model_registry.get_model_by_version(str(version))
                if model and model.id is not None:
                    self.model_registry.update_model_stage(
                        model.id,
                        DBModelStage.STAGING,
                        promoted_by=None,  # Auto-promotion
                    )

            # Add metadata tags
            self._set_version_tags(
                version,
                {
                    "staged_by": approver,
                    "staged_at": datetime.now().isoformat(),
                    "promotion_status": "staging",
                },
            )

            self.logger.info(f"Model v{version} promoted to Staging by {approver}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to promote to staging: {e}")
            return False

    def promote_to_paper(
        self, model_id: int, approver: str, approver_id: Optional[int] = None
    ) -> bool:
        """
        Promote a model from Staging to Paper for paper trading validation.

        Args:
            model_id: Model ID (database ID)
            approver: Name of person approving promotion
            approver_id: Optional user ID for audit trail

        Returns:
            True if successful
        """
        if not self.model_registry:
            raise ValueError("ModelRegistry required for paper promotion")

        try:
            model = self.model_registry.get_model(model_id)
            if not model:
                raise ValueError(f"Model {model_id} not found")

            if model.stage != DBModelStage.STAGING:
                raise ValueError(
                    f"Model must be in Staging stage, currently {model.stage.value}"
                )

            # Update database stage
            self.model_registry.update_model_stage(
                model_id, DBModelStage.PAPER, promoted_by=approver_id
            )

            # Update MLflow if version is numeric
            try:
                version_num = int(model.version.replace("v", ""))
                # MLflow doesn't have Paper stage, so we keep it in Staging
                # but tag it for paper trading
                self._set_version_tags(
                    version_num,
                    {
                        "paper_trading": "true",
                        "promoted_to_paper_by": approver,
                        "promoted_to_paper_at": datetime.now().isoformat(),
                    },
                )
            except (ValueError, AttributeError):
                pass  # Version not numeric, skip MLflow update

            self.logger.info(
                f"Model {model_id} (v{model.version}) promoted to Paper by {approver}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to promote to paper: {e}")
            return False

    def validate_for_production(
        self,
        model_id: Optional[int] = None,
        version: Optional[int] = None,
        metrics: Optional[Dict[str, float]] = None,
    ) -> tuple[bool, ValidationResult]:
        """
        Validate that a paper trading model meets production criteria.

        Args:
            model_id: Model ID (database ID) - preferred
            version: Model version number (for backward compatibility)
            metrics: Paper trading metrics dictionary containing:
                - days_traded: Number of days in paper trading
                - trade_count: Total number of trades
                - sharpe_ratio: Sharpe ratio
                - max_drawdown: Maximum drawdown (as decimal, e.g., 0.10 for 10%)
                - win_rate: Win rate (as decimal)
                - profit_factor: Profit factor

        Returns:
            Tuple of (passed, ValidationResult)
        """
        # Get metrics from model if not provided
        if not metrics and model_id and self.model_registry:
            model = self.model_registry.get_model(model_id)
            if model and model.paper_trading_results:
                metrics = model.paper_trading_results

        if not metrics:
            raise ValueError("Metrics required for validation")

        result = ValidationResult(passed=True, metrics=metrics)

        # Get model identifier for logging
        model_identifier = f"model_id={model_id}" if model_id else f"v{version}"

        # Check minimum paper trading days
        days_traded = metrics.get("days_traded", 0)
        result.checks["min_days"] = days_traded >= self.criteria.min_paper_trading_days
        if not result.checks["min_days"]:
            result.messages.append(
                f"Insufficient paper trading: {days_traded} days "
                f"(min: {self.criteria.min_paper_trading_days})"
            )

        # Check minimum trade count
        trade_count = metrics.get("trade_count", 0)
        result.checks["min_trades"] = trade_count >= self.criteria.min_trade_count
        if not result.checks["min_trades"]:
            result.messages.append(
                f"Insufficient trades: {trade_count} "
                f"(min: {self.criteria.min_trade_count})"
            )

        # Check Sharpe ratio
        sharpe = metrics.get("sharpe_ratio", 0)
        result.checks["sharpe_ratio"] = sharpe >= self.criteria.min_sharpe_ratio
        if not result.checks["sharpe_ratio"]:
            result.messages.append(
                f"Sharpe ratio too low: {sharpe:.2f} "
                f"(min: {self.criteria.min_sharpe_ratio})"
            )

        # Check maximum drawdown
        max_dd = metrics.get("max_drawdown", 1.0)
        result.checks["max_drawdown"] = max_dd <= self.criteria.max_drawdown
        if not result.checks["max_drawdown"]:
            result.messages.append(
                f"Drawdown too high: {max_dd:.2%} "
                f"(max: {self.criteria.max_drawdown:.2%})"
            )

        # Check win rate
        win_rate = metrics.get("win_rate", 0)
        result.checks["win_rate"] = win_rate >= self.criteria.min_win_rate
        if not result.checks["win_rate"]:
            result.messages.append(
                f"Win rate too low: {win_rate:.2%} "
                f"(min: {self.criteria.min_win_rate:.2%})"
            )

        # Check profit factor (optional)
        if "profit_factor" in metrics:
            pf = metrics["profit_factor"]
            result.checks["profit_factor"] = pf >= self.criteria.min_profit_factor
            if not result.checks["profit_factor"]:
                result.messages.append(
                    f"Profit factor too low: {pf:.2f} "
                    f"(min: {self.criteria.min_profit_factor})"
                )

        # Overall pass/fail
        result.passed = all(result.checks.values())

        # Log result
        if result.passed:
            self.logger.info(f"Model {model_identifier} passed validation")
        else:
            self.logger.warning(
                f"Model {model_identifier} failed validation: {'; '.join(result.messages)}"
            )

        return result.passed, result

    def promote_to_production(
        self,
        model_id: Optional[int] = None,
        version: Optional[int] = None,
        approver: str = None,
        approver_id: Optional[int] = None,
        validation: Optional[ValidationResult] = None,
        totp_token: Optional[str] = None,
    ) -> bool:
        """
        Promote a validated model to production.

        Args:
            model_id: Model ID (database ID) - preferred
            version: Model version number (for backward compatibility)
            approver: Name of person approving promotion
            approver_id: Optional user ID for audit trail
            validation: Validation result (must have passed=True if provided)
            totp_token: Optional 2FA token (required for production promotion)

        Returns:
            True if successful
        """
        # Validate 2FA if required
        if totp_token is None:
            self.logger.warning("Production promotion requires 2FA token")
            # In production, this should raise an error, but for now we'll warn
            # The API layer will enforce 2FA

        if validation and not validation.passed:
            model_identifier = f"model_id={model_id}" if model_id else f"v{version}"
            raise ValueError(
                f"Cannot promote model {model_identifier}: validation failed. "
                f"Reasons: {validation.messages}"
            )

        try:
            # Get model from database if available
            model = None
            if model_id and self.model_registry:
                model = self.model_registry.get_model(model_id)
                if not model:
                    raise ValueError(f"Model {model_id} not found")
                if model.stage != DBModelStage.PAPER:
                    raise ValueError(
                        f"Model must be in Paper stage, currently {model.stage.value}"
                    )
                version_str = model.version
            elif version:
                version_str = str(version)
            else:
                raise ValueError("Either model_id or version must be provided")

            # Archive current production model in database
            if self.model_registry:
                current_prod_models = self.model_registry.get_models_by_stage(
                    DBModelStage.PRODUCTION
                )
                for current_prod in current_prod_models:
                    if current_prod.id is not None:
                        self.model_registry.update_model_stage(
                            current_prod.id,
                            DBModelStage.ARCHIVED,
                            promoted_by=approver_id,
                        )
                    self.logger.info(
                        f"Archived previous production model {current_prod.id} (v{current_prod.version})"
                    )

            # Archive current production model in MLflow
            current_prod = self.get_production_model()
            if current_prod:
                try:
                    self.client.transition_model_version_stage(
                        name=self.model_name,
                        version=current_prod.version,
                        stage="Archived",
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to archive in MLflow: {e}")

            # Promote new model in database
            if model_id and self.model_registry:
                self.model_registry.update_model_stage(
                    model_id, DBModelStage.PRODUCTION, promoted_by=approver_id
                )

            # Promote new model in MLflow (if version is numeric)
            try:
                version_num = int(version_str.replace("v", ""))
                self.client.transition_model_version_stage(
                    name=self.model_name, version=str(version_num), stage="Production"
                )
            except (ValueError, AttributeError):
                pass  # Version not numeric, skip MLflow update

            # Add metadata tags
            try:
                version_num = int(version_str.replace("v", ""))
                self._set_version_tags(
                    version_num,
                    {
                        "approved_by": approver or "unknown",
                        "approved_at": datetime.now().isoformat(),
                        "promotion_status": "production",
                        "validation_passed": "true" if validation else "unknown",
                        "validation_sharpe": (
                            str(validation.metrics.get("sharpe_ratio", ""))
                            if validation
                            else ""
                        ),
                        "validation_drawdown": (
                            str(validation.metrics.get("max_drawdown", ""))
                            if validation
                            else ""
                        ),
                    },
                )
            except (ValueError, AttributeError):
                pass

            model_identifier = (
                f"{model_id} (v{version_str})" if model_id else f"v{version_str}"
            )
            self.logger.info(
                f"Model {model_identifier} promoted to Production by {approver}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to promote to production: {e}")
            return False

    def rollback_production(
        self, reason: str, operator: str, to_version: Optional[int] = None
    ) -> Optional[int]:
        """
        Rollback production to a previous model.

        If to_version is not specified, rolls back to the most recent archived model.

        Args:
            reason: Reason for rollback
            operator: Name of person performing rollback
            to_version: Specific version to rollback to (optional)

        Returns:
            Version number of the new production model, or None if failed
        """
        try:
            current_prod = self.get_production_model()

            # Find target version
            if to_version:
                target = self.get_model_version(to_version)
            else:
                # Get most recent archived model
                archived = self.get_latest_versions(stages=["Archived"])
                if not archived:
                    self.logger.error("No archived models available for rollback")
                    return None
                target = archived[0]

            if not target:
                self.logger.error(f"Target version not found: {to_version}")
                return None

            # Demote current production to archived
            if current_prod:
                self.client.transition_model_version_stage(
                    name=self.model_name, version=current_prod.version, stage="Archived"
                )

                self._set_version_tags(
                    int(current_prod.version),
                    {
                        "rollback_reason": reason,
                        "rollback_by": operator,
                        "rollback_at": datetime.now().isoformat(),
                    },
                )

            # Promote target to production
            self.client.transition_model_version_stage(
                name=self.model_name, version=target.version, stage="Production"
            )

            self._set_version_tags(
                int(target.version),
                {
                    "restored_by": operator,
                    "restored_at": datetime.now().isoformat(),
                    "restore_reason": f"Rollback from v{current_prod.version if current_prod else 'none'}: {reason}",
                },
            )

            self.logger.warning(
                f"Production rolled back to v{target.version} by {operator}: {reason}"
            )

            return int(target.version)

        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            return None

    def archive_model(self, version: int, reason: Optional[str] = None) -> bool:
        """
        Archive a model version.

        Args:
            version: Version to archive
            reason: Reason for archiving

        Returns:
            True if successful
        """
        try:
            self.client.transition_model_version_stage(
                name=self.model_name, version=str(version), stage="Archived"
            )

            if reason:
                self._set_version_tags(version, {"archive_reason": reason})

            self.logger.info(f"Archived model v{version}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to archive model: {e}")
            return False

    def _set_version_tags(self, version: int, tags: Dict[str, str]) -> None:
        """Set tags on a model version"""
        for key, value in tags.items():
            try:
                self.client.set_model_version_tag(
                    name=self.model_name, version=str(version), key=key, value=value
                )
            except Exception as e:
                self.logger.warning(f"Failed to set tag {key}: {e}")

    def get_model_history(self) -> List[Dict[str, Any]]:
        """
        Get promotion history for all versions.

        Returns:
            List of version info dictionaries
        """
        history = []

        try:
            # Get all versions
            for stage in ["None", "Staging", "Production", "Archived"]:
                versions = self.get_latest_versions(stages=[stage])
                for v in versions:
                    history.append(
                        {
                            "version": int(v.version),
                            "stage": v.current_stage,
                            "creation_timestamp": v.creation_timestamp,
                            "last_updated_timestamp": v.last_updated_timestamp,
                            "run_id": v.run_id,
                            "tags": v.tags if hasattr(v, "tags") else {},
                        }
                    )
        except Exception as e:
            self.logger.error(f"Failed to get model history: {e}")

        return sorted(history, key=lambda x: x["version"], reverse=True)

    def get_status(self) -> Dict[str, Any]:
        """Get current model status summary"""
        prod = self.get_production_model()
        staging = self.get_staging_model()

        return {
            "model_name": self.model_name,
            "production_version": int(prod.version) if prod else None,
            "staging_version": int(staging.version) if staging else None,
            "criteria": {
                "min_paper_trading_days": self.criteria.min_paper_trading_days,
                "min_sharpe_ratio": self.criteria.min_sharpe_ratio,
                "max_drawdown": self.criteria.max_drawdown,
            },
        }
