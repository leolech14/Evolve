#!/usr/bin/env python3
"""
Recebe POSTs de logs (multipart/form-data ou raw) e salva em ./ci_inbox/.
Retorna 200 OK imediatamente.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import datetime
import os

INBOX = Path("ci_inbox")
INBOX.mkdir(exist_ok=True)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")

        # Extract headers for organization
        repo_key = self.headers.get("X-Repo-Key", "unknown")
        branch = self.headers.get("X-Branch", "unknown")
        run_id = self.headers.get("X-Run-ID", "unknown")
        file_name = self.headers.get("X-File-Name", "unknown")

        # Create repo-specific subdirectory
        repo_dir = INBOX / repo_key
        repo_dir.mkdir(exist_ok=True)

        # Create filename with context, preserve original extension
        if file_name != "unknown":
            fname = repo_dir / f"{branch}_{run_id}_{ts}_{file_name}"
        else:
            fname = repo_dir / f"log_{branch}_{run_id}_{ts}.txt"

        with fname.open("wb") as f:
            # Write headers as metadata first
            metadata = "# Log metadata\n"
            metadata += f"# Repo: {repo_key}\n"
            metadata += f"# Branch: {branch}\n"
            metadata += f"# Run ID: {run_id}\n"
            metadata += f"# Timestamp: {ts}\n"
            metadata += f"# Content-Length: {length}\n\n"
            f.write(metadata.encode())
            f.write(body)

        print(f"📥 Received log from {repo_key}/{branch} (run {run_id}) -> {fname}")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")


if __name__ == "__main__":
    port = int(os.getenv("LOG_PORT", "5050"))
    print(f"Listening on http://localhost:{port}/")
    HTTPServer(("", port), Handler).serve_forever()
