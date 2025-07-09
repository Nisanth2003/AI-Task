provider "kubernetes" {
  config_path = "~/.kube/config"
}
 
provider "helm" {
  kubernetes  = {
    config_path = "~/.kube/config"
  }
}
 
data "aws_eks_cluster" "eks" {
  name = "eks-cluster"
}
 
data "aws_eks_cluster_auth" "eks" {
  name = "eks-cluster"
}
 
# Reference existing OIDC provider (already created in Stage 1)
data "aws_iam_openid_connect_provider" "eks" {
  url = data.aws_eks_cluster.eks.identity[0].oidc[0].issuer
}
 
resource "aws_iam_policy" "alb_controller_policy" {
  name   = "AWSLoadBalancerControllerIAMPolicy-v2"
  path   = "/"
  policy = file("${path.module}/iam-policy.json")
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [policy]  # Prevent replace if file content changes
  }
}
 
# IAM Role for ALB Controller using OIDC
resource "aws_iam_role" "alb_sa_role" {
  name = "AmazonEKSLoadBalancerControllerRole-v2"
 
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Federated = data.aws_iam_openid_connect_provider.eks.arn
      },
      Action = "sts:AssumeRoleWithWebIdentity",
      Condition = {
        StringEquals = {
          "${replace(data.aws_eks_cluster.eks.identity[0].oidc[0].issuer, "https://", "")}:sub" = "system:serviceaccount:kube-system:aws-load-balancer-controller"
        }
      }
    }]
  })
}
 
# Attach the existing policy to the new role
resource "aws_iam_role_policy_attachment" "alb_sa_attach" {
  role       = aws_iam_role.alb_sa_role.name
  policy_arn = aws_iam_policy.alb_controller_policy.arn
}
 
# Kubernetes Service Account with IRSA annotation
resource "kubernetes_service_account" "alb_sa" {
  metadata {
    name      = "aws-load-balancer-controller"
    namespace = "kube-system"
    annotations = {
      "eks.amazonaws.com/role-arn" = aws_iam_role.alb_sa_role.arn
    }
  }
}
 
# Helm deployment of ALB Controller
resource "helm_release" "alb_controller" {
  name       = "aws-load-balancer-controller"
  namespace  = "kube-system"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
 
  timeout        = 500
  wait           = true
  force_update   = true
  skip_crds      = true
 
  set = [
    {
      name  = "clusterName"
      value = "eks-cluster"
    },
    {
      name  = "region"
      value = "us-east-1"
    },
    {
      name  = "vpcId"
      value = data.aws_eks_cluster.eks.vpc_config[0].vpc_id
    },
    {
      name  = "serviceAccount.create"
      value = "false"
    },
    {
      name  = "serviceAccount.name"
      value = kubernetes_service_account.alb_sa.metadata[0].name
    },
    {
      name  = "replicaCount"
      value = "1"
    }
  ]
 
  depends_on = [
    kubernetes_service_account.alb_sa
  ]
}
 
output "alb_controller_service_account" {
  value = kubernetes_service_account.alb_sa.metadata[0].name
}
 