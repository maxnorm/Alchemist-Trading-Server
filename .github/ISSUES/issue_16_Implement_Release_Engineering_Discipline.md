Implement Release Engineering Discipline

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, release-engineering, deployment, P0
Milestone: Phase 4 - Release Engineering
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #16: Implement Release Engineering Discipline

## Problem Statement

Currently, there's no "last green build" discipline or release process. We need:
- Tagged releases from last green build
- Release notes
- Release validation
- Rollback procedures

Without release engineering, we cannot safely promote to production.

## Proposed Solution

1. **Create Release Process:**
   - File: `.github/workflows/release.yml`
   - Trigger: Manual workflow dispatch or tag push
   - Steps:
     - Run full test suite
     - Build Docker images
     - Tag release: `v{version}`
     - Generate release notes
     - Create GitHub release

2. **Create Release Script:**
   - File: `scripts/create-release.sh`
   - Steps:
     - Verify tests pass
     - Bump version (semver)
     - Create git tag
     - Push tag
     - Generate changelog

3. **Create Release Notes Template:**
   - File: `.github/release-notes-template.md`
   - Include: Features, fixes, breaking changes

4. **Document Release Process:**
   - Update `docs/DEPLOYMENT_GUIDE.md`

## Metadata

- **Effort:** M (5 story points)
- **Dependencies:** None
- **Owner Role:** DevOps / Release Engineering
