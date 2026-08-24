"""Black-box check that managed deployment fails closed without a session."""
from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from http.server import ThreadingHTTPServer

from server import AppHandler


def main() -> int:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), AppHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{httpd.server_port}"
    try:
        with urllib.request.urlopen(f"{base_url}/api/auth/config", timeout=5) as response:
            config = json.loads(response.read().decode("utf-8"))
            config_status = response.status
        try:
            urllib.request.urlopen(f"{base_url}/api/state", timeout=5)
            state_status = 200
        except urllib.error.HTTPError as exc:
            state_status = exc.code
        if not (config_status == 200 and config.get("required") and config.get("configured") and state_status == 401):
            raise SystemExit("El cierre de acceso no produjo el resultado esperado.")
        print(json.dumps({"configStatus": config_status, "authRequired": True, "authConfigured": True, "unauthenticatedStateStatus": state_status}))
        return 0
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
