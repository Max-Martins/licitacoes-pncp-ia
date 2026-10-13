@echo off
set LOG=%~dp0diagnostico_worker.log
echo ==== %date% %time% ==== > "%LOG%"
docker ps -a --filter name=licitacoes-worker >> "%LOG%" 2>&1
echo ---- LOGS ---- >> "%LOG%"
docker logs --tail 80 licitacoes-worker >> "%LOG%" 2>&1
echo ---- HEALTH ---- >> "%LOG%"
curl -s -m 10 http://localhost:8765/health >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo FIM >> "%LOG%"
type "%LOG%"
echo.
pause
