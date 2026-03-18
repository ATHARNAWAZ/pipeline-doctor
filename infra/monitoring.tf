# ---------------------------------------------------------------------------
# CloudWatch Log Groups
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "analyzer" {
  name              = "/aws/lambda/${local.name_prefix}-analyzer"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "notifier" {
  name              = "/aws/lambda/${local.name_prefix}-notifier"
  retention_in_days = 14
}

# ---------------------------------------------------------------------------
# CloudWatch Metric Alarms — Analyzer Lambda
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "analyzer_errors" {
  alarm_name          = "${local.name_prefix}-analyzer-errors"
  alarm_description   = "Analyzer Lambda error count exceeded threshold — check CloudWatch logs"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.analyzer.function_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "analyzer_duration" {
  alarm_name          = "${local.name_prefix}-analyzer-duration"
  alarm_description   = "Analyzer Lambda P99 duration approaching timeout (${var.lambda_timeout_seconds}s)"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  extended_statistic  = "p99"
  # 80% of the configured timeout
  threshold          = var.lambda_timeout_seconds * 1000 * 0.8
  treat_missing_data = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.analyzer.function_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

# ---------------------------------------------------------------------------
# CloudWatch Metric Alarms — Notifier Lambda
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "notifier_errors" {
  alarm_name          = "${local.name_prefix}-notifier-errors"
  alarm_description   = "Notifier Lambda error count exceeded threshold"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.notifier.function_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "notifier_duration" {
  alarm_name          = "${local.name_prefix}-notifier-duration"
  alarm_description   = "Notifier Lambda P99 duration approaching 60s timeout"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  extended_statistic  = "p99"
  # 80% of the 60-second notifier timeout in milliseconds
  threshold          = 48000
  treat_missing_data = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.notifier.function_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

# ---------------------------------------------------------------------------
# CloudWatch Dashboard
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_dashboard" "pipeline_doctor" {
  dashboard_name = local.name_prefix

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 1
        properties = {
          markdown = "## pipeline-doctor Lambda Observability — ${var.environment}"
        }
      },

      # --- Analyzer invocations ---
      {
        type   = "metric"
        x      = 0
        y      = 1
        width  = 8
        height = 6
        properties = {
          title  = "Analyzer — Invocations"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", "${local.name_prefix}-analyzer", { stat = "Sum", period = 300, label = "Invocations" }],
            ["AWS/Lambda", "Errors", "FunctionName", "${local.name_prefix}-analyzer", { stat = "Sum", period = 300, label = "Errors", color = "#d62728" }],
            ["AWS/Lambda", "Throttles", "FunctionName", "${local.name_prefix}-analyzer", { stat = "Sum", period = 300, label = "Throttles", color = "#ff7f0e" }],
          ]
          yAxis = { left = { min = 0 } }
        }
      },

      # --- Analyzer duration ---
      {
        type   = "metric"
        x      = 8
        y      = 1
        width  = 8
        height = 6
        properties = {
          title  = "Analyzer — Duration (ms)"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", "${local.name_prefix}-analyzer", { stat = "p50", period = 300, label = "p50" }],
            ["AWS/Lambda", "Duration", "FunctionName", "${local.name_prefix}-analyzer", { stat = "p95", period = 300, label = "p95" }],
            ["AWS/Lambda", "Duration", "FunctionName", "${local.name_prefix}-analyzer", { stat = "p99", period = 300, label = "p99", color = "#d62728" }],
          ]
          annotations = {
            horizontal = [{
              label = "80% timeout"
              value = var.lambda_timeout_seconds * 1000 * 0.8
              color = "#ff7f0e"
            }]
          }
          yAxis = { left = { min = 0 } }
        }
      },

      # --- Notifier invocations ---
      {
        type   = "metric"
        x      = 16
        y      = 1
        width  = 8
        height = 6
        properties = {
          title  = "Notifier — Invocations"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", "${local.name_prefix}-notifier", { stat = "Sum", period = 300, label = "Invocations" }],
            ["AWS/Lambda", "Errors", "FunctionName", "${local.name_prefix}-notifier", { stat = "Sum", period = 300, label = "Errors", color = "#d62728" }],
          ]
          yAxis = { left = { min = 0 } }
        }
      },

      # --- Analyzer error rate ---
      {
        type   = "metric"
        x      = 0
        y      = 7
        width  = 12
        height = 6
        properties = {
          title  = "Analyzer — Error Rate (%)"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            [{
              expression = "100 * errors / MAX([errors, invocations])"
              label      = "Error rate %"
              id         = "error_rate"
              color      = "#d62728"
            }],
            ["AWS/Lambda", "Errors", "FunctionName", "${local.name_prefix}-analyzer", { id = "errors", visible = false, stat = "Sum", period = 300 }],
            ["AWS/Lambda", "Invocations", "FunctionName", "${local.name_prefix}-analyzer", { id = "invocations", visible = false, stat = "Sum", period = 300 }],
          ]
          yAxis = { left = { min = 0, max = 100 } }
        }
      },

      # --- S3 object counts ---
      {
        type   = "metric"
        x      = 12
        y      = 7
        width  = 12
        height = 6
        properties = {
          title  = "S3 — Object Count"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            ["AWS/S3", "NumberOfObjects", "BucketName", "${local.name_prefix}-manifests-${data.aws_caller_identity.current.account_id}", "StorageType", "AllStorageTypes", { stat = "Average", period = 86400, label = "Manifests bucket" }],
            ["AWS/S3", "NumberOfObjects", "BucketName", "${local.name_prefix}-analysis-${data.aws_caller_identity.current.account_id}", "StorageType", "AllStorageTypes", { stat = "Average", period = 86400, label = "Analysis bucket" }],
          ]
          yAxis = { left = { min = 0 } }
        }
      },
    ]
  })
}
