@echo off
chcp 65001 >nul
title Licitacoes PNCP IA - Instalacao
echo ==========================================================
echo   Licitacoes PNCP IA - Instalacao em um computador novo
echo   (n8n + worker + fluxo + pastas)
echo ==========================================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar\instalar.ps1"
echo.
pause
