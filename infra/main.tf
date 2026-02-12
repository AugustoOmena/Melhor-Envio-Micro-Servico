locals {
  build_dir = "${path.module}/.build"

  auth_zip  = "${local.build_dir}/auth.zip"
  cart_zip  = "${local.build_dir}/cart.zip"
  layer_zip = "${local.build_dir}/shared_layer.zip"
}

data "aws_caller_identity" "current" {}

resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

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

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_cloudwatch_log_group" "auth" {
  name              = "/aws/lambda/${var.project_name}-auth"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "cart" {
  name              = "/aws/lambda/${var.project_name}-cart"
  retention_in_days = 14
}

resource "aws_lambda_layer_version" "shared" {
  layer_name          = "${var.project_name}-shared"
  filename            = local.layer_zip
  source_code_hash    = filebase64sha256(local.layer_zip)
  compatible_runtimes = ["python3.11"]
}

resource "aws_lambda_function" "auth" {
  function_name = "${var.project_name}-auth"
  role          = aws_iam_role.lambda_role.arn
  runtime       = "python3.11"
  handler       = "handler.lambda_handler"

  filename         = local.auth_zip
  source_code_hash = filebase64sha256(local.auth_zip)

  timeout     = var.lambda_timeout_seconds
  memory_size = var.lambda_memory_mb
  layers      = [aws_lambda_layer_version.shared.arn]
  publish     = true

  environment {
    variables = {
      MELHOR_ENVIO_ENV           = var.melhor_envio_env
      MELHOR_ENVIO_CLIENT_ID     = var.melhor_envio_client_id
      MELHOR_ENVIO_CLIENT_SECRET = var.melhor_envio_client_secret
      HTTP_TIMEOUT_SECONDS       = "15"
    }
  }

  depends_on = [aws_cloudwatch_log_group.auth]
}

resource "aws_lambda_function" "cart" {
  function_name = "${var.project_name}-cart"
  role          = aws_iam_role.lambda_role.arn
  runtime       = "python3.11"
  handler       = "handler.lambda_handler"

  filename         = local.cart_zip
  source_code_hash = filebase64sha256(local.cart_zip)

  timeout     = var.lambda_timeout_seconds
  memory_size = var.lambda_memory_mb
  layers      = [aws_lambda_layer_version.shared.arn]
  publish     = true

  environment {
    variables = {
      MELHOR_ENVIO_ENV     = var.melhor_envio_env
      HTTP_TIMEOUT_SECONDS = "15"
    }
  }

  depends_on = [aws_cloudwatch_log_group.cart]
}

resource "aws_apigatewayv2_api" "http_api" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["authorization", "content-type"]
  }
}

resource "aws_apigatewayv2_integration" "auth" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.auth.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "cart" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.cart.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.auth.id}"
}

resource "aws_apigatewayv2_route" "auth_token" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /auth/token"
  target    = "integrations/${aws_apigatewayv2_integration.auth.id}"
}

resource "aws_apigatewayv2_route" "cart_insert" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /cart"
  target    = "integrations/${aws_apigatewayv2_integration.cart.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw_auth" {
  statement_id  = "AllowExecutionFromAPIGatewayAuth"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auth.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "apigw_cart" {
  statement_id  = "AllowExecutionFromAPIGatewayCart"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cart.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}
