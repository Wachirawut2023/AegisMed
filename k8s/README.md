# 🐳 AegisMed Kubernetes Deployment

Deploy AegisMed on Kubernetes for auto-scaling, high availability, and modern DevOps practices.

## Quick Start

### 1. Prerequisites

```bash
# Check kubectl is configured
kubectl cluster-info

# Verify you have the required CLIs
kubectl version --client
helm version
```

### 2. Build and Push Docker Image

```bash
# Build locally
docker build -t your-registry/aegismed:latest .

# Push to registry (Docker Hub, GCR, ECR, etc.)
docker push your-registry/aegismed:latest

# Or use your container registry:
# - Docker Hub: docker.io/youruser/aegismed
# - Google Container Registry: gcr.io/your-project/aegismed
# - AWS ECR: your-account.dkr.ecr.us-east-1.amazonaws.com/aegismed
# - Azure ACR: your-registry.azurecr.io/aegismed
```

### 3. Create Namespace and Secret

```bash
# Create namespace
kubectl create namespace aegismed

# Create secret with Fireworks API key
kubectl create secret generic aegismed-secrets \
  --from-literal=api-key=fw_your_key_here \
  -n aegismed
```

### 4. Update Configuration

Edit `deployment.yaml`:
```bash
# Change image to your registry
sed -i 's|your-registry/aegismed|gcr.io/your-project/aegismed|g' k8s/deployment.yaml

# Change email in ingress.yaml
sed -i 's|admin@example.com|your-email@example.com|g' k8s/ingress.yaml

# Change domain in ingress.yaml
sed -i 's|aegismed.example.com|aegismed.yourdomain.com|g' k8s/ingress.yaml
```

### 5. Install Dependencies (if needed)

```bash
# Install NGINX Ingress Controller
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace

# Install cert-manager for SSL certificates
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
```

### 6. Deploy to Kubernetes

```bash
# Apply all manifests
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/ingress.yaml

# Watch deployment progress
kubectl get pods -n aegismed -w

# Check service status
kubectl get svc -n aegismed

# Check ingress status
kubectl get ingress -n aegismed -w
```

### 7. Access Application

```bash
# Get external IP of load balancer (may take 1-2 minutes)
kubectl get svc -n aegismed aegismed-service

# Access at: http://<EXTERNAL-IP> or https://aegismed.yourdomain.com
```

---

## File Structure

```
k8s/
├── README.md           # This file
├── deployment.yaml     # Deployment, Service, HPA, ConfigMap, PDB
└── ingress.yaml        # Ingress, TLS certificates, routing
```

## Configuration

### Replicas

Edit in `deployment.yaml`:
```yaml
spec:
  replicas: 3  # Change starting replicas
```

### Auto-Scaling Limits

Edit `HorizontalPodAutoscaler`:
```yaml
minReplicas: 3  # Minimum pods
maxReplicas: 10 # Maximum pods
```

### Resource Limits

Edit in pod spec:
```yaml
resources:
  requests:
    cpu: "100m"      # Minimum guaranteed
    memory: "256Mi"
  limits:
    cpu: "500m"      # Maximum allowed
    memory: "512Mi"
```

### Model and Environment

Edit `ConfigMap` in `deployment.yaml`:
```yaml
data:
  MODEL: "accounts/fireworks/models/gemma-3-27b-it"
  DEMO_MODE: "false"
```

---

## Monitoring

### Pod Status

```bash
# View all pods
kubectl get pods -n aegismed

# Watch pods in real-time
kubectl get pods -n aegismed -w

# Get detailed pod info
kubectl describe pod <pod-name> -n aegismed
```

### Logs

```bash
# View logs from a pod
kubectl logs <pod-name> -n aegismed

# Stream logs (follow)
kubectl logs -f <pod-name> -n aegismed

# View logs from all pods in deployment
kubectl logs -f deployment/aegismed -n aegismed
```

### Scaling Status

```bash
# Check HPA status
kubectl get hpa -n aegismed -w

# Get detailed HPA info
kubectl describe hpa aegismed-hpa -n aegismed

# Check current CPU/memory metrics
kubectl top pods -n aegismed
kubectl top nodes
```

### Health Checks

```bash
# Port-forward to a pod for local testing
kubectl port-forward pod/<pod-name> 8000:8000 -n aegismed

# Then test locally
curl http://localhost:8000/health
curl http://localhost:8000/
```

---

## Troubleshooting

### Pods not starting

```bash
# Get pod details
kubectl describe pod <pod-name> -n aegismed

# Check events
kubectl get events -n aegismed --sort-by='.lastTimestamp'

# Check logs
kubectl logs <pod-name> -n aegismed
```

### Image pull errors

```bash
# Verify image exists
docker push your-registry/aegismed:latest

# Check imagePullSecrets if using private registry
kubectl get secrets -n aegismed
```

### Pending pods (insufficient resources)

```bash
# Check node capacity
kubectl top nodes
kubectl describe nodes

# Add more nodes to cluster or reduce replica count
kubectl scale deployment aegismed --replicas=2 -n aegismed
```

### SSL certificate not issuing

```bash
# Check cert-manager status
kubectl get certificaterequest -n aegismed
kubectl describe certificaterequest <name> -n aegismed

# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager -f
```

### High latency

```bash
# Check pod CPU/memory usage
kubectl top pods -n aegismed

# Check if HPA is scaling up
kubectl get hpa -n aegismed

# Check network policies
kubectl get networkpolicies -n aegismed
```

---

## Operations

### Update Deployment

```bash
# Update image to new version
kubectl set image deployment/aegismed \
  aegismed=your-registry/aegismed:v1.2.3 \
  -n aegismed

# Watch rollout progress
kubectl rollout status deployment/aegismed -n aegismed -w

# Rollback if needed
kubectl rollout undo deployment/aegismed -n aegismed
```

### Scale Manually

```bash
# Scale to specific number of replicas
kubectl scale deployment aegismed --replicas=5 -n aegismed

# HPA will override manual scaling based on metrics
```

### Update Configuration

```bash
# Update ConfigMap
kubectl edit configmap aegismed-config -n aegismed

# Pods will pick up changes on restart
kubectl rollout restart deployment/aegismed -n aegismed
```

### Update Secrets

```bash
# Delete old secret
kubectl delete secret aegismed-secrets -n aegismed

# Create new secret
kubectl create secret generic aegismed-secrets \
  --from-literal=api-key=fw_new_key_here \
  -n aegismed

# Restart pods to use new secret
kubectl rollout restart deployment/aegismed -n aegismed
```

### Drain Node (for maintenance)

```bash
# Cordon node (prevent new pods)
kubectl cordon <node-name>

# Drain existing pods (graceful eviction)
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# Maintenance...

# Uncordon when done
kubectl uncordon <node-name>
```

---

## Performance Tuning

### Reduce startup time

```yaml
# Lower initialDelaySeconds in probes
livenessProbe:
  initialDelaySeconds: 5  # Was 10
readinessProbe:
  initialDelaySeconds: 2  # Was 5
```

### Increase throughput

```yaml
# Increase resource requests
requests:
  cpu: "200m"
  memory: "512Mi"
limits:
  cpu: "1000m"
  memory: "1Gi"

# Let HPA scale more aggressively
maxReplicas: 20  # Was 10
```

### Improve latency

```yaml
# Reduce max surge to control load impact
strategy:
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0  # Zero downtime updates

# Tune HPA to be more responsive
behavior:
  scaleUp:
    stabilizationWindowSeconds: 0  # Immediate scale up
```

---

## Cost Optimization

### Reduce cost (small deployments)

```yaml
# Lower minimum replicas
minReplicas: 1  # Was 3

# Reduce resource requests
requests:
  cpu: "50m"
  memory: "128Mi"
limits:
  cpu: "250m"
  memory: "256Mi"

# Limit max replicas
maxReplicas: 5  # Was 10
```

### Estimate monthly cost

```
Calculation for Google GKE (example):

Control plane: $74.40 (fixed)
Node pool: 3 nodes × $40/month = $120/month
Load balancer: $18/month (included in EKS cost)
Storage: ~$5/month

Total: ~$217/month

+ Fireworks API costs (~$0.003 per diagnosis)
```

---

## Security

### Network policies are included

- Allows ingress from ingress controller
- Allows egress to DNS and Fireworks API
- Restricts pod-to-pod communication

### Pod security context

- Runs as non-root (UID 1000)
- Read-only root filesystem
- No privilege escalation

### RBAC (optional)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: aegismed
  namespace: aegismed
rules:
- apiGroups: [""]
  resources: ["services"]
  verbs: ["get", "watch"]
```

---

## Backup & Restore

### Backup deployment configuration

```bash
# Export current deployment
kubectl get deployment aegismed -n aegismed -o yaml > aegismed-backup.yaml

# Export all resources
kubectl get all -n aegismed -o yaml > aegismed-full-backup.yaml
```

### Restore from backup

```bash
# Apply saved configuration
kubectl apply -f aegismed-backup.yaml
```

---

## Multi-Region Deployment

To deploy across multiple regions:

```bash
# Install on each region's cluster
# Configure DNS round-robin or GeoDNS
# Point aegismed.yourdomain.com to multiple regional endpoints
# Ensures low-latency access globally
```

---

## Integration with CI/CD

### GitOps with Flux

```bash
# Install Flux
flux bootstrap github \
  --owner=youruser \
  --repo=aegismed-k8s \
  --path=clusters/production

# Auto-deploy on git push
# (Flux watches git repo, auto-applies changes)
```

### GitOps with ArgoCD

```bash
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Create Application that syncs from git
kubectl apply -f - <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: aegismed
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/youruser/aegismed.git
    targetRevision: main
    path: k8s/
  destination:
    server: https://kubernetes.default.svc
    namespace: aegismed
EOF
```

---

## Cleanup

```bash
# Delete all resources in namespace
kubectl delete namespace aegismed

# Delete specific resources
kubectl delete deployment aegismed -n aegismed
kubectl delete service aegismed-service -n aegismed
kubectl delete ingress aegismed-ingress -n aegismed
```

---

## FAQ

**Q: How many pods do I need?**  
A: Start with 3 (high availability). HPA will scale up/down automatically.

**Q: Can I use Kubernetes locally?**  
A: Yes, use Minikube, Docker Desktop, or k3s for development.

**Q: How do I enable HTTPS?**  
A: Use ingress.yaml with cert-manager (automatic Let's Encrypt).

**Q: What's the cost?**  
A: ~$150-300/month for a small cluster + $0.003/diagnosis API costs.

**Q: Can I use spot instances?**  
A: Yes, on AWS EKS, GKE, or AKS. Requires PDB for safe eviction.

**Q: How do I upgrade the app?**  
A: Push new image tag, kubectl updates deployment automatically.

---

## Support

- Kubernetes docs: https://kubernetes.io/docs/
- NGINX Ingress: https://kubernetes.github.io/ingress-nginx/
- cert-manager: https://cert-manager.io/docs/
- AegisMed docs: ../docs/

