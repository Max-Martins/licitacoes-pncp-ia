@echo off
chcp 65001 >nul
title Licitacoes PNCP IA - Exportar para outro computador
echo ==========================================================
echo   Licitacoes PNCP IA - Exportar fluxo, credenciais e dados
echo   Rode no computador ANTIGO. Leve a pasta MIGRACAO gerada
echo   para o computador novo (pen drive / OneDrive).
echo ==========================================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar\exportar.ps1"
echo.
pause
