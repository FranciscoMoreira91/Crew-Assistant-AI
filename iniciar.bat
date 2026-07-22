@echo off
title Crew-Assistant-AI
color 0B

REM ------------------------------------------------------------------
REM iniciar.bat (correção issue #9)
REM Ficheiro em falta na v2.1.0 mas já referido pelo instalar.bat no
REM fim da instalação ("Para voltar a abrir a app no futuro, usa o
REM ficheiro iniciar.bat"). Apenas relança a app sem janela de consola
REM visível, através do mesmo script iniciar_oculto.vbs.
REM ------------------------------------------------------------------

if not exist "%~dp0venv\Scripts\pythonw.exe" (
    echo [ERRO] Nao foi encontrado o ambiente virtual ^(venv^).
    echo Corre primeiro o instalar.bat.
    echo.
    pause
    exit /b 1
)

echo A iniciar o Crew-Assistant-AI...
wscript.exe "%~dp0iniciar_oculto.vbs"

echo A app foi iniciada em segundo plano. Esta janela pode ser fechada.
timeout /t 3 /nobreak >nul
