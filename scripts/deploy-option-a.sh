#!/bin/bash
# AegisMed Deployment Script — Option A (Fireworks API on minimal droplet)
# Usage: ./deploy-option-a.sh <your_fireworks_api_key> [domain_name]
# Example: ./deploy-option-a.sh fw_XXXXX aegismed.example.com

set -e

FIREWORKS_API_KEY="${1:-}"
DOMAIN="${2:-}"

if [ -z "$FIREWORKS_API_KEY" ]; then
    echo "Usage: $0 <fireworks_api_key> [domain]"
    echo "Example: $0 fw_XXXXX aegismed.example.com"
    exit 1
fi

echo "=== AegisMed Option A Deployment ==="
echo "Deploying to: $(hostname -I | awk '{print $1}')"
echo "Domain: ${DOMAIN:-localhost}"

# Update system
echo "📦 Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install Docker
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh

    echo "👤 Adding docker to user group..."
    sudo usermod -aG docker $USER
    newgrp docker
fi

# Clone AegisMed if not already present
if [ ! -d "AegisMed" ]; then
    echo "📥 Cloning AegisMed..."
    git clone https://github.com/wachirawut2023/AegisMed.git
fi

cd AegisMed

# Create .env file
echo "⚙️  Creating .env configuration..."
cat > .env << EOF
FIREWORKS_API_KEY=$FIREWORKS_API_KEY
MODEL=accounts/fireworks/models/gemma-3-27b-it
DEMO_MODE=false
EOF

# Start the application
echo "🚀 Starting AegisMed with Docker..."
docker compose up -d --build

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

# Setup Nginx if domain provided
if [ -n "$DOMAIN" ]; then
    echo "🌐 Setting up Nginx reverse proxy..."
    sudo apt install -y nginx

    sudo tee /etc/nginx/sites-available/aegismed > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        client_max_body_size 50M;
    }

    # Health check endpoint
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

    echo "🔒 Installing SSL certificate with Let's Encrypt..."
    sudo apt install -y certbot python3-certbot-nginx
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email admin@$DOMAIN --redirect
fi

# Show status
echo ""
echo "✨ Deployment Complete!"
echo ""
echo "📊 Status:"
docker ps
echo ""
echo "🌐 Access at:"
if [ -n "$DOMAIN" ]; then
    echo "  - https://$DOMAIN"
    echo "  - http://$DOMAIN (auto-redirects to HTTPS)"
else
    echo "  - http://$(hostname -I | awk '{print $1}'):8000"
    echo "  - http://localhost:8000 (from this machine)"
fi
echo ""
echo "💾 Logs:"
echo "  docker logs aegismed -f"
echo ""
echo "📈 Monitor:"
echo "  docker stats"
echo ""
echo "💡 Next steps:"
echo "  1. Open the app and test with 'Load example case'"
echo "  2. Monitor Fireworks API usage at https://console.fireworks.ai"
echo "  3. If costs exceed budget, consider upgrading to Option B or C"
