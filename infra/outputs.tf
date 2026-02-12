output "api_base_url" {
  description = "Base URL for the HTTP API stage."
  value       = aws_apigatewayv2_api.http.api_endpoint
}

output "lambda_function_name" {
  description = "Deployed Lambda function name."
  value       = aws_lambda_function.api.function_name
}

