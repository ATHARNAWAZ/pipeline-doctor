"""
Slack notification service — standalone so it can be used from both the
FastAPI app and the Lambda function without any FastAPI dependencies.

Design decisions:
- Uses httpx (async) rather than the Slack SDK to keep dependencies minimal.
  The Slack Incoming Webhooks API is simple enough that a raw POST is cleaner
  than importing a whole SDK.
- Never raises — alert failures should not kill the pipeline or the Lambda.
  A broken Slack webhook is annoying but shouldn't block a dbt run result
  from being stored.
- Separate methods for failures vs. recoveries so the Slack channel stays
  useful — nobody wants to chase false positives.
"""

from __future__ import annotations

import structlog
import httpx

logger = structlog.get_logger(__name__)


class SlackNotifier:
    """Send Slack Block Kit messages via an Incoming Webhook URL.

    The webhook URL is provided at construction time so the notifier can be
    used with different channels (e.g. #data-alerts for prod, #data-dev for staging)
    without changing the code.
    """

    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    async def send_failure_alert(self, alert) -> bool:
        """POST a SlackMessage to the configured webhook.

        The `alert` parameter accepts anything with `.blocks` (list) and `.text`
        (str) attributes — compatible with the SlackMessage dataclass from
        claude_service.py without creating a circular import.

        Returns True on success, False on any failure. Logs the error but
        does not raise so the caller's pipeline continues regardless.
        """
        log = logger.bind(action="send_failure_alert")

        payload = {
            "text": alert.text,  # Fallback for notifications and accessibility
            "blocks": alert.blocks,
        }

        return await self._post_to_slack(payload, log)

    async def send_recovery_notice(self, recovered_models: list[str]) -> bool:
        """Notify the channel that previously failing models are now passing.

        Recovery notices matter — without them, the team doesn't know whether
        the fix they deployed actually worked. A simple green checkmark message
        is enough.
        """
        if not recovered_models:
            return True

        log = logger.bind(action="send_recovery_notice", count=len(recovered_models))

        model_list = ", ".join(f"`{m}`" for m in recovered_models[:10])
        extra = f" +{len(recovered_models) - 10} more" if len(recovered_models) > 10 else ""

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": ":large_green_circle: dbt Pipeline Recovered",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"The following model(s) are now passing:\n"
                        f"{model_list}{extra}"
                    ),
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Powered by pipeline-doctor",
                    }
                ],
            },
        ]

        fallback_text = (
            "dbt recovery: " + ", ".join(recovered_models[:3])
        )

        payload = {"text": fallback_text, "blocks": blocks}
        return await self._post_to_slack(payload, log)

    async def _post_to_slack(self, payload: dict, log) -> bool:
        """Execute the actual HTTP POST to the Slack webhook URL.

        Slack webhooks return HTTP 200 with body "ok" on success.
        Any other status (or a network error) is treated as a failure.
        Timeouts are set conservatively — we'd rather miss an alert than
        block the Lambda for 30 seconds waiting for Slack to respond.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self._webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

            if response.status_code == 200 and response.text == "ok":
                log.info("slack_notification_sent")
                return True

            # Slack returns descriptive error text in the body (e.g. "invalid_payload")
            log.warning(
                "slack_notification_rejected",
                status_code=response.status_code,
                response_body=response.text[:200],
            )
            return False

        except httpx.TimeoutException:
            log.warning("slack_notification_timeout", timeout_seconds=10)
            return False

        except httpx.RequestError as exc:
            log.error("slack_notification_network_error", error=str(exc))
            return False

        except Exception as exc:
            # Catch-all: never let an alert failure propagate to the caller
            log.error(
                "slack_notification_unexpected_error",
                error=str(exc),
                exc_info=True,
            )
            return False
