variable "aws_region" {
  description = "AWS region to deploy into. Defaults to ap-southeast-2 (Sydney)."
  type        = string
  default     = "ap-southeast-2"
}

variable "instance_type" {
  description = "EC2 instance type. Defaults to t3.micro (Free Tier eligible in most regions)."
  type        = string
  default     = "t3.micro"

  validation {
    condition     = contains(["t3.micro", "t3.small", "t3.medium"], var.instance_type)
    error_message = "Instance type must be t3.micro, t3.small, or t3.medium to manage costs and compatibility."
  }
}

variable "amadeus_client_id" {
  description = "Amadeus API Client ID. Store in terraform.tfvars — never commit that file."
  type        = string
  sensitive   = true
}

variable "amadeus_client_secret" {
  description = "Amadeus API Client Secret. Store in terraform.tfvars — never commit that file."
  type        = string
  sensitive   = true
}

variable "project_name" {
  description = "Name prefix applied to all AWS resources for consistent tagging."
  type        = string
  default     = "travelwise"
}

variable "key_name" {
  description = "Name of the existing AWS EC2 Key Pair to attach for the secure SSH tunnel."
  type        = string
}

variable "ssh_allowed_cidr" {
  description = "CIDR block allowed to connect via SSH. Defaults to 0.0.0.0/0 for frictionless demo reviews. Restrict to a specific IP (e.g., 203.0.113.0/32) for production deployments."
  type        = string
  default     = "0.0.0.0/0"
}