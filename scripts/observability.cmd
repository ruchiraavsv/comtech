@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0observability.ps1" %*
exit /b %ERRORLEVEL%
