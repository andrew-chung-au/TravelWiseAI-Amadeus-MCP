# ---------------------------------------------------------------------------
# Trust Policy — Allows the EC2 service to assume this identity
# Validates policy structure natively at plan-time
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

# ---------------------------------------------------------------------------
# IAM Role — Assumed by the EC2 instance via the trust policy
# ---------------------------------------------------------------------------
resource "aws_iam_role" "ec2_role" {
  name               = "${var.project_name}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

# ---------------------------------------------------------------------------
# Inline Policy — Grants read access to the specific Amadeus secret only
# Using a standalone resource avoids deprecated inline policy arguments.
# ---------------------------------------------------------------------------
resource "aws_iam_role_policy" "secrets_read" {
  name = "${var.project_name}-secrets-read"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [aws_secretsmanager_secret.amadeus.arn]
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Instance Profile — Required wrapper to attach the IAM role to EC2 instances
# ---------------------------------------------------------------------------
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}