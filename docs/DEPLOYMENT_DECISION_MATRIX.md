# 🎯 AMD GPU Droplet Deployment — Decision Matrix

Quick reference to choose the right deployment option for your needs.

## Decision Tree

```
START: "I want to deploy AegisMed"
│
├─ "Is this a demo/proof-of-concept?"
│  └─ YES → Use Option A (Fireworks API)
│           ✅ Fastest setup (5 min)
│           ✅ Cheapest upfront ($8-15/mo)
│           ✅ Demo mode doesn't need API key
│
└─ "Is this production with real traffic?"
   │
   ├─ "Do you expect < 100 diagnoses/month?"
   │  └─ YES → Use Option A
   │           ✅ Cost: ~$10-50/mo
   │           ℹ️  Re-evaluate at 500+ diagnoses/month
   │
   └─ "Do you expect 100-1000+ diagnoses/month?"
      │
      ├─ "Is cost the main concern?"
      │  └─ YES → Use Option A
      │           ⚠️  Monitor Fireworks costs
      │           📊 May hit $100-500/mo in API costs
      │
      └─ "Can you afford GPU infrastructure?"
         │
         ├─ "Do you want to demonstrate AMD support?"
         │  └─ YES → Use Option B (AMD GPU + Fireworks)
         │           ✅ Shows AMD platform commitment
         │           ✅ Better scaling than Option A
         │           💰 Cost: ~$500-700/mo sustained
         │
         └─ "Do you need unlimited, cost-effective inference?"
            └─ YES → Use Option C (Self-hosted vLLM)
                     ✅ No per-request API costs
                     ✅ Full data privacy
                     ✅ Complete control
                     💰 Cost: ~$900-1000/mo flat
                     ✅ Better ROI at 5000+ diagnoses/month
```

---

## Side-by-Side Comparison

### Quick Facts

| Dimension | Option A | Option B | Option C |
|-----------|----------|----------|----------|
| **Setup time** | 5 min | 10 min | 30 min + downloads |
| **Skill level** | Beginner | Intermediate | Advanced |
| **Monthly cost** | $10-50 | $500-700 | $900-1000 |
| **Cost per diagnosis** | $0.001-0.01 | $0.01-0.1 | $0.3-1.0 | 
| **Per-diagnosis limits** | API rate limits | API rate limits | None |
| **Scaling** | Via Fireworks | Via Fireworks | Batch size tuning |
| **Admin overhead** | Low | Low | High |
| **Data privacy** | Fireworks servers | Fireworks servers | Your server |

### Features

| Feature | Option A | Option B | Option C |
|---------|----------|----------|----------|
| Runs locally | ❌ (calls Fireworks API) | ❌ (calls Fireworks API) | ✅ (local vLLM) |
| GPU required | ❌ | ✅ | ✅ (80+ GB) |
| HTTPS support | ✅ (via Nginx) | ✅ (via Nginx) | ✅ (via Nginx) |
| Rate limiting | ⚠️ (Fireworks) | ✅ (built-in) | ✅ (built-in) |
| Monitoring | ✅ (Docker) | ✅ (Docker + GPU) | ✅ (Docker + vLLM + GPU) |
| Automatic scaling | ❌ (manual) | ❌ (manual) | ⚠️ (batch tuning) |
| Multi-region | ❌ | ❌ | ❌ |
| HA/Failover | ❌ | ❌ | ❌ (requires custom setup) |

---

## Workflow: Choose Your Option

### 1. Cost-Sensitive

You want the absolute lowest cost to get started.

```
→ Use Option A
  Monthly: ~$8-15 (droplet) + API costs (0.1-1.0¢ per diagnosis)
  Start with: ./scripts/deploy-option-a.sh
  Upgrade path: Move to Option C when API costs exceed $200/mo
```

**Watch for:**
- Fireworks API usage growing beyond budget
- Traffic exceeding 1000+ diagnoses/month
- Time to upgrade: When monthly Fireworks costs > $100

---

### 2. Platform Support + Balanced Cost

You want to support AMD while keeping infrastructure reasonable.

```
→ Use Option B
  Monthly: ~$500-700 (MI210 GPU instance)
  Setup: ./scripts/deploy-option-b-amd.sh
  Good for: 500-5000 diagnoses/month
```

**Watch for:**
- API costs adding up (still using Fireworks)
- GPU utilization (ensure you're using the GPU)
- Time to upgrade: When traffic exceeds 5000+ diagnoses/month

---

### 3. Maximum Privacy + High Volume

You need full data privacy and unlimited inference.

```
→ Use Option C
  Monthly: ~$900-1000 (flat, no per-request costs)
  Setup: ./scripts/deploy-option-c-vllm.sh
  Good for: 5000+ diagnoses/month
```

**Watch for:**
- GPU memory (need 80+ GB for Gemma-3-27B)
- Inference latency (adjust batch size if needed)
- Admin overhead (vLLM + ROCm maintenance)

---

## Cost Comparison at Different Volumes

Based on real pricing (Gemma-3-27B at ~$0.003 per diagnosis via Fireworks):

### 100 diagnoses/month
```
Option A: $10-15 + ($0.003 × 100) = $10.30-15.30 ✅ BEST
Option B: $500 (overkill)
Option C: $900 (overkill)
```

### 1,000 diagnoses/month
```
Option A: $10-15 + ($0.003 × 1,000) = $13-18 ✅ BEST
Option B: $500 + ($0.003 × 1,000) = $503 
Option C: $900
```

### 5,000 diagnoses/month
```
Option A: $10-15 + ($0.003 × 5,000) = $25-30
Option B: $500 + ($0.003 × 5,000) = $515
Option C: $900 ✅ BEST (no per-request costs)
```

### 10,000 diagnoses/month
```
Option A: $10-15 + ($0.003 × 10,000) = $40-45
Option B: $500 + ($0.003 × 10,000) = $530
Option C: $900 ✅ BEST (by $35-55/mo)
```

### 50,000 diagnoses/month
```
Option A: $10-15 + ($0.003 × 50,000) = $160-165
Option B: $500 + ($0.003 × 50,000) = $650
Option C: $900 ✅ BEST (by $245-250/mo)
```

**Breakeven:** Option C becomes cheaper around **3,000-5,000 diagnoses/month**.

---

## Upgrade Paths

### A → B (when to move)

**Migrate when:**
- Fireworks API costs exceed $50-100/month
- Want to demonstrate AMD platform support
- Expect sustained traffic > 500 diagnoses/month

**Migration steps:**
1. Provision AMD GPU instance
2. Run `deploy-option-b-amd.sh` with same Fireworks key
3. Update DNS/routing to new instance
4. Decommission old droplet

**Downtime:** ~10 min (with DNS propagation 5-30 min)

### B → C (when to move)

**Migrate when:**
- Fireworks API costs exceed $300-400/month
- Traffic exceeds 5000+ diagnoses/month
- Need full data privacy

**Migration steps:**
1. Provision larger GPU instance (with 80+ GB memory)
2. Run `deploy-option-c-vllm.sh` to install vLLM + Gemma
3. Wait for model download (~30 min)
4. Run AegisMed on same instance pointing to vLLM
5. Test, then switch DNS
6. Decommission Option B instance

**Downtime:** ~15 min during cutover

### A → C (direct jump)

**Possible when:**
- Current on Option A but expecting rapid growth
- Want to avoid intermediate B step
- Ready to commit to self-hosted LLM

**Challenges:**
- Larger upfront GPU provisioning
- Model download takes time
- More complex operations

**Recommendation:** Go A → B → C incrementally (easier to reverse if needed).

---

## Operational Readiness Checklist

Before deploying, ensure you have:

### Option A
- [ ] DigitalOcean/Linode account
- [ ] Fireworks API key (get from console.fireworks.ai)
- [ ] Domain name (optional, for HTTPS)
- [ ] 15-30 min for setup & testing

### Option B
- [ ] AMD Developer Cloud account
- [ ] Active GPU instance reservation (MI210+)
- [ ] SSH key configured
- [ ] Fireworks API key
- [ ] Domain name (optional)
- [ ] 30-60 min for setup & testing

### Option C
- [ ] AMD GPU instance (80+ GB memory required)
- [ ] ROCm 6.0+ installed
- [ ] HuggingFace account (free)
- [ ] HuggingFace token with Gemma access
- [ ] Accept Gemma-3-27B license: https://huggingface.co/google/gemma-3-27b-it
- [ ] 1-2 hours for setup (model download takes time)
- [ ] Comfort with systemd, ROCm troubleshooting

---

## FAQ: Option Selection

**Q: I have a limited budget. What should I do?**  
A: Start with Option A. Cost is $8-15/mo base + minimal API costs initially. Monitor usage and upgrade when/if needed.

**Q: My hospital has strict data privacy requirements.**  
A: Use Option C. All data stays on your infrastructure. No patient data sent to external APIs.

**Q: We're a startup with unpredictable traffic.**  
A: Start with Option A. Costs scale with usage. Once you see consistent demand > 3000/mo, migrate to Option C.

**Q: We want to be an AMD showcase project.**  
A: Use Option B or C. Demonstrates meaningful use of AMD platforms (GPU + ROCm + vLLM). Consider applying for AMD developer grants.

**Q: Do I need multiple regions?**  
A: None of these options support multi-region out-of-the-box. Would require custom Kubernetes/DNS setup (not covered here).

**Q: Can I run both Option A and C in parallel?**  
A: Yes, for testing/failover. But adds complexity and cost. Not recommended unless needed.

**Q: What if traffic suddenly spikes?**  
A: 
- Option A: Fireworks handles it (may trigger higher API usage)
- Option B: Check GPU/Fireworks utilization, may need to scale
- Option C: Adjust vLLM batch size, may need larger GPU

---

## Recommendation Summary

```
┌─────────────────────────────────────────────────────────────┐
│ 🎯 QUICK RECOMMENDATION                                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ JUST STARTING?          → Use Option A                      │
│ Small proof-of-concept  → Use Option A                      │
│                                                              │
│ EARLY PRODUCTION?       → Monitor Option A costs            │
│ < 500 diagnoses/month   → If >$50/mo → Upgrade to B or C   │
│                                                              │
│ SCALING UP?             → Use Option B or C                 │
│ 500-5000/month          → Option B if AMD support matters   │
│ 5000+/month             → Option C (cost-effective)         │
│                                                              │
│ PRIVACY-CRITICAL?       → Use Option C                      │
│ Patient data sensitive  → Keep data on your infrastructure  │
│                                                              │
│ UNSURE?                 → Start with Option A               │
│ Then upgrade as you learn → Costs scale, migration is easy  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Next Steps

1. **Calculate your expected costs:** `./scripts/cost-calculator.py`
2. **Choose an option** based on the matrix above
3. **Run the deployment script** for your option
4. **Monitor and measure** actual costs & performance
5. **Upgrade or optimize** based on real usage data

See `/docs/AMD_GPU_DEPLOYMENT.md` for detailed deployment guide.
