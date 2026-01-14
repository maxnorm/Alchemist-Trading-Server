Configure CPU and Memory Limits for Training Jobs

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: mvp-blocker, mlops, infra, P0
Milestone: Gate B - Live Training
Projects: 


<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->

---

## Issue #13: Configure CPU and Memory Limits for Training Jobs

## Problem Statement

Training jobs can consume unlimited resources, leading to system instability and resource contention. We need to enforce resource limits per training job.

## Proposed Solution

1. **Add Resource Limits to Training Container:**
   - Update `docker-compose.yml` for training services
   - CPU: 4 cores per training job
   - Memory: 8GB per training job
   - GPU: If available, 1 GPU per job

2. **Configure Docker Compose Resource Limits:**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '4'
         memory: 8G
   ```

3. **Add Monitoring for Resource Usage:**
   - Prometheus metrics for CPU/memory usage
   - Alert if resource usage exceeds limits

4. **Document Resource Requirements:**
   - Update `docs/DEPLOYMENT_GUIDE.md`

5. **Test Resource Limits:**
   - Run training job and verify limits enforced

## Metadata

- **Effort:** S (2 story points)
- **Dependencies:** None
- **Owner Role:** MLOps / DevOps
