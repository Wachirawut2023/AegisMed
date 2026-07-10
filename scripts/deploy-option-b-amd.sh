#!/bin/bash
# AegisMed Deployment Script — Option B (AMD Developer Cloud with Fireworks API)
# Prerequisites:
#   1. AMD Developer Cloud instance created (e.g., MI50, MI210)
#   2. Ubuntu 22.04 LTS
#   3. SSH access configured
#
# Usage: ./deploy-option-b-amd.sh <fireworks_api_key> [public_domain]
# Example: ./deploy-option-b-amd.sh fw_XXXXX aegismed.amd-dev.example.com

set -e

FIREWORKS_API_KEY="${1:-}"
DOMAIN="${2:-}"

if [ -z "$FIREWORKS_API_KEY" ]; then
    echo "Usage: $0 <fireworks_api_key> [domain]"
    echo "Example: $0 fw_XXXXX aegismed.amd-dev.example.com"
    exit 1
fi

echo "=== AegisMed Option B Deployment (AMD Developer Cloud) ==="
echo "Instance IP: $(hostname -I | awk '{print $1}')"
echo "Instance: $(lsb_release -d | cut -f2)"
echo "GPU Status:"
rocm-smi --showproductname 2>/dev/null || echo "  (No ROCm detected - will use Fireworks only)"

# Update system
echo ""
echo "📦 Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install Docker
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh

    sudo usermod -aG docker $USER
    newgrp docker
fi

# Install ROCm (if not pre-installed)
if ! command -v rocm-smi &> /dev/null; then
    echo "🔧 Installing ROCm..."
    wget -q -O - https://repo.radeon.com/rocm/rocm.gpg.key | sudo apt-key add -
    echo "deb [arch=amd64] https://repo.radeon.com/amd-gfx-arch-22.04 jammy main" | sudo tee /etc/apt/sources.list.d/amdgpu.list
    sudo apt update
    sudo apt install -y rocm-dkms
fi

# Clone AegisMed
if [ ! -d "AegisMed" ]; then
    echo "📥 Cloning AegisMed..."
    git clone https://github.com/wachirawut2023/AegisMed.git
fi

cd AegisMed

# Create optimized Dockerfile for AMD
echo "📝 Creating AMD-optimized Dockerfile..."
cat > Dockerfile.amd << 'EOF'
# AegisMed on AMD Developer Cloud
# Optimized for MI50/MI210 GPU instances
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    rocm-dev \
    rocm-libs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY aegismed/ aegismed/
COPY static/ static/

EXPOSE 8000

CMD ["uvicorn", "aegismed.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# Create .env
echo "⚙️  Creating .env configuration..."
cat > .env << EOF
FIREWORKS_API_KEY=$FIREWORKS_API_KEY
MODEL=accounts/fireworks/models/gemma-3-27b-it
DEMO_MODE=false
EOF

# Create docker-compose with GPU support
echo "📝 Updating docker-compose for GPU..."
cat > docker-compose.amd.yml << 'EOF'
version: "3.8"

services:
  aegismed:
    build:
      context: .
      dockerfile: Dockerfile.amd
    ports:
      - "8000:8000"
    env_file:
      - path: .env
        required: false
    devices:
      - /dev/kfd
      - /dev/dri
    volumes:
      - /sys/kernel/debug:/sys/kernel/debug
    cap_add:
      - SYS_PTRACE
    environment:
      - HSA_OVERRIDE_GFX_VERSION=0  # Auto-detect GPU
      - ROCM_HOME=/opt/rocm
EOF

# Start the application
echo "🚀 Starting AegisMed with GPU support..."
docker compose -f docker-compose.amd.yml up -d --build

# Wait for app to be ready
echo "⏳ Waiting for app to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ App is running!"
        break
    fi
    echo "  Attempt $i/30..."
    sleep 2
done

# Setup Nginx with rate limiting
if [ -n "$DOMAIN" ]; then
    echo "🌐 Setting up Nginx with rate limiting..."
    sudo apt install -y nginx

    sudo tee /etc/nginx/sites-available/aegismed > /dev/null << EOF
# Rate limit zone (10 req/min per IP)
limit_req_zone \$binary_remote_addr zone=diagnosis_limit:10m rate=10r/m;

# Buffer for bursts (up to 20 requests)
limit_req_status 429;

server {
    listen 80;
    server_name $DOMAIN;

    # Apply rate limiting to diagnosis endpoint
    location /api/diagnose {
        limit_req zone=diagnosis_limit burst=20 nodelay;
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        client_max_body_size 50M;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Other endpoints without strict rate limiting
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        client_max_body_size 50M;
    }

    # Health check
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

    echo "🔒 Installing SSL with Let's Encrypt..."
    sudo apt install -y certbot python3-certbot-nginx
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email admin@"$DOMAIN" --redirect
fi

# Setup monitoring script
echo "📊 Creating monitoring script..."
mkdir -p ./monitoring
cat > ./monitoring/monitor.sh << 'EOF'
#!/bin/bash
# Monitor AegisMed on AMD GPU
echo "=== AegisMed Monitoring Dashboard ==="
echo ""
echo "📦 Container Status:"
docker ps --filter "name=aegismed"
echo ""
echo "💾 Resource Usage:"
docker stats --no-stream
echo ""
echo "🔧 GPU Status:"
rocm-smi
echo ""
echo "🌐 API Health:"
curl -s http://localhost:8000/health | python3 -m json.tool || echo "  (App not responding)"
echo ""
echo "📊 Request Count (last hour):"
docker logs aegismed --since 1h | grep -c "POST /api/diagnose" || echo "  (No requests yet)"
EOF

chmod +x ./monitoring/monitor.sh

# Show completion status
echo ""
echo "✨ Deployment Complete!"
echo ""
echo "📊 Current Status:"
docker compose -f docker-compose.amd.yml ps
echo ""
echo "🔧 GPU Utilization:"
rocm-smi 2>/dev/null || echo "  (Run: rocm-smi)"
echo ""
echo "🌐 Access at:"
if [ -n "$DOMAIN" ]; then
    echo "  - https://$DOMAIN"
else
    echo "  - http://$(hostname -I | awk '{print $1}'):8000"
fi
echo ""
echo "💻 Monitor GPU & Performance:"
echo "  ./monitoring/monitor.sh"
echo "  # or continuous:"
echo "  watch -n 1 ./monitoring/monitor.sh"
echo ""
echo "📈 View Logs:"
echo "  docker compose -f docker-compose.amd.yml logs -f"
echo ""
echo "💰 Cost Optimization Tips:"
echo "  1. Monitor: docker stats (CPU/Memory usage)"
echo "  2. Check GPU: rocm-smi"
echo "  3. Scale: Increase max batch size for more efficient GPU use"
echo "  4. Compare: Fireworks API costs vs GPU reservation cost"
echo ""
echo "⚠️  Next Step: If Fireworks costs exceed GPU reservation cost,"
echo "   consider Option C (local Gemma with vLLM)"
