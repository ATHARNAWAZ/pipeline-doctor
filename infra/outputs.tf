output "manifests_bucket_name" {
  description = "Name of the S3 bucket that stores uploaded manifest.json files"
  value       = aws_s3_bucket.manifests.bucket
}

output "manifests_bucket_arn" {
  description = "ARN of the manifests S3 bucket"
  value       = aws_s3_bucket.manifests.arn
}

output "analysis_bucket_name" {
  description = "Name of the S3 bucket that stores AI analysis result JSON files"
  value       = aws_s3_bucket.analysis.bucket
}

output "analysis_bucket_arn" {
  description = "ARN of the analysis S3 bucket"
  value       = aws_s3_bucket.analysis.arn
}

output "analyzer_lambda_arn" {
  description = "ARN of the analyzer Lambda function"
  value       = aws_lambda_function.analyzer.arn
}

output "analyzer_lambda_name" {
  description = "Name of the analyzer Lambda function"
  value       = aws_lambda_function.analyzer.function_name
}

output "analyzer_lambda_url" {
  description = "Function URL endpoint for direct HTTP invocation of the analyzer Lambda"
  value       = aws_lambda_function_url.analyzer.function_url
}

output "notifier_lambda_arn" {
  description = "ARN of the notifier Lambda function"
  value       = aws_lambda_function.notifier.arn
}

output "notifier_lambda_name" {
  description = "Name of the notifier Lambda function"
  value       = aws_lambda_function.notifier.function_name
}

output "eventbridge_rule_arns" {
  description = "Map of EventBridge rule names to their ARNs"
  value = {
    manifest_uploaded = aws_cloudwatch_event_rule.manifest_uploaded.arn
    daily_check       = aws_cloudwatch_event_rule.daily_check.arn
  }
}

output "sns_topic_arn" {
  description = "ARN of the SNS alerts topic"
  value       = aws_sns_topic.alerts.arn
}

output "cloudwatch_dashboard_url" {
  description = "URL to the CloudWatch dashboard for pipeline-doctor"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.pipeline_doctor.dashboard_name}"
}

output "analyzer_log_group" {
  description = "CloudWatch log group name for the analyzer Lambda"
  value       = aws_cloudwatch_log_group.analyzer.name
}

output "notifier_log_group" {
  description = "CloudWatch log group name for the notifier Lambda"
  value       = aws_cloudwatch_log_group.notifier.name
}
