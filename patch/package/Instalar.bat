@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Gerenciar.ps1" -Action Install
pause
