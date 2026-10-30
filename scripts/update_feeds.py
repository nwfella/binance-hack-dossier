#!/usr/bin/env python3
"""
Hourly updater for the Binance hack dossier tracker.

Zero AI cost: plain HTTP + XML parsing, no LLM calls, no API keys.

  python scripts/update_feeds.py            # fetch, merge, rebuild docs/index.html
  python scripts/update_feeds.py --offline  # rebuild from existing state only

State:  docs/updates.json   (feed items, committed)
Output: docs/index.html     (static, data baked in — no runtime fetch)
"""
from __future__ import annotations

import email.utils
import html
import json
import pathlib
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
STATE = DOCS / "updates.json"
OUT = DOCS / "index.html"

MAX_ITEMS = 260
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"

FEEDS = [
    ("Protos",          "https://protos.com/feed/"),
    ("CoinDesk",        "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("The Block",       "https://www.theblock.co/rss.xml"),
    ("Cointelegraph",   "https://cointelegraph.com/rss"),
    ("Decrypt",         "https://decrypt.co/feed"),
    ("CryptoSlate",     "https://cryptoslate.com/feed/"),
    ("BleepingComputer","https://www.bleepingcomputer.com/feed/"),
    ("Bitcoin.com",     "https://news.bitcoin.com/feed/"),
    ("Rekt",            "https://rekt.news/rss/feed.xml"),
]

# An item must look like it is about THIS incident, not Binance in general.
RE_BINANCE = re.compile(r"\bbinance\b|\bbnb\b|\bcz_binance\b|\bzhao\b", re.I)
RE_INCIDENT = re.compile(
    r"\bhack|\bexploit|\bbreach|\bdrain|stolen|theft|securit[yi] (?:issue|incident|breach)"
    r"|withdraw(?:al)?s? (?:paused|halted|suspend|frozen|resume)|suspend"
    r"|frozen|freeze|post-?mortem|\bswept|sweeper|7702|hot wallet|\beip-?7702"
    r"|\$[\d.]+ ?(?:bn|billion)", re.I)
RE_ISSUER = re.compile(r"tether|circle\b|usdt|usdc|paolo ardoino|jeremy allaire", re.I)
RE_FREEZE = re.compile(r"freeze|frozen|blacklist|blocklist", re.I)


# ---------------------------------------------------------------- feed parsing
def fetch(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read()
    except Exception as e:  # noqa: BLE001
        print(f"  ! {url}: {e}", file=sys.stderr)
        return None


BOILER = [
    re.compile(r"\s*The post .{0,200}? appeared first on .{0,60}?\.?\s*$", re.I),
    re.compile(r"\s*Read more:?\s*$", re.I),
    re.compile(r"\s*Continue reading.{0,100}$", re.I),
    re.compile(r"\s*\[\s*\]\s*$"),
    re.compile(r"\s*Post navigation\s*$", re.I),
]


def clean_desc(s: str) -> str:
    for rx in BOILER:
        s = rx.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def strip_tags(s: str) -> str:
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    try:
        dt = email.utils.parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:  # noqa: BLE001
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(raw.replace("Z", "+0000"), fmt)
            return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_feed(xml_bytes: bytes, source: str) -> list[dict]:
    import xml.etree.ElementTree as ET

    out: list[dict] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return out

    def txt(node, *names):
        for n in names:
            el = node.find(n)
            if el is not None and (el.text or "").strip():
                return el.text.strip()
        return ""

    # RSS 2.0
    for item in root.iter("item"):
        title = strip_tags(txt(item, "title"))
        link = txt(item, "link") or txt(item, "guid")
        desc = strip_tags(txt(item, "description"))
        date = parse_date(txt(item, "pubDate") or txt(item, "date"))
        if title and link:
            out.append({"source": source, "title": title, "link": link, "desc": clean_desc(desc)[:400],
                        "date": date.isoformat() if date else None})

    # Atom
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
        title = strip_tags(txt(entry, "a:title"))
        link = ""
        for l in entry.findall("a:link", ns):
            if l.get("rel") in (None, "alternate"):
                link = l.get("href", "")
                break
        desc = strip_tags(txt(entry, "a:summary") or txt(entry, "a:content"))
        date = parse_date(txt(entry, "a:updated") or txt(entry, "a:published"))
        if title and link:
            out.append({"source": source, "title": title, "link": link, "desc": clean_desc(desc)[:400],
                        "date": date.isoformat() if date else None})
    return out


def relevant(it: dict) -> bool:
    blob = f"{it['title']} {it.get('desc','')}"
    if RE_BINANCE.search(it["title"]) and RE_INCIDENT.search(blob):
        return True
    # issuer-freeze stories about this incident often omit "Binance" from the headline
    if RE_ISSUER.search(it["title"]) and RE_FREEZE.search(it["title"]) and re.search(r"\$[\d.]+\s*(bn|billion|m|million)", blob, re.I):
        return True
    return False


def norm_key(it: dict) -> str:
    t = re.sub(r"[^a-z0-9 ]", "", it["title"].lower())
    t = re.sub(r"\s+", " ", t).strip()
    return t[:90]


# ---------------------------------------------------------------- state
def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"items": [], "first_run": None, "runs": 0, "last_run": None}


def update(offline: bool) -> dict:
    st = load_state()
    now = datetime.now(timezone.utc)
    st["runs"] = int(st.get("runs", 0)) + 1
    st["last_run"] = now.isoformat()
    st.setdefault("first_run", now.isoformat())

    seen = {norm_key(i) for i in st["items"]}
    seen_links = {i["link"] for i in st["items"]}
    added = 0

    if not offline:
        for source, url in FEEDS:
            raw = fetch(url)
            if not raw:
                continue
            got = parse_feed(raw, source)
            n_new = 0
            for it in got:
                if not relevant(it):
                    continue
                k = norm_key(it)
                if k in seen or it["link"] in seen_links:
                    continue
                seen.add(k)
                seen_links.add(it["link"])
                it["first_seen"] = now.isoformat()
                st["items"].append(it)
                n_new += 1
            added += n_new
            print(f"  {source:16s} {len(got):3d} items, {n_new:2d} new")

    # sort newest first; undated items fall back to first_seen
    def sort_key(i):
        return i.get("date") or i.get("first_seen") or ""

    st["items"].sort(key=sort_key, reverse=True)
    st["items"] = st["items"][:MAX_ITEMS]
    print(f"added {added} new items; total {len(st['items'])}")
    STATE.write_text(json.dumps(st, indent=1), encoding="utf-8")
    return st


# ---------------------------------------------------------------- render
def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def ago(dt: datetime, now: datetime) -> str:
    d = now - dt
    s = int(d.total_seconds())
    if s < 90:
        return "just now"
    if s < 5400:
        return f"{s//60} min ago"
    if s < 129600:
        return f"{s//3600} h ago"
    return f"{s//86400} d ago"


def render(st: dict) -> str:
    now = datetime.now(timezone.utc)
    tpl = (pathlib.Path(__file__).parent / "template.html").read_text(encoding="utf-8")

    rows = []
    for it in st["items"]:
        dt = None
        for key in ("date", "first_seen"):
            if it.get(key):
                dt = parse_date(it[key]) if key == "date" else datetime.fromisoformat(it[key])
                if dt:
                    break
        if dt:
            stamp = dt.astimezone(timezone.utc).strftime("%d %b %H:%M UTC")
            rel = ago(dt, now)
        else:
            stamp, rel = "—", ""
        rows.append(
            '<article class="upd">'
            f'<div class="uh"><span class="src s-{esc(re.sub(r"[^a-z0-9]", "", it["source"].lower()))}">{esc(it["source"])}</span>'
            f'<time datetime="{dt.isoformat() if dt else ""}">{stamp}</time>'
            f'<span class="rel">{rel}</span></div>'
            f'<a class="ut" href="{esc(it["link"])}" target="_blank" rel="noopener">{esc(it["title"])}</a>'
            + (f'<p class="ud">{esc(it["desc"][:230])}{"…" if len(it.get("desc",""))>230 else ""}</p>' if it.get("desc") else "")
            + "</article>"
        )
    feed_html = "\n".join(rows) or '<p class="empty">No matching items yet — the next refresh will populate this.</p>'

    last = st.get("last_run")
    last_dt = datetime.fromisoformat(last) if last else now
    fresh_age = (now - last_dt).total_seconds()
    stale = fresh_age > 3 * 3600
    built = last_dt.strftime("%d %b %Y, %H:%M UTC")

    # newest item time, for the "latest headline" chip
    newest = None
    for it in st["items"]:
        if it.get("date"):
            newest = parse_date(it["date"])
            if newest:
                break

    counts: dict[str, int] = {}
    for it in st["items"]:
        counts[it["source"]] = counts.get(it["source"], 0) + 1
    src_chips = " ".join(
        f'<span class="chip">{esc(k)} <b>{v}</b></span>' for k, v in sorted(counts.items(), key=lambda x: -x[1])
    )

    return (
        tpl.replace("{{FEED}}", feed_html)
        .replace("{{BUILT}}", built)
        .replace("{{LAST_ET}}", last_dt.astimezone(timezone(timedelta(hours=-7))).strftime("%d %b %H:%M PDT"))
        .replace("{{COUNT}}", str(len(st["items"])))
        .replace("{{RUNS}}", str(st.get("runs", 0)))
        .replace("{{STALE_CLASS}}", " stale" if stale else "")
        .replace("{{STALE_NOTE}}", '<div class="banner">Data is more than 3 hours old — the hourly job may be stalled. Check the Actions tab.</div>' if stale else "")
        .replace("{{SRC_CHIPS}}", src_chips)
        .replace("{{NEWEST}}", ago(newest, now) if newest else "—")
        .replace("{{GEN_ISO}}", now.isoformat())
    )


def main() -> None:
    offline = "--offline" in sys.argv
    st = update(offline)
    DOCS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(st), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
