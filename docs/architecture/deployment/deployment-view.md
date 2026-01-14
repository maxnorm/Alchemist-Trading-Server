# Deployment View

## Purpose
This document answers: **How is the Alchemist platform deployed and what runs where?**

## Scope
- **Includes**: Docker Compose topology, environment configurations, secrets management
- **Excludes**: Cloud-specific configurations (AWS, GCP, Azure)

## Source of Truth References
| Element | Evidence Path |
|---------|---------------|
| Docker Compose | `docker-compose.yml` |
| Gateway Config | `src/gateway/nginx.conf`, `src/gateway/conf.d/` |
| Prometheus Config | `src/monitoring/prometheus/prometheus.yml` |
| Grafana Provisioning | `src/monitoring/grafana/provisioning/` |
| Database Scripts | `src/database/scripts/` |
| Dockerfiles | `src/api/Dockerfile`, `src/trading_server/Dockerfile`, `src/dashboard/Dockerfile` |

## Deployment Diagram

```mermaid
flowchart TB
    subgraph Internet["🌐 Internet"]
        Users["Users<br/>(Browser)"]
        MT5["MT5 Terminals<br/>(Expert Advisors)"]
    end

    subgraph DockerHost["🐳 Docker Host"]
        subgraph Gateway["Gateway (nginx:alpine)"]
            Nginx["nginx<br/>:80, :443, :8080"]
        end

        subgraph Frontend["Frontend"]
            Dashboard["dashboard<br/>(React + nginx)"]
        end

        subgraph Backend["Backend Services"]
            API["api<br/>(FastAPI)<br/>:8000 internal"]
            Server["server<br/>(Trading Server)<br/>:8080 internal"]
        end

        subgraph DataPipeline["Data Pipeline"]
            AirflowWeb["airflow-webserver<br/>:8081 external"]
            AirflowSched["airflow-scheduler"]
            AirflowWorker["airflow-worker"]
        end

        subgraph MLOps["MLOps"]
            MLflow["mlflow<br/>:5000 internal"]
        end

        subgraph Monitoring["Monitoring"]
            Prometheus["prometheus<br/>:9090 internal"]
            Grafana["grafana<br/>:3000 internal"]
        end

        subgraph DataStores["Data Stores"]
            Postgres[("postgres<br/>(TimescaleDB)<br/>:5432")]
            Redis[("redis<br/>:6379")]
        end

        subgraph Volumes["Named Volumes"]
            PGData[("postgres_data")]
            RedisData[("redis_data")]
            MLflowData[("mlflow_data")]
            PromData[("prometheus_data")]
            GrafanaData[("grafana_data")]
            BackupData[("backup_data")]
        end
    end

    %% External connections
    Users -->|"HTTPS :80"| Nginx
    MT5 -->|"TCP :8080"| Nginx

    %% Gateway routing
    Nginx -->|"/"| Dashboard
    Nginx -->|"/api/*"| API
    Nginx -->|"/grafana"| Grafana
    Nginx -->|"TCP stream"| Server

    %% Service dependencies
    Dashboard -.->|"depends_on"| API
    API -.->|"depends_on"| Postgres
    API -.->|"depends_on"| MLflow
    API -.->|"depends_on"| Redis
    Server -.->|"depends_on"| Postgres
    Server -.->|"depends_on"| Redis
    MLflow -.->|"depends_on"| MLflowData
    AirflowWeb -.->|"depends_on"| Postgres
    AirflowWeb -.->|"depends_on"| Redis
    Prometheus -.->|"depends_on"| API
    Grafana -.->|"depends_on"| Prometheus

    %% Volume mounts
    Postgres --- PGData
    Redis --- RedisData
    MLflow --- MLflowData
    Prometheus --- PromData
    Grafana --- GrafanaData

    style Nginx fill:#27ae60,stroke:#229954,color:#fff
    style Dashboard fill:#3498db,stroke:#2980b9,color:#fff
    style API fill:#9b59b6,stroke:#8e44ad,color:#fff
    style Server fill:#e74c3c,stroke:#c0392b,color:#fff
    style Postgres fill:#336791,stroke:#264d73,color:#fff
    style Redis fill:#dc382d,stroke:#a91d1d,color:#fff
```

## What Runs Where Table

| Service | Container Name | Image | Ports Exposed | Volumes | Replicas |
|---------|----------------|-------|---------------|---------|----------|
| **Gateway** | gateway | nginx:alpine | 80, 443, 8080 | `./src/gateway/`, `./logs/gateway/` | 1 |
| **Dashboard** | dashboard | Custom (React+nginx) | - (internal 80) | - | 1 |
| **API** | api | Custom (FastAPI) | - (internal 8000) | `./logs/` | 1 |
| **Trading Server** | server | Custom (Python) | - (internal 8080) | `./logs/`, `./models/` | 1 |
| **PostgreSQL** | postgres | timescale/timescaledb:latest-pg16 | 5432 (dev only) | `postgres_data` | 1 |
| **Redis** | redis | redis:7-alpine | - (internal 6379) | `redis_data` | 1 |
| **MLflow** | mlflow | ghcr.io/mlflow/mlflow:v2.10.0 | - (internal 5000) | `mlflow_data` | 1 |
| **Prometheus** | prometheus | prom/prometheus:latest | - (internal 9090) | `prometheus_data` | 1 |
| **Grafana** | grafana | grafana/grafana:latest | - (internal 3000) | `grafana_data` | 1 |
| **Airflow Webserver** | airflow-webserver | apache/airflow:2.8.0 | 8081 | `./airflow_logs/` | 1 |
| **Airflow Scheduler** | airflow-scheduler | apache/airflow:2.8.0 | - | `./airflow_logs/` | 1 |
| **Airflow Worker** | airflow-worker | apache/airflow:2.8.0 | - | `./airflow_logs/` | 1 |
| **Backup** | db_backup | postgres:16 | - | `backup_data` | On-demand |

## Environment Configurations

### Development Environment

```bash
# Exposed ports for development
- Postgres: 5432 (direct access)
- Airflow: 8081 (web UI)
- All services: localhost access

# Debug settings
LOG_LEVEL=DEBUG
```

### Production Environment

```bash
# Only gateway exposed
- Gateway: 80, 443, 8080
- All other services: internal only

# Security
- Remove Postgres port exposure
- Enable HTTPS on gateway
- Rotate secrets regularly
```

## Port Mapping Summary

| External Port | Service | Protocol | Purpose |
|---------------|---------|----------|---------|
| **80** | Gateway → Dashboard/API | HTTP/HTTPS | Web access |
| **443** | Gateway | HTTPS | Secure web (future) |
| **8080** | Gateway → Server | TCP | MT5 EA connections |
| **8081** | Airflow (direct) | HTTP | Airflow UI |
| **5432** | Postgres (dev only) | PostgreSQL | Direct DB access |

## Network Topology

```mermaid
flowchart LR
    subgraph External["External Network"]
        Browser["Browser"]
        MT5EA["MT5 EA"]
    end

    subgraph DockerNetwork["Docker Bridge Network (default)"]
        Gateway["gateway"]
        Dashboard["dashboard"]
        API["api"]
        Server["server"]
        Postgres["postgres"]
        Redis["redis"]
        MLflow["mlflow"]
        Prometheus["prometheus"]
        Grafana["grafana"]
    end

    Browser -->|":80"| Gateway
    MT5EA -->|":8080"| Gateway
    
    Gateway -->|":80"| Dashboard
    Gateway -->|":8000"| API
    Gateway -->|":3000"| Grafana
    Gateway -->|":8080"| Server
    
    API -->|":5432"| Postgres
    API -->|":6379"| Redis
    API -->|":5000"| MLflow
    
    Server -->|":5432"| Postgres
    Server -->|":6379"| Redis
    
    Prometheus -->|":8000"| API
    Prometheus -->|":8080"| Server
    
    Grafana -->|":9090"| Prometheus
```

## Health Checks

| Service | Health Check Command | Interval | Timeout | Retries |
|---------|---------------------|----------|---------|---------|
| Gateway | `wget --spider http://127.0.0.1/gateway/health` | 30s | 10s | 3 |
| API | `curl -f http://127.0.0.1:8000/health` | 30s | 10s | 5 |
| Dashboard | `wget --spider http://127.0.0.1/health` | 30s | 10s | 3 |
| Postgres | `pg_isready -U $DB_USER -d $DB_NAME` | 10s | 5s | 5 |
| Redis | `redis-cli ping` | 10s | 5s | 5 |
| MLflow | Python urllib check | 30s | 10s | 3 |
| Prometheus | `wget --spider http://127.0.0.1:9090/-/healthy` | 30s | 10s | 3 |
| Grafana | `wget --spider http://localhost:3000/api/health` | 30s | 10s | 3 |
| Airflow | `curl --fail http://localhost:8081/health` | 30s | 10s | 5 |

## Startup Order (Dependency Chain)

```mermaid
flowchart LR
    Postgres --> Redis --> MLflow --> API --> Dashboard --> Gateway
    Postgres --> Redis --> Server
    Postgres --> Redis --> AirflowWeb --> AirflowScheduler --> AirflowWorker
    API --> Prometheus --> Grafana
```

1. **Postgres** - Database must be healthy first
2. **Redis** - Message broker for Celery
3. **MLflow** - Experiment tracking (can fail gracefully)
4. **API** - REST API and WebSocket
5. **Server** - Trading server
6. **Dashboard** - Frontend (depends on API)
7. **Gateway** - Entry point (depends on Dashboard, API)
8. **Prometheus** - Metrics collection (depends on API)
9. **Grafana** - Dashboards (depends on Prometheus)
10. **Airflow** - Data pipelines (depends on Postgres, Redis)

## Volume Management

### Persistent Volumes
```yaml
volumes:
  postgres_data:    # Database files
  backup_data:      # Database backups
  mlflow_data:      # MLflow experiments and artifacts
  prometheus_data:  # Metrics time-series
  grafana_data:     # Dashboard configurations
  redis_data:       # Redis persistence (AOF)
```

### Bind Mounts
```yaml
- ./logs:/app/logs              # Application logs (both API and Server)
- ./models:/app/models          # Model checkpoints
- ./src/gateway/:/etc/nginx/    # Nginx configuration
- ./src/database/scripts/:/docker-entrypoint-initdb.d/  # DB init scripts
```

## Secrets Management

| Secret | Location | Usage |
|--------|----------|-------|
| `DB_PASSWORD` | `.env` | Database password |
| `CLERK_SECRET_KEY` | `.env` | Clerk API authentication |
| `STREAMER_AUTH_TOKEN` | `.env` | MT5 tick streamer auth |
| `AIRFLOW_FERNET_KEY` | `.env` | Airflow encryption |
| `GF_SECURITY_ADMIN_PASSWORD` | `.env` | Grafana admin |

### Production Recommendations
1. Use Docker secrets or external secret manager
2. Never commit `.env` to version control
3. Rotate secrets regularly
4. Use different secrets per environment

## Scaling Considerations

| Service | Scalable? | Notes |
|---------|-----------|-------|
| Gateway | ✅ Yes | Load balancer in front |
| Dashboard | ✅ Yes | Stateless, CDN recommended |
| API | ⚠️ Limited | Sticky sessions for WebSocket |
| Server | ❌ No | Single instance required (stateful) |
| Postgres | ⚠️ Limited | Read replicas possible |
| Redis | ✅ Yes | Cluster mode |

## Assumptions
- **None** - All deployment configurations verified in codebase
