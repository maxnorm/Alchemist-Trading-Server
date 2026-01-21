---
name: Week 10 Model Promotion Automation
overview: Implement CI/CD integration for automated model promotion with gates, enhance the promotion workflow with automated validation, and create comprehensive integration tests for the promotion pipeline.
todos:
  - id: week10_cicd_workflow
    content: Create .github/workflows/model_promotion.yml with automated promotion gates for staging, paper, and production stages
    status: pending
  - id: week10_promotion_scripts
    content: Create promotion scripts (auto_promote_to_staging.py, validate_staging_metrics.py, promote_to_paper.py, validate_paper_trading.py, promote_to_production.py)
    status: pending
  - id: week10_enhance_promoter
    content: Enhance ModelPromoter class with auto_promote_to_staging(), validate_for_paper(), verify_paper_trading_results(), and get_promotion_status() methods
    status: pending
  - id: week10_2fa_integration
    content: Enhance 2FA integration with secure token handling, expiration, and audit logging in model_promoter.py and model_service.py
    status: pending
    dependencies:
      - week10_enhance_promoter
  - id: week10_audit_trail
    content: Add comprehensive audit trail logging for all promotion attempts with history storage in database
    status: pending
    dependencies:
      - week10_enhance_promoter
  - id: week10_integration_tests
    content: Create comprehensive integration tests in tests/integration/test_model_promotion.py covering all promotion stages and CI/CD workflows
    status: pending
    dependencies:
      - week10_cicd_workflow
      - week10_promotion_scripts
  - id: week10_documentation
    content: Update README.md and create promotion workflow documentation with CI/CD usage instructions
    status: pending
    dependencies:
      - week10_cicd_workflow
---

# Week 10: Model Promotion Automation

## Overview

Week 10 focuses on automating the model promotion workflow through CI/CD integration and enhancing the existing `ModelPromoter` class with automated gates. This builds on Week 9's risk controls and secrets management to create a production-ready model lifecycle management system.

## Current State Analysis

**Existing Components:**

- `ModelPromoter` class in [src/mt5-python_server/src/mlops/model_promoter.py](src/mt5-python_server/src/mlops/model_promoter.py) with manual promotion workflow
- Promotion stages: Training → Staging → Paper → Production → Archived
- Validation logic exists in `validate_for_production()` method
- Paper trading results stored in database (`paper_trading_results` JSON field)
- 2FA support in API layer
- Basic GitHub Actions workflows for testing/building

**Missing Components:**

- CI/CD workflow for automated promotion gates
- Automated paper trading validation checks
- Integration tests for promotion workflow
- Automated promotion from Training → Staging
- Promotion status tracking and notifications

## Task 10.1: CI/CD Integration (Days 28-30)

### Step 1: Create Model Promotion Workflow

**File to create:** `.github/workflows/model_promotion.yml`

**Implementation:**

```yaml
name: Model Promotion

on:
  workflow_dispatch:
    inputs:
      model_id:
        description: 'Model ID to promote'
        required: true
        type: string
      target_stage:
        description: 'Target stage (staging, paper, production)'
        required: true
        type: choice
        options:
     - staging
     - paper
     - production
      approver:
        description: 'Approver name'
        required: true
        type: string
  push:
    branches:
   - main
    paths:
   - 'src/mt5-python_server/src/mlops/model_promoter.py'
   - '.github/workflows/model_promotion.yml'

jobs:
  validate-promotion:
    runs-on: ubuntu-latest
    steps:
   - uses: actions/checkout@v4
      
   - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
   - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
   - name: Run promotion validation tests
        run: |
          pytest tests/integration/test_model_promotion.py -v
      
   - name: Validate model exists
        if: github.event_name == 'workflow_dispatch'
        run: |
          python scripts/validate_model_exists.py \
            --model-id ${{ github.event.inputs.model_id }}

  promote-to-staging:
    needs: validate-promotion
    runs-on: ubuntu-latest
    if: github.event.inputs.target_stage == 'staging' || github.event_name == 'push'
    steps:
   - uses: actions/checkout@v4
      
   - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
   - name: Install dependencies
        run: pip install -r requirements.txt
      
   - name: Auto-promote to staging
        env:
          MLFLOW_TRACKING_URI: ${{ secrets.MLFLOW_TRACKING_URI }}
          MODEL_NAME: trading-dqn
        run: |
          python scripts/auto_promote_to_staging.py \
            --model-id ${{ github.event.inputs.model_id || 'latest' }}

  promote-to-paper:
    needs: validate-promotion
    runs-on: ubuntu-latest
    if: github.event.inputs.target_stage == 'paper'
    steps:
   - uses: actions/checkout@v4
      
   - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
   - name: Install dependencies
        run: pip install -r requirements.txt
      
   - name: Validate staging metrics
        env:
          MLFLOW_TRACKING_URI: ${{ secrets.MLFLOW_TRACKING_URI }}
          DB_HOST: ${{ secrets.DB_HOST }}
          DB_PASSWORD: ${{ secrets.DB_PASSWORD }}
        run: |
          python scripts/validate_staging_metrics.py \
            --model-id ${{ github.event.inputs.model_id }}
      
   - name: Promote to paper
        env:
          MLFLOW_TRACKING_URI: ${{ secrets.MLFLOW_TRACKING_URI }}
          APPROVER: ${{ github.event.inputs.approver }}
        run: |
          python scripts/promote_to_paper.py \
            --model-id ${{ github.event.inputs.model_id }} \
            --approver "${{ github.event.inputs.approver }}"

  promote-to-production:
    needs: validate-promotion
    runs-on: ubuntu-latest
    if: github.event.inputs.target_stage == 'production'
    environment: production
    steps:
   - uses: actions/checkout@v4
      
   - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
   - name: Install dependencies
        run: pip install -r requirements.txt
      
   - name: Validate paper trading results
        env:
          MLFLOW_TRACKING_URI: ${{ secrets.MLFLOW_TRACKING_URI }}
          DB_HOST: ${{ secrets.DB_HOST }}
          DB_PASSWORD: ${{ secrets.DB_PASSWORD }}
        run: |
          python scripts/validate_paper_trading.py \
            --model-id ${{ github.event.inputs.model_id }} \
            --min-sharpe 1.0 \
            --min-win-rate 0.45 \
            --min-days 14 \
            --min-trades 100
      
   - name: Run integration tests
        run: |
          pytest tests/integration/test_model_promotion.py::TestProductionPromotion -v
      
   - name: Promote to production (requires manual approval)
        env:
          MLFLOW_TRACKING_URI: ${{ secrets.MLFLOW_TRACKING_URI }}
          APPROVER: ${{ github.event.inputs.approver }}
          TOTP_TOKEN: ${{ secrets.PRODUCTION_PROMOTION_TOKEN }}
        run: |
          python scripts/promote_to_production.py \
            --model-id ${{ github.event.inputs.model_id }} \
            --approver "${{ github.event.inputs.approver }}" \
            --totp-token "${{ env.TOTP_TOKEN }}"
      
   - name: Notify promotion success
        if: success()
        uses: 8398a7/action-slack@v3
        with:
          status: custom
          custom_payload: |
            {
              text: "Model ${{ github.event.inputs.model_id }} promoted to Production",
              attachments: [{
                color: 'good',
                text: "Promoted by: ${{ github.event.inputs.approver }}"
              }]
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### Step 2: Create Promotion Scripts

**Files to create:**

1. **`scripts/auto_promote_to_staging.py`** - Auto-promote models after training
2. **`scripts/validate_staging_metrics.py`** - Validate staging metrics before paper promotion
3. **`scripts/promote_to_paper.py`** - Promote to paper with validation
4. **`scripts/validate_paper_trading.py`** - Validate paper trading results
5. **`scripts/promote_to_production.py`** - Promote to production with 2FA

**Key Implementation Points:**

- Use `ModelPromoter` class for all promotion operations
- Integrate with secrets manager from Week 9
- Add comprehensive logging and error handling
- Support both model_id and version-based promotion

### Step 3: Enhance ModelPromoter with Automated Gates

**File to modify:** [src/mt5-python_server/src/mlops/model_promoter.py](src/mt5-python_server/src/mlops/model_promoter.py)

**Enhancements:**

1. **Add automated staging promotion method:**
   ```python
   def auto_promote_to_staging(self, version: int) -> bool:
       """Automatically promote model to staging after training"""
       # Check if model exists and is in Training stage
       # Validate basic metrics are logged
       # Promote to staging
   ```

2. **Add staging validation method:**
   ```python
   def validate_for_paper(self, model_id: int) -> tuple[bool, ValidationResult]:
       """Validate staging model before paper promotion"""
       # Check model exists in staging
       # Validate basic metrics (if available)
       # Return validation result
   ```

3. **Enhance paper trading validation:**

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Add automated metrics fetching from database
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Add configurable thresholds
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Add detailed validation reports

4. **Add promotion status tracking:**
   ```python
   def get_promotion_status(self, model_id: int) -> Dict[str, Any]:
       """Get current promotion status and next steps"""
       # Return current stage, validation status, next requirements
   ```


## Task 10.2: Promotion Workflow Enhancement (Days 30-32)

### Step 1: Add Automated Paper Trading Validation

**File to modify:** [src/mt5-python_server/src/mlops/model_promoter.py](src/mt5-python_server/src/mlops/model_promoter.py)

**Enhancements:**

1. **Automated metrics fetching:**

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Query paper trading results from database automatically
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Calculate metrics if not already computed
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Cache validation results

2. **Enhanced validation criteria:**

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Add configurable thresholds via environment variables
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Support custom validation rules
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Add validation history tracking

3. **Paper trading result verification:**
   ```python
   def verify_paper_trading_results(
       self, 
       model_id: int,
       min_days: Optional[int] = None,
       min_trades: Optional[int] = None
   ) -> Dict[str, Any]:
       """Verify paper trading results meet requirements"""
       # Fetch results from database
       # Validate completeness
       # Return verification status
   ```


### Step 2: Enhance 2FA Integration

**Files to modify:**

- [src/api/src/services/model_service.py](src/api/src/services/model_service.py)
- [src/mt5-python_server/src/mlops/model_promoter.py](src/mt5-python_server/src/mlops/model_promoter.py)

**Enhancements:**

1. **Secure 2FA token handling:**

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Use secrets manager for 2FA secrets
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Add token expiration
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Add audit logging for 2FA usage

2. **2FA verification in CI/CD:**

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Support GitHub environment protection rules
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Add manual approval gates for production
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Store 2FA tokens securely in GitHub secrets

### Step 3: Add Audit Trail Enhancement

**File to modify:** [src/mt5-python_server/src/mlops/model_promoter.py](src/mt5-python_server/src/mlops/model_promoter.py)

**Enhancements:**

1. **Comprehensive audit logging:**

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Log all promotion attempts (successful and failed)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Store promotion history in database
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Add promotion metadata (IP, user agent, etc.)

2. **Promotion history API:**

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Add endpoint to query promotion history
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Support filtering by stage, date, approver
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Export promotion reports

### Step 4: Create Integration Tests

**File to create:** `tests/integration/test_model_promotion.py`

**Test Coverage:**

1. **Test Training → Staging promotion:**

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Auto-promotion after training completes
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Validation of staging promotion
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Error handling for invalid models

2. **Test Staging → Paper promotion:**

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Manual promotion workflow
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Validation checks
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Database state verification

3. **Test Paper → Production promotion:**

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Paper trading validation
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - 2FA verification
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Production promotion workflow
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Rollback functionality

4. **Test CI/CD integration:**

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Workflow trigger validation
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Automated gate execution
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Error handling in workflows

5. **Test promotion criteria:**

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - All validation checks
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Threshold enforcement
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Custom criteria support

## Dependencies

### Week 10 Dependencies

- ✅ Week 9 completed (Risk controls, Secrets management)
- ✅ Existing `ModelPromoter` class
- ✅ Paper trading results in database
- ✅ MLflow integration
- ✅ Database model registry

### External Dependencies

- GitHub Actions (for CI/CD)
- MLflow tracking server (accessible from CI)
- Database access from CI (via secrets)
- Optional: Slack webhook for notifications

## Implementation Order

1. **Day 28**: Create promotion scripts and enhance `ModelPromoter` with automated gates
2. **Day 29**: Create CI/CD workflow and integration tests
3. **Day 30**: Test CI/CD workflow and fix issues
4. **Day 31**: Enhance 2FA integration and audit trail
5. **Day 32**: Final testing and documentation

## Files Summary

### Files to Create

- `.github/workflows/model_promotion.yml` - CI/CD promotion workflow
- `scripts/auto_promote_to_staging.py` - Auto-promotion script
- `scripts/validate_staging_metrics.py` - Staging validation script
- `scripts/promote_to_paper.py` - Paper promotion script
- `scripts/validate_paper_trading.py` - Paper trading validation script
- `scripts/promote_to_production.py` - Production promotion script
- `scripts/validate_model_exists.py` - Model existence validation
- `tests/integration/test_model_promotion.py` - Comprehensive promotion tests

### Files to Modify

- `src/mt5-python_server/src/mlops/model_promoter.py` - Add automated gates and enhancements
- `src/api/src/services/model_service.py` - Enhance 2FA integration
- `README.md` - Document promotion workflow

## Success Criteria

- ✅ CI/CD workflow triggers on model promotion requests
- ✅ Automated gates validate models before promotion
- ✅ Training → Staging promotion is automatic
- ✅ Paper trading validation is automated
- ✅ Production promotion requires manual approval + 2FA
- ✅ All integration tests pass
- ✅ Audit trail captures all promotion events
- ✅ Documentation updated with promotion workflow

## Risk Mitigation

1. **CI/CD Failures**: Add comprehensive error handling and rollback procedures
2. **Validation Failures**: Provide clear error messages and remediation steps
3. **2FA Issues**: Support fallback mechanisms and clear error reporting
4. **Database Access**: Use connection pooling and retry logic
5. **MLflow Connectivity**: Add health checks and fallback options

## Success Metrics

- **Promotion Automation**: 100% of Training → Staging promotions automated
- **Validation Coverage**: All promotion stages have automated validation
- **Test Coverage**: 90%+ test coverage for promotion workflow
- **Audit Trail**: 100% of promotions logged with full metadata
- **Error Rate**: < 1% promotion failures due to automation issues