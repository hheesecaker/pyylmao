from __future__ import annotations

import argparse
import functools
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .gay import DEFAULT_BASE_URL_FILE, DEFAULT_WWW_DIR


DEFAULT_PORT = 8765
TUNNEL_URL_RE = re.compile(r"https://[A-Za-z0-9-]+\.trycloudflare\.com")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve pyylmao generated web assets")
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path(os.getenv("PYYLMAO_WWW_DIR", DEFAULT_WWW_DIR)),
        help="directory containing generated images",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PYYLMAO_WWW_PORT", str(DEFAULT_PORT))),
        help="local HTTP port for generated images",
    )
    parser.add_argument(
        "--base-url-file",
        type=Path,
        default=Path(os.getenv("PYYLMAO_WWW_BASE_URL_FILE", DEFAULT_BASE_URL_FILE)),
        help="file where the discovered public tunnel URL is written",
    )
    parser.add_argument(
        "--no-tunnel",
        action="store_true",
        help="serve local HTTP only and do not start cloudflared",
    )
    parser.add_argument(
        "--cloudflared-protocol",
        default=os.getenv("PYYLMAO_CLOUDFLARED_PROTOCOL", "http2"),
        help="cloudflared transport protocol, for example http2 or quic",
    )
    args = parser.parse_args()

    args.dir.mkdir(parents=True, exist_ok=True)
    server = start_http_server(args.dir, args.port)
    local_url = f"http://127.0.0.1:{args.port}"
    print(f"serving {args.dir} at {local_url}", flush=True)

    tunnel: subprocess.Popen[str] | None = None
    try:
        try:
            if not args.no_tunnel:
                tunnel = start_cloudflared(args.port, args.cloudflared_protocol)
                stream_tunnel_output(tunnel, args.base_url_file)
            else:
                signal.pause()
        except KeyboardInterrupt:
            pass
    finally:
        if tunnel is not None and tunnel.poll() is None:
            tunnel.terminate()
        server.shutdown()


def start_http_server(directory: Path, port: int) -> ThreadingHTTPServer:
    handler = functools.partial(QuietHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def start_cloudflared(port: int, protocol: str = "http2") -> subprocess.Popen[str]:
    local_binary = Path.home() / ".local" / "bin" / "cloudflared"
    binary = shutil.which("cloudflared") or (
        str(local_binary) if local_binary.exists() else None
    )
    if binary is None:
        raise SystemExit(
            "cloudflared is not installed. Install it, then rerun: "
            f"python3 -m pyylmao.image_server --port {port}"
        )
    return subprocess.Popen(
        [
            binary,
            "tunnel",
            "--url",
            f"http://127.0.0.1:{port}",
            "--protocol",
            protocol,
            "--no-autoupdate",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )


def stream_tunnel_output(process: subprocess.Popen[str], base_url_file: Path) -> None:
    assert process.stdout is not None
    seen_url = False
    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        match = TUNNEL_URL_RE.search(line)
        if match:
            url = match.group(0)
            base_url_file.parent.mkdir(parents=True, exist_ok=True)
            base_url_file.write_text(url + "\n", encoding="utf-8")
            if not seen_url:
                print(f"PYYLMAO_WWW_BASE_URL={url}", flush=True)
                print(f"wrote {base_url_file}", flush=True)
                seen_url = True
    raise SystemExit(process.wait())


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    main()
