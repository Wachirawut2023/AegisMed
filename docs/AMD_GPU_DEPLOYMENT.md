# 🚀 AMD GPU Droplet Deployment Guide — Cost-Optimized

This guide covers deploying AegisMed on an AMD GPU droplet for maximum cost efficiency.

## Quick Comparison: Three Deployment Options

| Option | Hosting | LLM Backend | GPU Needed? | Monthly Cost* | Best For |
|--------|---------|-------------|------------|--------------|----------|
| **A** (Recommended) | DigitalOcean/Linode | Fireworks AI (external API) | No GPU | ~$6-24 | Low traffic, cost-focused |
| **B** (Balanced) | AMD Developer Cloud | Fireworks AI | Small GPU | ~$20-50 | Demo/testing, moderate traffic |
| **C** (Self-hosted LLM) | DigitalOcean/Linode/AMD Cloud | Local Gemma + vLLM | REQUIRED (MI210/MI300X) | ~$200-500+ | Production, high traffic, privacy |

\* Rough estimates; actual costs depend on traffic volume and sustained usage.

---

## Option A: Fireworks AI Backend (Simplest & Cheapest)

### Use case:
- Low-to-moderate traffic (< 100 diagnoses/day)
- Cost-sensitive deployments
- Fastest to production

### Setup

#### 1. Create a minimal DigitalOcean/Linode droplet
```bash
# Minimum specs:
# - 1-2 vCPU
# - 2-4 GB RAM
# - Any CPU (no GPU needed)
# - ~$6-12/month basic tier
# - OS: Ubuntu 22.04 LTS
```

#### 2. SSH and deploy
```bash
ssh root@your_droplet_ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Clone and run
git clone https://github.com/wachirawut2023/AegisMed.git
cd AegisMed

# Set up .env with your Fireworks API key
cp .env.example .env
# Edit .env and add: FIREWORKS_API_KEY=fw_your_key_here

# Run with Docker
docker compose up -d --build

# Check status
docker ps
curl http://localhost:8000/health
```

#### 3. Expose to the internet (with Nginx reverse proxy)
```bash
sudo apt update && sudo apt install -y nginx

# Create /etc/nginx/sites-available/aegismed
sudo cat > /etc/nginx/sites-available/aegismed << 'EOF'
server {
    listen 80;
    server_name your_domain_or_ip;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/aegismed /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 4. (Optional) Add SSL with Let's Encrypt
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your_domain
```

### Cost breakdown:
- Droplet: $6-12/month (basic tier)
- Fireworks API: Depends on usage (~$0.001-0.005 per diagnosis with Gemma-3-27B)
- **Total: ~$8-15/month + per-request costs**

### Scaling Option A:
- Add load balancer (DigitalOcean LB: ~$12/month) for multiple droplets
- Use managed database for audit logs (PostgreSQL: ~$15-30/month)

---

## Option B: AMD Developer Cloud with Fireworks (Balanced)

### Use case:
- Higher traffic (100-500 diagnoses/day)
- Want to support AMD platform directly
- Good demonstration of AMD-powered application

### Setup

1. Sign up for AMD Developer Cloud & claim $100 GPU credit
2. Reserve a small AMD GPU (MI50 or MI210):
   - MI210: ~2x cheaper than enterprise GPUs
   - ~$0.50-1.00/hour = ~$350-700/month sustained

3. SSH into AMD Developer Cloud instance:
```bash
# Follow AMD's SSH setup guide
# Then deploy as in Option A, just SSH to the AMD instance instead

git clone https://github.com/wachirawut2023/AegisMed.git
cd AegisMed
docker compose up -d --build
```

### Cost breakdown:
- GPU (MI210): $350-700/month sustained
- Fireworks API: ~$5-50/month (minimal LLM usage)
- **Total: $355-750/month**

### When to upgrade to Option B:
- Option A's Fireworks API costs exceed $50-100/month
- You want to demonstrate "AMD platform support"
- You need guaranteed GPU availability

---

## Option C: Self-Hosted Gemma with vLLM + ROCm (Production)

### Use case:
- High-volume production (>500 diagnoses/day)
- Cost optimization over long term
- Privacy-critical deployments
- Direct AMD GPU utilization

### Architecture
```
AegisMed (FastAPI) → vLLM Server (ROCm) → Gemma-3-27B (Local AMD GPU)
```

### Prerequisites
- AMD GPU with ROCm support: MI210, MI250, MI300X
- 80+ GB GPU memory minimum (Gemma-3-27B needs ~45GB)
- 128+ GB system RAM for batching

### Setup

#### 1. Create instance on AMD Developer Cloud or similar
```bash
# Reserve large GPU instance:
# - AMD MI250 or MI300X (Recommended: MI300X 192GB for batching)
# - 64+ vCPU
# - 512+ GB RAM
# - Ubuntu 22.04 with ROCm pre-installed
```

#### 2. Install ROCm and vLLM
```bash
# SSH to instance
ssh root@your_gpu_instance

# Install ROCm (if not pre-installed)
# See: https://rocmdocs.amd.com/en/latest/deploy/linux/

# Create Python environment
python3 -m venv /opt/vllm
source /opt/vllm/bin/activate

# Install vLLM with ROCm support
pip install vllm[rocm]

# Download Gemma-3-27B model
# (This is ~45GB, will take time)
mkdir -p /models
cd /models
# Note: Requires HuggingFace token for Gemma access
huggingface-cli login  # paste your HF token

# Using transformers to download
python3 << 'EOF'
from huggingface_hub import snapshot_download
snapshot_download(
    "google/gemma-3-27b-it",
    local_dir="/models/gemma-3-27b-it",
    token="your_hf_token"
)
EOF
```

#### 3. Start vLLM server
```bash
source /opt/vllm/bin/activate

# Run vLLM server on GPU
python -m vllm.entrypoints.openai.api_server \
  --model /models/gemma-3-27b-it \
  --tensor-parallel-size 1 \
  --port 8001 \
  --dtype float16 \
  --gpu-memory-utilization 0.9 \
  --max-model-len 2048
```

#### 4. Deploy AegisMed with local vLLM backend
```bash
# Clone AegisMed on same machine or different instance
git clone https://github.com/wachirawut2023/AegisMed.git
cd AegisMed

# Create modified .env pointing to local vLLM
cat > .env << 'EOF'
# Use local vLLM instead of Fireworks
FIREWORKS_API_KEY=  # Leave empty, we'll use custom URL
FIREWORKS_API_URL=http://vllm_server_ip:8001/v1/chat/completions
MODEL=google/gemma-3-27b-it
DEMO_MODE=false
EOF
```

#### 5. Modify `aegismed/config.py` to support local vLLM
```python
# See separate patch below
```

#### 6. Run AegisMed with Docker
```bash
docker compose up -d --build
```

### Cost breakdown (MI300X):
- GPU instance (MI300X): ~$3-5/hour sustained = $2,000-3,500/month
- Storage: ~$100-200/month
- **Total: $2,100-3,700/month for unlimited diagnoses**

### Break-even analysis:
- If using Fireworks: 10,000+ diagnoses/month breaks even with Option C
- High-traffic deployments (1000+ diagnoses/day) save money with Option C

---

## Cost Optimization Tips (All Options)

### 1. Use Reserved Instances
- DigitalOcean/Linode: Reserve for 1-year discount (~30-40% savings)
- AMD Developer Cloud: Use multi-month reservations

### 2. Right-size your compute
- Don't over-provision: start with minimum, scale up if needed
- Monitor with: `docker stats` and `nvidia-smi` (or `rocm-smi` for AMD)

### 3. Use spot/preemptible instances
- DigitalOcean: No spot option, but reserved instances offer discounts
- AWS EC2: Spot instances (savings up to 70%, but interruptible)
- AMD Developer Cloud: Reserved capacity discounts

### 4. Optimize model inference (if using Option C)
- Use quantization: GPTQ or AWQ (reduces memory by 4x)
- Enable token batching in vLLM
- Set appropriate `max_model_len` for your use case

### 5. Cache demo mode responses
- Serve pre-computed responses for common cases
- Reduces LLM calls by 50-80% for demos

### 6. Rate limiting & usage monitoring
```bash
# Add to Nginx config for Option A/B
# /etc/nginx/sites-available/aegismed
limit_req_zone $binary_remote_addr zone=diagnosis_limit:10m rate=10r/m;
limit_req zone=diagnosis_limit burst=20 nodelay;
```

---

## Monitoring & Debugging

### Health check
```bash
curl http://your_droplet_ip:8000/health
```

### View logs
```bash
# Option A/B (with Docker)
docker logs aegismed -f

# Option C (with vLLM)
# vLLM server logs
tail -f /var/log/vllm.log
```

### Performance metrics
```bash
# Option A/B: CPU/Memory
docker stats

# Option C: GPU utilization
rocm-smi

# Fireworks API usage
# Check Fireworks dashboard at https://console.fireworks.ai
```

---

## Recommended Path to Production

1. **Start with Option A** (Fireworks API on cheap CPU droplet)
   - Deploy in < 15 minutes
   - Test with real traffic
   - Measure actual API costs

2. **If Fireworks costs exceed $50-100/month, migrate to Option B**
   - Spin up AMD GPU instance
   - Keep same code, just change hosting

3. **If traffic exceeds 500 diagnoses/day, migrate to Option C**
   - Self-host Gemma with vLLM
   - Long-term economics favor this option

---

## Troubleshooting

### "Fireworks API key not found"
```bash
# Check .env exists and has your key
cat .env | grep FIREWORKS_API_KEY

# Verify in Docker container
docker exec aegismed env | grep FIREWORKS
```

### "Cannot reach vLLM server"
```bash
# Check vLLM is running
ps aux | grep vllm

# Test connectivity
curl http://vllm_server_ip:8001/v1/models
```

### "OOM: Out of memory on GPU"
- Reduce `max_model_len` in vLLM
- Enable tensor parallelism if multiple GPUs: `--tensor-parallel-size 2`
- Switch to quantized model (GPTQ, AWQ)

### "Slow response times"
- Monitor GPU utilization: `rocm-smi`
- Check if vLLM has backlog: check vLLM logs for queue length
- Enable batching: vLLM does this by default
- Scale to multiple replicas: use Docker Swarm or Kubernetes

---

## Next Steps

- **[Deployment scripts](/scripts/deploy-amd-gpu.sh)** — automated setup for Options A-C
- **[vLLM integration patch](/scripts/vllm-integration.patch)** — code changes to use local vLLM
- **[Cost calculator spreadsheet](#)** — estimate costs for your expected traffic

---

## FAQ

**Q: Can I start with Option A and upgrade later without downtime?**  
A: Yes. Both Option A and B use the same code. To migrate, update `.env` to point to Fireworks, and rebuild. Option C requires code changes but the app logic stays the same.

**Q: Will my Fireworks $50 credit cover Option A?**  
A: Likely yes, depending on volume. Gemma-3-27B costs ~$0.001-0.005 per diagnosis. $50 = ~10,000-50,000 diagnoses.

**Q: What's the minimum traffic to justify Option C?**  
A: ~100+ diagnoses/day (3,000/month). At that volume, Fireworks costs exceed $15-30/month, so the GPU's cost is better justified.

**Q: Can I use a different model?**  
A: Yes. Currently set to `gemma-3-27b-it`. You can use `llama-3.3-70b`, `mistral-7b`, etc. on Fireworks or locally with vLLM.

**Q: How do I handle multiple concurrent diagnosis requests?**  
A: 
- Option A/B: vLLM/Fireworks handle batching automatically
- Option C: vLLM queues requests; enable `--max-num-seqs` for aggressive batching

