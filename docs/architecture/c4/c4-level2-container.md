# C4 Level 2 - Container Diagram

## Purpose
This diagram answers: **What are the major deployable units (containers) of the Alchemist platform and how do they communicate?**

## Scope
- **Includes**: All Docker containers, databases, message brokers, and their interactions
- **Excludes**: Internal component details within each container

## Source of Truth References
| Container | Evidence Path |
|-----------|---------------|
| Gateway (nginx) | `docker-compose.yml:5-25`, `src/gateway/nginx.conf` |
| Dashboard (React) | `docker-compose.yml:189-211`, `src/dashboard/` |
| API (FastAPI) | `docker-compose.yml:144-184`, `src/api/src/main.py` |
| Trading Server | `docker-compose.yml:54-85`, `src/trading_server/src/server.py` |
| PostgreSQL + TimescaleDB | `docker-compose.yml:30-49`, `src/database/scripts/` |
| Redis | `docker-compose.yml:273-285` |
| MLflow | `docker-compose.yml:119-139` |
| Prometheus | `docker-compose.yml:216-242`, `src/monitoring/prometheus/` |
| Grafana | `docker-compose.yml:247-268`, `src/monitoring/grafana/` |
| Airflow (Scheduler, Webserver, Worker) | `docker-compose.yml:290-427` |

## Container Diagram

```mermaid
flowchart TB
    subgraph Users["👥 Users"]
        User["🧑‍💼 Trader/Researcher"]
    end

    subgraph ExternalSystems["🌐 External"]
        MT5EA["🏦 MT5 Expert Advisors"]
        Clerk["🔐 Clerk Auth"]
        DataAPIs["📊 Data APIs<br/>(FRED, ECB, NewsAPI)"]
    end

    subgraph AlchemistPlatform["🧪 Alchemist Platform"]
        subgraph Gateway["🚪 Gateway Layer"]
            Nginx["nginx:alpine<br/>Gateway<br/>Ports: 80, 443, 8080"]
        end

        subgraph Frontend["🖥️ Frontend"]
            Dashboard["React + Vite<br/>Dashboard<br/>TypeScript, TailwindCSS"]
        end

        subgraph Backend["⚙️ Backend Services"]
            API["FastAPI<br/>REST API + WebSocket<br/>Port: 8000"]
            Server["Python<br/>Trading Server<br/>Port: 8080 (internal)"]
        end

        subgraph DataPipeline["📊 Data Pipeline"]
            AirflowWeb["Airflow Webserver<br/>Port: 8081"]
            AirflowSched["Airflow Scheduler"]
            AirflowWorker["Airflow Worker<br/>Celery"]
        end

        subgraph MLOps["🤖 MLOps"]
            MLflow["MLflow<br/>Experiment Tracking<br/>Port: 5000"]
        end

        subgraph Monitoring["📈 Monitoring"]
            Prometheus["Prometheus<br/>Metrics Collection<br/>Port: 9090"]
            Grafana["Grafana<br/>Dashboards<br/>Port: 3000"]
        end

        subgraph DataStores["💾 Data Stores"]
            Postgres[("TimescaleDB<br/>PostgreSQL 16<br/>Port: 5432")]
            Redis[("Redis 7<br/>Message Broker<br/>Port: 6379")]
            MLflowDB[("SQLite<br/>MLflow Backend")]
        end
    end

    %% User connections
    User -->|"HTTPS:80"| Nginx
    
    %% Gateway routing
    Nginx -->|"/dashboard"| Dashboard
    Nginx -->|"/api/*"| API
    Nginx -->|"/grafana"| Grafana
    Nginx -->|"TCP:8080"| Server

    %% External connections
    MT5EA <-->|"TCP Socket"| Server
    API -->|"HTTPS"| Clerk
    Server -->|"HTTP"| DataAPIs

    %% Internal service communication
    Dashboard -->|"REST/WS"| API
    API -->|"TCP"| Server
    API -->|"HTTP"| MLflow
    
    %% Database connections
    API -->|"SQL"| Postgres
    Server -->|"SQL"| Postgres
    API -->|"Pub/Sub"| Redis
    Server -->|"Pub/Sub"| Redis

    %% Airflow connections
    AirflowSched --> AirflowWorker
    AirflowWorker -->|"Celery Broker"| Redis
    AirflowWorker -->|"SQL"| Postgres
    AirflowWeb -->|"SQL"| Postgres

    %% MLOps connections
    Server -->|"Track Experiments"| MLflow
    MLflow --> MLflowDB

    %% Monitoring connections
    Prometheus -->|"Scrape /metrics"| API
    Prometheus -->|"Scrape /metrics"| Server
    Grafana -->|"Query"| Prometheus

    style Nginx fill:#2ecc71,stroke:#27ae60,color:#fff
    style Dashboard fill:#3498db,stroke:#2980b9,color:#fff
    style API fill:#9b59b6,stroke:#8e44ad,color:#fff
    style Server fill:#e74c3c,stroke:#c0392b,color:#fff
    style Postgres fill:#336791,stroke:#264d73,color:#fff
    style Redis fill:#dc382d,stroke:#a91d1d,color:#fff
    style MLflow fill:#0194e2,stroke:#016bad,color:#fff
```

## Container Details

| Container | Technology | Port | Purpose |
|-----------|------------|------|---------|
| **Gateway** | nginx:alpine | 80, 443, 8080 | Reverse proxy, SSL termination, rate limiting, MT5 TCP proxy |
| **Dashboard** | React 18 + Vite + TypeScript | 80 (internal) | Web UI for experiments, models, trading, performance |
| **API** | FastAPI + Python 3.11 | 8000 | REST API, WebSocket channels, Clerk auth integration |
| **Trading Server** | Python 3.11 | 8080 (internal) | MT5 connection management, experiment runner, DRL training |
| **PostgreSQL** | TimescaleDB (PG 16) | 5432 | Time-series data, experiments, models, accounts |
| **Redis** | Redis 7 Alpine | 6379 | Celery broker, pub/sub alerts, caching |
| **MLflow** | MLflow 2.10 | 5000 | Experiment tracking, model registry, artifacts |
| **Prometheus** | Prometheus | 9090 | Metrics collection and alerting |
| **Grafana** | Grafana | 3000 | Monitoring dashboards |
| **Airflow Webserver** | Apache Airflow 2.8 | 8081 | DAG management UI |
| **Airflow Scheduler** | Apache Airflow 2.8 | - | DAG scheduling |
| **Airflow Worker** | Apache Airflow 2.8 + Celery | - | Task execution |

## Communication Protocols

| From | To | Protocol | Description |
|------|-----|----------|-------------|
| Gateway → Dashboard | HTTP | Static file serving, SPA routing |
| Gateway → API | HTTP | REST API proxying with /api prefix |
| Gateway → Server | TCP Stream | MT5 EA connection proxying |
| Dashboard → API | HTTP/WSS | REST calls and WebSocket subscriptions |
| API → Server | TCP Socket | Internal trading server communication |
| API/Server → Postgres | PostgreSQL | Primary data persistence |
| API/Server → Redis | Redis Protocol | Pub/sub for real-time alerts |
| Server → MLflow | HTTP | Experiment logging, model artifacts |
| Airflow → Redis | Redis/Celery | Task queue and results |

## Volume Mounts

| Service | Volume | Purpose |
|---------|--------|---------|
| Postgres | `postgres_data` | Persistent database storage |
| MLflow | `mlflow_data` | Experiment data and artifacts |
| Redis | `redis_data` | Persistent message queue |
| Prometheus | `prometheus_data` | Metrics time-series data |
| Grafana | `grafana_data` | Dashboard configurations |
| Trading Server | `./logs`, `./models` | Log files and model checkpoints |

## Assumptions
- **None** - All containers verified in `docker-compose.yml`
