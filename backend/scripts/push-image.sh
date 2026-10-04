#!/usr/bin/env bash
# Build the backend image and push it to Amazon ECR, tagged with the current commit.
# Usage (from anywhere in the repo):  backend/scripts/push-image.sh
# Needs: Docker, AWS CLI v2 signed in (aws sts get-caller-identity works).
# Optional env: AWS_REGION (default us-east-2), ECR_REPOSITORY (default coverage-compass-backend).
set -euo pipefail

REGION="${AWS_REGION:-us-east-2}"
REPO="${ECR_REPOSITORY:-coverage-compass-backend}"
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

command -v aws >/dev/null || { echo "AWS CLI not found. See backend/docs/deploy-ecs.md, step 0." >&2; exit 1; }
command -v docker >/dev/null || { echo "Docker not found." >&2; exit 1; }

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
TAG="$(git -C "$BACKEND_DIR" rev-parse --short HEAD)"
if [ -n "$(git -C "$BACKEND_DIR" status --porcelain -- .)" ]; then
  TAG="${TAG}-dirty"
  echo "Warning: backend/ has uncommitted changes; tagging as ${TAG}." >&2
fi

if ! aws ecr describe-repositories --region "$REGION" --repository-names "$REPO" >/dev/null 2>&1; then
  echo "Creating ECR repository ${REPO}..."
  aws ecr create-repository --region "$REGION" --repository-name "$REPO" \
    --image-scanning-configuration scanOnPush=true >/dev/null
fi

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY" >/dev/null

IMAGE="${REGISTRY}/${REPO}"
# Fargate runs x86_64 by default; build for it even on an ARM laptop.
docker build --platform linux/amd64 -t "${IMAGE}:${TAG}" -t "${IMAGE}:latest" "$BACKEND_DIR"
docker push "${IMAGE}:${TAG}"
docker push "${IMAGE}:latest"

echo
echo "Pushed: ${IMAGE}:${TAG}"
echo "Use this image URI in the ECS service (or deploy :latest with 'Force new deployment')."
