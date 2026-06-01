# No backend block — state is managed locally.
# For shared/team deployments, configure an S3/DynamoDB backend here.

terraform {
  required_version = ">= 1.3.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ---------------------------------------------------------------------------
# AWS Provider — region and default tags
# ---------------------------------------------------------------------------
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      ManagedBy   = "Terraform"
      Environment = "demo"
    }
  }
}

# ---------------------------------------------------------------------------
# Data Sources — fetch the default VPC and its subnets
# Prerequisite: Run `aws ec2 create-default-vpc` if no default VPC exists.
# ---------------------------------------------------------------------------
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}