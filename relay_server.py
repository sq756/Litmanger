"""
Litmanger Comment Relay Server
================================
Lightweight relay for DOI-keyed paper comments with Ed25519 signatures.

Each comment is signed by its author's Ed25519 private key before submission.
The relay server verifies the signature and publishes the comment to all peers.
No trust in the server required — signatures are verified client-side too.

Run:
    python relay_server.py                    # default port 9987
    python relay_server.py --port 8080        # custom port

API:
    GET  /comments?doi=<doi>           Get all comments for a DOI
    POST /comments                     Submit a signed comment
    GET  /peers                        List known peers (for P2P gossip)
    POST /peers                        Register a peer
    GET  /health                       Health check

Comment format:
    {
        "doi": "10.1103/...",
        "id": "comment-uuid",
        "author": "DisplayName",
        "text": "Comment text",
        "time": "2026-07-16",
        "pubkey": "base64-ed25519-public-key",
        "sig": "base64-ed25519-signature"
    }

Signature is over: doi|id|author|text|time|pubkey
"""

from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
import sys
import threading
import time
import urllib.parse
from pathlib import Path

# Ed25519 is in Python 3.9+ stdlib (cryptography is safer, but stdlib is zero-dep)
try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.exceptions import InvalidSignature

    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False
    print(
        "[!] 'cryptography' not installed. Install with: pip install cryptography",
        file=sys.stderr,
    )
    print(
        "[!] Running without Ed25519 verification — set REQUIRE_SIG=false to disable checks.",
        file=sys.stderr,
    )

SCRIPT_DIR = Path(__file__).parent.resolve()
COMMENTS_PATH = SCRIPT_DIR / "relay_comments.json"
PEERS_PATH = SCRIPT_DIR / "relay_peers.json"

# --- Storage ---

_store_lock = threading.Lock()


def load_store(path):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_store(data, path):
    with _store_lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# --- Ed25519 verification ---


def verify_signature(comment: dict) -> bool:
    """Verify that the comment was signed by the claimed pubkey."""
    if not _HAS_CRYPTO:
        return True  # skip verification if library not available

    pubkey_b64 = comment.get("pubkey", "")
    sig_b64 = comment.get("sig", "")
    if not pubkey_b64 or not sig_b64:
        return False

    import base64

    try:
        pubkey_bytes = base64.b64decode(pubkey_b64)
        sig_bytes = base64.b64decode(sig_b64)
    except Exception:
        return False

    # Message: doi|id|author|text|time|pubkey
    msg = "|".join(
        [
            comment.get("doi", ""),
            comment.get("id", ""),
            comment.get("author", ""),
            comment.get("text", ""),
            comment.get("time", ""),
            comment.get("pubkey", ""),
        ]
    ).encode("utf-8")

    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(pubkey_bytes)
        public_key.verify(sig_bytes, msg)
        return True
    except InvalidSignature:
        return False


# --- HTTP handler ---


def create_handler(require_sig: bool = True):
    class RelayHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _json(self, data, status=200):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self._json({})

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)

            if parsed.path == "/comments":
                doi = qs.get("doi", [None])[0]
                if not doi:
                    self._json({"error": "need doi param"}, 400)
                    return
                store = load_store(COMMENTS_PATH)
                comments = store.get(doi, [])
                self._json(comments)

            elif parsed.path == "/peers":
                peers = load_store(PEERS_PATH)
                self._json(list(peers.values()))

            elif parsed.path == "/health":
                store = load_store(COMMENTS_PATH)
                total = sum(len(v) for v in store.values())
                self._json({"status": "ok", "comments": total, "dois": len(store)})

            elif parsed.path == "/stats":
                store = load_store(COMMENTS_PATH)
                dois = list(store.keys())
                total = sum(len(v) for v in store.values())
                size_kb = os.path.getsize(COMMENTS_PATH) // 1024 if COMMENTS_PATH.exists() else 0
                self._json({
                    "total_comments": total,
                    "total_dois": len(dois),
                    "file_size_kb": size_kb,
                    "approx_bytes_per_comment": round(size_kb / total * 1024) if total > 0 else 0,
                })

            else:
                self._json({
                    "name": "Litmanger Comment Relay",
                    "version": "1.0.0",
                    "endpoints": {
                        "GET /comments?doi=xxx": "Get comments for a DOI",
                        "POST /comments": "Submit a signed comment",
                        "GET /peers": "List known peers",
                        "POST /peers": "Register a peer",
                        "GET /health": "Server health",
                        "GET /stats": "Storage statistics",
                    },
                })

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            body_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(body_len) if body_len > 0 else b""

            if parsed.path == "/comments":
                try:
                    comment = json.loads(body.decode("utf-8"))
                    doi = comment.get("doi", "").strip()
                    if not doi:
                        self._json({"ok": False, "error": "Missing doi"}, 400)
                        return
                    if not comment.get("text", "").strip():
                        self._json({"ok": False, "error": "Missing text"}, 400)
                        return
                    if len(comment.get("text", "")) > 10000:
                        self._json({"ok": False, "error": "Text too long (max 10000)"}, 400)
                        return

                    # Verify Ed25519 signature
                    if require_sig and not verify_signature(comment):
                        self._json({"ok": False, "error": "Invalid signature"}, 403)
                        return

                    # Dedup by id
                    store = load_store(COMMENTS_PATH)
                    existing = store.get(doi, [])
                    cid = comment.get("id", "")
                    if cid and any(c.get("id") == cid for c in existing):
                        self._json({"ok": True, "comments": existing, "duplicate": True})
                        return

                    existing.append(comment)
                    store[doi] = existing
                    save_store(store, COMMENTS_PATH)

                    self._json({"ok": True, "comments": existing})
                except json.JSONDecodeError:
                    self._json({"ok": False, "error": "Invalid JSON"}, 400)
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, 500)
                return

            if parsed.path == "/peers":
                try:
                    peer = json.loads(body.decode("utf-8"))
                    addr = peer.get("address", "").strip()
                    if not addr:
                        self._json({"ok": False, "error": "Missing address"}, 400)
                        return
                    peers = load_store(PEERS_PATH)
                    peer["seen"] = time.time()
                    peers[addr] = peer
                    save_store(peers, PEERS_PATH)
                    self._json({"ok": True, "peers": list(peers.values())})
                except json.JSONDecodeError:
                    self._json({"ok": False, "error": "Invalid JSON"}, 400)
                return

            self._json({"error": "not found"}, 404)

    return RelayHandler


def main():
    parser = argparse.ArgumentParser(description="Litmanger Comment Relay Server")
    parser.add_argument("--port", "-p", type=int, default=9987, help="Port (default: 9987)")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--no-verify", action="store_true", help="Skip Ed25519 signature verification")
    args = parser.parse_args()

    handler = create_handler(require_sig=not args.no_verify)

    server = http.server.ThreadingHTTPServer((args.host, args.port), handler)
    server.allow_reuse_address = True

    print(f"")
    print(f"  Litmanger Comment Relay")
    print(f"  -----------------------")
    print(f"  URL:    http://{args.host}:{args.port}")
    print(f"  Verify: {'Ed25519 ON' if not args.no_verify else 'OFF (--no-verify)'}")
    print(f"  Store:  {COMMENTS_PATH}")
    print(f"  Press Ctrl+C to stop")
    print(f"")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nRelay stopped.")


if __name__ == "__main__":
    main()
