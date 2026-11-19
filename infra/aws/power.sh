#!/usr/bin/env bash
# Start or stop the demo server. Stopped = you only pay for the disk and the Elastic IP
# (about 5 $ / month instead of about 12 $). Usage: bash infra/aws/power.sh start|stop|status
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash: do not rewrite /paths in AWS arguments
HERE="$(cd "$(dirname "$0")" && pwd)"
PROFILE="${AWS_PROFILE:-default}"
TF="${TF:-$(command -v terraform || true)}"
if [ -z "$TF" ]; then
  TF="$(ls "$LOCALAPPDATA"/Microsoft/WinGet/Packages/Hashicorp.Terraform*/terraform.exe 2>/dev/null | head -1)"
fi
REGION="$(cd "$HERE" && "$TF" output -raw region)"
INSTANCE="$(cd "$HERE" && "$TF" output -raw instance_id)"
aws_() { aws --region "$REGION" --profile "$PROFILE" "$@"; }

case "${1:-status}" in
  start)
    aws_ ec2 start-instances --instance-ids "$INSTANCE" --query 'StartingInstances[0].CurrentState.Name' --output text
    aws_ ec2 wait instance-running --instance-ids "$INSTANCE"
    echo "running — the app is back in ~1 min at $(cd "$HERE" && "$TF" output -raw app_url)"
    ;;
  stop)
    aws_ ec2 stop-instances --instance-ids "$INSTANCE" --query 'StoppingInstances[0].CurrentState.Name' --output text
    ;;
  status)
    aws_ ec2 describe-instances --instance-ids "$INSTANCE" \
      --query 'Reservations[0].Instances[0].State.Name' --output text
    ;;
  *) echo "usage: $0 start|stop|status" >&2; exit 1 ;;
esac
