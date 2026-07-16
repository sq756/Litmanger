#!/usr/bin/env bash
# Litmanger Relay — no-credit-card free deployment script
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
echo ""
echo "  Litmanger Relay — Free Deployment (no credit card)"
echo "  ==================================================="
echo ""

# ── Option 1: Alwaysdata (recommended, no credit card) ──
echo "  Option 1: Alwaysdata (alwaysdata.com)"
echo "  --------------------------------------"
echo "  1. Sign up at https://www.alwaysdata.com/en/register/"
echo "     (no credit card required, 100MB free)"
echo "  2. Create a site:"
echo "     - Type: Python WSGI"
echo "     - Address: pick anything (e.g. litmanger-relay)"
echo "  3. Upload these files via SFTP or their web file manager:"
echo "     - relay_server.py"
echo "     - requirements-relay.txt"
echo "  4. Set the WSGI app to: relay_server:app"
echo "  5. Your relay URL will be: https://litmanger-relay.alwaysdata.net"
echo ""

# ── Option 2: Cloudflare Tunnel (run from your PC) ──
echo "  Option 2: Cloudflare Tunnel (free, from your PC)"
echo "  -------------------------------------------------"
echo "  Install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
echo "  Then run:"
echo "    cloudflared tunnel --url http://localhost:9987"
echo ""
echo "  This gives you a public https://xxx.trycloudflare.com URL"
echo "  Works as long as your PC is on and Litmanger is running."
echo ""

# ── Option 3: SSH tunnel ──
echo "  Option 3: serveo.net SSH tunnel (zero setup)"
echo "  ---------------------------------------------"
echo "  Just run this (from Git Bash or WSL):"
echo "    ssh -R 80:localhost:9987 serveo.net"
echo ""
echo "  You'll get a public URL like https://xxx.serveo.net"
echo "  Works as long as your terminal stays open."
echo ""

echo "  For all options, after getting your public URL:"
echo "    1. Open Litmanger → Settings"
echo "    2. Paste the URL into the Relay field"
echo "    3. Click Save"
echo ""
echo "  All commenters must configure the same Relay URL."
echo ""
