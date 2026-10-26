"""Password access must reject tampering and protect editorial routes."""

from __future__ import annotations

import http.client
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import server
from src.platform.team_auth import SESSION_SECONDS, issue_session, make_password_hash, verify_password, verify_session


class TeamAuthTests(unittest.TestCase):
    def test_password_hash_and_session_expiry(self) -> None:
        password = "a-long-random-team-password-123"
        encoded = make_password_hash(password)
        self.assertTrue(verify_password(password, encoded))
        self.assertFalse(verify_password(password + "wrong", encoded))
        secret = "s" * 48
        token = issue_session(secret, now=1000)
        self.assertTrue(verify_session(token, secret, now=1000))
        self.assertTrue(verify_session(token, secret, now=1000 + SESSION_SECONDS - 1))
        self.assertFalse(verify_session(token, secret, now=1000 + SESSION_SECONDS))
        self.assertFalse(verify_session(token + "x", secret, now=1000))
        self.assertFalse(verify_session(token, "other" * 10, now=1000))

    def test_password_route_sets_private_cookie_and_requires_origin(self) -> None:
        password = "another-long-team-password-456"
        settings = {
            "NEXIAGP_AUTH_MODE": "password",
            "NEXIAGP_AUTH_REQUIRED": "1",
            "NEXIAGP_SHARED_PASSWORD_HASH": make_password_hash(password),
            "NEXIAGP_SESSION_SECRET": "q" * 48,
        }
        with patch.dict(os.environ, settings):
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.AppHandler)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                port = httpd.server_port
                def request(method: str, path: str, body: dict | None = None, headers: dict | None = None):
                    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                    data = json.dumps(body).encode() if body is not None else None
                    connection.request(method, path, data, headers or {})
                    response = connection.getresponse()
                    result = (response.status, dict(response.getheaders()), json.loads(response.read()))
                    connection.close()
                    return result

                status, _, _ = request("GET", "/api/state")
                self.assertEqual(status, 401)
                status, _, _ = request("POST", "/api/auth/password", {"password": password})
                self.assertEqual(status, 403)
                origin = {"Origin": f"http://127.0.0.1:{port}", "X-Forwarded-Proto": "http", "Content-Type": "application/json"}
                status, _, _ = request("POST", "/api/auth/password", {"password": "incorrect"}, origin)
                self.assertEqual(status, 401)
                status, response_headers, body = request("POST", "/api/auth/password", {"password": password}, origin)
                self.assertEqual(status, 200)
                self.assertEqual(body["user"]["role"], "admin")
                cookie = response_headers["set-cookie"]
                self.assertIn("HttpOnly; Secure; SameSite=Strict", cookie)
                status, _, body = request("GET", "/api/auth/session", headers={"Cookie": cookie.split(";", 1)[0]})
                self.assertEqual(status, 200)
                self.assertTrue(body["ok"])
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
