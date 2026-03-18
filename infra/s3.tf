# ---------------------------------------------------------------------------
# S3 Buckets
# ---------------------------------------------------------------------------

# Manifests bucket — stores uploaded manifest.json files and dbt run results
resource "aws_s3_bucket" "manifests" {
  bucket = "${local.name_prefix}-manifests-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "manifests" {
  bucket = aws_s3_bucket.manifests.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "manifests" {
  bucket = aws_s3_bucket.manifests.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "manifests" {
  bucket = aws_s3_bucket.manifests.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "manifests" {
  bucket = aws_s3_bucket.manifests.id

  rule {
    id     = "archive-and-expire"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }
}

# CORS for the manifests bucket — allows browser-side direct PUT uploads
resource "aws_s3_bucket_cors_configuration" "manifests" {
  bucket = aws_s3_bucket.manifests.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "POST", "GET", "HEAD"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# EventBridge notification — fires when any object matching manifests/*.json is uploaded
resource "aws_s3_bucket_notification" "manifests" {
  bucket      = aws_s3_bucket.manifests.id
  eventbridge = true
}

# ---------------------------------------------------------------------------

# Analysis bucket — stores AI analysis results as structured JSON
resource "aws_s3_bucket" "analysis" {
  bucket = "${local.name_prefix}-analysis-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "analysis" {
  bucket = aws_s3_bucket.analysis.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "analysis" {
  bucket = aws_s3_bucket.analysis.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "analysis" {
  bucket = aws_s3_bucket.analysis.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "analysis" {
  bucket = aws_s3_bucket.analysis.id

  rule {
    id     = "archive-and-expire"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }
}
