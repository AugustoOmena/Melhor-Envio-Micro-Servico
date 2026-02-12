terraform {
  backend "s3" {
    bucket = "augusto-omena-tfstate-dev"
    key    = "MelhorEnvio/terraform.tfstate"
    region = "us-east-1"
  }
}

