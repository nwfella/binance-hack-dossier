@echo off
REM Hourly local refresh for the Binance hack dossier.
REM Runs at :05 past every hour via Task Scheduler. Pulls first so a stale local
REM copy can never overwrite newer commits from the GitHub Actions fallback.
REM   schtasks /Run    /TN "BinanceHackTracker"
REM   schtasks /Query  /TN "BinanceHackTracker"
REM   schtasks /Delete /TN "BinanceHackTracker" /F
setlocal
set REPO=C:\Users\homee\projects\binance-hack-dossier
set PY=C:\Users\homee\miniconda3\python.exe
set NODE=C:\Program Files\nodejs\node.exe
set GIT=C:\Program Files\Git\cmd\git.exe
set LOG=%REPO%\logs\refresh.log

if not exist "%REPO%\logs" mkdir "%REPO%\logs"
echo [%DATE% %TIME%] start>>"%LOG%"
cd /d "%REPO%"

"%GIT%" pull --rebase --quiet
if errorlevel 1 goto pullfail

"%PY%" scripts\update_feeds.py >>"%LOG%" 2>&1
if errorlevel 1 goto updatefail

"%NODE%" scripts\verify_site.js >>"%LOG%" 2>&1
if errorlevel 1 goto verifyfail

"%GIT%" add docs\index.html docs\updates.json
"%GIT%" diff --cached --quiet
if not errorlevel 1 goto nochanges

"%GIT%" -c user.name=nwfella -c user.email=nwfella@users.noreply.github.com commit -q -m "chore: hourly refresh"
"%GIT%" push --quiet
if errorlevel 1 goto retrypush
echo [%DATE% %TIME%] ok committed>>"%LOG%"
exit /b 0

:retrypush
"%GIT%" pull --rebase --quiet
if errorlevel 1 goto pullfail
"%GIT%" push --quiet
if errorlevel 1 goto pushfail
echo [%DATE% %TIME%] ok committed after retry>>"%LOG%"
exit /b 0

:pullfail
"%GIT%" rebase --abort >nul 2>&1
echo [%DATE% %TIME%] FAIL pull/rebase>>"%LOG%"
exit /b 1

:updatefail
echo [%DATE% %TIME%] FAIL update_feeds>>"%LOG%"
exit /b 1

:verifyfail
echo [%DATE% %TIME%] FAIL verify_site>>"%LOG%"
exit /b 1

:pushfail
echo [%DATE% %TIME%] FAIL push>>"%LOG%"
exit /b 1

:nochanges
echo [%DATE% %TIME%] nochange>>"%LOG%"
exit /b 0
