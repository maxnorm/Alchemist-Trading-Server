Create Staging Environment with Production Parity

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, infra, deployment, P0
Milestone: Phase 1 - Foundation
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #1: Create Staging Environment with Production Parity

## Problem Statement

Currently, only production `docker-compose.yml` exists. There's no staging environment for:
- Testing changes before production
- Soak testing data collection
- Validating deployment procedures
- Training operators

Without staging, we cannot safely test changes or validate Gate A prerequisites.

## Proposed Solution

1. **Create Staging Docker Compose:**
   - File: `docker-compose.staging.yml`
   - Base on `docker-compose.yml` with modifications:
     - Different database name: `db_forex_staging`
     - Different volume names (staging-specific)
     - Reduced resource limits (for testing)
     - Optional: Use different MT5 demo account

2. **Create Staging Environment Variables:**
   - File: `.env.staging`
   - Staging-specific config:
     - `DB_NAME=db_forex_staging`
     - `ENVIRONMENT=staging`
     - Different log levels (DEBUG for staging)

3. **Create Staging Deployment Script:**
   - File: `scripts/deploy-staging.sh`
   - Steps:
     - Build images
     - Run migrations
     - Start services
     - Health checks
     - Smoke tests

4. **Create GitHub Workflow:**
   - File: `.github/workflows/deploy-staging.yml`
   - Trigger: Push to `develop` branch
   - Steps: Build, test, deploy to staging

5. **Document Staging Procedures:**
   - Update `docs/DEPLOYMENT_GUIDE.md`

## Metadata

- **Effort:** M (5 story points)
- **Dependencies:** None
- **Owner Role:** DevOps
