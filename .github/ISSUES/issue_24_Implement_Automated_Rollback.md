Implement Automated Rollback

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: reliability, P0, production-blocker, deployment, cicd
Milestone: M1 - Observable & Recoverable
Projects: 

---

## Issue #24: Implement Automated Rollback

## Problem Statement

The Production Readiness Report identifies that rollback is a manual process taking 10-15 minutes during incidents. There is no automated rollback script in the repository, and no one-command recovery. This increases MTTR and risk of human error during high-stress incident response.

**Report Section:** "Blocker 3: No Automated Rollback ❌ CRITICAL" (lines 725-748)

## Evidence

- **Report section:** "Blocker 3: No Automated Rollback ❌ CRITICAL" (lines 725-748)
- **Repo evidence:** No rollback script in repository
- **Repo evidence:** `docs/PRD_COMPLETE.md:3154-3207` - Manual rollback script documented but not in repo

## Scope (Do / Don't)

**Do:**
- Create `scripts/rollback.sh` script
- Implement version tagging strategy in CI
- Add rollback to CI/CD pipeline (GitHub Actions)
- Test rollback procedure in staging
- Document rollback runbook

**Don't:**
- Rollback without backup verification
- Skip testing in staging

## Implementation Notes

- Script should: checkout previous version tag, rebuild images, restart services, verify health
- Integrate with GitHub Actions workflow
- Support rollback to specific version: `./scripts/rollback.sh production v1.1.0`
- Add pre-rollback checks (backup exists, health status)

## Acceptance Criteria (TESTABLE)

- [ ] Rollback script exists (`scripts/rollback.sh`)
- [ ] One-command rollback: `./scripts/rollback.sh production v1.2.0`
- [ ] Rollback completes in < 2 minutes
- [ ] Service healthy after rollback (health check passes)
- [ ] Rollback tested in staging environment
- [ ] Rollback runbook documented

## Verification Plan

**Commands to run:**
```bash
# Test rollback in staging
./scripts/rollback.sh staging v1.1.0
# Should complete in < 2 minutes

# Verify health after rollback
curl http://staging-gateway/health
# Should return 200 OK
```

**Expected outputs/signals:**
- Rollback completes successfully
- Services restart with previous version
- Health checks pass
- No data loss

**Rollback/disable plan:**
- Manual rollback procedure documented as fallback

## Definition of Done (DoD)

- [ ] Code reviewed
- [ ] Tests updated/added (rollback script tests)
- [ ] Docs/runbook updated (rollback procedure)
- [ ] Observability added/updated (rollback events logged)
- [ ] Verified in staging (rollback tested and working)

## Dependencies

- **Blocks:** M1 milestone completion
- **Blocked by:** None

## Metadata

- **Effort:** M (3-4 days)
- **Owner Role:** DevOps / Release Engineering
