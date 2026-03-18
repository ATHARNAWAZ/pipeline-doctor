# ---------------------------------------------------------------------------
# Lambda deployment package — built from the backend/ directory
# ---------------------------------------------------------------------------

data "archive_file" "backend" {
  type        = "zip"
  source_dir  = "${path.module}/../backend"
  output_path = "${path.module}/../backend/lambda_deployment.zip"

  excludes = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".pytest_cache",
    "tests",
    "lambda_package",
    "lambda_deployment.zip",
    ".env",
    "Dockerfile",
  ]
}

# ---------------------------------------------------------------------------
# IAM — Analyzer Lambda
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "analyzer" {
  name               = "${local.name_prefix}-analyzer-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "analyzer" {
  # CloudWatch Logs — write only to its own log group
  statement {
    sid    = "CloudWatchLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.analyzer.arn}:*",
    ]
  }

  # S3 — read from manifests bucket only
  statement {
    sid    = "S3ReadManifests"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:HeadObject",
    ]

    resources = [
      "${aws_s3_bucket.manifests.arn}/*",
    ]
  }

  # S3 — write to analysis bucket only
  statement {
    sid    = "S3WriteAnalysis"
    effect = "Allow"

    actions = [
      "s3:PutObject",
      "s3:PutObjectAcl",
    ]

    resources = [
      "${aws_s3_bucket.analysis.arn}/*",
    ]
  }
}

resource "aws_iam_role_policy" "analyzer" {
  name   = "${local.name_prefix}-analyzer-policy"
  role   = aws_iam_role.analyzer.id
  policy = data.aws_iam_policy_document.analyzer.json
}

# ---------------------------------------------------------------------------
# IAM — Notifier Lambda
# ---------------------------------------------------------------------------

resource "aws_iam_role" "notifier" {
  name               = "${local.name_prefix}-notifier-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "notifier" {
  # CloudWatch Logs — write only to its own log group
  statement {
    sid    = "CloudWatchLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.notifier.arn}:*",
    ]
  }

  # S3 — read from analysis bucket only
  statement {
    sid    = "S3ReadAnalysis"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:HeadObject",
      "s3:ListBucket",
    ]

    resources = [
      aws_s3_bucket.analysis.arn,
      "${aws_s3_bucket.analysis.arn}/*",
    ]
  }

  # SNS — publish to the alerts topic
  statement {
    sid    = "SNSPublish"
    effect = "Allow"

    actions = [
      "sns:Publish",
    ]

    resources = [
      aws_sns_topic.alerts.arn,
    ]
  }
}

resource "aws_iam_role_policy" "notifier" {
  name   = "${local.name_prefix}-notifier-policy"
  role   = aws_iam_role.notifier.id
  policy = data.aws_iam_policy_document.notifier.json
}

# ---------------------------------------------------------------------------
# Lambda — Analyzer
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "analyzer" {
  function_name = "${local.name_prefix}-analyzer"
  role          = aws_iam_role.analyzer.arn
  handler       = "lambda_handler.analyze_handler"
  runtime       = "python3.11"

  filename         = data.archive_file.backend.output_path
  source_code_hash = data.archive_file.backend.output_base64sha256

  memory_size = var.lambda_memory_mb
  timeout     = var.lambda_timeout_seconds

  environment {
    variables = {
      ANTHROPIC_API_KEY    = var.anthropic_api_key
      DATABASE_URL         = var.database_url
      S3_ANALYSIS_BUCKET   = aws_s3_bucket.analysis.bucket
      SLACK_WEBHOOK_URL    = var.slack_webhook_url
      OPENAI_API_KEY       = var.openai_api_key
    }
  }

  depends_on = [
    aws_iam_role_policy.analyzer,
    aws_cloudwatch_log_group.analyzer,
  ]
}

# Lambda Function URL for direct HTTP invocation.
# Auth type is NONE — the Lambda itself validates the caller via shared secret
# header. Add IAM auth here once API Gateway or Cognito is wired up.
resource "aws_lambda_function_url" "analyzer" {
  function_name      = aws_lambda_function.analyzer.function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = false
    allow_origins     = ["*"]
    allow_methods     = ["POST", "GET"]
    allow_headers     = ["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key"]
    expose_headers    = ["X-Amz-Request-Id"]
    max_age           = 86400
  }
}

# Allow EventBridge to invoke the analyzer Lambda
resource "aws_lambda_permission" "analyzer_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.analyzer.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.manifest_uploaded.arn
}

# ---------------------------------------------------------------------------
# Lambda — Notifier
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "notifier" {
  function_name = "${local.name_prefix}-notifier"
  role          = aws_iam_role.notifier.arn
  handler       = "lambda_handler.notify_handler"
  runtime       = "python3.11"

  filename         = data.archive_file.backend.output_path
  source_code_hash = data.archive_file.backend.output_base64sha256

  memory_size = 512
  timeout     = 60

  environment {
    variables = {
      ANTHROPIC_API_KEY    = var.anthropic_api_key
      DATABASE_URL         = var.database_url
      S3_ANALYSIS_BUCKET   = aws_s3_bucket.analysis.bucket
      SLACK_WEBHOOK_URL    = var.slack_webhook_url
      OPENAI_API_KEY       = var.openai_api_key
    }
  }

  depends_on = [
    aws_iam_role_policy.notifier,
    aws_cloudwatch_log_group.notifier,
  ]
}

# Allow EventBridge scheduled rule to invoke the notifier Lambda
resource "aws_lambda_permission" "notifier_eventbridge" {
  statement_id  = "AllowEventBridgeScheduledInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.notifier.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_check.arn
}

# Allow SNS to invoke the notifier Lambda
resource "aws_lambda_permission" "notifier_sns" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.notifier.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.alerts.arn
}
