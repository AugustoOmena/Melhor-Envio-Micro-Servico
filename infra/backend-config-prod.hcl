# If you already had state at key "MelhorEnvio/terraform.tfstate", copy that object in S3 to this key once
# before the first prod apply so Terraform keeps managing the same resources (prefix melhorenvio-ms).
bucket = "augusto-omena-tfstate-prod"
key    = "MelhorEnvio/prod/terraform.tfstate"
region = "us-east-1"
