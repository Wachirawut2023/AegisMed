#!/bin/bash
# AegisMed Deployment Script — Option C (Self-hosted Gemma with vLLM + ROCm)
#
# Prerequisites:
#   1. AMD GPU with ROCm support (MI210, MI250, MI300X recommended)
#   2. ROCm pre-installed and working
#   3. Ubuntu 22.04 LTS
#   4. HuggingFace token for Gemma access
#
# Usage: ./deploy-option-c-vllm.sh <hf_token> [public_domain] [model_path]
# Example: ./deploy-option-c-vllm.sh hf_XXXXX aegismed.amd-dev.example.com /models

set -e

HF_TOKEN="${1:-}"
DOMAIN="${2:-}"
MODEL_PATH="${3:-/models}"
MODEL_NAME="google/gemma-3-27b-it"
MODEL_LOCAL_PATH="$MODEL_PATH/gemma-3-27b-it"

if [ -z "$HF_TOKEN" ]; then
    echo "Usage: $0 <huggingface_token> [domain] [model_path]"
    echo "Example: $0 hf_XXXXX aegismed.amd-dev.example.com /models"
    echo ""
    echo "To get HuggingFace token:"
    echo "  1. Visit https://huggingface.co/settings/tokens"
    echo "  2. Create a new token with 'repo' read permissions"
    echo "  3. Accept Gemma license at https://huggingface.co/google/gemma-3-27b-it"
    exit 1
fi

echo "=== AegisMed Option C Deployment (Self-hosted Gemma + vLLM) ==="
echo "GPU: $(rocm-smi --showproductname 2>/dev/null | head -1 || echo 'Unknown')"
echo "GPU Memory: $(rocm-smi --showmeminfo 2>/dev/null | grep 'GPU Memory' | head -1 || echo 'Unknown')"
echo "Model: $MODEL_NAME"
echo "Local path: $MODEL_LOCAL_PATH"
echo "Domain: ${DOMAIN:-localhost}"
echo ""
echo "⚠️  This setup requires ~80GB GPU memory. Minimum MI210+ recommended."
echo ""

# Check GPU
echo "🔍 Checking GPU support..."
if ! command -v rocm-smi &> /dev/null; then
    echo "❌ ROCm not found. Install ROCm first:"
    echo "   https://rocmdocs.amd.com/en/latest/deploy/linux/"
    exit 1
fi

# Check storage
echo "💾 Checking storage..."
AVAILABLE_SPACE=$(df "$MODEL_PATH" | tail -1 | awk '{print $4}')
REQUIRED_SPACE=$((45 * 1024 * 1024))  # 45GB in KB

if [ "$AVAILABLE_SPACE" -lt "$REQUIRED_SPACE" ]; then
    echo "❌ Insufficient storage at $MODEL_PATH"
    echo "   Available: $(numfmt --to=iec $((AVAILABLE_SPACE * 1024)) 2>/dev/null || echo $AVAILABLE_SPACE KB)"
    echo "   Required: ~45GB"
    exit 1
fi

# Update system
echo ""
echo "📦 Updating system packages..."
sudo apt update
sudo apt install -y build-essential python3-dev git

# Create Python environment for vLLM
echo "🐍 Setting up Python environment for vLLM..."
sudo mkdir -p /opt/vllm
sudo chown $USER:$USER /opt/vllm

if [ ! -d "/opt/vllm/venv" ]; then
    python3 -m venv /opt/vllm/venv
fi

source /opt/vllm/venv/bin/activate

# Install vLLM with ROCm
echo "⬇️  Installing vLLM with ROCm support..."
pip install --upgrade pip
pip install -q vllm[rocm]
pip install -q huggingface-hub

# Download model
echo "📥 Downloading Gemma-3-27B model (~45GB)..."
echo "   This may take 10-20 minutes depending on connection speed"

mkdir -p "$MODEL_PATH"
python3 << EOF
from huggingface_hub import snapshot_download
import sys

print(f"Downloading {sys.argv[1]} to {sys.argv[2]}")
try:
    snapshot_download(
        sys.argv[1],
        local_dir=sys.argv[2],
        token=sys.argv[3],
        repo_type="model",
    )
    print("✅ Download complete!")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
EOF "$MODEL_NAME" "$MODEL_LOCAL_PATH" "$HF_TOKEN"

# Create systemd service for vLLM
echo "🔧 Creating vLLM systemd service..."
sudo tee /etc/systemd/system/vllm.service > /dev/null << EOF
[Unit]
Description=vLLM Server (Gemma-3-27B on AMD GPU)
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/vllm
ExecStart=/opt/vllm/venv/bin/python -m vllm.entrypoints.openai.api_server \
    --model $MODEL_LOCAL_PATH \
    --tensor-parallel-size 1 \
    --pipeline-parallel-size 1 \
    --port 8001 \
    --dtype float16 \
    --gpu-memory-utilization 0.9 \
    --max-model-len 2048 \
    --disable-log-requests \
    --log-level INFO
Restart=always
RestartSec=10

Environment="HSA_OVERRIDE_GFX_VERSION=0"
Environment="VLLM_LOGGING_LEVEL=INFO"

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable vllm

# Start vLLM
echo "🚀 Starting vLLM server..."
sudo systemctl restart vllm

# Wait for vLLM to be ready
echo "⏳ Waiting for vLLM to start (~60 seconds)..."
for i in {1..120}; do
    if curl -s http://localhost:8001/v1/models > /dev/null 2>&1; then
        echo "✅ vLLM is ready!"
        break
    fi
    if [ $((i % 10)) -eq 0 ]; then
        echo "  Attempt $i/120..."
    fi
    sleep 1
done

# Install Docker
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    sudo usermod -aG docker $USER
    newgrp docker
fi

# Clone AegisMed
if [ ! -d "AegisMed" ]; then
    echo "📥 Cloning AegisMed..."
    git clone https://github.com/wachirawut2023/AegisMed.git
fi

cd AegisMed

# Create modified config for vLLM backend
echo "📝 Creating vLLM-optimized configuration..."
cat > .env << EOF
# Use local vLLM instead of Fireworks
FIREWORKS_API_KEY=
FIREWORKS_API_URL=http://localhost:8001/v1/chat/completions
MODEL=$MODEL_NAME
DEMO_MODE=false
EOF

# Create modified config.py that handles vLLM URLs
if [ ! -f aegismed/config_vllm.py ]; then
    cp aegismed/config.py aegismed/config_vllm.py
fi

# Patch config.py to accept local vLLM URLs
python3 << 'EOFPYTHON'
import re

config_path = 'aegismed/config.py'
with open(config_path, 'r') as f:
    content = f.read()

# Add vLLM-specific configuration
vllm_patch = '''
def get_api_url():
    """Get Fireworks or vLLM API endpoint."""
    api_url = os.getenv('FIREWORKS_API_URL', FIREWORKS_API_URL)
    # Support local vLLM: http://localhost:8001/v1/chat/completions
    # Support Fireworks: https://api.fireworks.ai/...
    return api_url
'''

# Replace the simple FIREWORKS_API_URL reference with a function call
if 'get_api_url' not in content:
    # Add the function before the config class
    content = content.replace(
        'FIREWORKS_API_URL = ',
        'FIREWORKS_API_URL_DEFAULT = '
    )
    content = content.replace(
        'class LLMError',
        vllm_patch + '\n\nclass LLMError'
    )

with open(config_path, 'w') as f:
    f.write(content)

print("✅ Config patched for vLLM support")
EOFPYTHON

# Patch llm.py to use the function
python3 << 'EOFPYTHON'
import re

llm_path = 'aegismed/llm.py'
with open(llm_path, 'r') as f:
    content = f.read()

# Update the API URL reference
if 'config.FIREWORKS_API_URL' in content:
    content = content.replace(
        'config.FIREWORKS_API_URL',
        'config.get_api_url()'
    )

with open(llm_path, 'w') as f:
    f.write(content)

print("✅ LLM module patched for vLLM support")
EOFPYTHON

# Build and start AegisMed
echo "🐳 Building AegisMed container..."
docker compose build

echo "🚀 Starting AegisMed..."
docker compose up -d

# Wait for app
echo "⏳ Waiting for AegisMed to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ AegisMed is ready!"
        break
    fi
    echo "  Attempt $i/30..."
    sleep 2
done

# Setup Nginx
if [ -n "$DOMAIN" ]; then
    echo "🌐 Setting up Nginx reverse proxy..."
    sudo apt install -y nginx

    sudo tee /etc/nginx/sites-available/aegismed > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN;

    # Long timeout for LLM inference (up to 5 minutes)
    proxy_read_timeout 300s;
    proxy_connect_timeout 75s;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        client_max_body_size 50M;
    }

    location /health {
        proxy_pass http://localhost:8000/health;
        access_log off;
    }
}
EOF

    sudo ln -sf /etc/nginx/sites-available/aegismed /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default

    sudo nginx -t
    sudo systemctl restart nginx

    echo "🔒 Installing SSL..."
    sudo apt install -y certbot python3-certbot-nginx
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email admin@"$DOMAIN" --redirect
fi

# Create monitoring script
echo "📊 Creating monitoring script..."
mkdir -p ./monitoring
cat > ./monitoring/monitor-vllm.sh << 'EOF'
#!/bin/bash
echo "=== AegisMed + vLLM Monitoring ==="
echo ""
echo "📊 vLLM Status:"
systemctl status vllm --no-pager | head -5
echo ""
echo "🔧 GPU Utilization:"
rocm-smi
echo ""
echo "🧠 vLLM Stats:"
curl -s http://localhost:8001/v1/models | python3 -m json.tool || echo "  (vLLM not responding)"
echo ""
echo "🐳 AegisMed Container:"
docker ps --filter "name=aegismed"
echo ""
echo "📈 Resource Usage:"
docker stats --no-stream
echo ""
echo "🌐 Health:"
curl -s http://localhost:8000/health | python3 -m json.tool
EOF

chmod +x ./monitoring/monitor-vllm.sh

# Show completion
echo ""
echo "✨ Option C Deployment Complete!"
echo ""
echo "🔧 Service Status:"
systemctl status vllm --no-pager | head -3
echo ""
echo "🧠 Model Loaded:"
curl -s http://localhost:8001/v1/models | python3 -c "import sys, json; print('  ✅ ' + json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null || echo "  (Loading...)"
echo ""
echo "🐳 Container Status:"
docker ps --filter "name=aegismed"
echo ""
echo "🌐 Access at:"
if [ -n "$DOMAIN" ]; then
    echo "  - https://$DOMAIN"
else
    echo "  - http://$(hostname -I | awk '{print $1}'):8000"
fi
echo ""
echo "📈 Monitor:"
echo "  ./monitoring/monitor-vllm.sh"
echo "  # or continuous:"
echo "  watch -n 1 ./monitoring/monitor-vllm.sh"
echo ""
echo "📋 Manage Services:"
echo "  # View vLLM logs:"
echo "  sudo journalctl -u vllm -f"
echo ""
echo "  # Restart vLLM:"
echo "  sudo systemctl restart vllm"
echo ""
echo "  # View AegisMed logs:"
echo "  docker compose logs -f"
echo ""
echo "💡 Performance Tuning:"
echo "  1. Max model length: 2048 (edit /etc/systemd/system/vllm.service)"
echo "  2. GPU memory: 0.9 (90% utilization)"
echo "  3. For more requests: increase --tensor-parallel-size or add more GPUs"
echo ""
echo "💰 Cost Benefits:"
echo "  ✓ No API costs per request"
echo "  ✓ Private inference (no data to external APIs)"
echo "  ✓ Unlimited diagnoses"
echo "  ✓ Full control over model & parameters"
