import http.server
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9080
BASE = os.path.join(os.path.dirname(__file__), "frontend")


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # strips /forms/ prefix added by tailscale serve --set-path
        path = self.path
        if path.startswith("/forms/"):
            path = path.removeprefix("/forms")
        elif path == "/forms":
            path = "/"
        elif path == "/":
            path = "/"

        if path == "/":
            path = "/public/index.html"

        full = os.path.normpath(os.path.join(BASE, path.lstrip("/")))
        if not full.startswith(os.path.normpath(BASE)):
            self.send_error(404)
            return

        if os.path.isdir(full):
            full = os.path.join(full, "index.html")

        if not os.path.isfile(full):
            self.send_error(404)
            return

        ct = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".json": "application/json",
        }.get(os.path.splitext(full)[1], "application/octet-stream")

        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.end_headers()
        with open(full, "rb") as f:
            self.wfile.write(f.read())


if __name__ == "__main__":
    srv = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Serving frontend/ at http://0.0.0.0:{PORT}")
    print(f"Prefix /forms/ is stripped automatically (for tailscale serve --set-path)")
    srv.serve_forever()
