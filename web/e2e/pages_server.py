"""Local stand-in for Cloudflare Pages, for checking the build before deploy.

Serves web/dist applying the same rules Pages applies to our config:
  * `_headers` `/*` block on every response
  * `_redirects` rewrites (exact, or `/path/*` splat) with status 200
  * anything else that isn't a file -> 404.html with HTTP 404
It is an emulation: confirm against the real deploy with
`curl -sI https://<deploy>/nope` (expect 404).

Usage: python pages_server.py [dist_dir] [port]
"""

import http.server
import mimetypes
import sys
from pathlib import Path

DIST = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parents[1] / "dist").resolve()
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8788


def parse_headers() -> dict[str, str]:
    out: dict[str, str] = {}
    active = False
    for line in (DIST / "_headers").read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            active = line.strip() == "/*"
        elif active:
            k, _, v = line.strip().partition(":")
            out[k.strip()] = v.strip()
    return out


def parse_redirects() -> list[tuple[str, str]]:
    rules = []
    for line in (DIST / "_redirects").read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        src, dst, status = line.split()
        assert status == "200", "only rewrites expected"
        rules.append((src, dst))
    return rules


HEADERS, REDIRECTS = parse_headers(), parse_redirects()


def resolve(path: str) -> tuple[int, Path]:
    path = path.split("?")[0]
    for src, dst in REDIRECTS:
        if src == path or (src.endswith("/*") and path.startswith(src[:-1])):
            return 200, DIST / dst.lstrip("/")
    f = DIST / path.lstrip("/")
    if path.endswith("/"):
        f = f / "index.html"
    if f.is_file() and DIST in f.resolve().parents:
        return 200, f
    return 404, DIST / "404.html"


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, head: bool) -> None:
        status, f = resolve(self.path)
        body = f.read_bytes()
        self.send_response(status)
        self.send_header("Content-Type", mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        for k, v in HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        self._send(False)

    def do_HEAD(self) -> None:  # noqa: N802
        self._send(True)

    def log_message(self, *_a: object) -> None:
        pass


if __name__ == "__main__":
    print(f"serving {DIST} on http://127.0.0.1:{PORT}")
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
