# ---------------------------------------------------------------------------
# AMI — Dynamic lookup for the latest Ubuntu 24.04 LTS image.
# Ensures evergreen security patches without risking major-version drift.
# ---------------------------------------------------------------------------
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ---------------------------------------------------------------------------
# Security Group — Implements the Zero Trust SSH Tunnel architecture
# ---------------------------------------------------------------------------
resource "aws_security_group" "mcp_server" {
  name        = "${var.project_name}-mcp-sg"
  description = "Allow SSH tunnel access only. Restrict ssh_allowed_cidr in tfvars for production."
  vpc_id      = data.aws_vpc.default.id

  # ONLY port 22 is open. The MCP application runs on localhost inside the instance.
  ingress {
    description = "SSH access for secure tunnel"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ---------------------------------------------------------------------------
# EC2 Instance — Core compute node for the TravelWise MCP server
# ---------------------------------------------------------------------------
resource "aws_instance" "mcp_server" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = data.aws_subnets.default.ids[0]
  vpc_security_group_ids      = [aws_security_group.mcp_server.id]
  iam_instance_profile        = aws_iam_instance_profile.ec2_profile.name
  key_name                    = var.key_name
  associate_public_ip_address = true

  # Forces Terraform to recreate the instance if the bootstrap script changes
  user_data_replace_on_change = true

  # Injects Terraform-managed variables directly into the bash script
  user_data = templatefile("${path.module}/user_data.sh", {
    secret_name = "${var.project_name}/amadeus-credentials"
    aws_region  = var.aws_region
  })

  tags = {
    Name = "${var.project_name}-mcp-server"
  }
}