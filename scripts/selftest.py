"""Connectivity self-test. Run: python -m scripts.selftest [--send-email]

Verifies CSFloat key, Steam inventory access, and (optionally) SMTP email.
Never prints secret values. Read-only except the optional email step.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request

from cs2_arb.config import load_settings
from cs2_arb.csfloat_client import CSFloatClient
from cs2_arb.steam_inventory import fetch_inventory, parse_inventory

OK, FAIL, SKIP = "[ OK ]", "[FAIL]", "[SKIP]"


def check_csfloat(s) -> bool:
    if not s.csfloat_api_key:
        print(f"{SKIP} CSFloat: no API key")
        return False
    try:
        client = CSFloatClient(api_key=s.csfloat_api_key, min_interval=0.0)
        # auth-protected endpoint; 200 => key valid
        req = urllib.request.Request(
            "https://csfloat.com/api/v1/me",
            headers={"Authorization": s.csfloat_api_key, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
        print(f"{OK} CSFloat: API key accepted (/me 200)")
        return True
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print(f"{FAIL} CSFloat: 401 — key rejected")
        else:
            # /me may not exist; fall back to a public listings call
            try:
                got = next(client.iter_listings(market_hash_name="AK-47 | Redline (Field-Tested)",
                                                 max_pages=1), None)
                print(f"{OK} CSFloat: reachable (listings ok; /me returned {e.code})")
                return got is not None
            except Exception as e2:
                print(f"{FAIL} CSFloat: {e.code} on /me, listings failed: {e2}")
        return False
    except Exception as e:
        print(f"{FAIL} CSFloat: {type(e).__name__}: {e}")
        return False


def check_steam(s) -> bool:
    if not s.steam_id64:
        print(f"{SKIP} Steam: no STEAM_ID64")
        return False
    try:
        raw = fetch_inventory(s.steam_id64)
        items = parse_inventory(raw, s.steam_id64)
        with_inspect = sum(1 for i in items if i.inspect_link)
        print(f"{OK} Steam: inventory public — {len(items)} marketable items, "
              f"{with_inspect} with inspect links")
        for i in items[:5]:
            print(f"       - {i.market_hash_name}")
        if len(items) > 5:
            print(f"       ... (+{len(items) - 5} more)")
        return True
    except Exception as e:
        print(f"{FAIL} Steam: {type(e).__name__}: {e}")
        return False


def check_email(s, send: bool) -> bool:
    import smtplib
    import ssl
    if not s.email_configured:
        print(f"{SKIP} Email: SMTP not fully configured")
        return False
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as server:
            server.starttls(context=ctx)
            server.login(s.smtp_user, s.smtp_password)
            if send:
                from email.message import EmailMessage
                msg = EmailMessage()
                msg["Subject"] = "CS2 arb — self-test OK"
                msg["From"] = s.mail_from
                msg["To"] = s.mail_to
                msg.set_content("If you're reading this, SMTP alerting works. "
                                "Alert-only; no trades placed.")
                server.send_message(msg)
                print(f"{OK} Email: login OK + test email sent to {s.mail_to}")
            else:
                print(f"{OK} Email: SMTP login OK (no email sent; pass --send-email to send)")
        return True
    except Exception as e:
        print(f"{FAIL} Email: {type(e).__name__}: {e}")
        return False


def main() -> None:
    send = "--send-email" in sys.argv
    s = load_settings(".env")
    print("=" * 60)
    print("CS2 ARB SELF-TEST")
    print("=" * 60)
    results = {
        "csfloat": check_csfloat(s),
        "steam": check_steam(s),
        "email": check_email(s, send),
    }
    print("-" * 60)
    print("summary:", ", ".join(f"{k}={'pass' if v else 'fail/skip'}" for k, v in results.items()))


if __name__ == "__main__":
    main()
