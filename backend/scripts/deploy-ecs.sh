#!/usr/bin/env bash
# Point the ECS Express service at a new image and wait until it's healthy.
# Only the image changes: environment variables, the DATABASE_URL secret, port and
# health check are read from the running service and kept as they are.
#
# Usage:   backend/scripts/deploy-ecs.sh <image-uri>
# Needs:   AWS CLI v2 (signed in), python3, curl.
# Env:     AWS_REGION (default us-east-2), ECS_SERVICE_ARN (default: the team's service).
set -euo pipefail

IMAGE="${1:?Usage: deploy-ecs.sh <image-uri>}"
REGION="${AWS_REGION:-us-east-2}"
SERVICE_ARN="${ECS_SERVICE_ARN:-arn:aws:ecs:us-east-2:231161110378:service/default/coverage-compass-backend-4320}"
CLUSTER="$(echo "$SERVICE_ARN" | cut -d/ -f2)"
SERVICE="$(echo "$SERVICE_ARN" | cut -d/ -f3)"
TIMEOUT_SECONDS="${DEPLOY_TIMEOUT_SECONDS:-900}"
export AWS_PAGER=""

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

aws ecs describe-express-gateway-service --region "$REGION" --service-arn "$SERVICE_ARN" \
  --output json > "$WORK/service.json"

python3 - "$WORK" "$IMAGE" <<'PY'
import json, sys
work, image = sys.argv[1], sys.argv[2]
svc = json.load(open(f"{work}/service.json"))["service"]
cfg = svc["activeConfigurations"][0]
container = dict(cfg["primaryContainer"])
print(f"current image: {container['image']}")
print(f"new image:     {image}")
container["image"] = image
json.dump(container, open(f"{work}/container.json", "w"))
open(f"{work}/endpoint", "w").write(cfg["ingressPaths"][0]["endpoint"])
open(f"{work}/health", "w").write(cfg.get("healthCheckPath") or "/v1/health")
PY

OLD_DEPLOYMENT="$(aws ecs describe-services --region "$REGION" --cluster "$CLUSTER" \
  --services "$SERVICE" --query 'services[0].deployments[0].id' --output text)"

aws ecs update-express-gateway-service --region "$REGION" --service-arn "$SERVICE_ARN" \
  --primary-container "file://$WORK/container.json" --query 'service.status.statusCode' --output text

ENDPOINT="$(cat "$WORK/endpoint")"
echo "Waiting for the new deployment to finish (up to $((TIMEOUT_SECONDS / 60)) minutes)..."
deadline=$(( $(date +%s) + TIMEOUT_SECONDS ))
while :; do
  read -r DEPLOYMENT STATE RUNNING <<<"$(aws ecs describe-services --region "$REGION" --cluster "$CLUSTER" \
    --services "$SERVICE" --query 'services[0].[deployments[0].id,deployments[0].rolloutState,runningCount]' --output text)"
  # Until ECS registers the new deployment, the newest one listed is still the old one.
  if [ "$DEPLOYMENT" = "$OLD_DEPLOYMENT" ]; then STATE="WAITING_FOR_NEW_DEPLOYMENT"; fi
  echo "  $(date +%H:%M:%S) rollout=$STATE running=$RUNNING"
  case "$STATE" in
    COMPLETED) break ;;
    FAILED)
      aws ecs describe-services --region "$REGION" --cluster "$CLUSTER" --services "$SERVICE" \
        --query 'services[0].events[0:5].message' --output text >&2
      echo "Deployment failed; ECS keeps or restores the previous version." >&2
      exit 1 ;;
  esac
  if [ "$(date +%s)" -ge "$deadline" ]; then echo "Timed out waiting for the deployment." >&2; exit 1; fi
  sleep 20
done

READY="$(curl -s -m 20 "https://$ENDPOINT/v1/ready" || true)"
echo "https://$ENDPOINT/v1/ready -> $READY"
[ "$READY" = '{"status":"ok"}' ] || { echo "Service deployed but not ready." >&2; exit 1; }
echo "Deployed $IMAGE"
