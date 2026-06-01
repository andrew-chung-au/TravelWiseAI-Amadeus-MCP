# Infrastructure — TravelWise AI

> ⚠️ **SUNSET NOTICE (July 2026):** Amadeus has officially decommissioned their Self-Service API tier as of July 17, 2026. Consequently, live data fetching via this MCP server is no longer functional without an Enterprise Amadeus account.
> 
> This repository is now maintained as an Architectural Reference. The Terraform infrastructure, Server-Sent Events (SSE) implementation, and dynamic Secrets Manager injection remain fully valid demonstrations of cloud deployment, zero-trust networking, and MCP tool orchestration.
 
This directory contains the Terraform code that provisions the **Remote Brain** for TravelWise AI: a secure, ephemeral AWS EC2 instance that hosts the Amadeus MCP server and accepts connections exclusively via an encrypted SSH tunnel.
 
> **On-Demand Architecture:** The infrastructure is designed to be spun up, tested, and torn down — not left running. There are no persistent costs between sessions. The IaC is the deliverable.

## Architecture Overview

```
┌─────────────────────┐         SSH Tunnel          ┌─────────────────────────┐
│   Local Agent       │  ─── (port 8500 → 8000) ──→ │   EC2 Instance (AWS)    │
│  (Kaggle / Claude)  │                             │   Amadeus MCP Server    │
│  localhost:8500/sse │                             │   localhost:8000/sse    │
└─────────────────────┘                             └─────────────────────────┘
                                                               ↑
                                                    IAM Role reads secrets
                                                    from AWS Secrets Manager
                                                    (never written to disk)
```

The server binds exclusively to `127.0.0.1` — it is never exposed to the public internet. Access requires an authenticated SSH tunnel, enforcing a **Zero-Trust application perimeter** at the network layer.

## Why EC2 (and not ECS or Lambda)?

> | Option          | Verdict              | Reason                                                                  |
> |-----------------|----------------------|-------------------------------------------------------------------------|
> | **EC2**         | Chosen               | Full SSE support, transparent infrastructure layer, no over-engineering |
> | **ECS Fargate** | Production evolution | Correct for high-traffic containerised workloads, but adds task         |
> |                 |                      | definitions, ECR, and ALB complexity unnecessary for a single-node demo |
> | **Lambda**      | Incompatible         | Hard execution timeouts break long-lived SSE connections by design      |

EC2 was chosen to keep the infrastructure readable and auditable. The goal is to demonstrate Terraform fundamentals clearly — not to optimise prematurely.

## Quick Start Deployment

### Prerequisites
- An active AWS Account with a Default VPC (run `aws ec2 create-default-vpc` if one does not exist).
- An AWS EC2 Key Pair (RSA `.pem` created in your target region).
- Terraform >= 1.3.0 installed locally.

#### 1. Configure the Environment

```bash
cd infrastructure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars to include your specific AWS Key Pair name and Amadeus credentials
```

Note: For evaluation purposes, leaving the Amadeus credentials as "mock" placeholders will automatically trigger the Level C Mock Engine.

#### 2. Deploy

```bash
terraform init
terraform validate
terraform plan
terraform apply
```

Terraform will output a dynamic public IP and a pre-formatted SSH tunnel command.

#### 3. Tear Down

```bash
terraform destroy
```

## Directory Structure

```
infrastructure/
├── README.md                 # This file
├── main.tf                   # Provider config, version pinning, default VPC data source
├── variables.tf              # Input layer with validation, sensitive flags, and descriptions
├── terraform.tfvars.example  # Credential template — copy to terraform.tfvars before deploying
├── iam.tf                    # IAM role, instance profile, and least-privilege Secrets Manager policy
├── secrets.tf                # AWS Secrets Manager container and versioned credential payload
├── ec2.tf                    # Compute resource, security groups, and templatefile injection
├── userdata.sh               # EC2 bootstrap script — installs deps, fetches secrets, starts server
└── outputs.tf                # Dynamic SSH command and MCP endpoint URL printed after apply
```

## Design Decisions & Engineering Trade-offs

### 1. Zero-Trust Security & Network Perimeter

Exposing unauthenticated application endpoints to the public internet is a critical vulnerability. This configuration enforces a strict Zero-Trust application perimeter:

- Localhost Binding: The Starlette web server is bound explicitly to `127.0.0.1` (localhost) rather than `0.0.0.0`.
- Ingress Restriction: Ingress is restricted entirely to port `22` (SSH). Application ports (e.g., `8500`) are closed.
- Cryptographic Tunneling: Reviewers must establish an SSH tunnel to access the service, heavily reducing the external attack surface.
- Cloud Agent Integration: The `ssh_allowed_cidr` variable defaults to `0.0.0.0/0` to allow testing via dynamic cloud agents (Kaggle/Google Colab). While true Zero Trust dictates locking this to a specific administrator IP (which is fully supported via variable override), this default ensures frictionless evaluation by shifting the security boundary entirely to the cryptographic RSA `.pem` key.

> | Mode                 | Example          | When to use                                         |
> | -------------------- | ---------------- | --------------------------------------------------- |
> | Strict (recommended) | "203.0.113.0/32" | Local machine with a static IP                      |
> | Cloud Agent          | "0.0.0.0/0"      | Kaggle, Google Colab, or any dynamic-IP environment |

### 2. Secrets Isolation & IAM Least Privilege
Hardcoded credentials and `.env` files are completely removed from the deployment pipeline to ensure zero-leakage secrets handling.
- Secrets Manager: Terraform accepts API keys locally but provisions them directly into a secure AWS Secrets Manager vault.
- Granular IAM Scoping: An instance profile is attached to the EC2 instance, granting it least-privilege access. The IAM policy is hard-scoped directly to the specific `aws_secretsmanager_secret.amadeus.arn` instead of using a resource wildcard (`*`), preventing credential escalation.
- Memory-Only Injection: The EC2 `user_data.sh` script dynamically fetches the secrets at boot and passes them to the application runtime via `nohup env VAR=VALUE`. Secrets are never written to disk.

Alternatively, credentials can be passed entirely via environment variables to avoid writing them to disk at all:

```bash
export TF_VAR_amadeus_client_id="your_key"
export TF_VAR_amadeus_client_secret="your_secret"
terraform apply
```
### 3. Application Integration: Graceful Degradation
To ensure the repository remains a fully functional demonstration despite the upstream deprecation of the Amadeus API, the application utilizes a Dependency Injection pattern paired with a Level C Mock Engine.

If the user_data.sh script passes placeholder API credentials (e.g., `mock_client_id_123`), the Python server detects this during `app_lifespan` initialization. It dynamically injects a `MockAmadeusClient` that perfectly mirrors the real SDK interface. This engine uses `random.uniform()` to dynamically generate realistic pricing, flight numbers, and durations within the precise structural bounds of the expected Amadeus schema, allowing reviewers to test the complete end-to-end network path without relying on external service uptime.

### 4. State Management & IaC Best Practices
- Local State: Terraform state is managed locally rather than utilizing a remote backend (e.g., S3 + DynamoDB). Because the infrastructure is meant to be provisioned, tested, and immediately destroyed by a single reviewer, local state provides the simplest, most frictionless developer experience.
- Provider Version Pinning: The HashiCorp AWS provider is locked pessimistically (`~> 5.0`) to ensure future major breaking changes do not silently degrade the infrastructure code.
- Deterministic Bootstrapping: The `user_data_replace_on_change` flag is enabled. Any change to the server configuration completely destroys and rebuilds the node, guaranteeing an immutable infrastructure pattern where the running instance perfectly reflects the declared code state.

## Troubleshooting

### 1. Port 8500 unreachable after tunnel connects
The SSH tunnel reports active but the local port never binds. This is most commonly caused by the AWS Security Group silently dropping Kaggle's dynamic outbound IP.
- Fix: Set `ssh_allowed_cidr = "0.0.0.0/0"` in `terraform.tfvars` and reapply.
- Alternative: Ensure you do not have another local application (like a local Docker container) already using port `8500`.

### 2. `ResourceAlreadyExistsException` on `terraform apply`
AWS Secrets Manager schedules deletions over a 7–30 day window by default. This project sets `recovery_window_in_days = 0` for immediate deletion. If you see this error, either wait for the deletion window to clear or change `project_name` in `terraform.tfvars`.

### 3. No default VPC found
Run `aws ec2 create-default-vpc --region your-region` before deploying.