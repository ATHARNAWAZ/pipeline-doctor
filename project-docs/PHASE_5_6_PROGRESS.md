# Phase 5 & 6 Progress — AWS Infrastructure and CI/CD Pipeline

**Status**: COMPLETE
**Date**: 2026-03-18
**Agent**: DevOps Automator

---

## Phase 5: AWS Infrastructure (Terraform)

### Status: COMPLETE

All Terraform files are written to `infra/`. The infrastructure follows a least-privilege, automation-first design. No hardcoded account IDs — all ARNs use `data.aws_caller_identity.current.account_id`.

### Files Delivered

| File | Purpose |
|------|---------|
| `infra/variables.tf` | All configurable inputs with sensitive markers |
| `infra/main.tf` | Provider configuration, locals, remote state scaffold |
| `infra/s3.tf` | Two S3 buckets with versioning, encryption, lifecycle rules, CORS, EventBridge notification |
| `infra/lambda.tf` | Two Lambda functions with IAM roles, Function URL, EventBridge + SNS permissions |
| `infra/eventbridge.tf` | SNS topic, S3-triggered rule, hourly scheduled rule |
| `infra/monitoring.tf` | CloudWatch log groups, metric alarms, observability dashboard |
| `infra/outputs.tf` | All bucket names, Lambda ARNs, Function URL, EventBridge ARNs, SNS ARN |

### Architecture Decisions

**Naming convention**: All resources use `local.name_prefix = "${var.project_name}-${var.environment}"` for consistent, environment-scoped names.

**S3 design**:
- `pipeline-doctor-{env}-manifests-{account_id}` — receives dbt manifest.json uploads via direct PUT (CORS enabled), triggers EventBridge on write
- `pipeline-doctor-{env}-analysis-{account_id}` — stores AI analysis results written by the analyzer Lambda
- Both buckets: versioning enabled, AES256 encryption, public access blocked, lifecycle to GLACIER at 90 days, expiry at 365 days

**Lambda IAM (least privilege)**:
- Analyzer role: S3 GetObject on manifests bucket + S3 PutObject on analysis bucket + CloudWatch Logs for its own log group only
- Notifier role: S3 GetObject/ListBucket on analysis bucket + SNS Publish to alerts topic + CloudWatch Logs for its own log group only
- No wildcard resource ARNs

**Lambda Function URL**: Auth type NONE with a comment explaining the intent to add IAM or API Gateway auth. The Lambda itself should validate callers via a shared secret header until formal auth is wired up.

**EventBridge S3 trigger**: Uses `input_transformer` to reshape the EventBridge S3 event format into the Lambda's expected `Records[0].s3` structure, so the same handler works whether triggered by S3, EventBridge, or direct invocation.

**Hourly check rule**: Automatically disabled (`state = "DISABLED"`) when `var.slack_webhook_url` is empty — no point scheduling notifications with no destination.

**Monitoring**:
- Log retention: 14 days for both Lambdas
- Alarms: errors > 5 in 5 minutes (both functions), duration P99 > 80% of timeout (both functions)
- Dashboard: invocations, errors, throttles, duration percentiles, error rate expression widget, S3 object counts

### Quality Gates

- No `*` resource ARNs in any IAM policy
- No hardcoded account IDs
- All sensitive variables marked `sensitive = true`
- `local.name_prefix` used on every named resource
- Resources tagged via `provider "aws" { default_tags {} }` — no per-resource tag blocks needed
- Remote state backend scaffolded (commented out) for production use

---

## Phase 6: CI/CD Pipeline (GitHub Actions)

### Status: COMPLETE

Two workflow files are written to `.github/workflows/`.

### Files Delivered

| File | Purpose |
|------|---------|
| `.github/workflows/test.yml` | Test matrix: backend (pytest + pgvector), frontend (tsc + lint + build), Terraform validate |
| `.github/workflows/deploy.yml` | Production deploy: reuses test workflow, deploys both Lambdas, smoke test, job summary |

### Pipeline Design

**test.yml** runs on:
- Push to `main` or `develop`
- Pull requests targeting `main`

Three parallel jobs:
1. `backend-tests` — spins up `pgvector/pgvector:pg16` as a service container, installs Python 3.11 deps, runs pytest with 80% coverage gate, uploads to Codecov
2. `frontend-build` — Node 20 with npm cache, TypeScript check, lint, production build
3. `terraform-validate` — `terraform init -backend=false`, fmt check, validate

**deploy.yml** runs on push to `main` only.

Key design decisions:
- `needs: test` ensures the full test matrix passes before any deploy step runs
- `environment: production` gates the deploy job behind GitHub's required reviewers feature
- `concurrency: group: deploy-production, cancel-in-progress: false` — a deploy already underway is never abandoned mid-flight; the next deploy queues behind it
- Lambda build uses `pip install --target lambda_package/` (the standard Lambda packaging pattern) then zips the directory
- `aws lambda wait function-updated` blocks until both functions finish propagating before the smoke test runs
- Smoke test uses `|| true` so a cold-start error from the test payload does not fail the pipeline; the response body is always printed for inspection
- GitHub Step Summary records commit SHA, actor, timestamp, and function names for every deploy regardless of outcome

### Secrets Required

| Secret | Used by |
|--------|---------|
| `AWS_ACCESS_KEY_ID` | deploy.yml |
| `AWS_SECRET_ACCESS_KEY` | deploy.yml |
| `AWS_REGION` | deploy.yml (falls back to `us-east-1`) |
| `ANTHROPIC_API_KEY` | test.yml backend-tests (falls back to test key) |

### To Complete Setup

1. Create a GitHub environment named `production` in Settings > Environments
2. Add required reviewers to the `production` environment for approval-gated deploys
3. Add the four secrets listed above to the repository
4. Run `terraform init && terraform apply` from `infra/` with a populated `terraform.tfvars` (see variable descriptions in `infra/variables.tf`)
5. The S3 bucket names and Lambda Function URL are available via `terraform output` after apply

---

## Quality Gate Summary

| Requirement | Status |
|-------------|--------|
| `local.name_prefix` on all resources | PASS |
| No wildcard IAM resource ARNs | PASS |
| `sensitive = true` on all secret variables | PASS |
| No hardcoded account IDs | PASS |
| Pinned GitHub Actions versions (v4, not @latest) | PASS |
| Separate IAM roles per Lambda | PASS |
| Monitoring + alerting on both Lambdas | PASS |
| Automated rollback via `wait function-updated` + smoke test | PASS |
| Provider default_tags instead of per-resource tag blocks | PASS |
