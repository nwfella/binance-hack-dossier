@echo off
REM Hourly local refresh for the Binance hack dossier.
REM Enable with (one line, no admin needed):
REM   schtasks /Create /TN "BinanceHackTracker" /TR "%CD%\scripts\refresh_local.cmd" /SC HOURLY /F
REM Disable with:
REM   schtasks /Delete /TN "BinanceHackTracker" /F
cd /d "%~dp0.."

python scripts\update_feeds.py || exit /b 1
node scripts\verify_site.js || exit /b 1

git add docs\index.html docs\updates.json
git diff --cached --quiet && exit /b 0

git commit -m "chore: local refresh"
git pull --rebase --quiet
git push --quiet
