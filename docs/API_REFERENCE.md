# API Reference

The Alchemist Platform provides a REST API and WebSocket interface for managing experiments, models, and trading operations.

## Base URL

- Local: `http://localhost:8000`
- API prefix: `/api/v1`

## Authentication

Currently, the API does not require authentication for local deployment. Future versions will support OAuth2 with JWT tokens.

## Endpoints

### Features

#### List Features
```
GET /api/v1/features
```

Query Parameters:
- `source` (optional): Filter by data source
- `category` (optional): Filter by category

Response:
```json
{
  "features": [
    {
      "name": "price_bid_EURUSD",
      "data_type": "float",
      "source": "price",
      "description": "Bid price for EURUSD",
      "category": "price",
      "available": true
    }
  ],
  "total": 1
}
```

#### Get Feature Details
```
GET /api/v1/features/{name}
```

Response:
```json
{
  "name": "price_bid_EURUSD",
  "data_type": "float",
  "source": "price",
  "description": "Bid price for EURUSD",
  "category": "price",
  "available": true
}
```

### Experiments

#### Create Experiment
```
POST /api/v1/experiments
```

Request Body:
```json
{
  "name": "test_experiment",
  "description": "Test experiment",
  "features": ["price_bid_EURUSD", "rsi_14_EURUSD"],
  "currency_pairs": ["EURUSD"],
  "training_mode": "live",
  "hyperparameters": {
    "learning_rate": 0.001,
    "gamma": 0.99,
    "batch_size": 32
  }
}
```

#### List Experiments
```
GET /api/v1/experiments
```

Query Parameters:
- `status` (optional): Filter by status (created, training, completed, failed)

#### Start Experiment
```
POST /api/v1/experiments/{id}/start
```

#### Stop Experiment
```
POST /api/v1/experiments/{id}/stop
```

### Hyperparameters

#### Start Optuna Search
```
POST /api/v1/experiments/{id}/optuna/start
```

Request Body:
```json
{
  "metric": "sharpe_ratio",
  "direction": "maximize",
  "n_trials": 50
}
```

#### Get Optuna Status
```
GET /api/v1/experiments/{id}/optuna/status
```

#### Get Optuna Trials
```
GET /api/v1/experiments/{id}/optuna/trials
```

### Trading Control

#### Trigger Kill Switch
```
POST /api/v1/trading/kill-switch/trigger
```

#### Reset Kill Switch
```
POST /api/v1/trading/kill-switch/reset
```

#### Get Circuit Breaker Status
```
GET /api/v1/trading/circuit-breaker/status
```

### Performance

#### Get Portfolio Metrics
```
GET /api/v1/performance/portfolio
```

Query Parameters:
- `period` (optional): Time period (daily, weekly, monthly, yearly, all_time)

#### Get Experiment Trades
```
GET /api/v1/performance/experiments/{id}/trades
```

#### Get Equity Curve
```
GET /api/v1/performance/experiments/{id}/equity-curve
```

## WebSocket Channels

### Experiment Progress
```
ws://localhost:8000/ws/experiments/{id}/progress
```

Messages:
```json
{
  "type": "progress",
  "experiment_id": 1,
  "epoch": 10,
  "metrics": {
    "loss": 0.5,
    "reward": 100.0
  }
}
```

### Trading Status
```
ws://localhost:8000/ws/trading/status
```

Messages:
```json
{
  "type": "status",
  "kill_switch_active": false,
  "circuit_breaker_state": "closed",
  "active_positions": 2
}
```

## Error Responses

All errors follow this format:
```json
{
  "detail": "Error message"
}
```

Status Codes:
- `400`: Bad Request
- `404`: Not Found
- `500`: Internal Server Error

## Interactive Documentation

When the API is running, interactive documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
