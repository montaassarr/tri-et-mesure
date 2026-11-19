output "app_url" {
  description = "Public HTTPS link to the demo"
  value       = "https://${aws_cloudfront_distribution.app.domain_name}"
}

output "instance_id" {
  description = "For start/stop and Session Manager (aws ssm start-session --target ...)"
  value       = aws_instance.app.id
}

output "registry" {
  value = local.registry
}

output "ecr_api" {
  value = aws_ecr_repository.app["api"].repository_url
}

output "ecr_web" {
  value = aws_ecr_repository.app["web"].repository_url
}

output "log_group" {
  value = aws_cloudwatch_log_group.containers.name
}

output "region" {
  value = var.region
}
