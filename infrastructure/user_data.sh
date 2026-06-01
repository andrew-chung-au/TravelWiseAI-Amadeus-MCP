#!/bin/bash
# =============================================================================
# TravelWise AI: EC2 Bootstrap Script (user_data.sh)
#
# Executed once by cloud-init on first boot as root.
# Provisions the EC2 instance as a fully operational MCP server by:
#   1. Installing system dependencies (AWS CLI, uv, git)
#   2. Fetching Amadeus API credentials from AWS Secrets Manager via IAM role
#   3. Cloning the TravelWise application from GitHub
#   4. Launching the SSE server as a background process
#
# Design Decisions:
#   - AWS CLI is installed at runtime (not baked into AMI) for image portability
#   - Credentials are injected as env vars into the process, never written to disk
#   - Server runs as root (cloud-init context) but file ownership fixed to ubuntu
#   - If credentials are placeholder/mock, server activates graceful degradation
#
# Logs: /var/log/user-data.log (boot log), /home/ubuntu/mcp_server.log (server log)
# =============================================================================
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "Starting TravelWise MCP bootstrap sequence..."

# Step 1: Update the package list and install the tools this script needs
apt-get update -y
apt-get install -y git curl jq unzip

# Step 2: Install AWS CLI v2
# Required to fetch secrets from Secrets Manager before the server starts.
# Must be installed before Step 3 — the secrets fetch depends on it.
echo "Installing AWS CLI..."
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
unzip /tmp/awscliv2.zip -d /tmp
/tmp/aws/install
rm -rf /tmp/aws /tmp/awscliv2.zip
which aws || { echo "ERROR: AWS CLI install failed"; exit 1; }

# Step 3: Install 'uv' — a fast Python package manager used to run the MCP server
#         Installing to /usr/local/bin makes it available to all users on the system
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh
which uv || { echo "ERROR: uv install failed — check /var/log/user-data.log"; exit 1; }

# Step 4: Fetch the Amadeus API credentials from AWS Secrets Manager
#         The secret name and region are passed in by Terraform — they are never hardcoded here
echo "Retrieving Amadeus credentials from Secrets Manager..."
SECRET_JSON=$(aws secretsmanager get-secret-value \
  --region "${aws_region}" \
  --secret-id "${secret_name}" \
  --query SecretString \
  --output text)

# Parse the two keys out of the JSON response using jq
AMADEUS_CLIENT_ID=$(echo $SECRET_JSON | jq -r .AMADEUS_CLIENT_ID)
AMADEUS_CLIENT_SECRET=$(echo $SECRET_JSON | jq -r .AMADEUS_CLIENT_SECRET)

echo "✅ Secrets fetched. Client ID prefix: $${AMADEUS_CLIENT_ID:0:4}****"

# Step 5: Clone the project from GitHub
#         user_data runs as root, so we fix file ownership to the 'ubuntu' user afterwards
echo "Cloning repository..."
cd /home/ubuntu
git clone https://github.com/andrew-chung-au/TravelWiseAI-Amadeus-MCP.git
chown -R ubuntu:ubuntu TravelWiseAI-Amadeus-MCP
cd TravelWiseAI-Amadeus-MCP

# Step 6: Start the SSE server in the background using 'nohup'
#         This detaches it from cloud-init so it keeps running after the script finishes.
#         Credentials are passed directly to the process instead of exporting them globally.
echo "Starting SSE server on localhost:8000..."
nohup env AMADEUS_CLIENT_ID="$AMADEUS_CLIENT_ID" \
          AMADEUS_CLIENT_SECRET="$AMADEUS_CLIENT_SECRET" \
          uv run src/run_sse.py > /home/ubuntu/mcp_server.log 2>&1 &

echo "Bootstrap complete. The server is running and ready for SSH tunneling."
