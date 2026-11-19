terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Local state on purpose for a one-person demo (gitignored). For a team, switch to the
  # S3 backend with native locking:  backend "s3" { bucket = "..." key = "tri-mesure.tfstate"
  # region = "eu-west-3" use_lockfile = true }
}

provider "aws" {
  region  = var.region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project   = "tri-et-mesure"
      ManagedBy = "terraform"
      Purpose   = "student-demo-synthetic-data"
    }
  }
}
