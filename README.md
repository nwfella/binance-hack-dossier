# Binance Hack Dossier — Oct 29, 2026

Detailed incident report (PDF) + an hourly-updating live tracker for the October 29, 2026
Binance hot-wallet compromise.

- **Live tracker:** <https://nwfella.github.io/binance-hack-dossier/>
- **PDF report:** [`docs/Binance-Hack-Report-2026-10-29.pdf`](docs/Binance-Hack-Report-2026-10-29.pdf)

## How the hourly update works (and why it costs $0)

The tracker is **not** an AI-generated digest. A plain Python script
(`scripts/update_feeds.py`) polls public RSS feeds from crypto newsrooms, filters items for
Binance-incident keywords, dedupes against a committed state file, and regenerates a static
`docs/index.html` with the data **baked in**. GitHub Actions runs it every hour and commits
the result.

- No LLM calls, no API keys, no per-token cost — pure HTTP + XML parsing.
- Data is baked into the HTML rather than fetched in the browser, so the page renders fully
  even where XHR/fetch to `github.io` is blocked.
- GitHub Actions on a public repo is free; hourly runs are well inside the free allowance.

## Layout

```
docs/index.html                     generated — do not hand-edit
docs/report.html                    report source (print CSS → A4)
docs/Binance-Hack-Report-2026-10-29.pdf
docs/updates.json                   current feed state (committed)
scripts/update_feeds.py             fetch → filter → dedupe → render
scripts/build_report.py             report.html → PDF via headless Chrome
scripts/verify_site.js              verification gate
state/seen.json                     dedupe index (committed)
.github/workflows/hourly.yml        hourly rebuild + commit
```


## Refresh triggers — read this

**GitHub Actions `schedule` does not work for this repository.** Proven, not suspected: two
different workflow files, including a five-minute canary left running for 13 minutes, produced
**zero** `schedule` events. `push` and `workflow_dispatch` triggers work normally. This is a
GitHub-side scheduling failure, not a configuration error.

What this means: the hourly rebuild only happens if something else triggers it. Three options:

1. **Manual dispatch** (always available):
   ```bash
   gh workflow run "Refresh tracker" --ref main
   ```
2. **Local Windows Task Scheduler** — no third party, nothing leaves the machine, but only runs
   while the PC is on. Opt in with:
   ```
   schtasks /Create /TN "BinanceHackTracker" /TR "C:\path\to\repo\scripts\refresh_local.cmd" /SC HOURLY /F
   ```
   Remove with `schtasks /Delete /TN "BinanceHackTracker" /F`.
3. **External cron service** hitting the `workflow_dispatch` API — works with the PC off, but
   requires storing a repo-scoped `actions:write` token with a third party.

### The page cannot rot silently

The build instant is baked into `<body data-built="...">` and the page computes its own age in the
browser. Past three hours it flips the metabar to a red **refresh stalled** indicator and shows an
amber banner stating the feed is frozen at that build time. If the scheduler dies, the page says so
rather than pretending to be current.

## Manual refresh

```bash
python scripts/update_feeds.py          # refresh feeds + rebuild index.html
python scripts/build_report.py          # rebuild the PDF
node scripts/verify_site.js docs/index.html
```

## Verification

The deploy is verified by fetching the live page and comparing its hash to the local build
(CRLF-normalised), plus a headless-browser render check that the DOM populated.

## Disclaimer

Security-incident reporting in the first 24 hours is provisional. Figures below are attributed
to their sources and should be treated as estimates until Binance publishes its post-mortem.
Not financial advice.

Licence: MIT
