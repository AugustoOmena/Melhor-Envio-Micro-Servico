output "api_base_url" {
  description = "Base URL for the HTTP API."
  value       = aws_apigatewayv2_api.http_api.api_endpoint
}

output "auth_token_url" {
  description = "Auth token endpoint URL."
  value       = "${aws_apigatewayv2_api.http_api.api_endpoint}/auth/token"
}

output "cart_url" {
  description = "Cart insert endpoint URL."
  value       = "${aws_apigatewayv2_api.http_api.api_endpoint}/cart"
}

