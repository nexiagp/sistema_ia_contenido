"""Create a one-time team password and private server settings without printing them."""

from __future__ import annotations

import secrets
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.platform.team_auth import make_password_hash  # noqa: E402


def main() -> None:
    target = ROOT / "secrets"
    target.mkdir(exist_ok=True)
    password_file = target / "team-password.txt"
    settings_file = target / "team-access-env.txt"
    if password_file.exists() or settings_file.exists():
        raise SystemExit("Ya existen archivos de acceso. Guárdalos o retíralos antes de generar otros.")

    password = secrets.token_urlsafe(24)
    signing_secret = secrets.token_urlsafe(48)
    password_file.write_text(password + "\n", encoding="utf-8")
    settings_file.write_text(
        "NEXIAGP_AUTH_MODE=password\n"
        "NEXIAGP_AUTH_REQUIRED=1\n"
        f"NEXIAGP_SHARED_PASSWORD_HASH={make_password_hash(password)}\n"
        f"NEXIAGP_SESSION_SECRET={signing_secret}\n",
        encoding="utf-8",
    )
    print(f"Contraseña para el equipo: {password_file}")
    print(f"Variables privadas del servidor: {settings_file}")
    print("Los valores no se han enviado a ningún servicio.")


if __name__ == "__main__":
    main()
