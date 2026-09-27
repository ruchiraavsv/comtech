@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0compose.ps1" %*
exit /b %ERRORLEVEL%
