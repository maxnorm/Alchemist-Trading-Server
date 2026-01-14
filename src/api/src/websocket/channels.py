"""
WebSocket channel handlers
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Optional, Set, Dict
import json
import logging
import re
from websocket.manager import websocket_manager
from services.clerk_service import clerk_service

logger = logging.getLogger(__name__)

# Map frontend channel paths to backend channel names
CHANNEL_MAPPING = {
    "/ws/trading/positions": "positions",
    "/ws/training/metrics": "training",
    "/ws/performance/updates": "performance",
    "/ws/alerts": "alerts",
    "/ws/trading/status": "trading",
    "/ws/accounts/mt5": "mt5_accounts",
    "/ws/optuna": "optuna",
    "/ws/metrics": "metrics",
    "/ws/trades": "trades",
    "/ws/models": "models",
}

# Pattern-based mappings for dynamic channels
CHANNEL_PATTERNS = [
    (re.compile(r"^/ws/experiments/\d+/progress$"), "training"),
    (re.compile(r"^/ws/optuna/\d+/trials$"), "optuna"),
]


async def handle_websocket(websocket: WebSocket, channel: str):
    """Handle WebSocket connection for a specific channel with Clerk authentication"""
    # Get token from query params
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return

    try:
        # Verify token with Clerk
        session_data = clerk_service.verify_token(token)
        user_id = session_data["user_id"]
        user_data = clerk_service.get_user(user_id)
        roles = clerk_service.extract_roles(user_data)

        # Store user info in websocket state
        websocket.state.user_id = user_id
        websocket.state.user_email = user_data.get("email")
        websocket.state.roles = roles

        logger.info(f"WebSocket authenticated: user_id={user_id}, channel={channel}")

        # Accept connection and connect to channel
        await websocket.accept()
        await websocket_manager.connect(websocket, channel, accept=False)

    except ValueError as e:
        logger.warning(f"WebSocket authentication failed: {e}")
        await websocket.close(code=1008, reason="Invalid token")
        return

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


async def handle_generic_websocket(websocket: WebSocket):
    """
    Handle generic WebSocket connection with channel subscription support.
    
    Clients can subscribe to multiple channels via messages:
    - {"action": "subscribe", "channel": "/ws/trading/positions"}
    - {"action": "unsubscribe", "channel": "/ws/trading/positions"}
    """
    # Get token from query params
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return

    try:
        # Verify token with Clerk
        session_data = clerk_service.verify_token(token)
        user_id = session_data["user_id"]
        user_data = clerk_service.get_user(user_id)
        roles = clerk_service.extract_roles(user_data)

        # Store user info in websocket state
        websocket.state.user_id = user_id
        websocket.state.user_email = user_data.get("email")
        websocket.state.roles = roles

        logger.info(f"Generic WebSocket authenticated: user_id={user_id}")

        # Accept connection
        await websocket.accept()
        logger.info("Generic WebSocket connection accepted")

    except ValueError as e:
        logger.warning(f"Generic WebSocket authentication failed: {e}")
        await websocket.close(code=1008, reason="Invalid token")
        return

    # Track which channels this connection is subscribed to
    subscribed_channels: Set[str] = set()

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                action = message.get("action")
                channel_path = message.get("channel")
                
                if action == "subscribe" and channel_path:
                    # Map frontend channel path to backend channel name
                    backend_channel = CHANNEL_MAPPING.get(channel_path)
                    
                    # Try pattern matching for dynamic channels
                    if not backend_channel:
                        for pattern, mapped_channel in CHANNEL_PATTERNS:
                            if pattern.match(channel_path):
                                backend_channel = mapped_channel
                                break
                    
                    if backend_channel:
                        # Subscribe to the backend channel
                        await websocket_manager.connect(websocket, backend_channel, accept=False)
                        subscribed_channels.add(backend_channel)
                        logger.info(f"Client subscribed to {channel_path} (backend: {backend_channel})")
                        
                        # Send confirmation
                        await websocket_manager.send_personal_message(
                            {
                                "type": "subscription_confirmed",
                                "channel": channel_path,
                                "status": "subscribed"
                            },
                            websocket
                        )
                    else:
                        logger.warning(f"Unknown channel path: {channel_path}")
                        await websocket_manager.send_personal_message(
                            {
                                "type": "error",
                                "message": f"Unknown channel: {channel_path}"
                            },
                            websocket
                        )
                
                elif action == "unsubscribe" and channel_path:
                    backend_channel = CHANNEL_MAPPING.get(channel_path)
                    
                    # Try pattern matching for dynamic channels
                    if not backend_channel:
                        for pattern, mapped_channel in CHANNEL_PATTERNS:
                            if pattern.match(channel_path):
                                backend_channel = mapped_channel
                                break
                    
                    if backend_channel and backend_channel in subscribed_channels:
                        await websocket_manager.disconnect(websocket, backend_channel)
                        subscribed_channels.discard(backend_channel)
                        logger.info(f"Client unsubscribed from {channel_path} (backend: {backend_channel})")
                        
                        # Send confirmation
                        await websocket_manager.send_personal_message(
                            {
                                "type": "unsubscription_confirmed",
                                "channel": channel_path,
                                "status": "unsubscribed"
                            },
                            websocket
                        )
                    else:
                        logger.warning(f"Channel not subscribed or unknown: {channel_path}")
                
                else:
                    logger.debug(f"Received message on generic WebSocket: {message}")
                    
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received on generic WebSocket: {data}")
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")

    except WebSocketDisconnect:
        logger.info("Generic WebSocket disconnected")
        # Unsubscribe from all channels
        for channel in subscribed_channels.copy():
            await websocket_manager.disconnect(websocket, channel)
    except Exception as e:
        logger.error(f"Generic WebSocket error: {e}")
        # Unsubscribe from all channels
        for channel in subscribed_channels.copy():
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


async def broadcast_alert(
    alert_type: str, message: str, severity: str = "info", metrics: Optional[dict] = None
):
    """Broadcast alert notification"""
    alert = {
        "type": "alert",
        "alert_type": alert_type,
        "message": message,
        "severity": severity,
    }
    if metrics:
        alert["metrics"] = metrics
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


# MT5 Accounts WebSocket channels


async def broadcast_account_connected(account_id: int, terminal_id: Optional[int] = None):
    """Broadcast MT5 account connection event"""
    from datetime import datetime

    message = {
        "type": "account_connected",
        "data": {
            "account_id": account_id,
            "terminal_id": terminal_id,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }
    await websocket_manager.broadcast_to_channel("mt5_accounts", message)
    await websocket_manager.broadcast_to_channel(f"mt5_account_{account_id}", message)


async def broadcast_account_disconnected(account_id: int, reason: Optional[str] = None):
    """Broadcast MT5 account disconnection event"""
    from datetime import datetime

    message = {
        "type": "account_disconnected",
        "data": {
            "account_id": account_id,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }
    await websocket_manager.broadcast_to_channel("mt5_accounts", message)
    await websocket_manager.broadcast_to_channel(f"mt5_account_{account_id}", message)


async def broadcast_model_assigned(account_id: int, model_id: int, model_version: Optional[str] = None):
    """Broadcast model assignment to account"""
    from datetime import datetime

    message = {
        "type": "model_assigned",
        "data": {
            "account_id": account_id,
            "model_id": model_id,
            "model_version": model_version,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }
    await websocket_manager.broadcast_to_channel("mt5_accounts", message)
    await websocket_manager.broadcast_to_channel(f"mt5_account_{account_id}", message)


async def broadcast_model_unassigned(account_id: int):
    """Broadcast model unassignment from account"""
    from datetime import datetime

    message = {
        "type": "model_unassigned",
        "data": {
            "account_id": account_id,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }
    await websocket_manager.broadcast_to_channel("mt5_accounts", message)
    await websocket_manager.broadcast_to_channel(f"mt5_account_{account_id}", message)
