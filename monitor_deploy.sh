#!/bin/bash
# Monitor EthioDeploy deployment status

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     🚀 Monitoring EthioDeploy Deployment                ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

cd "H:/بوت الفحص الشغال/checker"

# Loop until deployment is READY or fails
for i in {1..40}; do
    STATUS=$(ethiodeploy status 2>&1 | grep "cmvxciefe0" | awk '{print $2}')

    case $STATUS in
        "BUILDING")
            echo "⏳ [$i/40] Building... ($(date +%H:%M:%S))"
            ;;
        "DEPLOYING")
            echo "🚀 [$i/40] Deploying... ($(date +%H:%M:%S))"
            ;;
        "READY")
            echo ""
            echo "╔══════════════════════════════════════════════════════════╗"
            echo "║     ✅ Deployment Successful!                            ║"
            echo "╚══════════════════════════════════════════════════════════╝"
            echo ""
            ethiodeploy status
            echo ""
            echo "📊 Showing last 30 log lines:"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ethiodeploy logs 2>&1 | tail -30
            exit 0
            ;;
        "FAILED"|"ERROR")
            echo ""
            echo "╔══════════════════════════════════════════════════════════╗"
            echo "║     ❌ Deployment Failed!                                ║"
            echo "╚══════════════════════════════════════════════════════════╝"
            echo ""
            ethiodeploy status
            echo ""
            echo "📊 Error Logs:"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ethiodeploy logs 2>&1 | tail -50
            exit 1
            ;;
        *)
            echo "❓ [$i/40] Unknown status: $STATUS"
            ;;
    esac

    sleep 5
done

echo ""
echo "⚠️  Timeout: Deployment taking too long"
ethiodeploy status
