#!/bin/bash
# AegisMed CPU-Only Deployment with Load Balancer (Multi-Droplet Scaling)
#
# This script sets up multiple CPU droplets with a load balancer
# for high-availability without GPU costs.
#
# Prerequisites:
#   - DigitalOcean CLI (doctl) installed and configured
#   - Fireworks API key
#
# Usage: ./deploy-cpu-scaling.sh <fireworks_api_key> <domain> [num_droplets]
# Example: ./deploy-cpu-scaling.sh fw_XXXXX aegismed.example.com 3

set -e

FIREWORKS_API_KEY="${1:-}"
DOMAIN="${2:-}"
NUM_DROPLETS="${3:-3}"

if [ -z "$FIREWORKS_API_KEY" ] || [ -z "$DOMAIN" ]; then
    echo "Usage: $0 <fireworks_api_key> <domain> [num_droplets]"
    echo "Example: $0 fw_XXXXX aegismed.example.com 3"
    exit 1
fi

echo "=== AegisMed CPU-Only Scaled Deployment ==="
echo "Domain: $DOMAIN"
echo "Number of droplets: $NUM_DROPLETS"
echo "Total base cost: ~$$(($NUM_DROPLETS * 12))/month + LB $12/month + API costs"
echo ""

# Check doctl
if ! command -v doctl &> /dev/null; then
    echo "❌ doctl CLI not found. Install from:"
    echo "   https://docs.digitalocean.com/reference/doctl/how-to/install/"
    exit 1
fi

# Verify doctl auth
if ! doctl auth list > /dev/null 2>&1; then
    echo "❌ doctl not authenticated. Run: doctl auth init"
    exit 1
fi

echo "🐳 Creating $NUM_DROPLETS CPU droplets..."

# Create tag for load balancer targeting
TAG="aegismed-backend"

DROPLET_IDS=()

for i in $(seq 1 $NUM_DROPLETS); do
    DROPLET_NAME="aegismed-backend-$i"

    echo "  Creating $DROPLET_NAME..."

    # Create droplet (basic 1vCPU, 1GB RAM)
    DROPLET_ID=$(doctl compute droplet create "$DROPLET_NAME" \
        --region nyc3 \
        --image ubuntu-22-04-x64 \
        --size s-1vcpu-1gb \
        --enable-backups \
        --enable-monitoring \
        --format ID \
        --no-header \
        --tag-names "$TAG")

    DROPLET_IDS+=("$DROPLET_ID")
    echo "    ✅ Droplet $DROPLET_ID created"
done

# Wait for droplets to be active
echo ""
echo "⏳ Waiting for droplets to boot (60-90 seconds)..."
sleep 30

for i in $(seq 1 $NUM_DROPLETS); do
    echo "  Checking droplet $i..."
    while true; do
        STATUS=$(doctl compute droplet get ${DROPLET_IDS[$((i-1))]} --format Status --no-header)
        if [ "$STATUS" = "active" ]; then
            echo "    ✅ Droplet $i is active"
            break
        fi
        echo "    ⏳ Status: $STATUS, waiting..."
        sleep 10
    done
done

# Get droplet IPs
echo ""
echo "📋 Droplet IPs:"
DROPLET_IPS=()
for id in "${DROPLET_IDS[@]}"; do
    IP=$(doctl compute droplet get "$id" --format PublicIPv4 --no-header)
    DROPLET_IPS+=("$IP")
    echo "  $id: $IP"
done

# Deploy app to each droplet
echo ""
echo "🚀 Deploying AegisMed to each droplet..."

for i in $(seq 0 $((NUM_DROPLETS-1))); do
    IP=${DROPLET_IPS[$i]}
    DROPLET_NUM=$((i+1))

    echo ""
    echo "  Setting up droplet $DROPLET_NUM ($IP)..."

    # SSH setup (add public key)
    # Skip if already done

    # Run deployment script via SSH
    cat > /tmp/droplet-setup.sh << 'EOF'
#!/bin/bash
set -e
# Update and install Docker
apt update && apt upgrade -y
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh
usermod -aG docker root

# Clone AegisMed
cd /root
git clone https://github.com/wachirawut2023/AegisMed.git
cd AegisMed

# Create .env
cat > .env << EOFENV
FIREWORKS_API_KEY=$1
MODEL=accounts/fireworks/models/gemma-3-27b-it
DEMO_MODE=false
EOFENV

# Start app
docker compose up -d --build

# Wait for app
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ App started on $2"
        exit 0
    fi
    sleep 1
done
echo "❌ App failed to start on $2"
exit 1
EOF

    chmod +x /tmp/droplet-setup.sh

    # Execute via SSH (assumes root access)
    # Note: You may need to configure SSH keys first
    scp -o StrictHostKeyChecking=no /tmp/droplet-setup.sh "root@$IP:/tmp/"
    ssh -o StrictHostKeyChecking=no "root@$IP" "bash /tmp/droplet-setup.sh '$FIREWORKS_API_KEY' '$IP'" &
done

# Wait for all deployments
echo ""
echo "⏳ Waiting for all droplets to be configured (120-180 seconds)..."
wait

# Create load balancer
echo ""
echo "⚖️  Creating load balancer..."

DROPLET_IDS_COMMA=$(printf '%s,' "${DROPLET_IDS[@]}" | sed 's/,$//')

doctl compute load-balancer create \
    --name "aegismed-lb" \
    --region nyc3 \
    --forwarding-rules "entry_protocol:http,entry_port:80,target_protocol:http,target_port:8000" \
    --health-check "protocol:http,port:8000,path:/health,check_interval_seconds:10,response_timeout_seconds:5,healthy_threshold:5,unhealthy_threshold:3" \
    --sticky-sessions "type:none" \
    --droplet-ids "$DROPLET_IDS_COMMA" \
    --format Name,IP,Status \
    --no-header

# Get load balancer IP
sleep 10
LB_IP=$(doctl compute load-balancer list --format Name,IP --no-header | grep "aegismed-lb" | awk '{print $2}')

echo ""
echo "✨ Deployment Complete!"
echo ""
echo "📊 Infrastructure:"
echo "  Load Balancer: $LB_IP"
echo "  Backend droplets:"
for i in $(seq 0 $((NUM_DROPLETS-1))); do
    echo "    - ${DROPLET_IPS[$i]}"
done
echo ""
echo "🌐 Access at:"
echo "  Temporary: http://$LB_IP"
echo "  Production: Point $DOMAIN to $LB_IP (update DNS CNAME or A record)"
echo ""
echo "📈 Monitor & Manage:"
echo ""
echo "  View droplets:"
echo "    doctl compute droplet list --tag-name $TAG"
echo ""
echo "  View load balancer:"
echo "    doctl compute load-balancer get aegismed-lb"
echo ""
echo "  SSH to a droplet:"
echo "    ssh root@${DROPLET_IPS[0]}"
echo ""
echo "  View app logs on droplet:"
echo "    ssh root@${DROPLET_IPS[0]} 'docker logs aegismed -f'"
echo ""
echo "  Check health:"
echo "    curl http://$LB_IP/health"
echo ""
echo "💰 Cost:"
echo "  - $NUM_DROPLETS CPU droplets @ $12/mo = \$$((NUM_DROPLETS * 12))/month"
echo "  - Load Balancer: \$12/month"
echo "  - Fireworks API: variable based on traffic"
echo "  - Total base: \$$((NUM_DROPLETS * 12 + 12))/month + API"
echo ""
echo "🔄 Scaling:"
echo "  Add droplet: Create new droplet, tag with '$TAG', attach to LB"
echo "  Remove droplet: Remove tag, detach from LB, delete"
echo ""
echo "📝 Next Steps:"
echo "  1. Update DNS records to point $DOMAIN to $LB_IP"
echo "  2. Wait 5-30 min for DNS propagation"
echo "  3. Access at https://$DOMAIN"
echo ""
echo "  To enable HTTPS on load balancer:"
echo "  - Get SSL cert from Let's Encrypt"
echo "  - Upload to DigitalOcean: doctl compute certificate create ..."
echo "  - Add HTTPS rule to LB forwarding rules"
echo ""
