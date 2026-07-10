# 🌐 AMD Cloud Alternatives — GPU-Free Deployment Options

Since AegisMed calls Fireworks AI for LLM inference (not running models locally), you can deploy on **any** AMD cloud infrastructure. Here are cost-optimized alternatives to GPU droplets.

## Quick Comparison: CPU vs GPU vs Serverless

| Option | Solution | Cost | Latency | Best For | Complexity |
|--------|----------|------|---------|----------|-----------|
| **CPU-1** | CPU Droplet | $6-24/mo | Low | Dev/demo, low traffic | ⭐ |
| **CPU-2** | Kubernetes | $30-100/mo | Low | Scaling, multiple regions | ⭐⭐⭐ |
| **Serverless-1** | Cloud Functions | $0-50/mo | Medium (cold start) | Bursty traffic, no infrastructure | ⭐⭐ |
| **Serverless-2** | Cloud Run | $0-100/mo | Medium | Container-native serverless | ⭐⭐ |
| **GPU-A** | GPU Droplet | $8-15/mo (CPU only) | Low | Running local LLM (expensive) | ⭐ |
| **GPU-B** | AMD GPU Cloud | $500-700/mo | Low | Production with local LLM | ⭐⭐ |

---

## Option 1: CPU-Only Droplet (Simple Scaling)

### Best for: Low-to-moderate traffic, minimal ops overhead

Since AegisMed just acts as an API proxy to Fireworks, you **don't need a GPU at all**.

### Architecture
```
User → Nginx (CPU Droplet) → AegisMed (Python FastAPI) → Fireworks API (external)
```

### Setup (even simpler than GPU)

```bash
# On AMD Developer Cloud or DigitalOcean (CPU-only instance)
# Requirements: 1-2 vCPU, 2-4 GB RAM

./scripts/deploy-option-a.sh fw_your_key_here your-domain.com

# That's it! No GPU needed.
```

### Cost Breakdown
- **CPU Droplet**: $6-24/month (DigitalOcean/Linode CPU-only)
- **Fireworks API**: $0.001-0.005 per diagnosis
- **Total**: $6-30/month base + API costs

### Scaling
```bash
# Load balance across multiple CPU droplets
# DigitalOcean Load Balancer: $12/month
# 3x CPU Droplets: $24/month
# Total: $36/month for high availability
```

### Pros
✅ Extremely cheap ($6/mo base)  
✅ No GPU complexity  
✅ Easy to scale horizontally (add more droplets)  
✅ Works perfectly for Fireworks API architecture  

### Cons
❌ Need to manage multiple instances for HA  
❌ Not for running local LLMs  

---

## Option 2: Kubernetes on AMD Cloud

### Best for: Production deployments, multi-region, auto-scaling

Run AegisMed on Kubernetes for **automatic scaling** based on traffic.

### Architecture
```
Internet → Load Balancer → Kubernetes Service
                            ↓
                    Pod 1: AegisMed + Nginx
                    Pod 2: AegisMed + Nginx
                    Pod 3: AegisMed + Nginx (scales automatically)
                    ↓
           Fireworks AI (external)
```

### Prerequisites
- AMD Kubernetes cluster (e.g., AMD on-prem, managed services)
- kubectl CLI
- Docker image built & pushed to registry

### Deployment Files

**Dockerfile** (same as current):
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY aegismed/ aegismed/
COPY static/ static/
EXPOSE 8000
CMD ["uvicorn", "aegismed.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Kubernetes Deployment** (`k8s/deployment.yaml`):
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aegismed
spec:
  replicas: 3  # Start with 3, scales up/down based on CPU
  selector:
    matchLabels:
      app: aegismed
  template:
    metadata:
      labels:
        app: aegismed
    spec:
      containers:
      - name: aegismed
        image: your-registry/aegismed:latest
        ports:
        - containerPort: 8000
        env:
        - name: FIREWORKS_API_KEY
          valueFrom:
            secretKeyRef:
              name: aegismed-secrets
              key: api-key
        resources:
          requests:
            cpu: "100m"
            memory: "256Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: aegismed-service
spec:
  type: LoadBalancer
  selector:
    app: aegismed
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: aegismed-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: aegismed
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

**Secrets** (store Fireworks key):
```bash
kubectl create secret generic aegismed-secrets \
  --from-literal=api-key=fw_your_key_here
```

### Deploy
```bash
# Build and push image
docker build -t your-registry/aegismed:latest .
docker push your-registry/aegismed:latest

# Deploy to Kubernetes
kubectl apply -f k8s/deployment.yaml

# Check status
kubectl get pods
kubectl get svc
```

### Cost Breakdown (Example: Google GKE or similar)
- **Control plane**: $70-100/month (usually included/flat fee)
- **Worker nodes** (3x small): $60-90/month
- **Load Balancer**: $15-20/month
- **Fireworks API**: $0.001-0.005 per diagnosis
- **Total**: $150-200/month base + API costs

### Auto-Scaling in Action
```bash
# Monitor scaling
kubectl get hpa -w

# HPA automatically:
# - Increases pods when CPU > 70%
# - Decreases pods when CPU < 70% for 5 min
# - Min 3 pods, max 10 pods
# - Cost adjusts automatically with traffic
```

### Pros
✅ Automatic scaling based on traffic  
✅ Self-healing (restarts failed pods)  
✅ Easy multi-region setup  
✅ Industry-standard platform  
✅ Cost scales with traffic (no paying for idle capacity)

### Cons
❌ More complex to set up & manage  
❌ Requires Kubernetes knowledge  
❌ Overkill for small deployments  
❌ Minimum cost higher (~$150/mo)

---

## Option 3: Serverless Functions (Cloud Functions / Cloud Run)

### Best for: Bursty traffic, minimal infrastructure, super low cost

Deploy AegisMed as a **serverless function** that only runs when requests come in.

### Architecture (Cloud Functions)
```
User Request → Cloud Functions Trigger → AegisMed Handler → Fireworks API
               (scales to zero when idle)
```

### Serverless Limitations for AegisMed
⚠️ **Cold start**: First request takes 5-15 seconds (Python bootstrap)  
⚠️ **Timeout**: Typical limit is 60-540 seconds (should be OK, Fireworks is <30s)  
⚠️ **Memory**: 256MB-8GB (AegisMed needs ~256MB)  
⚠️ **Concurrency**: Limited simultaneous requests (usually 100+, OK for diagnosis)

### Option 3A: Cloud Functions (Most Serverless)

**Minimal wrapper** (`cloud_function.py`):
```python
# Google Cloud Functions entry point
# Deploy this as a function, not the full FastAPI app

from aegismed import orchestrator, intake
from aegismed.main import PatientCase
import json

async def diagnose(request):
    """HTTP Cloud Function for diagnosis."""
    request_json = request.get_json()
    
    case = PatientCase(**request_json)
    
    # Run intake
    intake_response = await intake.ask_clarifying_questions(case)
    
    # Run diagnosis
    diagnosis = await orchestrator.run_full_board(case, intake_response)
    
    return {
        "status": "success",
        "diagnosis": diagnosis,
        "intake": intake_response
    }
```

**Deploy to Google Cloud Functions**:
```bash
gcloud functions deploy aegismed-diagnose \
  --runtime python3.11 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point diagnose \
  --set-env-vars FIREWORKS_API_KEY=fw_your_key_here \
  --memory 512MB \
  --timeout 300
```

### Option 3B: Cloud Run (Containerized Serverless)

Deploy the full FastAPI app as a container:

```bash
# Build container
docker build -t gcr.io/your-project/aegismed .

# Push to Google Container Registry
docker push gcr.io/your-project/aegismed

# Deploy to Cloud Run
gcloud run deploy aegismed \
  --image gcr.io/your-project/aegismed \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars FIREWORKS_API_KEY=fw_your_key_here \
  --memory 512Mi \
  --timeout 300
```

### Cost Breakdown

**Cloud Functions**:
- First 2M invocations/month: Free
- After that: $0.40 per million invocations
- For 1000 diagnoses/month: **~$0-1**
- Compute: $0.0000083 per GB-second
- **Total**: ~$1-5/month

**Cloud Run**:
- First 180K CPU-seconds/month: Free
- After that: $0.00002400 per CPU-second
- For 1000 diagnoses/month @ 10s each = 10,000 CPU-seconds: **Free**
- **Total**: ~$0-2/month until you exceed free tier

### Pros
✅ Ultra-cheap ($0-5/month for low traffic)  
✅ Scales to zero (no cost when idle)  
✅ No infrastructure to manage  
✅ Auto-scaling built-in  
✅ Pay only for what you use

### Cons
❌ Cold start latency (5-15 seconds on first request)  
❌ Cannot run local LLMs (timeout/memory constraints)  
❌ Debugging harder (logs in cloud provider)  
❌ Vendor lock-in (Google/AWS specific)  
❌ May be overkill if you need always-on service

---

## Cost Comparison: CPU-Only Solutions

### Scenario: 1000 diagnoses/month

```
┌─────────────────────────────────────────────────────────────┐
│ Option 1: CPU Droplet (Simple)                              │
│ Cost: $12 (droplet) + $3 (API) = $15/month                 │
│ ✅ BEST for simplicity                                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Option 2: Kubernetes (Scalable)                             │
│ Cost: $150 (K8s) + $3 (API) = $153/month                   │
│ ⚠️  Overkill for 1000/month, but auto-scales               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Option 3: Serverless (Pay-per-use)                          │
│ Cost: $0-2 (Cloud Run free tier) + $3 (API) = $3-5/month   │
│ ✅ BEST for bursty traffic, super cheap                    │
└─────────────────────────────────────────────────────────────┘
```

### Scenario: 50,000 diagnoses/month

```
┌─────────────────────────────────────────────────────────────┐
│ Option 1: CPU Droplet                                       │
│ Cost: $24 (or $36 with LB) + $150 (API) = $174-186/month  │
│ ✅ Simple, predictable cost                                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Option 2: Kubernetes                                        │
│ Cost: $200 (K8s nodes scaled to 5) + $150 (API) = $350/mo  │
│ ✅ Auto-scales, handles spikes without manual work         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Option 3: Serverless                                        │
│ Cost: $20 (past free tier) + $150 (API) = $170/month       │
│ ✅ Still cheaper than K8s, scales automatically           │
└─────────────────────────────────────────────────────────────┘
```

---

## Decision Tree: CPU vs Serverless

```
START: "I want to deploy AegisMed without a GPU"
│
├─ "Do I need always-on availability?"
│  ├─ YES  → Use CPU Droplet or Kubernetes
│  └─ NO   → Use Serverless (scales to zero)
│
├─ "What's my expected traffic pattern?"
│  ├─ Steady, predictable → CPU Droplet ($6-24/mo)
│  ├─ Variable, bursty → Serverless ($0-50/mo)
│  └─ High-volume, global → Kubernetes ($150+/mo)
│
└─ "Do I need to handle spikes automatically?"
   ├─ YES  → Kubernetes or Serverless (auto-scale)
   └─ NO   → CPU Droplet (simple, fixed cost)
```

---

## Comparison Matrix: All Options (CPU-Only)

| Criteria | CPU Droplet | Kubernetes | Serverless |
|----------|-------------|-----------|-----------|
| **Setup time** | 5 min | 30 min | 10 min |
| **Monthly cost** (low traffic) | $12 | $150 | $1 |
| **Monthly cost** (high traffic) | $24-36 | $200-300 | $20-50 |
| **Auto-scaling** | Manual | Automatic | Automatic |
| **Always-on** | ✅ | ✅ | ⚠️ (cold starts) |
| **Cold start latency** | None | None | 5-15 sec |
| **Infrastructure mgmt** | Minimal | Moderate | None |
| **Multi-region** | Manual | Easy | Easy |
| **Monitoring** | Docker logs | kubectl logs | Cloud provider |
| **Suitable for** | Dev/small prod | Large prod | Bursty traffic |

---

## Recommendation: CPU-Only Path

Since AegisMed **doesn't need a GPU** for API mode:

### Stage 1: Development (0-100 diagnoses/month)
```
→ Use CPU Droplet (Option 1)
  Cost: $12/month
  Setup: 5 minutes
  Effort: Minimal
  Script: ./scripts/deploy-option-a.sh
```

### Stage 2: Early Production (100-5000 diagnoses/month)
```
→ Stick with CPU Droplet + load balancer
  Cost: $36/month (3x droplets + LB)
  Setup: 10 minutes
  Effort: Add load balancer via DigitalOcean UI
```

### Stage 3: High-Volume Production (5000+ diagnoses/month)
```
→ Upgrade to Kubernetes or Serverless
  Kubernetes: If you need guaranteed latency <100ms
  Serverless: If budget is critical, can tolerate cold starts
  Cost: $150-200/month
```

### Stage 4: Enterprise (Multi-region, HA)
```
→ Kubernetes + CDN
  Cost: $300+/month
  Benefit: Global presence, redundancy, auto-failover
```

---

## When to Use GPU vs CPU

| Scenario | Solution | Reason |
|----------|----------|--------|
| Using Fireworks API | CPU-only | No LLM runs locally |
| Demo/proof-of-concept | CPU Droplet | Cheapest ($12/mo) |
| Want AMD showcase | Any of above | CPU still on AMD infra |
| Want local Gemma | GPU required | 45GB model needs space |
| Privacy-critical | GPU required | Data stays local |
| High-volume, cheap | CPU Kubernetes | Scales, costs less than GPU |
| Bursty traffic | Serverless | Scales to zero |

---

## Migration Path: CPU to GPU

If you start on **CPU (Fireworks)** but later want to add a **GPU (local Gemma)**:

```
CPU Droplet (Fireworks only)
    ↓
    Can add vLLM on same GPU instance
    ↓
GPU Droplet (Fireworks + local vLLM, user picks which to use)
    ↓
GPU Droplet (local vLLM only, no Fireworks)
```

This gives you **flexibility**: start cheap, add capability later.

---

## Conclusion

**If you use Fireworks API (not running local LLMs), you don't need a GPU at all.**

Best options:
1. **CPU Droplet** — Simple, cheap, perfect for starting out ($12/mo)
2. **Serverless** — Ultra-cheap for bursty traffic ($1-50/mo)
3. **Kubernetes** — For high-volume with auto-scaling ($150+/mo)

**GPU is only needed if you want to run Gemma locally** (privacy, unlimited inference, no API costs).

