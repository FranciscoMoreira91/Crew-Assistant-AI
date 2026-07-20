@echo off
title Crew-Assistant-AI
color 0B

echo ============================================
echo         Crew-Assistant-AI
echo ============================================
echo.

if not exist venv (
    echo [ERRO] Nao foi encontrado o ambiente virtual ^(venv^).
    echo Corre primeiro o instalar.bat.
    echo.
    pause
    exit /b 1
)

echo A iniciar o Crew-Assistant-AI ^(sem janela de consola^)...
echo O browser vai abrir automaticamente assim que o servidor estiver pronto.
echo.

wscript.exe "%~dp0iniciar_oculto.vbs"

echo A app foi iniciada em segundo plano.
echo Podes fechar esta janela.
echo.
pause
