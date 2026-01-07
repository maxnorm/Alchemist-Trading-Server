"""
Model registry service
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from typing import List, Optional, Dict, Any, cast
from schemas.models import ModelResponse, PaperSessionResponse
import json
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

logger = logging.getLogger(__name__)

# Try to import TwoFactorAuth (may not be available in API context)
try:
    # Try different import paths
    try:
        from src.trading_server.src.mlops.two_factor_auth import TwoFactorAuth
    except ImportError:
        # Alternative path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
        from src.trading_server.src.mlops.two_factor_auth import TwoFactorAuth
    TWO_FA_AVAILABLE = True
except ImportError:
    TWO_FA_AVAILABLE = False
    logger.warning("TwoFactorAuth not available - 2FA verification will be limited")

    # Create a stub for development
    class TwoFactorAuth:  # type: ignore[no-redef]
        @staticmethod
        def verify_promotion_token(secret, token, user_id):
            # Development mode: accept any 6-digit code
            return len(token) == 6 and token.isdigit()


# Try to import WebSocket channels
try:
    from websocket import channels as ws_channels  # type: ignore[attr-defined]

    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False
    logger.warning("WebSocket channels not available")


def get_all_models(
    db: Session, stage: Optional[str] = None, experiment_id: Optional[int] = None
) -> List[ModelResponse]:
    """Get all models with optional filters"""
    query = "SELECT * FROM models WHERE 1=1"
    params: Dict[str, Any] = {}

    if stage:
        query += " AND stage = :stage"
        params["stage"] = stage

    if experiment_id:
        query += " AND experiment_id = :experiment_id"
        params["experiment_id"] = experiment_id

    query += " ORDER BY created_at DESC"

    result = db.execute(text(query), params)
    rows = result.fetchall()

    models = []
    for row in rows:
        row_dict = dict(row._mapping)
        # Parse JSON fields
        for json_field in [
            "features",
            "hyperparameters",
            "metrics",
            "paper_trading_results",
        ]:
            if row_dict.get(json_field) and isinstance(row_dict[json_field], str):
                try:
                    row_dict[json_field] = json.loads(row_dict[json_field])
                except (ValueError, TypeError):
                    row_dict[json_field] = [] if json_field == "features" else {}
        models.append(ModelResponse(**row_dict))

    return models


def get_model_by_id(db: Session, model_id: int) -> Optional[ModelResponse]:
    """Get model by ID"""
    result = db.execute(text("SELECT * FROM models WHERE id = :id"), {"id": model_id})
    row = result.fetchone()

    if not row:
        return None

    row_dict = dict(row._mapping)
    # Parse JSON fields
    for json_field in [
        "features",
        "hyperparameters",
        "metrics",
        "paper_trading_results",
    ]:
        if row_dict.get(json_field) and isinstance(row_dict[json_field], str):
            try:
                row_dict[json_field] = json.loads(row_dict[json_field])
            except (ValueError, TypeError):
                row_dict[json_field] = [] if json_field == "features" else {}

    return ModelResponse(**row_dict)


def get_model_by_version(db: Session, version: str) -> Optional[ModelResponse]:
    """Get model by version"""
    result = db.execute(
        text("SELECT * FROM models WHERE version = :version"), {"version": version}
    )
    row = result.fetchone()

    if not row:
        return None

    row_dict = dict(row._mapping)
    # Parse JSON fields
    for json_field in [
        "features",
        "hyperparameters",
        "metrics",
        "paper_trading_results",
    ]:
        if row_dict.get(json_field) and isinstance(row_dict[json_field], str):
            try:
                row_dict[json_field] = json.loads(row_dict[json_field])
            except (ValueError, TypeError):
                row_dict[json_field] = [] if json_field == "features" else {}

    return ModelResponse(**row_dict)


def promote_model(
    db: Session,
    model_id: int,
    target_stage: str,
    promoted_by: Optional[int] = None,
    totp_token: Optional[str] = None,
) -> Optional[ModelResponse]:
    """Promote model to a new stage"""
    # Get current model to track stage change
    current_model = get_model_by_id(db, model_id)
    if not current_model:
        raise ValueError(f"Model {model_id} not found")

    # Validate 2FA for production promotion
    if target_stage == "production":
        if not totp_token:
            raise ValueError("2FA token required for production promotion")

        # Verify 2FA token
        if TWO_FA_AVAILABLE:
            # For now, accept any 6-digit code (in production, verify against user's secret)
            if not TwoFactorAuth.verify_promotion_token(None, totp_token, promoted_by):
                raise ValueError("Invalid 2FA token")
        elif len(totp_token) != 6 or not totp_token.isdigit():
            raise ValueError("Invalid 2FA token format")

        # Validate model meets production criteria
        validation = validate_model_for_production(db, model_id)
        if not validation["passed"]:
            raise ValueError(
                f"Model validation failed: {', '.join(validation['messages'])}"
            )

        # Archive current production models
        db.execute(
            text("UPDATE models SET stage = 'archived' WHERE stage = 'production'")
        )

    update_fields = ["stage = :stage", "promoted_at = NOW()"]
    params = {"id": model_id, "stage": target_stage}

    if promoted_by:
        update_fields.append("promoted_by = :promoted_by")
        params["promoted_by"] = promoted_by

    query = f"UPDATE models SET {', '.join(update_fields)} WHERE id = :id"

    result = db.execute(text(query), params)
    db.commit()

    # Cast to CursorResult to access rowcount attribute
    cursor_result = cast(CursorResult[Any], result)
    if cursor_result.rowcount == 0:
        return None

    # Broadcast stage change via WebSocket (async call)
    if WS_AVAILABLE:
        try:
            # Note: In a real async context, this would be awaited
            # For now, we'll use asyncio.run_coroutine_threadsafe if needed
            # or the WebSocket manager will handle it when called from async endpoints
            pass  # WebSocket broadcasts will be handled by the router endpoints
        except Exception as e:
            logger.warning(f"Failed to broadcast stage change: {e}")

    return get_model_by_id(db, model_id)


def archive_model(db: Session, model_id: int) -> Optional[ModelResponse]:
    """Archive a model"""
    return promote_model(db, model_id, "archived")


def rollback_production(
    db: Session, current_model_id: int, target_model_id: Optional[int] = None
) -> Optional[ModelResponse]:
    """Rollback production to a previous model"""
    # Archive current production
    db.execute(
        text("UPDATE models SET stage = 'archived' WHERE id = :id"),
        {"id": current_model_id},
    )

    # Find target model (most recent archived if not specified)
    if target_model_id:
        target = get_model_by_id(db, target_model_id)
    else:
        result = db.execute(
            text(
                "SELECT * FROM models WHERE stage = 'archived' ORDER BY promoted_at DESC LIMIT 1"
            )
        )
        row = result.fetchone()
        if row:
            row_dict = dict(row._mapping)
            for json_field in [
                "features",
                "hyperparameters",
                "metrics",
                "paper_trading_results",
            ]:
                if row_dict.get(json_field) and isinstance(row_dict[json_field], str):
                    try:
                        row_dict[json_field] = json.loads(row_dict[json_field])
                    except (ValueError, TypeError):
                        row_dict[json_field] = [] if json_field == "features" else {}
            target = ModelResponse(**row_dict)
        else:
            target = None

    if not target:
        return None

    # Promote target to production
    return promote_model(db, target.id, "production")


def get_paper_sessions(db: Session, model_id: int) -> List[PaperSessionResponse]:
    """Get paper trading sessions for a model"""
    result = db.execute(
        text(
            """
            SELECT * FROM paper_trading_sessions
            WHERE model_id = :model_id
            ORDER BY started_at DESC
        """
        ),
        {"model_id": model_id},
    )
    rows = result.fetchall()

    sessions = []
    for row in rows:
        row_dict = dict(row._mapping)
        sessions.append(PaperSessionResponse(**row_dict))

    return sessions


def start_paper_session(
    db: Session, model_id: int, start_balance: float
) -> PaperSessionResponse:
    """Start a paper trading session"""
    # Verify model is in paper stage
    model = get_model_by_id(db, model_id)
    if not model:
        raise ValueError(f"Model {model_id} not found")
    if model.stage != "paper":
        raise ValueError(f"Model must be in paper stage, currently {model.stage}")

    result = db.execute(
        text(
            """
            INSERT INTO paper_trading_sessions
            (model_id, status, start_balance, current_balance, started_at)
            VALUES (:model_id, 'running', :start_balance, :start_balance, NOW())
        """
        ),
        {"model_id": model_id, "start_balance": start_balance},
    )
    db.commit()

    # Cast to CursorResult to access lastrowid attribute
    cursor_result = cast(CursorResult[Any], result)
    session_id = cursor_result.lastrowid

    # Broadcast session start via WebSocket
    if WS_AVAILABLE:
        try:
            import asyncio

            asyncio.create_task(
                ws_channels.broadcast_paper_session_update(
                    model_id=model_id,
                    session_id=session_id,
                    status="running",
                    metrics={"start_balance": start_balance},
                )
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast session start: {e}")

    return get_paper_session(db, session_id)


def get_paper_session(db: Session, session_id: int) -> Optional[PaperSessionResponse]:
    """Get paper trading session by ID"""
    result = db.execute(
        text("SELECT * FROM paper_trading_sessions WHERE id = :id"), {"id": session_id}
    )
    row = result.fetchone()

    if not row:
        return None

    row_dict = dict(row._mapping)
    return PaperSessionResponse(**row_dict)


def stop_paper_session(db: Session, session_id: int) -> PaperSessionResponse:
    """Stop a paper trading session"""
    session = get_paper_session(db, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    db.execute(
        text(
            """
            UPDATE paper_trading_sessions
            SET status = 'completed', ended_at = NOW()
            WHERE id = :id
        """
        ),
        {"id": session_id},
    )
    db.commit()

    updated_session = get_paper_session(db, session_id)

    # Calculate final metrics and store in model
    if updated_session:
        # Store paper trading results in model
        results = {
            "total_trades": updated_session.total_trades,
            "winning_trades": updated_session.winning_trades,
            "win_rate": (
                updated_session.winning_trades / updated_session.total_trades
                if updated_session.total_trades > 0
                else 0.0
            ),
            "pnl": float(updated_session.pnl),
            "sharpe_ratio": (
                float(updated_session.sharpe_ratio)
                if updated_session.sharpe_ratio
                else None
            ),
            "max_drawdown": (
                float(updated_session.max_drawdown)
                if updated_session.max_drawdown
                else None
            ),
            "days_traded": (
                (updated_session.ended_at - updated_session.started_at).days
                if updated_session.ended_at
                else 0
            ),
            "trade_count": updated_session.total_trades,
        }

        db.execute(
            text(
                "UPDATE models SET paper_trading_results = :results WHERE id = :model_id"
            ),
            {"results": json.dumps(results), "model_id": session.model_id},
        )
        db.commit()

        # Broadcast session end via WebSocket
        if WS_AVAILABLE:
            try:
                import asyncio

                asyncio.create_task(
                    ws_channels.broadcast_paper_session_update(
                        model_id=session.model_id,
                        session_id=session_id,
                        status="completed",
                        metrics=results,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to broadcast session end: {e}")

    return updated_session


def validate_model_for_production(db: Session, model_id: int) -> Dict[str, Any]:
    """Validate model for production promotion"""
    model = get_model_by_id(db, model_id)
    if not model:
        return {
            "passed": False,
            "checks": {},
            "metrics": {},
            "messages": ["Model not found"],
        }

    # Check if model has paper trading results
    if not model.paper_trading_results:
        return {
            "passed": False,
            "checks": {},
            "metrics": {},
            "messages": ["No paper trading results available"],
        }

    results = model.paper_trading_results
    checks = {}
    messages = []

    # Validation criteria
    min_trades = 100
    min_win_rate = 0.45
    min_sharpe_ratio = 1.0
    max_drawdown = 0.10

    # Check trades
    trade_count = results.get("total_trades", 0)
    checks["min_trades"] = trade_count >= min_trades
    if not checks["min_trades"]:
        messages.append(f"Insufficient trades: {trade_count} (min: {min_trades})")

    # Check win rate
    win_rate = results.get("win_rate", 0)
    checks["min_win_rate"] = win_rate >= min_win_rate
    if not checks["min_win_rate"]:
        messages.append(f"Win rate too low: {win_rate:.2%} (min: {min_win_rate:.2%})")

    # Check Sharpe ratio
    sharpe = results.get("sharpe_ratio", 0)
    checks["min_sharpe"] = sharpe >= min_sharpe_ratio
    if not checks["min_sharpe"]:
        messages.append(f"Sharpe ratio too low: {sharpe:.2f} (min: {min_sharpe_ratio})")

    # Check drawdown
    drawdown = results.get("max_drawdown", 1.0)
    checks["max_drawdown"] = drawdown <= max_drawdown
    if not checks["max_drawdown"]:
        messages.append(f"Drawdown too high: {drawdown:.2%} (max: {max_drawdown:.2%})")

    passed = all(checks.values())

    return {
        "passed": passed,
        "checks": checks,
        "metrics": results,
        "messages": messages,
    }
