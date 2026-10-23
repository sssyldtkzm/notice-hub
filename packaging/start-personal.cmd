@echo off
cd /d "%~dp0"
if not exist ".env" copy ".env.example" ".env" >nul
echo Open http://127.0.0.1:8766 and configure your own connection.
echo Keep this window open while using Notice Hub.
"%~dp0qq-live-digest-personal.exe" --env "%~dp0.env" run
pause
