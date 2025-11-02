#!/bin/bash
# This script runs inside the Azure container to generate missing digests

cd /app

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Running Manual Digest Fix for October 6-8, 2025             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

python manual_digest_fix.py

echo ""
echo "✅ Digest generation complete!"
echo "Check email for delivery confirmation."
