variable "cluster_name" {
  description = "The name of the EKS cluster."
  type        = string
  default     = "eks-cluster"
}

variable "region" {
  description = "The AWS region to deploy the EKS cluster in."
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "The CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "node_instance_types" {
  description = "A list of instance types for the EKS node group."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "desired_capacity" {
  description = "The desired number of worker nodes in the EKS node group."
  type        = number
  default     = 2
}

variable "min_capacity" {
  description = "The minimum number of worker nodes in the EKS node group."
  type        = number
  default     = 1
}

variable "max_capacity" {
  description = "The maximum number of worker nodes in the EKS node group."
  type        = number
  default     = 4
}

variable "environment" {
  description = "The environment name (e.g., dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "tags" {
  description = "A map of tags to apply to all resources."
  type        = map(string)
  default     = {}
}