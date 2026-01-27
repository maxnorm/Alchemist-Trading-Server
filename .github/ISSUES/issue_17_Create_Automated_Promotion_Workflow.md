Create Automated Promotion Workflow from Staging to Production

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, deployment, ci-cd, P0
Milestone: Phase 4 - Release Engineering
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #17: Create Automated Promotion Workflow from Staging to Production

## Problem Statement

No automated promotion workflow exists for staging→production. We need:
- Automated promotion from staging to production
- Release gates (tests, health checks)
- Manual approval gates
- Rollback on failure

## Proposed Solution

1. **Create Promotion Workflow:**
   - File: `.github/workflows/promote-production.yml`
   - Trigger: Manual workflow dispatch with release tag
   - Steps:
     - Verify staging health (7 days)
     - Run smoke tests
     - Manual approval gate
     - Deploy to production
     - Health checks
     - Rollback on failure

2. **Create Promotion Script:**
   - File: `scripts/promote-to-production.sh`
   - Steps:
     - Verify staging status
     - Run pre-deployment checks
     - Deploy to production
     - Post-deployment validation

3. **Create Go/No-Go Checklist:**
   - File: `docs/go-no-go-checklist.md`
   - Include: Health checks, test results, approvals

4. **Integrate with Release Process:**
   - Link promotion to release tags

## Metadata

- **Effort:** L (8 story points)
- **Dependencies:** Issues #1, #15 (staging environment and release process)
- **Owner Role:** DevOps / Release Engineering
