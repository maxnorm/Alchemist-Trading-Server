Implement HTTPS/TLS for Gateway

<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->

Assignees: 
Labels: security, P0, production-blocker, gateway, deploy
Milestone: M3 - Alpha Deploy Ready
Projects: 

---

## Issue #22: Implement HTTPS/TLS for Gateway

## Problem Statement

The Production Readiness Report identifies that the gateway serves HTTP only (port 80), with no SSL termination. All traffic, including authentication tokens, is transmitted unencrypted. This is a critical security vulnerability that fails compliance requirements (PCI-DSS, SOC 2, GDPR) and exposes credentials to interception.

**Report Section:** "Blocker 1: No HTTPS/TLS ❌ CRITICAL" (lines 669-693)

## Evidence

- **Report section:** "Blocker 1: No HTTPS/TLS ❌ CRITICAL" (lines 669-693)
- **Repo evidence:** `src/gateway/conf.d/default.conf:5-6` - `listen 80`, port 443 commented
- **Repo evidence:** `docker-compose.yml:10` - Port 443 exposed but unused

## Scope (Do / Don't)

**Do:**
- Generate/obtain SSL certificates (Let's Encrypt, AWS ACM, or cloud provider)
- Configure Nginx SSL termination on port 443
- Add HTTP → HTTPS redirect
- Update CORS origins to HTTPS
- Test certificate renewal process

**Don't:**
- Use self-signed certificates for production
- Skip certificate renewal automation
- Expose HTTP port without redirect

## Implementation Notes

- Use Let's Encrypt for cost-effective certificates, or cloud provider ACM for managed certificates
- Configure certificate auto-renewal
- Update gateway config to serve HTTPS and redirect HTTP
- Update API CORS configuration to accept HTTPS origins

## Acceptance Criteria (TESTABLE)

- [ ] Gateway serves HTTPS on port 443
- [ ] HTTP requests redirect to HTTPS (301/302)
- [ ] Valid SSL certificate (not self-signed, not expired)
- [ ] All API endpoints accessible via HTTPS
- [ ] Dashboard connects via HTTPS without certificate errors
- [ ] Certificate renewal process documented

## Verification Plan

**Commands to run:**
```bash
curl -I https://your-domain.com/api/health
curl -I http://your-domain.com/api/health  # Should redirect
openssl s_client -connect your-domain.com:443 -servername your-domain.com
```

**Expected outputs/signals:**
- HTTPS returns 200 OK with valid certificate
- HTTP redirects to HTTPS (301 or 302)
- Certificate chain valid, not expired

**Rollback/disable plan:**
- Revert gateway config to HTTP-only
- Update CORS to allow HTTP origins

## Definition of Done (DoD)

- [ ] Code reviewed
- [ ] Tests updated/added (HTTPS connectivity tests)
- [ ] Docs/runbook updated (certificate renewal procedure)
- [ ] Observability added/updated (certificate expiry monitoring)
- [ ] Verified in staging (HTTPS works, redirect works)

## Dependencies

- **Blocks:** M3 milestone completion
- **Blocked by:** None

## Metadata

- **Effort:** M (3-4 days)
- **Owner Role:** DevOps / Security
