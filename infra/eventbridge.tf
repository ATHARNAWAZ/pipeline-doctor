# ---------------------------------------------------------------------------
# SNS Topic — alerts hub for CloudWatch alarms and Lambda notifications
# ---------------------------------------------------------------------------

resource "aws_sns_topic" "alerts" {
  name = "${local.name_prefix}-alerts"
}

# Subscribe the alert email only when one is provided
resource "aws_sns_topic_subscription" "email" {
  count = var.alert_email != "" ? 1 : 0

  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Subscribe the notifier Lambda so it can receive SNS-triggered invocations
resource "aws_sns_topic_subscription" "notifier_lambda" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.notifier.arn
}

# ---------------------------------------------------------------------------
# EventBridge Rule 1 — manifest uploaded
# Fires when a new manifest.json lands in the manifests bucket under the
# manifests/ prefix. The S3 bucket is configured with eventbridge = true
# so EventBridge receives all S3 object events.
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "manifest_uploaded" {
  name        = "${local.name_prefix}-manifest-uploaded"
  description = "Trigger analyzer Lambda when a manifest.json is uploaded to S3"

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [aws_s3_bucket.manifests.bucket]
      }
      object = {
        key = [{
          prefix = "manifests/"
        }, {
          suffix = ".json"
        }]
      }
    }
  })
}

resource "aws_cloudwatch_event_target" "manifest_uploaded_to_analyzer" {
  rule = aws_cloudwatch_event_rule.manifest_uploaded.name
  arn  = aws_lambda_function.analyzer.arn

  # Pass the S3 event details through to the Lambda as the event payload
  input_transformer {
    input_paths = {
      bucket = "$.detail.bucket.name"
      key    = "$.detail.object.key"
    }
    input_template = <<-JSON
      {
        "Records": [{
          "s3": {
            "bucket": {"name": <bucket>},
            "object": {"key": <key>}
          }
        }]
      }
    JSON
  }
}

# ---------------------------------------------------------------------------
# EventBridge Rule 2 — hourly check
# Runs every hour to trigger the notifier Lambda. Only enabled when a Slack
# webhook is configured — there is no point scheduling alerts with no target.
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "daily_check" {
  name        = "${local.name_prefix}-daily-check"
  description = "Hourly trigger for the notifier Lambda (only useful with Slack configured)"

  schedule_expression = "rate(1 hour)"

  # Disable the rule entirely when no Slack webhook is provided
  state = var.slack_webhook_url != "" ? "ENABLED" : "DISABLED"
}

resource "aws_cloudwatch_event_target" "daily_check_to_notifier" {
  rule = aws_cloudwatch_event_rule.daily_check.name
  arn  = aws_lambda_function.notifier.arn
}
