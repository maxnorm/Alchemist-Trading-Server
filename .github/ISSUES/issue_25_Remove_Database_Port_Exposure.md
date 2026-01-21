Remove Database Port Exposure

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: security, P0, production-blocker, database, deploy
Milestone: M3 - Alpha Deploy Ready
Projects: 

---

## Issue #25: Remove Database Port Exposure

## Problem Statement

The Production Readiness Report identifies that PostgreSQL port 5432 is exposed to the host in docker-compose, creating a security vulnerability. The database should only be accessible via the internal Docker network.

**Report Section:** "Blocker 4: Database Port Exposed ❌ CRITICAL" (lines 752-773)

## Evidence

- **Report section:** "Blocker 4: Database Port Exposed ❌ CRITICAL" (lines 752-773)
- **Repo evidence:** `docker-compose.yml:35` - `ports: - "5432:5432"` with comment "REMOVE THIS LINE FOR PRODUCTION"

## Scope (Do / Don't)

**Do:**
- Remove port mapping from production docker-compose
- Use internal Docker network only
- Document admin access via SSH tunnel if needed
- Keep port mapping in development docker-compose for local access

**Don't:**
- Remove port mapping without documenting admin access
- Expose port without firewall rules

## Implementation Notes

- Create `docker-compose.prod.yml` without port mapping
- Or use environment-specific compose files
- Document SSH tunnel procedure for database admin access

## Acceptance Criteria (TESTABLE)

- [ ] Port 5432 not exposed in production docker-compose
- [ ] Database accessible only via internal network (from containers)
- [ ] Admin access documented (SSH tunnel procedure)
- [ ] Development docker-compose still allows local access (if needed)

## Verification Plan

**Commands to run:**
```bash
# From host, should fail
nc -zv localhost 5432
# Connection refused

# From container, should work
docker exec -it postgres psql -U forex_user -d db_forex
# Connects successfully
```

**Expected outputs/signals:**
- Port 5432 not accessible from host
- Database accessible from containers
- SSH tunnel works for admin access

**Rollback/disable plan:**
- Re-add port mapping temporarily if needed

## Definition of Done (DoD)

- [ ] Code reviewed
- [ ] Tests updated/added (network isolation tests)
- [ ] Docs/runbook updated (admin access procedure)
- [ ] Observability added/updated (connection monitoring)
- [ ] Verified in staging (port not exposed, internal access works)

## Dependencies

- **Blocks:** M3 milestone completion
- **Blocked by:** None

## Metadata

- **Effort:** S (1 hour)
- **Owner Role:** DevOps / Security
