Create GitHub Actions Workflow for Staging Deployments

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, ci-cd, deployment, P0
Milestone: Phase 1 - Foundation
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #3: Create GitHub Actions Workflow for Staging Deployments

## Problem Statement

There is no automated way to deploy to staging. Manual deployments are error-prone and slow down development cycles.

## Proposed Solution

1. **Create Staging Deployment Workflow:**
   - File: `.github/workflows/deploy-staging.yml`
   - Triggers on push to `develop` branch
   - Steps:
     - Build Docker images
     - Run database migrations
     - Deploy to staging
     - Run smoke tests
     - Send notification on success/failure

2. **Add Staging Environment Secrets:**
   - Configure GitHub environment secrets for staging

3. **Document Deployment Process:**
   - Update `docs/DEPLOYMENT_GUIDE.md`

## Metadata

- **Effort:** M (3 story points)
- **Dependencies:** Issue #1 (Staging Environment)
- **Owner Role:** DevOps
