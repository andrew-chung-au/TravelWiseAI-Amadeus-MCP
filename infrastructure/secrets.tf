# ---------------------------------------------------------------------------
# Secret Container — Defines the secret name, metadata, and deletion behavior.
# Setting recovery_window_in_days = 0 forces immediate deletion on destroy,
# preventing name conflicts during rapid create/destroy cycles.
# ---------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "amadeus" {
  name                    = "${var.project_name}/amadeus-credentials"
  description             = "Amadeus API credentials for the TravelWise MCP server"
  recovery_window_in_days = 0
}

# ---------------------------------------------------------------------------
# Secret Version — Stores the actual sensitive values.
# Encoded as a single JSON object to follow AWS multi-credential best practices,
# reduce API calls, and simplify IAM permissions (one ARN instead of many).
# ---------------------------------------------------------------------------
resource "aws_secretsmanager_secret_version" "amadeus" {
  secret_id = aws_secretsmanager_secret.amadeus.id
  secret_string = jsonencode({
    AMADEUS_CLIENT_ID     = var.amadeus_client_id
    AMADEUS_CLIENT_SECRET = var.amadeus_client_secret
  })
}
