# Pipeline Doctor — Project Specification
**Version**: 1.0
**Date**: 2026-03-18

## Summary

Pipeline Doctor is a production-grade, open source AI-powered dbt pipeline debugger.
When a dbt model fails or produces wrong results, data engineers spend hours tracing
lineage manually. Pipeline Doctor ingests dbt manifest.json + run_results.json, builds
a knowledge base, and lets you ask "why did my orders model fail?" in plain English.
It answers using your actual pipeline context.

## Full Specification

See: `project-docs/ORCHESTRATION_PLAN.md`

This spec file exists as the canonical reference for project-manager-senior.
The orchestration plan contains the complete build specification including:
- All 8 phases with detailed deliverables
- Quality gates between phases
- Agent assignments
- Technical requirements
- Code quality rules
- Project structure

## Quick Reference

**Stack**: Python 3.11 + FastAPI + LlamaIndex + pgvector + Claude API + React 18 + TypeScript + Terraform
**AI Model**: claude-sonnet-4-6 (exact ID)
**Database**: PostgreSQL 16 with pgvector extension
**Infrastructure**: AWS (Lambda, S3, EventBridge, SNS, CloudWatch)
**Frontend**: React Flow DAG + streaming chat UI, dark terminal theme

## Scope

This is NOT a tutorial project. It is a production-grade tool intended for real use
by data engineering teams. Every implementation decision should reflect this.
