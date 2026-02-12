locals {
  lambda_name = "${var.project_name}-api"
  build_dir   = "${path.module}/.build"

  layer_src_dir = "${local.build_dir}/layer"
  layer_py_dir  = "${local.layer_src_dir}/python"

  artifacts_dir = "${local.build_dir}/artifacts"
}

resource "null_resource" "build_layer" {
  triggers = {
    # Force rebuild when TF variables change (simple and effective).
    base_url = var.melhor_envio_base_url
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      mkdir -p "${local.artifacts_dir}"
      mkdir -p "${local.layer_py_dir}"
      rm -rf "${local.layer_py_dir}/"*
      python3 -m pip install --upgrade \
        --target "${local.layer_py_dir}" \
        --platform manylinux2014_x86_64 \
        --implementation cp \
        --python-version 311 \
        --abi cp311 \
        --only-binary=:all: \
        "aws-lambda-powertools>=2.0" \
        "aws-xray-sdk>=2.12" \
        "requests>=2.31" \
        "pydantic>=2.0"
    EOT
  }
}

data "archive_file" "layer_zip" {
  type        = "zip"
  source_dir  = local.layer_src_dir
  output_path = "${local.artifacts_dir}/dependencies-layer.zip"

  depends_on = [null_resource.build_layer]
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/me_microservice"
  output_path = "${local.artifacts_dir}/lambda.zip"
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.lambda_name}"
  retention_in_days = 14
}

resource "aws_iam_role" "lambda" {
  name = "${local.lambda_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_layer_version" "dependencies" {
  layer_name          = "${local.lambda_name}-dependencies"
  filename            = data.archive_file.layer_zip.output_path
  source_code_hash    = data.archive_file.layer_zip.output_base64sha256
  compatible_runtimes = ["python3.11"]
}

resource "aws_lambda_function" "api" {
  function_name = local.lambda_name
  role          = aws_iam_role.lambda.arn
  runtime       = "python3.11"
  handler       = "handler.lambda_handler"
  timeout       = 30
  memory_size   = 256

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  layers = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      MELHOR_ENVIO_BASE_URL      = var.melhor_envio_base_url
      MELHOR_ENVIO_CLIENT_ID     = var.melhor_envio_client_id
      MELHOR_ENVIO_CLIENT_SECRET = var.melhor_envio_client_secret
      MELHOR_ENVIO_DEFAULT_SCOPE = var.melhor_envio_default_scope
      HTTP_TIMEOUT_SECONDS       = tostring(var.http_timeout_seconds)
      USER_AGENT                 = var.user_agent
      POWERTOOLS_SERVICE_NAME    = var.project_name
      LOG_LEVEL                  = "INFO"
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

resource "aws_apigatewayv2_api" "http" {
  name          = "${var.project_name}-http"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw_invoke" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}
