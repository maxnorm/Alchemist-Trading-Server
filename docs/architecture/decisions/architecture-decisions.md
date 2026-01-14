# Architecture Decisions Record (ADR)

## Purpose
This document captures key architectural decisions made in the Alchemist platform design.

## ADR-001: Microservices with Docker Compose

### Context
The platform needs to handle multiple concerns: web UI, API, trading logic, ML training, monitoring, and data pipelines.

### Decision
Use Docker Compose with separate containers for each major component rather than a monolithic application.

### Rationale
- **Isolation**: Each service can be developed, tested, and deployed independently
- **Technology choice**: Different services can use optimal technologies (Python for ML, Node for frontend)
- **Scaling**: Individual components can be scaled (though currently single-instance)
- **Development**: Team members can work on services in parallel

### Consequences
- ✅ Clear service boundaries
- ✅ Independent deployment
- ⚠️ Increased operational complexity
- ⚠️ Network latency between services

---

## ADR-002: TimescaleDB for Time-Series Data

### Context
Need to store millions of tick data points with efficient time-range queries.

### Decision
Use TimescaleDB (PostgreSQL extension) as the primary database.

### Rationale
- **Hypertables**: Automatic time-based partitioning
- **Compression**: Native compression for historical data
- **SQL**: Standard PostgreSQL interface
- **Retention policies**: Built-in data lifecycle management

### Consequences
- ✅ Efficient time-series queries
- ✅ Familiar PostgreSQL tooling
- ✅ Good compression ratios
- ⚠️ PostgreSQL-only (not easily portable)

---

## ADR-003: Clerk for Authentication

### Context
Need secure user authentication without building auth infrastructure.

### Decision
Use Clerk as external identity provider rather than custom auth.

### Rationale
- **Security**: Professionally managed auth service
- **Features**: OAuth, MFA, session management out of box
- **Compliance**: SOC 2, GDPR compliant
- **Speed**: Faster development, less code to maintain

### Consequences
- ✅ Secure, production-ready auth
- ✅ Rich features (2FA, social login)
- ⚠️ External dependency
- ⚠️ Cost at scale

---

## ADR-004: MLflow for Experiment Tracking

### Context
Need to track ML experiments, hyperparameters, metrics, and model artifacts.

### Decision
Integrate MLflow for experiment tracking and model registry.

### Rationale
- **Industry standard**: Widely adopted in ML community
- **Model registry**: Built-in versioning and promotion
- **UI**: Web interface for experiment comparison
- **Artifacts**: Stores model files, plots, configs

### Consequences
- ✅ Comprehensive experiment tracking
- ✅ Model versioning
- ✅ Reproducibility metadata
- ⚠️ Additional service to maintain

---

## ADR-005: TCP Socket for MT5 Communication

### Context
MetaTrader 5 Expert Advisors need to communicate with the trading server.

### Decision
Use raw TCP sockets with JSON protocol rather than HTTP/REST.

### Rationale
- **Low latency**: Direct socket connection is fastest
- **Bidirectional**: Server can push trade commands to EA
- **Simplicity**: MQL5 has basic socket support
- **Reliability**: Persistent connection, immediate detection of disconnects

### Consequences
- ✅ Low-latency communication
- ✅ Bidirectional messaging
- ⚠️ Custom protocol maintenance
- ⚠️ No standard tooling (Postman, etc.)

---

## ADR-006: Redis for Message Broker

### Context
Need async task queue (Celery) and real-time pub/sub for alerts.

### Decision
Use Redis as message broker for both Celery and pub/sub.

### Rationale
- **Simplicity**: Single service for multiple uses
- **Performance**: In-memory, very fast
- **Celery support**: First-class Celery broker
- **Pub/Sub**: Native support for real-time events

### Consequences
- ✅ Single broker for multiple purposes
- ✅ Very fast pub/sub
- ⚠️ No message persistence guarantees (AOF helps)
- ⚠️ Not suitable for mission-critical queuing

---

## ADR-007: Airflow for Data Pipelines

### Context
Need scheduled data collection from external sources (FRED, ECB, news).

### Decision
Use Apache Airflow with Celery executor for DAG orchestration.

### Rationale
- **DAG support**: Complex workflow dependencies
- **Monitoring**: Built-in web UI for monitoring
- **Scheduling**: Cron-like scheduling
- **Celery**: Distributed task execution

### Consequences
- ✅ Powerful workflow orchestration
- ✅ Good visibility into pipeline status
- ⚠️ Heavy resource usage (multiple containers)
- ⚠️ Learning curve

---

## ADR-008: WebSocket for Real-Time Updates

### Context
Dashboard needs real-time updates for training metrics, positions, alerts.

### Decision
Use WebSocket channels with channel-based subscriptions.

### Rationale
- **Real-time**: Immediate updates without polling
- **Efficiency**: Single connection, multiple channels
- **Native**: Browser WebSocket API
- **FastAPI**: Built-in WebSocket support

### Consequences
- ✅ Real-time user experience
- ✅ Efficient bandwidth usage
- ⚠️ Connection management complexity
- ⚠️ Sticky sessions for load balancing

---

## ADR-009: Model Lifecycle Stages

### Context
Need controlled progression from trained model to production deployment.

### Decision
Implement stage-based model lifecycle: training → staging → paper → production → archived.

### Rationale
- **Safety**: Mandatory paper trading before production
- **Validation**: Automated checks before promotion
- **Audit**: Clear trail of when/who promoted
- **Rollback**: Easy reversion to previous stage

### Consequences
- ✅ Safe model deployment
- ✅ Clear promotion workflow
- ✅ Audit trail
- ⚠️ Slower path to production (by design)

---

## ADR-010: TOTP for Sensitive Operations

### Context
Critical actions (kill switch, production promotion) need extra protection.

### Decision
Require TOTP (Time-based One-Time Password) verification for sensitive operations.

### Rationale
- **Security**: Second factor beyond session auth
- **Deliberate action**: Forces user to confirm intent
- **Standard**: Compatible with Google Authenticator, etc.
- **Audit**: Log shows 2FA was used

### Consequences
- ✅ Strong protection for critical actions
- ✅ Compliance-friendly
- ⚠️ Additional user friction
- ⚠️ Recovery procedures needed if phone lost

---

## ADR-011: Connector Pattern for Data Sources

### Context
Need to integrate multiple data sources with consistent interface.

### Decision
Implement `IDataSourceConnector` interface with `stream()`, `batch()`, `backfill()` methods.

### Rationale
- **Extensibility**: Easy to add new data sources
- **Consistency**: All sources have same interface
- **Testing**: Easy to mock connectors
- **Discovery**: Registry enables feature catalog

### Consequences
- ✅ Clean abstraction
- ✅ Easy to add sources
- ✅ Testable
- ⚠️ Some sources may not fit pattern perfectly

---

## ADR-012: nginx as API Gateway

### Context
Need single entry point for HTTP, WebSocket, and TCP traffic.

### Decision
Use nginx as reverse proxy and TCP stream proxy.

### Rationale
- **Performance**: Highly optimized for proxying
- **Features**: Rate limiting, SSL termination, routing
- **Stream support**: Can proxy TCP for MT5
- **Lightweight**: Alpine image is small

### Consequences
- ✅ Single entry point
- ✅ SSL termination
- ✅ Rate limiting
- ⚠️ Additional configuration to maintain

---

## Open Questions / Future Considerations

1. **Kubernetes migration**: Current Docker Compose works but consider k8s for production scale
2. **Read replicas**: PostgreSQL read replicas for analytics workloads
3. **Model serving**: Consider dedicated model serving (TensorFlow Serving, Triton)
4. **Feature store**: Consider dedicated feature store (Feast) as features grow
5. **Secrets management**: Move from .env to proper secrets manager (Vault, AWS Secrets Manager)

## Assumptions
- **None** - All decisions are based on verified codebase implementation
