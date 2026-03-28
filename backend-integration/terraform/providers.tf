terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    # Injected at init time via -backend-config in deploy.ps1
    # Never hardcode bucket, key, or region here
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "tra3"
      Client      = var.client_name
      ManagedBy   = "terraform"
      Environment = var.environment
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
