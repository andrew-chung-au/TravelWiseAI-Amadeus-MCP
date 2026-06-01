# ---------------------------------------------------------------------------
# Instance IP — Raw public address of the compute node
# ---------------------------------------------------------------------------
output "instance_public_ip" {
  description = "The public IP address of the EC2 instance."
  value       = aws_instance.mcp_server.public_ip
}

# ---------------------------------------------------------------------------
# SSH Tunnel Command — Complete copy‑paste command for establishing the tunnel
# Tilde (~) is intentionally unquoted so the shell expands it correctly.
# ---------------------------------------------------------------------------
output "ssh_tunnel_command" {
  description = "Run this command in a separate terminal to establish the secure SSH tunnel."
  value = format(
    "ssh -N -L 8500:127.0.0.1:8000 -i ~/.ssh/%s.pem -o StrictHostKeyChecking=accept-new ubuntu@%s",
    var.key_name,
    aws_instance.mcp_server.public_ip
  )
}

# ---------------------------------------------------------------------------
# Local MCP Endpoint — Only reachable while the SSH tunnel is active
# ---------------------------------------------------------------------------
output "mcp_endpoint" {
  description = "Add this URL to your MCP client config (requires the SSH tunnel to be active)."
  value       = "http://127.0.0.1:8500/sse"
}

# ---------------------------------------------------------------------------
# Next Steps — Printed to console after terraform apply completes
# ---------------------------------------------------------------------------
output "next_steps" {
  description = "Quick start instructions."
  value       = <<-EOT
    ✅ Deployment complete. To connect:
       1. Wait 60–90 seconds for the instance to finish bootstrapping.
       2. Run the SSH tunnel command shown above.
       3. Add the MCP endpoint URL to your Claude Desktop config.
  EOT
}