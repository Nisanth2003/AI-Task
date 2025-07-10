"""
EKS AI Automation Pipeline - Updated for Google Gemini API
"""

import os
import logging
import json
#import boto3
import google.generativeai as genai
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import re
import yaml

class EKSAutomationPipeline:
    def __init__(self, config_path: str = None):
        """Initialize the EKS automation pipeline with Gemini API"""
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        self.logger.info("EKS Automation Pipeline initialized")
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize Gemini client
        self._init_gemini_client()
        
        # Initialize AWS clients
        #self._init_aws_clients()
        
        # Create required directories
        self._create_directories()
        
        self.logger.info(f"Configuration loaded: {self.config}")

    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/eks_automation.log'),
                logging.StreamHandler()
            ]
        )

    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """Load configuration from file or environment variables"""
        default_config = {
            'cluster_name': os.getenv('EKS_CLUSTER_NAME', 'eks-cluster'),
            'region': os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
            'node_js_repo': 'https://github.com/acemilyalcin/sample-node-project',
            'ecr_repository': f"{os.getenv('AWS_ACCOUNT_ID', '123456789012')}.dkr.ecr.{os.getenv('AWS_DEFAULT_REGION', 'us-east-1')}.amazonaws.com",
            'gemini_model': 'gemini-2.5-pro',
            'max_tokens': 1048576,  # Increased for longer single file
            'temperature': 0.3,
            'vpc_cidr': '10.0.0.0/16',
            'node_instance_types': ['t3.medium'],
            'desired_capacity': 2,
            'min_capacity': 1,
            'max_capacity': 4
        }
        
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                file_config = json.load(f)
                default_config.update(file_config)
        
        return default_config

    def _init_gemini_client(self):
        """Initialize Google Gemini client"""
        try:
            api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
            if not api_key:
                raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set")
            
            genai.configure(api_key=api_key)
            self.gemini_model = genai.GenerativeModel(self.config['gemini_model'])
            self.logger.info("Gemini client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Gemini client: {str(e)}")
            raise

    #def _init_aws_clients(self):
        #"""Initialize AWS clients"""
        #try:
            #self.ec2_client = boto3.client('ec2', region_name=self.config['region'])
            #self.eks_client = boto3.client('eks', region_name=self.config['region'])
            #self.ecr_client = boto3.client('ecr', region_name=self.config['region'])
            #self.iam_client = boto3.client('iam', region_name=self.config['region'])
            #self.logger.info("AWS clients initialized successfully")
        #except Exception as e:
            #self.logger.error(f"Failed to initialize AWS clients: {str(e)}")
            #raise

    def _create_directories(self):
        """Create required directories"""
        directories = [
            'terraform', 'k8s', 'scripts',
            '.github/workflows', 'logs', 'sample-node-project'
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Directory created/verified: {os.path.abspath(directory)}")

    def _call_gemini_api(self, prompt: str) -> str:
        """Make API call to Gemini"""
        try:
            response = self.gemini_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=self.config['max_tokens'],
                    temperature=self.config['temperature']
                )
            )
            return response.text
        except Exception as e:
            self.logger.error(f"Gemini API call failed: {str(e)}")
            raise

    def generate_complete_terraform_main(self) -> str:
        """Generate complete Terraform main.tf file with all components"""
        try:
            prompt1 = f"""
            Generate a complete Terraform main.tf file for AWS EKS base infrastructure with the following specifications:
        
            CONFIGURATION:
            - Cluster name: {self.config['cluster_name']}
            - Region: {self.config['region']}
            - VPC CIDR: {self.config['vpc_cidr']}
            - Node instance types: {self.config['node_instance_types']}
            - Desired capacity: {self.config['desired_capacity']}
            - Min capacity: {self.config['min_capacity']}
            - Max capacity: {self.config['max_capacity']}
        
            INCLUDE THE FOLLOWING COMPONENTS:
            1. Terraform providers (aws, tls)
            2. VPC with ONLY public subnets across 2 Availability Zones (no private subnets)
            3. Internet Gateway for public internet access
            4. Route table and associations for public subnets
            5. EKS cluster and managed node group using public subnets
            6. IAM roles for EKS cluster and node group
            7. OIDC provider configuration for service accounts (IRSA)
            8. Security groups for EKS control plane and worker nodes
            9. ECR repository with lifecycle policy
            10. Outputs for VPC ID, Public Subnet IDs, Cluster Name, Cluster Endpoint, EKS Role ARN, OIDC URL
        
            IMPORTANT:
            -  Use correct resource dependencies
            -  Follow AWS EKS best practices
            -  Include proper tagging
            -  Ensure resource dependencies are handled correctly
            -  Do not include ALB Controller resources or Kubernetes provider config
            -  Use data sources for availability zones
        
            Return ONLY the complete Terraform code, no explanations or comments outside the code.
            """
        
            response = self._call_gemini_api(prompt1)
            terraform_content = self._extract_terraform_code(response)
        
            # Save to main.tf file
            terraform_file = "terraform/Stage1/main.tf"
            with open(terraform_file, 'w') as f:
                f.write(terraform_content)
    
            #stage_2
            prompt2 = f"""
            Generate a Terraform main.tf file to deploy the AWS ALB Controller on an existing EKS cluster with the following setup:
    
            ASSUMPTIONS:
            - The EKS cluster is already deployed using Terraform
            - The OIDC provider is already created
            - The IAM policy file for ALB Controller (iam-policy.json) is manually downloaded and placed in the same folder
            - Terraform has access to kubeconfig (either via AWS CLI or local file)
    
            INCLUDE THE FOLLOWING COMPONENTS:
            1. Terraform providers: aws, kubernetes, helm
            2. Kubernetes provider configuration using data from the existing EKS cluster
            3. IAM Role for the ALB Controller with:
            - IAM Policy loaded from a local file (iam-policy.json) using: file("${{path.module}}/iam-policy.json")
            - Trust relationship with the EKS OIDC provider and namespace `kube-system`, service account `aws-load-balancer-controller`
            4. Kubernetes service account for the ALB Controller in `kube-system` namespace
            5. Helm release to install AWS Load Balancer Controller
            6. Required labels and annotations to bind IAM role to the service account (IRSA)
            7. Outputs: IAM Role ARN, ALB Controller Helm release name, service account name
    
            REQUIREMENTS:
            - Use `data` blocks to fetch existing EKS cluster name, OIDC provider URL, and region
            - Ensure the IAM role uses proper assume role policy for service account via OIDC
            - Set proper `depends_on` relationships where needed (e.g., Helm release depends on service account and IAM role)
            - Do not include VPC, EKS, or OIDC creation in this file
            - Follow AWS and Kubernetes best practices throughout
            """
    
            response = self._call_gemini_api(prompt2)
            terraform_content = self._extract_terraform_code(response)
        
            # Save to main.tf file
            terraform_file = "terraform/Stage2/main.tf"
            with open(terraform_file, 'w') as f:
                f.write(terraform_content)
    
    
            self.logger.info(f"Generated complete Terraform main.tf: {terraform_file}")
            return terraform_content
    
        except Exception as e:
            self.logger.error(f"Failed to generate complete Terraform main.tf: {str(e)}")
            raise

    def _extract_terraform_code(self, response: str) -> str:
        """Extract Terraform code from Gemini response"""
        # Look for code blocks
        code_patterns = [
            r'```(?:terraform|hcl)?\n(.*?)\n```',
            r'```\n(.*?)\n```',
            r'```(.*?)```'
        ]
        
        for pattern in code_patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            if matches:
                return matches[0].strip()
        
        # If no code blocks found, return the response as-is
        return response.strip()

    def generate_terraform_variables(self) -> str:
        """Generate variables.tf file"""
        try:
            prompt = f"""
            Generate a Terraform variables.tf file for the EKS infrastructure with:
            - cluster_name (default: {self.config['cluster_name']})
            - region (default: {self.config['region']})
            - vpc_cidr (default: {self.config['vpc_cidr']})
            - node_instance_types (default: {self.config['node_instance_types']})
            - desired_capacity (default: {self.config['desired_capacity']})
            - min_capacity (default: {self.config['min_capacity']})
            - max_capacity (default: {self.config['max_capacity']})
            - environment (default: "dev")
            - tags (map of strings)
            
            Include proper descriptions and types for all variables.
            Return ONLY the Terraform variables code.
            """
            
            response = self._call_gemini_api(prompt)
            variables_content = self._extract_terraform_code(response)
            
            # Save to variables.tf file
            variables_file = "terraform/Stage1/variables.tf"
            with open(variables_file, 'w') as f:
                f.write(variables_content)
            
            self.logger.info(f"Generated Terraform variables.tf: {variables_file}")
            return variables_content
            
        except Exception as e:
            self.logger.error(f"Failed to generate Terraform variables.tf: {str(e)}")
            raise

    def generate_kubernetes_manifests(self) -> Dict[str, str]:
        """Generate Kubernetes deployment manifests"""
        try:
            prompt = f"""
            Generate Kubernetes YAML manifests for deploying a Node.js application on AWS EKS using ALB Ingress Controller.
 
                        Configuration:
                        
                        1. Image:
                        - Format: `AWS_ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/ECR_REPO:latest`
                        - The following values are injected via GitHub Secrets:
                            - `AWS_ACCOUNT_ID`
                            - `AWS_REGION`
                            - `ECR_REPOSITORY`
                        - Final format (example):
                            `123456789012.dkr.ecr.ap-south-1.amazonaws.com/node-app:latest`
                        
                        In the manifest, you may hardcode the final ECR image URL (not as `${{ secrets. }}`).
                        
                        2. Deployment:
                        - Name: node-app
                        - Replicas: 2
                        - Labels: `app: node-app`
                        - Container:
                            - Name: node-app
                            - Image: ECR URL (as above)
                            - Port: 3005
                            - readinessProbe: HTTP GET `/` on port 3005
                            - livenessProbe: HTTP GET `/` on port 3005
                            - initialDelaySeconds: 10
                            - periodSeconds: 10
                            - Resources:
                            - Requests: cpu: 100m, memory: 128Mi
                            - Limits: cpu: 500m, memory: 256Mi
                        
                        3. Service:
                        - Type: ClusterIP
                        - Name: node-app-service
                        - Selector: app: node-app
                        - Port: 3005 (port and targetPort)
                        
                        4. Ingress:
                        - Name: node-app-ingress
                        - Path: `/`
                        - Backend: node-app-service:3005
                        - Annotations (for ALB Ingress Controller):
                            - `kubernetes.io/ingress.class: alb`
                            - `alb.ingress.kubernetes.io/scheme: internet-facing`
                            - `alb.ingress.kubernetes.io/target-type: ip`
                            - `alb.ingress.kubernetes.io/backend-protocol: HTTP`
                            - `alb.ingress.kubernetes.io/listen-ports: '[{"HTTP":80}]'`
                        
                        Output:
                        - Combine all three manifests (Deployment, Service, Ingress)
                        - Separate them using `---`
                        - Output valid Kubernetes YAML
            """
            
            response = self._call_gemini_api(prompt)
            
            # Parse response to extract individual manifests
            manifests = self._parse_k8s_manifests(response)
            
            # Save manifests to files
            for name, content in manifests.items():
                file_path = f"{name}.yaml"
                with open(file_path, 'w') as f:
                    f.write(content)
                self.logger.info(f"Generated Kubernetes manifest: {file_path}")
            
            return manifests
            
        except Exception as e:
            self.logger.error(f"Failed to generate Kubernetes manifests: {str(e)}")
            raise

    def _parse_k8s_manifests(self, response: str) -> Dict[str, str]:
        """Parse Kubernetes manifests from response"""
        manifests = {}
        
        # Split by --- (YAML document separator)
        docs = response.split('---')
        
        for doc in docs:
            doc = doc.strip()
            if not doc:
                continue
            
            try:
                # Try to parse as YAML to get kind
                yaml_doc = yaml.safe_load(doc)
                if yaml_doc and 'kind' in yaml_doc:
                    kind = yaml_doc['kind'].lower()
                    manifests[kind] = doc
            except:
                # If parsing fails, use generic naming
                if 'Deployment' in doc:
                    manifests['deployment'] = doc
                elif 'Service' in doc:
                    manifests['service'] = doc
                elif 'Ingress' in doc:
                    manifests['ingress'] = doc
        
        return manifests

    def generate_github_actions_workflow(self) -> str:
        """Generate GitHub Actions workflow"""
        try:
            prompt = f"""
            Write a GitHub Actions workflow in YAML that:
                
                1. Builds a Docker image from the project root
                2. Tags and pushes it to AWS ECR
                3.setup kubectl and configure it  
                # 3. Configures kubectl using a base64 KUBECONFIG from secrets
                # 4. Installs Helm
                # 5. Installs Prometheus and Grafana using Helm into the `monitoring` namespace:
                # - Prometheus from `prometheus-community/prometheus`
                # - Grafana from `grafana/grafana`
                # - Use `LoadBalancer` service type for Grafana
                6. Applies `deployment.yaml`, `service.yaml`, and `ingress.yaml` using kubectl
                
                Environment details:
                - Use `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` , `AWS_ACCOUNT_ID` from GitHub secrets
                - `ECR_REPOSITORY` is the target ECR repo name
                # - Use `KUBE_CONFIG_DATA` secret to configure kubectl
                
                Respond with only the content of `.github/workflows/deploy.yml`. No markdown or explanation.
            """
            
            response = self._call_gemini_api(prompt)
            workflow_content = self._extract_yaml_content(response)
            
            # Save workflow file
            workflow_path = ".github/workflows/deploy.yml"
            with open(workflow_path, 'w') as f:
                f.write(workflow_content)
            
            self.logger.info(f"Generated GitHub Actions workflow: {workflow_path}")
            return workflow_content
            
        except Exception as e:
            self.logger.error(f"Failed to generate GitHub Actions workflow: {str(e)}")
            raise

    def _extract_yaml_content(self, response: str) -> str:
        """Extract YAML content from response"""
        # Look for YAML code blocks
        yaml_patterns = [
            r'```(?:yaml|yml)?\n(.*?)\n```',
            r'```\n(.*?)\n```'
        ]
        
        for pattern in yaml_patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            if matches:
                return matches[0].strip()
        
        return response.strip()

    def generate_dockerfile(self) -> str:
        """Generate Dockerfile for Node.js application"""
        try:
            prompt = """
           Generate a Dockerfile for a Node.js application that:
                
                1.Uses node:18-slim as the base image
                2.Sets the working directory to /app
                3.Copies package*.json and installs production dependencies with npm install --omit=dev
                4.Copies the rest of the app code
                5.Runs npm install again to ensure dependencies are installed
                6.Exposes port 3005
                7.Uses node app.js as the default command
                
                Do not explain just code no other words for explaining as i want ready to use
                ⚠️ Do not wrap the output in ``` or any markdown.
                ⚠️ Do not include any explanation or "Before running" section.
                ⚠️ Just return clean, executable DOCKERFILE code only.
            """
            
            response = self._call_gemini_api(prompt)
            dockerfile_content = self._extract_dockerfile_content(response)
            
            # Save Dockerfile
            dockerfile_path = "Dockerfile"
            with open(dockerfile_path, 'w') as f:
                f.write(dockerfile_content)
            
            self.logger.info(f"Generated Dockerfile: {dockerfile_path}")
            return dockerfile_content
            
        except Exception as e:
            self.logger.error(f"Failed to generate Dockerfile: {str(e)}")
            raise

    def _extract_dockerfile_content(self, response: str) -> str:
        """Extract Dockerfile content from response"""
        # Look for Dockerfile code blocks
        dockerfile_patterns = [
            r'```(?:dockerfile|docker)?\n(.*?)\n```',
            r'```\n(.*?)\n```'
        ]
        
        for pattern in dockerfile_patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            if matches:
                return matches[0].strip()
        
        return response.strip()

    def generate_deployment_scripts(self) -> Dict[str, str]:
        """Generate deployment and setup scripts"""
        try:
            scripts = {}
            
            # Generate setup script
            setup_prompt = f"""
            Generate a bash script for setting up the EKS environment with:
            - AWS CLI configuration check
            - kubectl installation check
            - Terraform initialization
            - EKS cluster creation
            - kubectl configuration
            - ALB controller installation
            - Cluster validation
            
            Script should be production-ready with error handling.
            """
            
            setup_response = self._call_gemini_api(setup_prompt)
            setup_content = self._extract_script_content(setup_response)
            scripts['setup'] = setup_content
            
            # Generate deploy script
            deploy_prompt = f"""
            Generate a bash script for deploying the Node.js application with:
            - Build Docker image
            - Push to ECR
            - Update Kubernetes manifests
            - Deploy to EKS
            - Health check validation
            - Rollback capability
            
            Script should include proper error handling and logging.
            """
            
            deploy_response = self._call_gemini_api(deploy_prompt)
            deploy_content = self._extract_script_content(deploy_response)
            scripts['deploy'] = deploy_content
            
            # Save scripts
            for script_name, content in scripts.items():
                script_path = f"scripts/{script_name}.sh"
                with open(script_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                # Make script executable
                os.chmod(script_path, 0o755)
                self.logger.info(f"Generated script: {script_path}")
            
            return scripts
            
        except Exception as e:
            self.logger.error(f"Failed to generate deployment scripts: {str(e)}")
            raise

    def _extract_script_content(self, response: str) -> str:
        """Extract script content from response"""
        # Look for bash/shell code blocks
        script_patterns = [
            r'```(?:bash|sh|shell)?\n(.*?)\n```',
            r'```\n(.*?)\n```'
        ]
        
        for pattern in script_patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            if matches:
                return matches[0].strip()
        
        return response.strip()

    def run_full_pipeline(self):
        """Run the complete automation pipeline"""
        try:
            self.logger.info("Starting full automation pipeline")
            
            # Generate single complete Terraform main.tf
            self.logger.info("Generating complete Terraform main.tf")
            self.generate_complete_terraform_main()
            
            # Generate Terraform variables and outputs
            self.logger.info("Generating Terraform variables.tf")
            self.generate_terraform_variables()
            

            # Generate Kubernetes manifests
            self.logger.info("Generating Kubernetes manifests")
            self.generate_kubernetes_manifests()
            
            # Generate GitHub Actions workflow
            self.logger.info("Generating GitHub Actions workflow")
            self.generate_github_actions_workflow()
            
            # Generate Dockerfile
            self.logger.info("Generating Dockerfile")
            self.generate_dockerfile()
            
            # Generate deployment scripts
            self.logger.info("Generating deployment scripts")
            self.generate_deployment_scripts()
            
            self.logger.info("Full automation pipeline completed successfully")
            self._print_completion_summary()
            
        except Exception as e:
            self.logger.error(f"Pipeline failed: {str(e)}")
            raise

    def _print_completion_summary(self):
        """Print completion summary"""
        print("\n" + "="*60)
        print("🎉 EKS AUTOMATION PIPELINE COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nGenerated Files:")
        print("📁 terraform/")
        print("   ├── Stage1/")
        print("       ├── main.tf         (Complete infrastructure)")
        print("       └── variables.tf    (Input variables)")
        print("   └── Stage2/")
        print("       └── main.tf         (ALB Controller setup)")
        print("\n")
        print("   ├── deployment.yaml (Application deployment)")
        print("   ├── service.yaml    (Service configuration)")
        print("   └── ingress.yaml    (Ingress configuration)")
        print("\n📁 .github/workflows/")
        print("   └── deploy.yml      (CI/CD pipeline)")
        print("\n📁 scripts/")
        print("   ├── setup.sh        (Environment setup)")
        print("   └── deploy.sh       (Application deployment)")
        print("\n")
        print("   └── Dockerfile      (Container configuration)")
        print("\n" + "="*60)
        print("Next Steps:")
        print("1. Review and customize the generated files")
        print("2. Set up AWS credentials and environment variables")
        print("3. Run: cd terraform && terraform init && terraform plan")
        print("4. Run: terraform apply")
        print("5. Configure kubectl: aws eks update-kubeconfig --region <region> --name <cluster-name>")
        print("6. Deploy application: kubectl apply -f k8s/")
        print("="*60)

    def test_gemini_connection(self) -> bool:
        """Test Gemini API connection"""
        try:
            test_prompt = "Say 'Hello, EKS automation pipeline!' and nothing else."
            response = self._call_gemini_api(test_prompt)
            self.logger.info(f"Gemini API test successful: {response}")
            return True
        except Exception as e:
            self.logger.error(f"Gemini API test failed: {str(e)}")
            return False

if __name__ == "__main__":
    pipeline = EKSAutomationPipeline()
    
    # Test connection
    if pipeline.test_gemini_connection():
        print("✅ Gemini API connection successful!")
        
        # Run full pipeline
        pipeline.run_full_pipeline()
    else:
        print("❌ Gemini API connection failed!")