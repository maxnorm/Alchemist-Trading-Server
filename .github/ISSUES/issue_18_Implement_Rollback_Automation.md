Implement Rollback Automation

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, deployment, safety, P0
Milestone: Phase 4 - Release Engineering
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #18: Implement Rollback Automation

## Problem Statement

While PRD describes rollback procedures, there's no automated rollback. We need:
- Automated rollback on deployment failure
- Rollback to previous release
- Database migration rollback
- State verification after rollback

## Proposed Solution

1. **Create Rollback Script:**
   - File: `scripts/rollback.sh`
   - Steps:
     - Identify previous release
     - Stop current services
     - Restore previous Docker images
     - Rollback database migrations (if needed)
     - Start services
     - Verify health

2. **Integrate with Promotion Workflow:**
   - Auto-rollback on health check failure
   - Auto-rollback on smoke test failure

3. **Create Rollback Runbook:**
   - File: `docs/runbooks/rollback.md`
   - Procedures for manual rollback

4. **Add Rollback API Endpoint:**
   - `POST /api/v1/deployment/rollback` - Trigger rollback

## Metadata

- **Effort:** M (5 story points)
- **Dependencies:** Issue #15 (release process)
- **Owner Role:** DevOps
