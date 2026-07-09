#!/bin/bash
# Monitor Fireworks inference recovery and auto-run A/B test when ready

set -e

KEY=$(grep FIREWORKS_API_KEY .env | cut -d= -f2)
MAX_ATTEMPTS=120  # 10 hours (120 * 5 min)
ATTEMPT=0

echo "🔍 Monitoring Fireworks inference endpoint recovery..."
echo "   Checking every 5 minutes (up to 10 hours)"
echo "   Will auto-run tests when service is back"
echo ""

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  ATTEMPT=$((ATTEMPT + 1))
  TIME=$(date "+%H:%M:%S")
  
  # Test inference endpoint
  RESPONSE=$(curl -s -X POST https://api.fireworks.ai/inference/v1/chat/completions \
    -H "Authorization: Bearer $KEY" \
    -H "Content-Type: application/json" \
    -d '{"model":"accounts/fireworks/models/gemma-3-27b-it","messages":[{"role":"user","content":"Hi"}],"max_tokens":10}')
  
  if echo "$RESPONSE" | grep -q "choices"; then
    echo "[$TIME] ✅ FIREWORKS RECOVERED!"
    echo ""
    echo "Running Multi-LoRA A/B test automatically..."
    echo ""
    bash eval/run_ab_test.sh
    exit 0
  else
    ERROR=$(echo "$RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('error',{}).get('message','unknown'))" 2>/dev/null || echo "connection error")
    printf "[$TIME] Attempt %d/%d - Still down: %s\n" $ATTEMPT $MAX_ATTEMPTS "$ERROR"
    
    if [ $ATTEMPT -lt $MAX_ATTEMPTS ]; then
      sleep 300  # 5 minutes
    fi
  fi
done

echo ""
echo "❌ Monitoring timed out after 10 hours"
echo "Fireworks may still be having issues. Check https://status.fireworks.ai"
