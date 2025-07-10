#!/usr/bin/env bash

# ==============================================================================
#
# EKS Environment Setup Script
#
# Description:
#   This script automates the setup of an Amazon EKS cluster using Terraform.
#   It checks for dependencies, configures AWS credentials, initializes and
#   applies Terraform, configures kubectl, installs the AWS Load Balancer
#   Controller, and validates the cluster.
#
# Prerequisites:
#   - AWS CLI (v2) installed and configured with credentials.
#   - Terraform installed.
#   - kubectl installed.
#   - helm installed.
#   - A directory with Terraform files to define the EKS cluster.
#     (See the example `main.tf` in the comments below).
#
# Usage:
#   ./setup_eks.sh
#   ./setup_eks.sh --destroy
#
# ==============================================================================

# --- Script Configuration ---
# These variables should be configured to match your Terraform setup.

# The name of your EKS cluster (must match the one in your Terraform variables)
CLUSTER_NAME="my-eks-cluster"

# The AWS region where the cluster is deployed (must match your Terraform variables)
AWS_REGION="us-east-1"

# The name of the AWS Load Balancer Controller service account created by Terraform.
# This is a standard name, but verify if your Terraform module uses a different one.
ALB_CONTROLLER_SA_NAME="aws-load-balancer-controller"

# --- End of Configuration ---


# --- Bash "Strict Mode" ---
# Exit immediately if a command exits with a non-zero status.
# Treat unset variables as an error when substituting.
# Pipestatus is the exit status of the last command to exit with a non-zero status.
set -euo pipefail

# --- Helper Functions for Logging ---
# Use color codes for better readability
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# --- Main Functions ---

# Function to check for required command-line tools
check_dependencies() {
    log_info "Checking for required dependencies..."
    local missing_deps=0
    for cmd in aws kubectl terraform helm; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "Dependency '$cmd' is not installed or not in PATH."
            missing_deps=1
        fi
    done

    if [[ $missing_deps -eq 1 ]]; then
        log_error "Please install all required dependencies and try again."
        exit 1
    fi
    log_info "All dependencies are satisfied."
}

# Function to verify AWS CLI configuration and credentials
check_aws_config() {
    log_info "Verifying AWS CLI configuration..."
    if ! aws sts get-caller-identity --query "Account" --output text &> /dev/null; then
        log_error "AWS credentials are not configured or are invalid."
        log_error "Please run 'aws configure' or set environment variables."
        exit 1
    fi
    local account_id
    account_id=$(aws sts get-caller-identity --query "Account" --output text)
    local identity_arn
    identity_arn=$(aws sts get-caller-identity --query "Arn" --output text)
    log_info "Successfully authenticated with AWS."
    log_info "  - Account ID: ${account_id}"
    log_info "  - Identity:   ${identity_arn}"
}

# Function to initialize Terraform
terraform_init() {
    log_info "Initializing Terraform in the current directory..."
    if ! terraform init -input=false; then
        log_error "Terraform initialization failed."
        exit 1
    fi
    log_info "Terraform initialized successfully."
}

# Function to apply Terraform configuration and create the EKS cluster
terraform_apply() {
    log_info "Applying Terraform configuration to create EKS cluster..."
    log_warn "This may take 15-20 minutes."
    if ! terraform apply -auto-approve -input=false; then
        log_error "Terraform apply failed. The EKS cluster was not created."
        exit 1
    fi
    log_info "Terraform apply completed. EKS cluster infrastructure is provisioned."
}

# Function to configure kubectl to connect to the new EKS cluster
configure_kubectl() {
    log_info "Configuring kubectl to connect to cluster '${CLUSTER_NAME}'..."
    if ! aws eks update-kubeconfig --region "${AWS_REGION}" --name "${CLUSTER_NAME}"; then
        log_error "Failed to update kubeconfig for cluster '${CLUSTER_NAME}'."
        exit 1
    fi
    log_info "kubectl configured successfully."
}

# Function to install the AWS Load Balancer Controller using Helm
install_alb_controller() {
    log_info "Installing the AWS Load Balancer Controller..."

    # The VPC ID is required for the ALB controller helm chart.
    # We get it from the Terraform output.
    log_info "Fetching VPC ID from Terraform output..."
    local vpc_id
    vpc_id=$(terraform output -raw vpc_id)
    if [[ -z "$vpc_id" ]]; then
        log_error "Could not retrieve 'vpc_id' from Terraform output."
        log_error "Ensure your Terraform configuration has an output named 'vpc_id'."
        exit 1
    fi
    log_info "Found VPC ID: ${vpc_id}"

    log_info "Adding the EKS Helm chart repository..."
    helm repo add eks https://aws.github.io/eks-charts &> /dev/null
    helm repo update

    log_info "Installing/upgrading the aws-load-balancer-controller chart..."
    if ! helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
        --namespace kube-system \
        --set clusterName="${CLUSTER_NAME}" \
        --set serviceAccount.create=false \
        --set serviceAccount.name="${ALB_CONTROLLER_SA_NAME}" \
        --set region="${AWS_REGION}" \
        --set vpcId="${vpc_id}"; then
        log_error "Helm installation of AWS Load Balancer Controller failed."
        exit 1
    fi

    log_info "Waiting for AWS Load Balancer Controller deployment to be ready..."
    if ! kubectl wait --namespace kube-system \
        --for=condition=ready pod \
        --selector=app.kubernetes.io/name=aws-load-balancer-controller \
        --timeout=300s; then
        log_error "AWS Load Balancer Controller pods did not become ready in time."
        exit 1
    fi

    log_info "AWS Load Balancer Controller installed and running."
}

# Function to validate the cluster is up and nodes are ready
validate_cluster() {
    log_info "Validating EKS cluster status..."
    if ! kubectl get nodes -o wide; then
        log_error "Could not get cluster nodes. Validation failed."
        exit 1
    fi

    log_info "Checking system pods..."
    if ! kubectl get pods -n kube-system; then
        log_error "Could not get pods in kube-system namespace. Validation failed."
        exit 1
    fi

    log_info "Cluster validation successful. Nodes are registered and system pods are running."
}

# Function to destroy all resources created by Terraform
destroy_resources() {
    log_warn "You are about to destroy the EKS cluster and all related resources."
    read -p "Are you sure? Type 'destroy' to continue: " -r
    echo
    if [[ $REPLY == "destroy" ]]; then
        log_info "Destroying all resources managed by Terraform..."
        if ! terraform destroy -auto-approve; then
            log_error "Terraform destroy failed."
            exit 1
        fi
        log_info "All resources have been destroyed."
    else
        log_info "Destroy operation cancelled."
    fi
}

# --- Main Execution Logic ---
main() {
    if [[ "${1-}" == "--destroy" ]]; then
        check_dependencies
        check_aws_config
        terraform_init
        destroy_resources
    else
        log_info "Starting EKS Environment Setup..."
        
        check_dependencies
        check_aws_config
        terraform_init
        terraform_apply
        configure_kubectl
        install_alb_controller
        validate_cluster

        log_info "================================================================="
        log_info " EKS Cluster '${CLUSTER_NAME}' is ready! "
        log_info "================================================================="
        log_info "You can now connect to the cluster using:"
        log_info "  kubectl get nodes"
        log_info "  kubectl get pods --all-namespaces"
    fi
}

# Run the main function
main "$@"