#!/usr/bin/env bash
# Build ARM64 images, push them to ECR, then redeploy the server through SSM Run Command
# (no SSH). Usage:  bash infra/aws/deploy.sh        (from the repo root, after terraform apply)
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash: do not rewrite /paths in AWS arguments

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PROFILE="${AWS_PROFILE:-default}"
TF="${TF:-$(command -v terraform || true)}"
if [ -z "$TF" ]; then
  TF="$(ls "$LOCALAPPDATA"/Microsoft/WinGet/Packages/Hashicorp.Terraform*/terraform.exe 2>/dev/null | head -1)"
fi

out() { (cd "$HERE" && "$TF" output -raw "$1"); }
REGION="$(out region)"
REGISTRY="$(out registry)"
API="$(out ecr_api)"
WEB="$(out ecr_web)"
INSTANCE="$(out instance_id)"
TAG="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || date -u +%Y%m%d%H%M%S)"

# The ECR token is too large for the Windows credential store ("wincred"): use a throwaway
# Docker config for this run only, keeping the current Docker context. Deleted on exit.
TMP_DOCKER="$(mktemp -d)"
trap 'rm -rf "$TMP_DOCKER"' EXIT
cp -r "$HOME/.docker/contexts" "$TMP_DOCKER/" 2>/dev/null || true
# A non-empty "auths" stops Docker from auto-selecting the Windows credential store.
printf '{"auths":{"placeholder.invalid":{}},"currentContext":"%s"}\n' "$(docker context show)" \
  > "$TMP_DOCKER/config.json"
if command -v cygpath >/dev/null; then export DOCKER_CONFIG="$(cygpath -w "$TMP_DOCKER")"; else export DOCKER_CONFIG="$TMP_DOCKER"; fi

echo "==> ECR login ($REGISTRY)"
aws ecr get-login-password --region "$REGION" --profile "$PROFILE" \
  | docker login --username AWS --password-stdin "$REGISTRY"

echo "==> Building and pushing linux/arm64 images (tag $TAG)"
docker buildx build --platform linux/arm64 -f "$ROOT/apps/api/Dockerfile" \
  -t "$API:latest" -t "$API:$TAG" --push "$ROOT"
docker buildx build --platform linux/arm64 -f "$ROOT/apps/web/Dockerfile" \
  -t "$WEB:latest" -t "$WEB:$TAG" --push "$ROOT"

echo "==> Redeploying on $INSTANCE via SSM"
CMD_ID="$(aws ssm send-command --region "$REGION" --profile "$PROFILE" \
  --instance-ids "$INSTANCE" --document-name AWS-RunShellScript \
  --comment "tri-mesure deploy $TAG" \
  --parameters 'commands=["/opt/tri-mesure/deploy.sh"]' \
  --query Command.CommandId --output text)"
aws ssm wait command-executed --region "$REGION" --profile "$PROFILE" \
  --command-id "$CMD_ID" --instance-id "$INSTANCE" || true
aws ssm get-command-invocation --region "$REGION" --profile "$PROFILE" \
  --command-id "$CMD_ID" --instance-id "$INSTANCE" \
  --query '{status: Status, output: StandardOutputContent, errors: StandardErrorContent}' --output yaml

echo "==> Live at $(out app_url)"
