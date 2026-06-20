"""Alert sinks: where signals go. All read-only / outbound notifications.

ConsoleSink  - local, free, instant (build/tune first)
JsonStateSink- writes state.json for the dashboard to read
EmailSink    - SMTP digest (Gmail app-password or Outlook), config-driven
"""

from __future__ import annotations

import json
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Sequence

from .config import Settings
from .models import Signal


def _money(c: int) -> str:
    return f"${c / 100:,.2f}"


class ConsoleSink:
    def emit(self, signals: Sequence[Signal]) -> None:
        if not signals:
            print("[cs2-arb] no signals this cycle")
            return
        for s in signals:
            print(f"[cs2-arb][{s.severity.upper()}] {s.message}")


class JsonStateSink:
    """Persist current signals so a read-only dashboard can render them."""

    def __init__(self, path: str = "state.json"):
        self.path = Path(path)

    def emit(self, signals: Sequence[Signal]) -> None:
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "signals": [
                {
                    "kind": s.kind,
                    "severity": s.severity,
                    "holding": s.holding.label,
                    "listing_id": s.listing.id,
                    "price": _money(s.listing.price_cents),
                    "float": round(s.listing.float_value, 4),
                    "fair_value": _money(s.fair_value.median_cents) if s.fair_value.median_cents else None,
                    "message": s.message,
                    "url": s.metadata.get("listing_url", ""),
                }
                for s in signals
            ],
        }
        self.path.write_text(json.dumps(payload, indent=2))


class EmailSink:
    """Send a single digest email for a batch of signals over SMTP+STARTTLS."""

    def __init__(self, settings: Settings):
        self.s = settings

    def _body(self, signals: Sequence[Signal]) -> str:
        lines = [f"{len(signals)} CS2 signal(s):", ""]
        for s in signals:
            lines.append(f"[{s.severity.upper()}] {s.message}")
            url = s.metadata.get("listing_url")
            if url:
                lines.append(f"    {url}")
            lines.append("")
        lines.append("— alert-only; no trades were placed.")
        return "\n".join(lines)

    @staticmethod
    def _discount(s: Signal):
        fv = s.fair_value.median_cents
        if not fv:
            return None
        return 1 - (s.listing.price_cents / fv)

    def _card(self, s: Signal) -> str:
        high = s.severity == "high"
        accent = "#f87171" if high else "#fbbf24"
        tag_bg = "rgba(248,113,113,.15)" if high else "rgba(251,191,36,.15)"
        kind = s.kind.replace("_", " ").upper()
        disc = self._discount(s)
        disc_txt = f"{disc:.0%} under fair" if disc is not None else ""
        fv = _money(s.fair_value.median_cents) if s.fair_value.median_cents else "—"
        url = s.metadata.get("listing_url", "")
        btn = (
            f'<a href="{url}" style="display:inline-block;margin-top:10px;padding:8px 16px;'
            f'background:#d8b66b;color:#0b1410;text-decoration:none;border-radius:6px;'
            f'font-weight:600;font-size:13px">View listing &rarr;</a>'
            if url else ""
        )
        return f"""
        <tr><td style="padding:0 0 12px 0">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f1d17;border-left:4px solid {accent};border-radius:0 10px 10px 0">
            <tr><td style="padding:16px 18px">
              <span style="font-size:10px;font-weight:700;letter-spacing:.5px;color:{accent};background:{tag_bg};padding:3px 9px;border-radius:999px">{kind}</span>
              <div style="font-size:16px;font-weight:600;color:#e7f0ea;margin:10px 0 6px">{s.holding.label}</div>
              <div style="font-size:22px;font-weight:700;color:#ffffff">{_money(s.listing.price_cents)}
                <span style="font-size:13px;font-weight:400;color:#8aa499">vs fair {fv}</span></div>
              <div style="font-size:12px;color:{accent};margin-top:4px">{disc_txt}</div>
              <div style="font-size:12px;color:#8aa499;margin-top:6px">float {s.listing.float_value:.4f} &nbsp;&middot;&nbsp; {s.fair_value.n_comps} comps</div>
              {btn}
            </td></tr>
          </table>
        </td></tr>"""

    def _html(self, signals: Sequence[Signal]) -> str:
        high = sum(1 for s in signals if s.severity == "high")
        sub = f"{len(signals)} signal{'s' if len(signals) != 1 else ''}" + (f" · {high} high" if high else "")
        cards = "".join(self._card(s) for s in signals)
        return f"""<!doctype html><html><body style="margin:0;padding:0;background:#0b1410">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0b1410;padding:24px 0">
<tr><td align="center">
  <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;font-family:Arial,Helvetica,sans-serif">
    <tr><td style="padding:0 18px 18px">
      <div style="font-size:20px;color:#e7f0ea;font-weight:700">CS2 <span style="color:#d8b66b">Arb</span></div>
      <div style="font-size:13px;color:#8aa499;margin-top:2px">{sub}</div>
    </td></tr>
    {cards}
    <tr><td style="padding:14px 18px 0">
      <div style="font-size:11px;color:#5f6f68;border-top:1px solid #1f3a2d;padding-top:12px">
        Alert-only — no trades were placed. Float-band comparables from CSFloat.</div>
    </td></tr>
  </table>
</td></tr></table></body></html>"""

    def emit(self, signals: Sequence[Signal]) -> None:
        if not signals:
            return
        if not self.s.email_configured:
            raise RuntimeError("email not configured — set SMTP_* and MAIL_TO in .env")

        msg = EmailMessage()
        high = sum(1 for s in signals if s.severity == "high")
        msg["Subject"] = f"CS2 arb: {len(signals)} signal(s)" + (f" ({high} high)" if high else "")
        msg["From"] = self.s.mail_from
        msg["To"] = self.s.mail_to
        msg.set_content(self._body(signals))              # plain-text fallback
        msg.add_alternative(self._html(signals), subtype="html")  # pretty HTML

        ctx = ssl.create_default_context()
        with smtplib.SMTP(self.s.smtp_host, self.s.smtp_port, timeout=30) as server:
            server.starttls(context=ctx)
            server.login(self.s.smtp_user, self.s.smtp_password)
            server.send_message(msg)
