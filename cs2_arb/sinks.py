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

    # CSFloat rarity int -> CS2 color (matches the dashboard palette)
    _RARITY = {1: "#b0c3d9", 2: "#5e98d9", 3: "#4b69ff", 4: "#8847ff",
               5: "#d32ce6", 6: "#eb4b4b", 7: "#cf9b3f"}
    _DISP = "'Saira Condensed',Arial,sans-serif"
    _MONO = "'JetBrains Mono',Consolas,monospace"

    @classmethod
    def _rarity_color(cls, rarity: int, label: str) -> str:
        if label and label.strip().startswith("★"):   # knives/gloves -> gold
            return "#e4ae39"
        return cls._RARITY.get(rarity, "#2d8fef")

    @staticmethod
    def _discount(s: Signal):
        fv = s.fair_value.median_cents
        return None if not fv else 1 - (s.listing.price_cents / fv)

    def _chip(self, text: str, color: str) -> str:
        return (f'<span style="font-family:{self._MONO};font-size:10px;font-weight:600;'
                f'letter-spacing:.5px;color:{color};border:1px solid {color};padding:2px 7px">{text}</span>')

    def _card(self, s: Signal) -> str:
        sev = "#eb4b4b" if s.severity == "high" else "#e4ae39"
        rar = self._rarity_color(getattr(s.listing, "rarity", 0) or getattr(s.holding, "rarity", 0),
                                 s.holding.label)
        fair = _money(s.fair_value.median_cents) if s.fair_value.median_cents else "—"
        url = s.metadata.get("listing_url", "")
        kind = s.kind.replace("_", " ").upper()
        is_flip = s.kind == "flip"

        if is_flip and s.metadata.get("roi") is not None:
            roi = s.metadata["roi"] * 100
            net = _money(s.metadata.get("net_cents")) if s.metadata.get("net_cents") is not None else "—"
            middle = (
                f'<div style="margin:11px 0 9px">'
                f'<span style="font-family:{self._DISP};font-weight:bold;font-size:26px;color:#4ee39a">+{roi:.0f}%</span>'
                f'&nbsp;&nbsp;<span style="font-family:{self._MONO};font-size:13px;color:#bccace">'
                f'{_money(s.listing.price_cents)} <span style="color:{rar}">&rarr;</span> '
                f'<span style="color:#9fd6a8">{fair}</span></span></div>'
            )
            meta = f"FLOAT {s.listing.float_value:.4f} &middot; {s.fair_value.n_comps} COMPS &middot; NET {net}"
        else:
            disc = self._discount(s)
            disc_txt = (f'<span style="color:{sev};font-size:12px"> &middot; {disc:.0%} under</span>'
                        if disc is not None else "")
            middle = (
                f'<div style="margin:9px 0 7px">'
                f'<span style="font-family:{self._DISP};font-weight:bold;font-size:22px;color:#ffffff">'
                f'{_money(s.listing.price_cents)}</span>'
                f'<span style="font-family:{self._MONO};font-size:12px;color:#6f8189"> vs fair {fair}</span>'
                f'{disc_txt}</div>'
            )
            meta = f"FLOAT {s.listing.float_value:.4f} &middot; {s.fair_value.n_comps} COMPS"

        btn = (f'<a href="{url}" style="font-family:{self._DISP};font-weight:bold;font-size:12px;'
               f'letter-spacing:1px;color:#2d8fef;text-decoration:none">VIEW LISTING &rarr;</a>'
               if url else "")

        return f"""
        <tr><td style="padding:0 0 11px 0">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f191e;border:1px solid #1b2a31;border-left:3px solid {rar}">
            <tr><td style="padding:13px 16px">
              <table width="100%" cellpadding="0" cellspacing="0"><tr>
                <td style="font-family:{self._DISP};font-weight:bold;font-size:17px;color:#eef5f7">
                  <span style="color:{rar};font-size:13px">&#9679;</span>&nbsp; {s.holding.label}</td>
                <td align="right" style="white-space:nowrap">{self._chip(kind, sev)}</td>
              </tr></table>
              {middle}
              <table width="100%" cellpadding="0" cellspacing="0"><tr>
                <td style="font-family:{self._MONO};font-size:11px;color:#6f8189;letter-spacing:.3px">{meta}</td>
                <td align="right">{btn}</td>
              </tr></table>
            </td></tr>
          </table>
        </td></tr>"""

    def _html(self, signals: Sequence[Signal]) -> str:
        high = sum(1 for s in signals if s.severity == "high")
        flips = sum(1 for s in signals if s.kind == "flip")
        label = "FLIPS" if flips and flips == len(signals) else "SIGNALS"
        status = f"{len(signals)} {label}" + (f" &middot; {high} HIGH" if high else "")
        cards = "".join(self._card(s) for s in signals)
        stripe = ("background:#e4ae39;background-image:repeating-linear-gradient(45deg,"
                  "#e4ae39,#e4ae39 6px,#0b1014 6px,#0b1014 12px)")
        return f"""<!doctype html><html><body style="margin:0;padding:0;background:#070a0b">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#070a0b;padding:24px 0">
<tr><td align="center">
  <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">
    <tr><td style="padding:0 18px 12px">
      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td width="34" style="vertical-align:middle"><div style="width:30px;height:30px;background:#10355c;color:#fff;text-align:center;line-height:30px;font-size:16px">&#9678;</div></td>
        <td style="padding-left:10px;vertical-align:middle">
          <div style="font-family:{self._DISP};font-weight:bold;font-size:19px;letter-spacing:2px;color:#e6eef0">CS2 <span style="color:#2d8fef">ARBITRAGE</span> TERMINAL</div>
          <div style="font-family:{self._MONO};font-size:11px;letter-spacing:.5px;color:#6f8189;margin-top:3px">{status}</div>
        </td>
      </tr></table>
    </td></tr>
    <tr><td style="padding:0 18px"><div style="height:3px;{stripe}"></div></td></tr>
    <tr><td style="padding:16px 18px 0">
      <table width="100%" cellpadding="0" cellspacing="0">
        {cards}
      </table>
    </td></tr>
    <tr><td style="padding:6px 18px 0">
      <div style="font-family:{self._MONO};font-size:11px;color:#52646b;border-top:1px solid #1b2a31;padding-top:12px">
        ALERT-ONLY &middot; NO TRADES PLACED &middot; FLOAT-BAND COMPARABLES FROM CSFLOAT</div>
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
