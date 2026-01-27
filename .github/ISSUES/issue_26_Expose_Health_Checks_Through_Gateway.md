Expose Health Checks Through Gateway

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: observability, P0, production-blocker, gateway, deploy
Milestone: M1 - Observable & Recoverable
Projects: 

---

## Issue #26: Expose Health Checks Through Gateway

## Problem Statement

The Production Readiness Report identifies that health check endpoints are internal-only. The gateway and load balancers cannot verify service health, preventing proper traffic routing and external monitoring.

**Report Section:** "Blocker 5: Health Checks Not Exposed ⚠️ HIGH" (lines 777-800)

## Evidence

- **Report section:** "Blocker 5: Health Checks Not Exposed ⚠️ HIGH" (lines 777-800)
- **Repo evidence:** `src/gateway/conf.d/default.conf:50-52` - Health endpoints removed with comment "Health endpoints are now internal-only"
- **Repo evidence:** `src/api/src/routers/health.py:18-21` - Health endpoint exists but not routed through gateway

## Scope (Do / Don't)

**Do:**
- Add health check route to gateway (with IP whitelist or authentication)
- Expose `/health` and `/gateway/health` endpoints
- Configure load balancer health checks
- Add authentication or IP whitelist for security

**Don't:**
- Expose health checks without authentication/whitelist
- Expose sensitive information in health responses

## Implementation Notes

- Add route in `src/gateway/conf.d/default.conf` for `/health` and `/gateway/health`
- Use IP whitelist for monitoring tools, or basic auth
- Aggregate health from multiple services if needed
- Keep detailed health checks internal-only

## Acceptance Criteria (TESTABLE)

- [ ] `/health` accessible through gateway
- [ ] `/gateway/health` returns gateway status
- [ ] Returns 200 OK when healthy, non-200 when unhealthy
- [ ] IP whitelist or authentication configured
- [ ] Load balancer health checks configured
- [ ] Health endpoint tested from external tools

## Verification Plan

**Commands to run:**
```bash
curl http://gateway/health
# Should return 200 OK with health status

curl http://gateway/gateway/health
# Should return 200 OK
```

**Expected outputs/signals:**
- Health endpoints return 200 when services healthy
- Health endpoints return non-200 when services unhealthy
- IP whitelist blocks unauthorized access

**Rollback/disable plan:**
- Remove health routes from gateway config

## Definition of Done (DoD)

- [ ] Code reviewed
- [ ] Tests updated/added (health check routing tests)
- [ ] Docs/runbook updated (health check configuration)
- [ ] Observability added/updated (health check metrics)
- [ ] Verified in staging (health checks accessible, load balancer configured)

## Dependencies

- **Blocks:** M1 milestone completion
- **Blocked by:** None

## Metadata

- **Effort:** S (2-3 hours)
- **Owner Role:** DevOps / Observability
