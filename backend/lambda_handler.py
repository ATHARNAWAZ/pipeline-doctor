"""
AWS Lambda handlers for pipeline-doctor.

Two triggers:

1. analyze_handler — triggered by S3 PutObject events when a new manifest.json
   is uploaded. Parses the manifest, runs Claude analysis on any failures,
   and stores a structured analysis JSON back to S3. If there are failures,
   also triggers a Slack notification.

2. notify_handler — triggered by EventBridge (scheduled) or SNS. Reads the
   latest analysis from S3 and sends a Slack alert if failures exist.
   Useful for periodic check-ins ("are we still broken after 1 hour?").

Design decisions:
- asyncio.run() wraps async work because Lambda's runtime is synchronous.
  Python 3.12 Lambda runtimes support asyncio well; this is the standard pattern.
- S3 downloads/uploads use boto3 (sync) since we're inside asyncio.run() calls
  that are themselves sync from Lambda's perspective. Mixing boto3 async clients
  with synchronous Lambda execution adds complexity without benefit.
- Results are stored as analysis_{timestamp}.json alongside the manifest so
  multiple analysis runs don't overwrite each other. The Lambda function can
  be invoked multiple times for the same manifest (e.g. on retry) safely.
- The "latest analysis" key (latest_analysis.json) is a pointer file so the
  notify_handler always knows where to look without scanning the bucket.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import boto3
import structlog

# Configure basic logging for Lambda — structlog's full configuration is
# overkill in Lambda where CloudWatch captures stdout as-is
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger(__name__)


def analyze_handler(event: dict, context) -> dict:
    """S3 trigger: parse a newly uploaded manifest and generate Claude analysis.

    Expected S3 event format:
    {
        "Records": [{
            "s3": {
                "bucket": {"name": "my-pipeline-doctor-bucket"},
                "object": {"key": "manifests/my_project/manifest.json"}
            }
        }]
    }
    """
    log = logger.bind(handler="analyze_handler")

    # Extract S3 coordinates from the event
    try:
        record = event["Records"][0]["s3"]
        bucket_name = record["bucket"]["name"]
        object_key = record["object"]["key"]
    except (KeyError, IndexError) as exc:
        log.error("invalid_s3_event", error=str(exc), event=str(event)[:500])
        return {"statusCode": 400, "body": f"Invalid S3 event: {exc}"}

    log = log.bind(bucket=bucket_name, key=object_key)
    log.info("analyze_triggered")

    try:
        result = asyncio.run(_async_analyze(bucket_name, object_key))
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as exc:
        log.error("analyze_handler_failed", error=str(exc), exc_info=True)
        return {"statusCode": 500, "body": f"Analysis failed: {exc}"}


def notify_handler(event: dict, context) -> dict:
    """SNS/EventBridge trigger: read latest analysis and send Slack alert if needed.

    Can be invoked on a schedule (e.g. every 30 minutes during business hours)
    to proactively alert the team about ongoing failures.
    """
    log = logger.bind(handler="notify_handler")
    log.info("notify_triggered")

    bucket_name = os.environ.get("S3_BUCKET_NAME")
    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")

    if not bucket_name:
        log.error("missing_s3_bucket_env_var")
        return {"statusCode": 500, "body": "S3_BUCKET_NAME env var not set"}

    if not slack_webhook:
        log.info("slack_webhook_not_configured", note="skipping notification")
        return {"statusCode": 200, "body": "No Slack webhook configured"}

    try:
        result = asyncio.run(_async_notify(bucket_name, slack_webhook))
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as exc:
        log.error("notify_handler_failed", error=str(exc), exc_info=True)
        return {"statusCode": 500, "body": f"Notification failed: {exc}"}


# ---------------------------------------------------------------------------
# Async implementation
# ---------------------------------------------------------------------------


async def _async_analyze(bucket_name: str, object_key: str) -> dict:
    """Download manifest from S3, parse it, run Claude analysis, store results."""
    from app.config import get_settings
    from app.services.manifest_parser import ManifestParser
    from app.services.lineage_graph import LineageGraph
    from app.services.claude_service import ClaudeService, FailingModelSummary
    from app.services.slack_notifier import SlackNotifier

    log = logger.bind(action="async_analyze", bucket=bucket_name, key=object_key)
    settings = get_settings()

    s3_client = boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )

    # Download manifest.json from S3
    log.info("downloading_manifest")
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        manifest_bytes = response["Body"].read()
        manifest_data = json.loads(manifest_bytes)
    except Exception as exc:
        log.error("manifest_download_failed", error=str(exc))
        raise

    # Check for run_results.json alongside the manifest
    # Convention: manifest is at prefix/manifest.json → run results at prefix/run_results.json
    run_results_data = None
    run_results_key = object_key.replace("manifest.json", "run_results.json")
    if run_results_key != object_key:
        try:
            rr_response = s3_client.get_object(Bucket=bucket_name, Key=run_results_key)
            run_results_data = json.loads(rr_response["Body"].read())
            log.info("run_results_loaded", key=run_results_key)
        except s3_client.exceptions.NoSuchKey:
            log.info("no_run_results_found", key=run_results_key)
        except Exception as exc:
            log.warning("run_results_download_failed", error=str(exc))

    # Parse manifest
    parser = ManifestParser()
    parsed = parser.parse_manifest(manifest_data=manifest_data)

    run_results_map = {}
    if run_results_data:
        run_results_map = parser.parse_run_results(run_results_data=run_results_data)

    merged = parser.merge(parsed, run_results_map)
    lineage_graph = LineageGraph.build_from_manifest(merged)

    log.info(
        "manifest_parsed",
        models=merged.node_count,
        failing=len(merged.failing_models),
    )

    # Generate Claude explanations for failing models
    claude = ClaudeService(settings)
    failure_analyses: list[dict] = []

    for failing_id in merged.failing_models:
        node = merged.models.get(failing_id)
        run_result = merged.run_results.get(failing_id)

        if not node or not run_result:
            continue

        model_name = node.name
        error_message = run_result.message or "Unknown error"
        upstream = lineage_graph.get_upstream(failing_id, depth=2)
        downstream = lineage_graph.get_downstream(failing_id, depth=1)

        lineage_summary = {
            "upstream_models": [
                merged.models[u].name for u in upstream if u in merged.models
            ],
            "downstream_affected": [
                merged.models[d].name for d in downstream if d in merged.models
            ],
        }

        # Build a minimal RetrievedContext for the Lambda context
        # (no pgvector in Lambda — we use the raw model SQL directly)
        from app.services.rag_engine import RetrievedContext
        from app.services.lineage_graph import LineageGraph as LG

        sql = node.compiled_code or node.raw_code or "-- SQL not available"
        context_str = (
            f"### {model_name}\n"
            f"SQL:\n```sql\n{sql[:3000]}\n```\n"
            f"Error: {error_message}"
        )
        context = RetrievedContext(
            relevant_nodes=[failing_id],
            context_string=context_str,
            retrieval_score=0.0,
        )

        try:
            explanation = await claude.explain_failure(
                failing_model=model_name,
                error_message=error_message,
                context=context,
                lineage_summary=lineage_summary,
            )
        except Exception as exc:
            log.warning(
                "claude_explanation_failed",
                model=model_name,
                error=str(exc),
            )
            explanation = f"Analysis unavailable: {exc}"

        failure_analyses.append({
            "model_name": model_name,
            "unique_id": failing_id,
            "error_message": error_message,
            "explanation": explanation,
            "upstream_models": lineage_summary["upstream_models"],
            "downstream_affected": lineage_summary["downstream_affected"],
        })

    # Assemble the final analysis result
    timestamp = datetime.now(timezone.utc).isoformat()
    analysis_result = {
        "analyzed_at": timestamp,
        "manifest_key": object_key,
        "total_models": merged.node_count,
        "failing_models": len(merged.failing_models),
        "failure_analyses": failure_analyses,
    }

    # Store result back to S3
    analysis_key = object_key.replace(
        "manifest.json", f"analysis_{timestamp.replace(':', '-')}.json"
    )
    latest_key = object_key.replace("manifest.json", "latest_analysis.json")

    analysis_json = json.dumps(analysis_result, indent=2)
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=analysis_key,
            Body=analysis_json.encode("utf-8"),
            ContentType="application/json",
        )
        # Also update the "latest" pointer so notify_handler can find it
        s3_client.put_object(
            Bucket=bucket_name,
            Key=latest_key,
            Body=analysis_json.encode("utf-8"),
            ContentType="application/json",
        )
        log.info("analysis_stored", key=analysis_key)
    except Exception as exc:
        log.error("analysis_store_failed", error=str(exc))
        raise

    # Send Slack alert if failures exist and webhook is configured
    if merged.failing_models and settings.slack_webhook_url:
        slack_notifier = SlackNotifier(settings.slack_webhook_url)

        # Build FailingModelSummary objects for the Slack alert
        failing_summaries = []
        for analysis in failure_analyses:
            failing_summaries.append(
                FailingModelSummary(
                    model_name=analysis["model_name"],
                    error_message=analysis["error_message"],
                    upstream_models=analysis["upstream_models"],
                    downstream_affected=analysis["downstream_affected"],
                )
            )

        project_name = _extract_project_name_from_key(object_key)
        slack_message = await claude.generate_slack_alert(
            failing_models=failing_summaries,
            project_name=project_name,
        )
        await slack_notifier.send_failure_alert(slack_message)

    log.info(
        "analyze_complete",
        failing_models=len(merged.failing_models),
        result_key=analysis_key,
    )

    return {
        "analyzed_at": timestamp,
        "total_models": merged.node_count,
        "failing_models": len(merged.failing_models),
        "result_key": analysis_key,
    }


async def _async_notify(bucket_name: str, slack_webhook_url: str) -> dict:
    """Read the latest analysis from S3 and send a Slack alert if failures exist."""
    from app.config import get_settings
    from app.services.claude_service import ClaudeService, FailingModelSummary
    from app.services.slack_notifier import SlackNotifier

    log = logger.bind(action="async_notify", bucket=bucket_name)
    settings = get_settings()

    s3_client = boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )

    # Find the latest analysis — we look for any latest_analysis.json in the bucket
    # In practice you'd scope this to a specific project prefix
    latest_key = _find_latest_analysis_key(s3_client, bucket_name)
    if not latest_key:
        log.info("no_latest_analysis_found")
        return {"sent": False, "reason": "no analysis found"}

    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=latest_key)
        analysis = json.loads(response["Body"].read())
    except Exception as exc:
        log.error("analysis_read_failed", key=latest_key, error=str(exc))
        raise

    failing_count = analysis.get("failing_models", 0)
    if failing_count == 0:
        log.info("no_failures_to_report")
        return {"sent": False, "reason": "no failures"}

    # Build summaries from the stored analysis
    claude = ClaudeService(settings)
    slack_notifier = SlackNotifier(slack_webhook_url)

    failing_summaries = []
    for fa in analysis.get("failure_analyses", []):
        failing_summaries.append(
            FailingModelSummary(
                model_name=fa.get("model_name", "unknown"),
                error_message=fa.get("error_message", ""),
                upstream_models=fa.get("upstream_models", []),
                downstream_affected=fa.get("downstream_affected", []),
            )
        )

    project_name = analysis.get("manifest_key", "unknown").split("/")[1] if "/" in analysis.get("manifest_key", "") else "dbt_project"

    slack_message = await claude.generate_slack_alert(
        failing_models=failing_summaries,
        project_name=project_name,
    )

    sent = await slack_notifier.send_failure_alert(slack_message)
    log.info("notify_complete", sent=sent, failing_count=failing_count)

    return {"sent": sent, "failing_models": failing_count}


def _find_latest_analysis_key(s3_client, bucket_name: str) -> str | None:
    """List the bucket and find the most recently modified latest_analysis.json."""
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        latest_key = None
        latest_modified = None

        for page in paginator.paginate(Bucket=bucket_name, Prefix=""):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith("latest_analysis.json"):
                    if latest_modified is None or obj["LastModified"] > latest_modified:
                        latest_key = obj["Key"]
                        latest_modified = obj["LastModified"]

        return latest_key
    except Exception as exc:
        logger.warning("s3_list_failed", error=str(exc))
        return None


def _extract_project_name_from_key(object_key: str) -> str:
    """Extract the dbt project name from an S3 key like 'manifests/my_project/manifest.json'."""
    parts = object_key.strip("/").split("/")
    # If the key has at least 2 path components, the second-to-last directory
    # before 'manifest.json' is typically the project name
    if len(parts) >= 2:
        return parts[-2]
    return "dbt_project"
