"""
Claude integration — turns retrieved context into actionable failure diagnoses.

The system prompt is load-bearing. A vague prompt produces vague answers.
This one is tuned specifically for the dbt debugging use case: it tells
Claude exactly what role it's in, what data it has access to, and what
format the answer should take. Every rule in SYSTEM_PROMPT was added because
without it, Claude would do the wrong thing.

Production failure modes we handle explicitly:
- anthropic.RateLimitError: back off and return a graceful message
- anthropic.AuthenticationError: fail fast with a clear error (bad API key)
- anthropic.BadRequestError: usually content policy — log and return safe message
- All other exceptions: log with full context, re-raise so the caller can decide
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator

import anthropic
import structlog
from anthropic import AsyncAnthropic

from app.config import Settings
from app.services.rag_engine import RetrievedContext

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# System prompt — the most important string in this file
# ---------------------------------------------------------------------------

# Rules are ordered by how often violating them produces bad output in practice.
# The "never say 'the model' generically" rule is #1 because it's the most
# common way LLMs produce answers that sound plausible but are useless.
SYSTEM_PROMPT = """You are a senior data engineer embedded in a dbt pipeline debugging tool.
You have full access to the project's dbt manifest, SQL code, and run results.

Your job is to diagnose pipeline failures and explain them clearly to the engineer who owns this pipeline.

Rules:
- Always reference actual model names (e.g., mart_customer_ltv, stg_transactions) — never say "the model" generically
- When you see a SQL error, quote the relevant SQL and explain exactly what line fails and why
- Mention upstream dependencies when relevant ("stg_transactions feeds int_customer_transactions which feeds mart_customer_ltv")
- Suggest a specific fix, not "check your SQL" — show the corrected SQL if you can
- If you're not sure, say so — don't hallucinate column names or schema details not in the context
- Keep explanations under 400 words unless the problem is genuinely complex
- Use markdown: headers, code blocks, bullet points — engineers read this in terminals and web UIs
- When a model fails because an upstream model failed, say that explicitly — don't diagnose the symptom when the root cause is upstream
- If multiple models failed, start with the root cause (the one with no failing upstream dependencies)"""


# ---------------------------------------------------------------------------
# Supporting dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FailingModelSummary:
    """Lightweight failure summary for Slack alerts and batch analysis."""

    model_name: str
    error_message: str
    upstream_models: list[str] = field(default_factory=list)
    downstream_affected: list[str] = field(default_factory=list)


@dataclass
class SlackMessage:
    """Slack Block Kit message. `blocks` is the rich format; `text` is the fallback
    shown in notifications and accessibility contexts."""

    blocks: list[dict] = field(default_factory=list)
    text: str = ""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ClaudeService:
    """Wraps the Anthropic async client with domain-specific prompt construction.

    All public methods are async. The streaming method returns an AsyncIterator
    that yields text chunks as they arrive from the API — callers must consume
    the iterator (e.g. in a WebSocket handler) rather than awaiting a single result.
    """

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.claude_model  # "claude-sonnet-4-6"

    async def explain_failure(
        self,
        failing_model: str,
        error_message: str,
        context: RetrievedContext,
        lineage_summary: dict,
    ) -> str:
        """Return a complete failure explanation as a single string.

        Used for Slack alerts, batch analysis, and the non-streaming /ask endpoint.
        Blocking from the caller's perspective, but non-blocking at the asyncio level.
        """
        log = logger.bind(
            action="explain_failure",
            model=failing_model,
        )

        upstream = lineage_summary.get("upstream_models", [])
        downstream = lineage_summary.get("downstream_affected", [])

        prompt = self._build_failure_prompt(
            failing_model=failing_model,
            error_message=error_message,
            context_string=context.context_string,
            upstream_models=upstream,
            downstream_affected=downstream,
        )

        try:
            message = await self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = message.content[0].text
            log.info(
                "failure_explanation_complete",
                input_tokens=message.usage.input_tokens,
                output_tokens=message.usage.output_tokens,
            )
            return response_text

        except anthropic.RateLimitError:
            log.warning("claude_rate_limited", model=failing_model)
            return (
                f"**Rate limit reached** — Claude is temporarily unavailable. "
                f"The failing model is `{failing_model}`. Error: `{error_message}`. "
                f"Please retry in a few seconds."
            )

        except anthropic.AuthenticationError as exc:
            log.error("claude_auth_failed", error=str(exc))
            raise RuntimeError(
                "Anthropic API key is invalid or expired. "
                "Check ANTHROPIC_API_KEY in your .env file."
            ) from exc

        except anthropic.BadRequestError as exc:
            # Usually triggered by content policy on very unusual SQL errors
            log.warning("claude_bad_request", error=str(exc), model=failing_model)
            return (
                f"**Analysis unavailable** — the error message for `{failing_model}` "
                f"could not be processed. Raw error: `{error_message}`"
            )

        except Exception as exc:
            log.error(
                "claude_unexpected_error",
                error=str(exc),
                exc_info=True,
            )
            raise

    async def stream_response(
        self,
        question: str,
        context: RetrievedContext,
        manifest_summary: dict,
    ) -> AsyncIterator[str]:
        """Stream Claude's response for the WebSocket endpoint.

        Yields raw text chunks as they arrive. Each chunk is a string fragment,
        not a complete sentence or paragraph. Callers should buffer appropriately
        if they need complete tokens for display.

        This is genuinely async streaming — we don't buffer the full response
        and then pretend to stream it.
        """
        log = logger.bind(action="stream_response", question=question[:80])

        prompt = self._build_question_prompt(
            question=question,
            context_string=context.context_string,
            manifest_summary=manifest_summary,
        )

        try:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                async for text_chunk in stream.text_stream:
                    yield text_chunk

            # Log token usage after stream completes (available via get_final_message)
            final_message = await stream.get_final_message()
            log.info(
                "stream_complete",
                input_tokens=final_message.usage.input_tokens,
                output_tokens=final_message.usage.output_tokens,
            )

        except anthropic.RateLimitError:
            log.warning("claude_stream_rate_limited")
            yield "\n\n**Rate limit reached** — please retry in a few seconds."

        except anthropic.AuthenticationError as exc:
            log.error("claude_stream_auth_failed", error=str(exc))
            # Yield an error message so the WebSocket client sees something
            # rather than a silent close
            yield "\n\n**Authentication error** — check your Anthropic API key."

        except anthropic.BadRequestError as exc:
            log.warning("claude_stream_bad_request", error=str(exc))
            yield "\n\n**Unable to process this request** — the question may contain unsupported content."

        except Exception as exc:
            log.error("claude_stream_unexpected_error", error=str(exc), exc_info=True)
            yield f"\n\n**Unexpected error**: {type(exc).__name__}"

    async def generate_slack_alert(
        self,
        failing_models: list[FailingModelSummary],
        project_name: str,
    ) -> SlackMessage:
        """Generate a Slack Block Kit message summarizing pipeline failures.

        Asks Claude for a concise root-cause summary, then wraps it in Block Kit
        formatting suitable for a #data-alerts channel. Kept deliberately short —
        Slack messages should be scannable in 10 seconds, not full post-mortems.
        """
        log = logger.bind(
            action="generate_slack_alert",
            project=project_name,
            failing_count=len(failing_models),
        )

        if not failing_models:
            return SlackMessage(
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f":white_check_mark: *{project_name}* — all models passing",
                        },
                    }
                ],
                text=f"{project_name}: all models passing",
            )

        # Build a compact summary prompt — we want 2-3 sentences, not a novel
        model_list = "\n".join(
            f"- `{m.model_name}`: {m.error_message[:150]}"
            for m in failing_models[:5]  # cap at 5 models in the prompt
        )
        extra = f"\n...and {len(failing_models) - 5} more" if len(failing_models) > 5 else ""

        summary_prompt = (
            f"These dbt models failed in project `{project_name}`:\n\n"
            f"{model_list}{extra}\n\n"
            f"Write a 2-3 sentence Slack alert summary. "
            f"Lead with the most likely root cause. "
            f"Mention which models are affected. "
            f"End with a one-line suggested action. "
            f"No markdown headers. Keep it under 200 words."
        )

        try:
            message = await self._client.messages.create(
                model=self._model,
                max_tokens=300,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": summary_prompt}],
            )
            summary_text = message.content[0].text
            log.info("slack_alert_generated", output_tokens=message.usage.output_tokens)
        except anthropic.RateLimitError:
            log.warning("slack_alert_rate_limited")
            summary_text = (
                f"{len(failing_models)} model(s) failed: "
                + ", ".join(f"`{m.model_name}`" for m in failing_models[:3])
            )
        except Exception as exc:
            log.error("slack_alert_generation_failed", error=str(exc))
            summary_text = (
                f"{len(failing_models)} model(s) failed in `{project_name}`. "
                f"Check pipeline-doctor for details."
            )

        # Build Block Kit blocks
        failing_names = ", ".join(f"`{m.model_name}`" for m in failing_models[:5])
        if len(failing_models) > 5:
            failing_names += f" +{len(failing_models) - 5} more"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":red_circle: dbt Pipeline Failure — {project_name}",
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": summary_text},
            },
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Failed models ({len(failing_models)}):*\n{failing_names}",
                    },
                ],
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Powered by pipeline-doctor | Use `/ask` for full diagnosis",
                    }
                ],
            },
        ]

        fallback_text = (
            f"dbt failure in {project_name}: "
            + ", ".join(m.model_name for m in failing_models[:3])
        )

        return SlackMessage(blocks=blocks, text=fallback_text)

    # ---------------------------------------------------------------------------
    # Prompt builders — the "thinking" happens here before Claude sees the input
    # ---------------------------------------------------------------------------

    def _build_failure_prompt(
        self,
        failing_model: str,
        error_message: str,
        context_string: str,
        upstream_models: list[str],
        downstream_affected: list[str],
    ) -> str:
        """Build the failure analysis prompt.

        Error first — Claude (and humans) should see the problem statement before
        the supporting context. Burying the error at the bottom causes Claude to
        anchor on the context and produce less targeted diagnoses.
        """
        upstream_line = (
            f"Upstream models (may be root cause): {', '.join(upstream_models)}"
            if upstream_models
            else "No upstream model dependencies (this is a source model or base stage)"
        )
        downstream_line = (
            f"Downstream models blocked by this failure: {', '.join(downstream_affected)}"
            if downstream_affected
            else "No downstream models affected"
        )

        return f"""## Failure to Diagnose

**Failing model:** `{failing_model}`

**Error message:**
```
{error_message}
```

**Lineage context:**
- {upstream_line}
- {downstream_line}

---

{context_string}

---

Please diagnose this failure. Explain:
1. What exactly failed and why (reference the SQL if relevant)
2. Whether the root cause is in `{failing_model}` or in an upstream dependency
3. A specific fix — show corrected SQL or configuration if possible
4. Which downstream models are blocked and what impact that has"""

    def _build_question_prompt(
        self,
        question: str,
        context_string: str,
        manifest_summary: dict,
    ) -> str:
        """Build the prompt for a natural language question about the pipeline.

        For open-ended questions (not tied to a specific failure), we lead with
        the question and provide context after. The manifest summary gives Claude
        a high-level map so it can answer questions like "what models use the
        orders table?" even if the specific model wasn't top-ranked by RAG.
        """
        total_models = manifest_summary.get("total_models", 0)
        failing_count = manifest_summary.get("failing_count", 0)
        project_name = manifest_summary.get("project_name", "this dbt project")

        health_line = (
            f"{failing_count} of {total_models} models are currently failing"
            if failing_count > 0
            else f"All {total_models} models are passing"
        )

        return f"""## Question about {project_name}

{health_line}.

**Question:** {question}

---

{context_string}

---

Please answer the question based on the context above.
Reference specific model names and SQL details where relevant.
If the answer requires information not in the context, say so clearly."""
