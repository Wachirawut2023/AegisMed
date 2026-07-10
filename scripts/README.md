# 🚀 AegisMed Deployment Scripts

Automated deployment scripts for AegisMed on AMD GPU droplets, with multiple cost-optimization options.

## Quick Start

### 1. Choose Your Option

| Script | Cost | Best For | Setup Time |
|--------|------|----------|-----------|
| `deploy-option-a.sh` | ~$8-15/mo | Low traffic, cost-focused | 5 min |
| `deploy-option-b-amd.sh` | ~$355-750/mo | AMD platform support, balanced | 10 min |
| `deploy-option-c-vllm.sh` | ~$900-1000/mo | High volume, privacy-critical | 30 min |

### 2. Calculate Costs for Your Volume

```bash
./cost-calculator.py 1000  # Calculate for 1000 diagnoses/month
```

## Deployment Scripts

### Option A: Fireworks API Backend (Simplest & Cheapest)

Use this if you want the fastest, cheapest deployment. The app runs on a minimal droplet and calls Fireworks AI for LLM inference.

```bash
# Prerequisites:
#   - DigitalOcean/Linode account
#   - Fireworks API key (from https://console.fireworks.ai)
#   - A domain name (optional)

./deploy-option-a.sh fw_your_key_here aegismed.example.com
```

**What it does:**
1. Creates `.env` with your Fireworks API key
2. Installs Docker
3. Clones AegisMed and starts it with `docker compose`
4. Installs Nginx and SSL certificate (optional)
5. Starts serving on port 8000 (or your domain)

**Outputs:**
- Running container accessible at `http://your_droplet_ip:8000`
- Nginx reverse proxy (if domain provided)
- SSL certificate from Let's Encrypt (if domain provided)

**Estimated cost:** $6-12/month droplet + $0.001-0.005 per diagnosis in Fireworks API costs

---

### Option B: AMD Developer Cloud with Fireworks

Use this if you want to demonstrate AMD platform support while keeping API inference costs low.

```bash
# Prerequisites:
#   - AMD Developer Cloud instance (MI50/MI210 recommended)
#   - SSH access configured
#   - Fireworks API key
#   - Ubuntu 22.04 LTS
#   - ROCm pre-installed (on AMD Cloud, usually included)

./deploy-option-b-amd.sh fw_your_key_here aegismed.amd-dev.example.com
```

**What it does:**
1. Checks ROCm and GPU availability
2. Installs Docker
3. Creates AMD-optimized Dockerfile with ROCm support
4. Clones AegisMed
5. Starts app with GPU device access
6. Installs Nginx with rate limiting
7. Sets up SSL certificate

**Outputs:**
- Running container with GPU support
- Nginx reverse proxy with request rate limiting
- Monitoring script at `./monitoring/monitor.sh`
- Docker Compose configuration for AMD (`docker-compose.amd.yml`)

**Estimated cost:** $350-700/month (MI210 sustained) + minimal API costs

---

### Option C: Self-Hosted Gemma with vLLM + ROCm (Production)

Use this for high-volume deployments where local LLM inference is cheaper than API calls.

```bash
# Prerequisites:
#   - AMD GPU instance (MI210/MI250/MI300X minimum)
#   - ROCm 6.0+ installed
#   - 80+ GB GPU memory available
#   - ~50 GB free disk space for model
#   - HuggingFace token (for Gemma model access)
#   - Docker installed
#   - Ubuntu 22.04 LTS

./deploy-option-c-vllm.sh hf_your_token aegismed.amd-dev.example.com /models
```

**What it does:**
1. Checks GPU memory and storage
2. Creates isolated Python venv for vLLM
3. Downloads Gemma-3-27B model (~45 GB, takes 10-20 minutes)
4. Creates systemd service for vLLM
5. Starts vLLM server with ROCm support
6. Clones AegisMed and configures it to use local vLLM
7. Starts AegisMed container pointing to local LLM
8. Sets up Nginx and SSL
9. Creates monitoring script

**Outputs:**
- vLLM systemd service running on `localhost:8001`
- AegisMed Docker container on `localhost:8000`
- Nginx reverse proxy with long timeouts for inference
- Monitoring script at `./monitoring/monitor-vllm.sh`
- Modified `aegismed/config.py` and `aegismed/llm.py` to use local vLLM

**Estimated cost:** $900-1000/month (includes GPU, admin time, storage)

---

## Cost Calculator

Estimate your total cost of ownership based on expected diagnosis volume:

```bash
./cost-calculator.py               # Interactive (prompts for volume)
./cost-calculator.py 1000          # For 1000 diagnoses/month
./cost-calculator.py 10000         # For 10,000 diagnoses/month
```

**Output includes:**
- Monthly cost for each option
- Breakeven points (when to upgrade from A to B to C)
- Cost per diagnosis
- Annual costs
- Recommendation based on your volume

---

## Monitoring & Operations

### Option A (Fireworks API)

```bash
# Check app status
docker ps
curl http://localhost:8000/health

# View logs
docker logs aegismed -f

# Monitor resource usage
docker stats

# Stop app
docker compose down

# Restart app
docker compose up -d
```

### Option B (AMD GPU + Fireworks)

```bash
# Check GPU utilization
rocm-smi

# Run monitoring dashboard
./monitoring/monitor.sh

# Continuous monitoring
watch -n 1 ./monitoring/monitor.sh

# View app logs
docker compose -f docker-compose.amd.yml logs -f
```

### Option C (Self-Hosted vLLM)

```bash
# Check vLLM service
systemctl status vllm
sudo journalctl -u vllm -f

# Check GPU
rocm-smi

# Run monitoring dashboard
./monitoring/monitor-vllm.sh

# View AegisMed logs
docker compose logs -f

# Restart services
sudo systemctl restart vllm       # Restart LLM server
docker compose restart            # Restart app
```

---

## Troubleshooting

### "Fireworks API key not found"
```bash
# Verify .env file
cat .env | grep FIREWORKS_API_KEY

# Check in Docker
docker exec aegismed env | grep FIREWORKS
```

### "GPU not detected"
```bash
# Check ROCm installation
rocm-smi

# List available devices
docker run --rm --device=/dev/kfd --device=/dev/dri rocm/rocm-terminal rocm-smi
```

### "Out of memory on GPU"
```bash
# For Option C, reduce model length in /etc/systemd/system/vllm.service:
# Change: --max-model-len 2048
# To:     --max-model-len 1024

sudo systemctl restart vllm
```

### "Slow API responses"
- Check GPU utilization: `rocm-smi` or `nvidia-smi`
- Verify vLLM queue length in logs: `sudo journalctl -u vllm -f`
- Consider: more GPU memory, tensor parallelism, or model quantization

### "Port 8000 already in use"
```bash
# Find what's using it
sudo lsof -i :8000

# Stop conflicting service or use different port
docker compose down
# Edit docker-compose.yml and change port
docker compose up -d
```

---

## Upgrading Between Options

### Option A → Option B

When Fireworks API costs exceed $50-100/month:

1. Stop Option A: `docker compose down`
2. Run Option B script: `./deploy-option-b-amd.sh`
3. Code stays the same, just different hosting

### Option B → Option C

When traffic exceeds 500 diagnoses/day:

1. Stop Option B: `docker compose down`
2. Run Option C script: `./deploy-option-c-vllm.sh`
3. Minor code patches (done by script) to use local vLLM

---

## Performance Tuning

### Option A
- Keep model/temperature/max_tokens as-is (Fireworks-optimized)
- Add caching for demo responses to reduce API calls

### Option B
- Same as Option A (uses Fireworks)
- Monitor GPU utilization to ensure adequate headroom

### Option C (vLLM)

Edit `/etc/systemd/system/vllm.service`:

```bash
# Increase throughput (more concurrent requests)
--max-num-seqs 256

# Reduce latency (fewer concurrent requests, faster per-request)
--max-num-seqs 16

# Use more GPU memory (better performance)
--gpu-memory-utilization 0.95

# Enable tensor parallelism (on multi-GPU systems)
--tensor-parallel-size 2

# Reduce memory (on smaller GPUs)
--dtype bfloat16
--max-model-len 1024
```

Then restart: `sudo systemctl restart vllm`

---

## Security Considerations

### All Options
- Always use HTTPS in production
- Enable rate limiting (included in Option B & C)
- Use firewall to restrict access if needed
- Rotate API keys regularly

### Option A
- Fireworks handles API security
- Store `FIREWORKS_API_KEY` securely (use `.env`, never commit)
- Monitor usage for unexpected API calls

### Option C (Additional)
- Gemma model never leaves your infrastructure
- Patient data stays local (no cloud API calls)
- Ensure GPU instance has strong network isolation

---

## Cleanup

### Remove Option A deployment
```bash
docker compose down -v      # Stop and remove volumes
# Droplet still running — delete via DigitalOcean/Linode dashboard
```

### Remove Option C deployment
```bash
# Stop services
docker compose down -v
sudo systemctl stop vllm
sudo systemctl disable vllm

# Remove vLLM
sudo rm -f /etc/systemd/system/vllm.service
sudo systemctl daemon-reload

# Remove model and venv
rm -rf /opt/vllm
rm -rf /models/gemma-3-27b-it

# Stop GPU instance via AMD Developer Cloud dashboard
```

---

## Environment Variables

### Common to all options

```bash
FIREWORKS_API_KEY      # Your Fireworks API key (empty for Option C)
FIREWORKS_API_URL      # API endpoint (auto-set, can override for vLLM)
MODEL                  # Model name (default: gemma-3-27b-it)
DEMO_MODE              # true/false/auto (demo pre-written responses)
```

### Option C (vLLM-specific)

Automatically set in `/etc/systemd/system/vllm.service`:

```bash
HSA_OVERRIDE_GFX_VERSION   # Auto-detect GPU architecture
VLLM_LOGGING_LEVEL         # Set to INFO or DEBUG for troubleshooting
```

---

## FAQ

**Q: Which option is best for starting out?**  
A: Option A. Fastest to deploy (5 min), cheapest ($8-15/mo base), can upgrade later.

**Q: Can I switch options without losing data?**  
A: Yes, if using a database. Currently AegisMed is stateless (no data persistence). See docs/API.md for adding persistence.

**Q: How much does the Fireworks $50 credit cover?**  
A: ~10,000-50,000 diagnoses, depending on model complexity.

**Q: Can I use a different LLM model?**  
A: Yes. Set `MODEL=accounts/fireworks/models/mistral-7b` (Option A/B) or download a different model (Option C).

**Q: What's the minimum volume to justify Option C?**  
A: ~100+ diagnoses/day. Breakeven is typically 3,000-5,000 diagnoses/month.

**Q: Can I mix options (e.g., Fireworks backup for Option C)?**  
A: Yes, but requires code changes to fallback if vLLM is unreachable. Not covered by these scripts.

---

## Support & Debugging

For detailed documentation, see:
- `/docs/AMD_GPU_DEPLOYMENT.md` — Full deployment guide with architecture
- `/docs/API.md` — API reference for custom integrations
- `/docs/ARCHITECTURE.md` — System architecture overview

For issues:
1. Check script output for errors
2. Review logs: `docker logs` or `sudo journalctl -u vllm`
3. Test connectivity: `curl http://localhost:8000/health`
4. Check resources: `docker stats` or `rocm-smi`

---

## License

These scripts are part of AegisMed (MIT License).

See `/LICENSE` for full license text.
