"""Configuration loaded from environment / .env (stdlib only, no deps).

Secrets live in .env (gitignored). Real env vars always win over .env so the
same code runs unchanged on a host with injected secrets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def load_env(path: str = ".env") -> None:
    """Populate os.environ from a .env file without overriding existing vars."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    csfloat_api_key: Optional[str]
    steam_id64: Optional[str]
    csfloat_inspect_base: str
    smtp_host: str
    smtp_port: int
    smtp_user: Optional[str]
    smtp_password: Optional[str]
    mail_from: Optional[str]
    mail_to: Optional[str]
    poll_seconds: int
    divergence_pct: float
    cooldown_seconds: int

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password and self.mail_to)


def load_settings(env_path: str = ".env") -> Settings:
    load_env(env_path)
    return Settings(
        csfloat_api_key=os.environ.get("CSFLOAT_API_KEY") or None,
        steam_id64=os.environ.get("STEAM_ID64") or None,
        csfloat_inspect_base=os.environ.get("CSFLOAT_INSPECT_BASE", "https://api.csgofloat.com"),
        smtp_host=os.environ.get("SMTP_HOST", ""),
        smtp_port=_int("SMTP_PORT", 587),
        smtp_user=os.environ.get("SMTP_USER") or None,
        smtp_password=os.environ.get("SMTP_PASSWORD") or None,
        mail_from=os.environ.get("MAIL_FROM") or os.environ.get("SMTP_USER") or None,
        mail_to=os.environ.get("MAIL_TO") or None,
        poll_seconds=_int("POLL_SECONDS", 900),
        divergence_pct=_float("DIVERGENCE_PCT", 0.10),
        cooldown_seconds=_int("COOLDOWN_SECONDS", 21600),
    )
