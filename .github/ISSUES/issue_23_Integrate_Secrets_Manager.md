Integrate Secrets Manager

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: security, P0, production-blocker, infrastructure, deploy
Milestone: M3 - Alpha Deploy Ready
Projects: 

---

## Issue #23: Integrate Secrets Manager

## Problem Statement

The Production Readiness Report identifies that all secrets (DB passwords, Clerk keys, MT5 encryption keys) are stored in `.env` file or docker-compose environment variables. There is no integration with a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.), no rotation mechanism, and secrets are at risk of being committed to version control.

**Report Section:** "Blocker 2: Secrets in Environment Variables ❌ CRITICAL" (lines 696-722)

## Evidence

- **Report section:** "Blocker 2: Secrets in Environment Variables ❌ CRITICAL" (lines 696-722)
- **Repo evidence:** `docker-compose.yml:68-85` - Secrets in `environment:` section
- **Repo evidence:** `src/api/src/config.py:57-60` - Clerk keys from env
- **Repo evidence:** `src/trading_server/src/infrastructure/security/credential_manager.py:22-24` - MT5 encryption key from env

## Scope (Do / Don't)

**Do:**
- Choose secrets manager (AWS Secrets Manager recommended, or Vault/GCP Secret Manager)
- Migrate all secrets to secrets manager (DB password, Clerk keys, MT5 encryption key, Airflow Fernet key, etc.)
- Update config classes to fetch from secrets manager at startup
- Remove secrets from docker-compose and .env files
- Implement secret rotation mechanism
- Add secret scanning to CI to detect leaks

**Don't:**
- Store secrets in code or version control
- Skip rotation mechanism
- Hardcode fallback secrets

## Implementation Notes

- Use cloud provider secrets manager (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault) or HashiCorp Vault
- Fetch secrets at application startup, cache in memory
- Update `src/api/src/config.py` and `src/trading_server/src/infrastructure/security/credential_manager.py`
- Add boto3/azure-keyvault/google-cloud-secret-manager dependency
- Create secrets migration script

**Note:** This issue is blocked by Issue #15 (Cloud Provider Decision) - need to know which cloud provider before choosing secrets manager.

## Acceptance Criteria (TESTABLE)

- [ ] All secrets in secrets manager (DB password, Clerk keys, MT5 encryption key, Airflow Fernet key)
- [ ] No secrets in docker-compose.yml or .env files (only variable names)
- [ ] Secrets fetched at startup (log success message)
- [ ] Secret rotation mechanism implemented (documented procedure)
- [ ] CI scans for secrets (fails build if secrets detected)
- [ ] Application starts successfully with secrets from manager

## Verification Plan

**Commands to run:**
```bash
# Verify no secrets in code
grep -ri "password.*=" docker-compose.yml src/ | grep -v "DB_PASSWORD=" | grep -v "PASSWORD="
# Should return no matches

# Verify secrets loaded
docker logs api | grep "Secrets loaded"
# Should show success message

# Test secret rotation
# Rotate secret in manager, restart service, verify new secret used
```

**Expected outputs/signals:**
- No secrets found in code/config files
- Application logs show "Secrets loaded from [manager]"
- Services start successfully

**Rollback/disable plan:**
- Revert to environment variables temporarily
- Document manual secret injection process

## Definition of Done (DoD)

- [ ] Code reviewed
- [ ] Tests updated/added (secrets manager integration tests)
- [ ] Docs/runbook updated (secrets rotation procedure)
- [ ] Observability added/updated (secret fetch failures logged)
- [ ] Verified in staging (secrets loaded from manager)

## Dependencies

- **Blocks:** M3 milestone completion
- **Blocked by:** Issue #15 (Cloud Provider Decision)

## Metadata

- **Effort:** L (5-7 days)
- **Owner Role:** DevOps / Security
