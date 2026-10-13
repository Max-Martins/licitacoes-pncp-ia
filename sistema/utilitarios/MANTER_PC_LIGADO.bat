@echo off
chcp 65001 >nul
echo ==========================================================
echo  Licitacoes PNCP IA - Manter o notebook sempre ligado
echo  Tela, suspensao e hibernacao: NUNCA (na tomada e na bateria)
echo  Fechar a tampa: NAO FAZER NADA (na tomada)
echo ==========================================================
powercfg /change monitor-timeout-ac 0
powercfg /change monitor-timeout-dc 0
powercfg /change standby-timeout-ac 0
powercfg /change standby-timeout-dc 0
powercfg /change hibernate-timeout-ac 0
powercfg /change hibernate-timeout-dc 0
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setactive SCHEME_CURRENT
echo.
echo Configuracao aplicada. Conferencia:
powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE | findstr /i "Atual Current"
echo.
echo (valor 0x00000000 = nunca)
echo %date% %time% - energia configurada > "%~dp0energia_configurada.log"
powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE >> "%~dp0energia_configurada.log"
pause
