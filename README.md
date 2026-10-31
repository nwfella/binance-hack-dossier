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


## Refresh triggers — how it actually works

**Primary writer: a Windows scheduled task, hourly at :05.**

```
schtasks /Query  /TN "BinanceHackTracker"     # status + next run
schtasks /Run    /TN "BinanceHackTracker"     # trigger now
schtasks /Delete /TN "BinanceHackTracker" /F  # remove
```

It runs `scripts/refresh_local.cmd`, which syncs to origin, regenerates the page, runs the
verification gate, and commits. It logs every attempt to `logs/refresh.log`.

**It is conflict-safe by construction.** `docs/index.html` and `docs/updates.json` are *generated*
files, so rebasing them against a concurrent run can only ever conflict. Instead the runner resets
to `origin/main` and regenerates from that state — a stale local copy can never overwrite newer
remote data, and a race costs at most one retry. It also refuses to run at all if the working tree
has uncommitted hand edits.

**Fallback: GitHub Actions `schedule`.** GitHub delivers this repo's cron at roughly 3–7 hour
intervals regardless of the requested cadence (measured over 7 scheduled runs: mean gap 5.5h), so
it is a backstop for when the PC is off, not the primary path. `workflow_dispatch` also works.

> Note: the workflow deliberately has **no `push` trigger**. With the local task running hourly, a
> push-triggered rebuild would fire on every refresh and add a duplicate commit each hour.

## History of this problem

The first deployment used GitHub's cron as the only trigger. It delivered **zero** events in 4
hours, then (after re-registering the workflow under a new filename) only about every six hours.
That is why the page computes its own age from a baked `data-built` timestamp and flips to a red
"refresh stalled" banner past three hours — a stalled scheduler is now visible rather than silent.

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
