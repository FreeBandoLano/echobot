#!/bin/bash
# Quick guide to manually generate today's digest via Azure SSH

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Manual Digest Generation for October 10, 2025               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "This will:"
echo "  1. Connect to Azure container via SSH"
echo "  2. Check if today's blocks are completed"
echo "  3. Generate and email today's digest"
echo ""
echo "Press Enter to connect (or Ctrl+C to cancel)..."
read

echo "🔌 Connecting to Azure container..."
echo ""
echo "💡 Once connected, run these commands:"
echo ""
echo "   cd /app"
echo "   python generate_today_digest.py"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

az webapp ssh --name echobot-docker-app --resource-group echobot-rg
