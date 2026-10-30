#!/usr/bin/env python3
"""Render docs/report.html -> PDF using headless Chrome/Edge (no external deps)."""
import os, shutil, subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "report.html"
OUT = ROOT / "docs" / "Binance-Hack-Report-2026-10-29.pdf"

CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
]

def find_browser():
    for c in CANDIDATES:
        if os.path.exists(c):
            return c
    for name in ("chrome", "chromium", "google-chrome", "msedge"):
        p = shutil.which(name)
        if p:
            return p
    return None

def main():
    br = find_browser()
    if not br:
        sys.exit("No Chrome/Edge found for PDF rendering.")

    url = SRC.as_uri()
    # Chrome must be pointed at a native path; MSYS paths are not translated.
    out_native = str(OUT)
    cmd = [
        br,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=4000",
        f"--print-to-pdf={out_native}",
        url,
    ]
    print("using:", br)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if not OUT.exists():
        print(r.stdout[-3000:]); print(r.stderr[-3000:])
        sys.exit("PDF was not produced.")

    size = OUT.stat().st_size
    print(f"WROTE {OUT}  ({size/1024:.1f} KB)")
    if size < 40_000:
        sys.exit("PDF suspiciously small — layout may have failed.")

if __name__ == "__main__":
    main()
