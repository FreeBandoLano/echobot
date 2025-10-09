#!/bin/bash
# Deploy SSH-enabled Docker image to Azure

set -e

echo "🔧 Building Docker image with SSH support..."

# Get commit SHA and build time
GIT_COMMIT=$(git rev-parse HEAD)
BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Build the image
docker build \
    --build-arg GIT_COMMIT=$GIT_COMMIT \
    --build-arg BUILD_TIME=$BUILD_TIME \
    -t echobot-ssh:latest .

echo "✅ Docker image built successfully"

# Tag for Azure Container Registry
ACR_NAME="echobotbb"
IMAGE_NAME="echobot-ssh"
TAG="latest"

echo "🏷️  Tagging image for ACR..."
docker tag echobot-ssh:latest ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${TAG}

echo "🔐 Logging into Azure Container Registry..."
az acr login --name ${ACR_NAME}

echo "⬆️  Pushing image to ACR..."
docker push ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${TAG}

echo "🔄 Restarting Azure Web App..."
az webapp restart --name echobot-docker-app --resource-group echobot-rg

echo "✅ Deployment complete!"
echo ""
echo "Wait 30-60 seconds for the container to start, then test SSH:"
echo "  az webapp ssh --name echobot-docker-app --resource-group echobot-rg"
