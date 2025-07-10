#!/bin/bash

# ========================================================================================
# A script to build, push, and deploy a Node.js application to Amazon EKS.
#
# Features:
# - Builds a Docker image for the application.
# - Pushes the image to Amazon ECR.
# - Updates a Kubernetes deployment to use the new image.
# - Monitors the deployment rollout for success.
# - Automatically rolls back to the previous version if the deployment fails.
# - Includes robust error handling and logging.
# ========================================================================================

# --- Script Configuration ---
# Stop script on any error
set -e
# Treat unset variables as an error
set -u
# Pipestatus will be the status of the last command to exit with a non-zero status
set -o pipefail

# --- Application & AWS Configuration ---
# Name of your application (used for naming conventions)
APP_NAME="my-node-app"
# AWS Region where ECR and EKS are located
AWS_REGION="us-east-1"
# Name of your ECR repository
ECR_REPO_NAME="$APP_NAME"
# Name of your Kubernetes deployment
K8S_DEPLOYMENT_NAME="$APP_NAME-deployment"
# Name of the container within the deployment to update
K8S_CONTAINER_NAME="$APP_NAME"
# Kubernetes namespace where the application is deployed
K8S_NAMESPACE="default"
# Deployment timeout in seconds
DEPLOYMENT_TIMEOUT="300s"

# --- Logging Functions ---
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1: $2"
}

info() {
    log "INFO" "$1"
}

error() {
    log "ERROR" "$1" >&2
}

# --- Helper Functions ---

# Function to check for required command-line tools
check_dependencies() {
    info "Checking for required dependencies..."
    for cmd in aws kubectl docker; do
        if ! command -v "$cmd" &> /dev/null; then
            error "$cmd could not be found. Please install it and configure it properly."
            exit 1
        fi
    done
    info "All dependencies are satisfied."
}

# --- Main Deployment Logic ---
main() {
    check_dependencies

    # 1. Get Image Tag
    # Use the first argument as the image tag, or default to the short git hash
    local IMAGE_TAG="${1:-$(git rev-parse --short HEAD)}"
    info "Starting deployment for image tag: $IMAGE_TAG"

    # 2. Configure ECR variables
    info "Fetching AWS Account ID..."
    local AWS_ACCOUNT_ID
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    if [ -z "$AWS_ACCOUNT_ID" ]; then
        error "Failed to get AWS Account ID. Is the AWS CLI configured correctly?"
        exit 1
    fi
    local ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    local ECR_REPO_URI="${ECR_REGISTRY}/${ECR_REPO_NAME}"
    local FULL_IMAGE_NAME="${ECR_REPO_URI}:${IMAGE_TAG}"

    # 3. Build Docker Image
    info "Building Docker image: ${FULL_IMAGE_NAME}"
    docker build -t "$FULL_IMAGE_NAME" .
    info "Docker image built successfully."

    # 4. Authenticate with and Push to ECR
    info "Authenticating Docker with Amazon ECR..."
    aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"
    info "Authentication successful."

    info "Pushing image to ECR: ${FULL_IMAGE_NAME}"
    docker push "$FULL_IMAGE_NAME"
    info "Image pushed successfully to ECR."

    # 5. Update Kubernetes Deployment and Monitor
    info "Updating Kubernetes deployment '${K8S_DEPLOYMENT_NAME}' to use new image..."
    kubectl set image deployment/"${K8S_DEPLOYMENT_NAME}" \
        "${K8S_CONTAINER_NAME}"="${FULL_IMAGE_NAME}" \
        --namespace "${K8S_NAMESPACE}" \
        --record

    info "Watching rollout status (timeout: ${DEPLOYMENT_TIMEOUT})..."
    # The `rollout status` command will exit with a non-zero status if it fails
    if ! kubectl rollout status deployment/"${K8S_DEPLOYMENT_NAME}" --namespace "${K8S_NAMESPACE}" --timeout="${DEPLOYMENT_TIMEOUT}"; then
        error "Deployment failed!"
        
        # 6. Rollback on Failure
        error "Initiating rollback for deployment '${K8S_DEPLOYMENT_NAME}'..."
        kubectl rollout undo deployment/"${K8S_DEPLOYMENT_NAME}" --namespace "${K8S_NAMESPACE}"
        error "Rollback complete. The deployment has been reverted to the previous version."
        exit 1
    fi

    # 7. Health Check Validation (Success)
    # `kubectl rollout status` succeeding is our primary health check.
    # It confirms that the new pods are running and passing their readiness probes.
    info "----------------------------------------------------"
    info "✅ Deployment successful!"
    info "Application '${APP_NAME}' is now running version '${IMAGE_TAG}'."
    info "----------------------------------------------------"
}

# --- Script Execution ---
# Pass all script arguments to the main function
main "$@"