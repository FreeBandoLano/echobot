#!/bin/bash
# Interactive SSH helper for running diagnostics and fixes

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Azure Container SSH Helper - Digest Fix Tool                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "This will connect you to the Azure container via SSH."
echo "Once connected, you can run:"
echo ""
echo "  1️⃣  Diagnostic: python diagnose_task_queue.py"
echo "  2️⃣  Fix: python manual_digest_fix.py"
echo ""
echo "The diagnostic will show:"
echo "  - Task queue database status"
echo "  - Pending/running tasks"
echo "  - Recent digest creation attempts"
echo "  - Blocks vs digests comparison"
echo ""
echo "The fix will:"
echo "  - Generate digests for Oct 6, 7, 8"
echo "  - Email to: delano@futurebarbados.bb, anya@futurebarbados.bb, Roy.morris@barbados.gov.bb"
echo ""
echo "Press Enter to connect via SSH (or Ctrl+C to cancel)..."
read

echo "🔌 Connecting to Azure container..."
echo "💡 Tip: Run 'cd /app' first, then run the Python scripts above"
echo ""

az webapp ssh --name echobot-docker-app --resource-group echobot-rg
