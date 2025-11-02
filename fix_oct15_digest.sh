#!/bin/bash
# Fix October 15, 2025 premature digest
# This will SSH into Azure and regenerate the digest with all blocks

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  FIX OCTOBER 15, 2025 PREMATURE DIGEST                        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "This script will:"
echo "  1. SSH into the Azure container"
echo "  2. Check current block status"
echo "  3. Wait for all 4 blocks to complete (if needed)"
echo "  4. Regenerate the digest with all blocks"
echo "  5. Email to all recipients"
echo ""
echo "The script will handle everything automatically!"
echo ""
echo "Press Enter to connect to Azure (or Ctrl+C to cancel)..."
read

echo ""
echo "🔌 Connecting to Azure container..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 Once connected, run:"
echo ""
echo "   cd /app"
echo "   python fix_oct16_digest.py"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Connect to Azure
az webapp ssh --name echobot-docker-app --resource-group echobot-rg
