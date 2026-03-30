terraform {
  required_version = ">= 1.5.0"

  backend "s3" {
    dynamodb_table = "tra3-terraform-state-lock"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}
