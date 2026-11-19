# Tri & Mesure on AWS — lean, real, and cheap.
#
#   Browser ──HTTPS──▶ CloudFront (free TLS, security headers, caches /assets)
#                         │ HTTP, only CloudFront's IP ranges are allowed in
#                         ▼
#              EC2 t4g.micro (Graviton, AL2023)  ── Docker Compose:
#                 web (nginx) ─▶ api (FastAPI + analysis worker) ─▶ db (PostgreSQL 16)
#
#   Images: ECR · Secrets & config: SSM Parameter Store · Logs: CloudWatch
#   Access: SSM Session Manager (no SSH, no port 22) · Backups: daily EBS snapshots (DLM)

data "aws_caller_identity" "me" {}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  registry  = "${data.aws_caller_identity.me.account_id}.dkr.ecr.${var.region}.amazonaws.com"
  ssm_root  = "/${var.name}"
  log_group = "/${var.name}/containers"
}

# --- network: one public subnet, no NAT gateway (NAT would cost more than the server) ---

resource "aws_vpc" "main" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = var.name }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = var.name }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.42.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = false # the instance gets an Elastic IP instead
  tags                    = { Name = "${var.name}-public" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "${var.name}-public" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# Only CloudFront may reach the server: AWS-managed list of CloudFront origin-facing IPs.
data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_security_group" "app" {
  name        = "${var.name}-app"
  description = "HTTP from CloudFront only; no SSH (Session Manager instead)"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "HTTP from CloudFront origin-facing servers"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    prefix_list_ids = [data.aws_ec2_managed_prefix_list.cloudfront.id]
  }

  egress {
    description = "Pull images, call model vendors, reach AWS APIs"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# --- container registry ------------------------------------------------------------

resource "aws_ecr_repository" "app" {
  for_each             = toset(["api", "web"])
  name                 = "${var.name}-${each.key}"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration {
    scan_on_push = true
  }
  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "keep_recent" {
  for_each   = aws_ecr_repository.app
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the 5 most recent images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
      action       = { type = "expire" }
    }]
  })
}

# --- configuration and secrets (SSM Parameter Store, standard tier = free) --------------

resource "random_password" "auth_secret" {
  length  = 48
  special = false
}

resource "random_password" "postgres" {
  length  = 32
  special = false
}

locals {
  plain_env = {
    ENVIRONMENT        = "prod"
    LLM_PROVIDER       = var.llm_provider
    DAILY_BUDGET_EUR   = tostring(var.daily_budget_eur)
    WORKER_ENABLED     = "true"
    WORKER_CONCURRENCY = "2"
    RAW_RETENTION_DAYS = "30"
    API_IMAGE          = "${aws_ecr_repository.app["api"].repository_url}:latest"
    WEB_IMAGE          = "${aws_ecr_repository.app["web"].repository_url}:latest"
    AWS_REGION         = var.region
    LOG_GROUP          = local.log_group
  }
  secret_env = merge(
    {
      AUTH_SECRET       = random_password.auth_secret.result
      POSTGRES_PASSWORD = random_password.postgres.result
    },
    var.anthropic_api_key != "" ? { ANTHROPIC_API_KEY = var.anthropic_api_key } : {},
    var.openai_compat_api_key != "" ? { OPENAI_COMPAT_API_KEY = var.openai_compat_api_key } : {},
  )
}

resource "aws_ssm_parameter" "env_plain" {
  for_each = local.plain_env
  name     = "${local.ssm_root}/env/${each.key}"
  type     = "String"
  value    = each.value
}

resource "aws_ssm_parameter" "env_secret" {
  for_each = nonsensitive(toset(keys(local.secret_env)))
  name     = "${local.ssm_root}/env/${each.key}"
  type     = "SecureString"
  value    = local.secret_env[each.key]
}

# The compose file lives in SSM too: changing it is `terraform apply` + redeploy, no rebuild.
resource "aws_ssm_parameter" "compose" {
  name  = "${local.ssm_root}/compose"
  type  = "String"
  value = file("${path.module}/docker-compose.prod.yml")
}

# --- logs -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "containers" {
  name              = local.log_group
  retention_in_days = 14
}

# --- instance identity: least privilege ------------------------------------------------

resource "aws_iam_role" "instance" {
  name = "${var.name}-instance"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "ecr_read" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy" "app" {
  name = "${var.name}-app"
  role = aws_iam_role.instance.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadOwnConfig"
        Effect   = "Allow"
        Action   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
        Resource = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.me.account_id}:parameter${local.ssm_root}/*"
      },
      {
        Sid      = "DecryptSecureStringsViaSsmOnly"
        Effect   = "Allow"
        Action   = "kms:Decrypt"
        Resource = "*"
        Condition = {
          StringEquals = { "kms:ViaService" = "ssm.${var.region}.amazonaws.com" }
        }
      },
      {
        Sid      = "ShipContainerLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
        Resource = "${aws_cloudwatch_log_group.containers.arn}:*"
      },
    ]
  })
}

resource "aws_iam_instance_profile" "instance" {
  name = "${var.name}-instance"
  role = aws_iam_role.instance.name
}

# --- the server -----------------------------------------------------------------------

data "aws_ssm_parameter" "al2023_arm64" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

resource "aws_instance" "app" {
  ami                    = data.aws_ssm_parameter.al2023_arm64.value
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.instance.name

  # T4g defaults to "unlimited" and bills surplus CPU silently: stay in "standard".
  credit_specification {
    cpu_credits = "standard"
  }

  metadata_options {
    http_tokens                 = "required" # IMDSv2 only (SSRF protection)
    http_put_response_hop_limit = 2          # still reachable from containers
    http_endpoint               = "enabled"
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = var.volume_size_gb
    encrypted   = true
    tags        = { Name = "${var.name}-data", Backup = "daily" }
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    region   = var.region
    registry = local.registry
    ssm_root = local.ssm_root
  })

  # New AMI releases must not replace a running demo server by surprise.
  lifecycle {
    ignore_changes = [ami, user_data]
  }

  tags = { Name = var.name }
}

resource "aws_eip" "app" {
  domain   = "vpc"
  instance = aws_instance.app.id
  tags     = { Name = var.name }
}

# --- HTTPS front door -------------------------------------------------------------------

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_origin_request_policy" "all_viewer_except_host" {
  name = "Managed-AllViewerExceptHostHeader"
}

data "aws_cloudfront_response_headers_policy" "security" {
  name = "Managed-SecurityHeadersPolicy"
}

resource "aws_cloudfront_distribution" "app" {
  enabled         = true
  comment         = "Tri & Mesure (student demo, synthetic data)"
  price_class     = "PriceClass_100"
  is_ipv6_enabled = true
  http_version    = "http2and3"

  origin {
    origin_id   = "ec2"
    domain_name = aws_eip.app.public_dns
    custom_origin_config {
      http_port                = 80
      https_port               = 443
      origin_protocol_policy   = "http-only"
      origin_ssl_protocols     = ["TLSv1.2"]
      origin_read_timeout      = 60
      origin_keepalive_timeout = 5
    }
  }

  # Everything dynamic (API, index.html, SPA routes): never cached, all headers forwarded
  # (the Authorization header carries the session token).
  default_cache_behavior {
    target_origin_id           = "ec2"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id   = data.aws_cloudfront_origin_request_policy.all_viewer_except_host.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id
    compress                   = true
  }

  # Hashed static assets: cached at the edge.
  ordered_cache_behavior {
    path_pattern               = "/assets/*"
    target_origin_id           = "ec2"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id
    compress                   = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# --- backups: daily EBS snapshot, keep 3 ------------------------------------------------

resource "aws_iam_role" "dlm" {
  name = "${var.name}-dlm"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "dlm.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "dlm" {
  role       = aws_iam_role.dlm.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole"
}

resource "aws_dlm_lifecycle_policy" "daily" {
  description        = "${var.name} daily snapshots"
  execution_role_arn = aws_iam_role.dlm.arn
  state              = "ENABLED"

  policy_details {
    resource_types = ["VOLUME"]
    target_tags    = { Backup = "daily", Project = "tri-et-mesure" }

    schedule {
      name = "daily-3am-utc"
      create_rule {
        interval      = 24
        interval_unit = "HOURS"
        times         = ["03:00"]
      }
      retain_rule {
        count = 3
      }
      copy_tags = true
    }
  }
}

# --- optional cost alarm ------------------------------------------------------------------

resource "aws_budgets_budget" "monthly" {
  count        = var.budget_alert_email != "" ? 1 : 0
  name         = "${var.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "TagKeyValue"
    values = ["user:Project$tri-et-mesure"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_alert_email]
  }
}
