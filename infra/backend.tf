# State path is set at init: terraform init -backend-config=backend-config-<dev|prod>.hcl
terraform {
  backend "s3" {
  }
}

