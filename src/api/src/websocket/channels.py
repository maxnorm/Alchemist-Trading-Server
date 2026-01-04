"""
WebSocket channel handlers
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Optional
import json
import logging
from websocket.manager import websocket_manager

logger = logging.getLogger(__name__)


async def handle_websocket(websocket: WebSocket, channel: str):
    """Handle WebSocket connection for a specific channel"""
    await websocket_manager.connect(websocket, channel)

    try:
        while True:
            # Keep connection alive and handle any incoming messages
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                # Handle client messages if needed
                logger.debug(f"Received message on {channel}: {message}")
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received on {channel}: {data}")
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket, channel)
    except Exception as e:
        logger.error(f"WebSocket error on {channel}: {e}")
        await websocket_manager.disconnect(websocket, channel)


async def broadcast_tick(symbol: str, bid: float, ask: float, time: str):
    """Broadcast tick data"""
    message = {"type": "tick", "symbol": symbol, "bid": bid, "ask": ask, "time": time}
    await websocket_manager.broadcast_to_channel("ticks", message)


async def broadcast_training_progress(
    experiment_id: int, step: int, loss: float, reward: float, epsilon: float
):
    """Broadcast training progress"""
    message = {
        "type": "training",
        "experiment_id": experiment_id,
        "step": step,
        "loss": loss,
        "reward": reward,
        "epsilon": epsilon,
    }
    await websocket_manager.broadcast_to_channel("training", message)


async def broadcast_optuna_trial(
    study_id: int,
    trial_number: int,
    params: dict,
    value: Optional[float],
    is_best: bool,
):
    """Broadcast Optuna trial result"""
    message = {
        "type": "optuna",
        "study_id": study_id,
        "trial_number": trial_number,
        "params": params,
        "value": value,
        "is_best": is_best,
    }
    await websocket_manager.broadcast_to_channel("optuna", message)


async def broadcast_position_update(positions: list):
    """Broadcast position updates"""
    message = {"type": "positions", "positions": positions}
    await websocket_manager.broadcast_to_channel("positions", message)


async def broadcast_metrics(balance: float, equity: float, pnl: float):
    """Broadcast performance metrics"""
    message = {"type": "metrics", "balance": balance, "equity": equity, "pnl": pnl}
    await websocket_manager.broadcast_to_channel("metrics", message)


async def broadcast_alert(alert_type: str, message: str, severity: str = "info"):
    """Broadcast alert notification"""
    alert = {
        "type": "alert",
        "alert_type": alert_type,
        "message": message,
        "severity": severity,
    }
    await websocket_manager.broadcast_to_channel("alerts", alert)


async def broadcast_performance_update(
    portfolio_pnl: float,
    model_pnl: Optional[float],
    sharpe: Optional[float],
    drawdown: Optional[float],
):
    """Broadcast performance update (legacy)"""
    message = {
        "type": "performance",
        "portfolio_pnl": portfolio_pnl,
        "model_pnl": model_pnl,
        "sharpe": sharpe,
        "drawdown": drawdown,
    }
    await websocket_manager.broadcast_to_channel("performance", message)


async def broadcast_portfolio_update(
    total_pnl: float,
    sharpe_ratio: Optional[float],
    max_drawdown: Optional[float],
    win_rate: Optional[float],
):
    """Broadcast portfolio-level performance update"""
    from datetime import datetime

    message = {
        "type": "portfolio_update",
        "data": {
            "total_pnl": total_pnl,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }
    await websocket_manager.broadcast_to_channel("performance", message)


async def broadcast_model_update(
    model_id: int,
    model_version: str,
    pnl: float,
    sharpe_ratio: Optional[float],
    win_rate: Optional[float],
):
    """Broadcast model-level performance update"""
    from datetime import datetime

    message = {
        "type": "model_update",
        "data": {
            "model_id": model_id,
            "model_version": model_version,
            "pnl": pnl,
            "sharpe_ratio": sharpe_ratio,
            "win_rate": win_rate,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }
    await websocket_manager.broadcast_to_channel("performance", message)


async def broadcast_trade_executed(
    model_id: int,
    symbol: str,
    action: str,
    entry_price: float,
    volume: float,
    pnl: Optional[float] = None,
):
    """Broadcast trade execution notification"""
    from datetime import datetime

    message = {
        "type": "trade_executed",
        "data": {
            "model_id": model_id,
            "symbol": symbol,
            "action": action,
            "entry_price": entry_price,
            "volume": volume,
            "pnl": pnl,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }
    await websocket_manager.broadcast_to_channel("performance", message)
    await websocket_manager.broadcast_to_channel("trades", message)


async def broadcast_trade(
    model: str, symbol: str, action: str, pnl: Optional[float], time: str
):
    """Broadcast trade notification"""
    message = {
        "type": "trade",
        "model": model,
        "symbol": symbol,
        "action": action,
        "pnl": pnl,
        "time": time,
    }
    await websocket_manager.broadcast_to_channel("trades", message)


# Model lifecycle WebSocket channels


async def broadcast_model_stage_change(
    model_id: int, old_stage: str, new_stage: str, promoted_by: Optional[int] = None
):
    """Broadcast model stage change"""
    from datetime import datetime

    message = {
        "type": "model_stage_change",
        "data": {
            "model_id": model_id,
            "old_stage": old_stage,
            "new_stage": new_stage,
            "promoted_by": promoted_by,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }
    await websocket_manager.broadcast_to_channel("models", message)
    await websocket_manager.broadcast_to_channel(f"models/{model_id}/status", message)


async def broadcast_paper_session_update(
    model_id: int, session_id: int, status: str, metrics: Optional[dict] = None
):
    """Broadcast paper trading session update"""
    from datetime import datetime

    message = {
        "type": "paper_session_update",
        "data": {
            "model_id": model_id,
            "session_id": session_id,
            "status": status,
            "metrics": metrics or {},
            "timestamp": datetime.utcnow().isoformat(),
        },
    }
    await websocket_manager.broadcast_to_channel("models", message)
    await websocket_manager.broadcast_to_channel(
        f"models/{model_id}/paper-session", message
    )


async def broadcast_validation_update(model_id: int, validation_result: dict):
    """Broadcast model validation status update"""
    from datetime import datetime

    message = {
        "type": "validation_update",
        "data": {
            "model_id": model_id,
            "validation": validation_result,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }
    await websocket_manager.broadcast_to_channel("models", message)
    await websocket_manager.broadcast_to_channel(
        f"models/{model_id}/validation", message
    )
