@echo off
setlocal enabledelayedexpansion
title Crew-Assistant-AI - Instalacao Limpa
color 0B

echo ============================================
echo         🚀Crew Assistant  v2.0.0
echo ============================================
echo.

REM --- Verifica se o Python esta instalado e no PATH ---
where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao encontrado no PATH.
    echo Instala o Python de https://www.python.org/downloads/
    echo e marca a opcao "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

echo [OK] Python encontrado:
python --version
echo.

REM --- Remove ambiente virtual anterior, se existir ---
if exist venv (
    echo A remover ambiente virtual anterior...
    rmdir /s /q venv
    echo [OK] Ambiente anterior removido.
    echo.
)

REM --- Cria novo ambiente virtual ---
echo A criar novo ambiente virtual...
python -m venv venv
if errorlevel 1 (
    echo [ERRO] Falha ao criar o ambiente virtual.
    pause
    exit /b 1
)
echo [OK] Ambiente virtual criado.
echo.

REM --- Ativa o ambiente virtual ---
call venv\Scripts\activate.bat

REM --- Atualiza o pip ---
echo A atualizar o pip...
python -m pip install --upgrade pip
echo.

REM --- Instala primeiro o tokenizers numa versao com wheel pronta, ---
REM --- para o litellm nao tentar compilar via Rust ---
echo A preparar dependencias base (evitar build via Rust)...
pip install "tokenizers>=0.20,<1.0"
echo.

REM --- Instala as dependencias ---
echo A instalar dependencias...
echo.

if exist requirements.txt (
    pip install -r requirements.txt
) else (
    echo [AVISO] requirements.txt nao encontrado. A instalar lista fixa...
    pip install "crewai>=1.15.0,<2.0.0" flask==3.0.3 flask-cors==4.0.1 python-dotenv==1.0.1 litellm requests pytesseract Pillow pypdf huggingface_hub replicate openpyxl python-docx python-pptx
)

if errorlevel 1 (
    echo.
    echo [ERRO] Ocorreu um problema durante a instalacao das dependencias.
    echo Verifica as mensagens acima.
    pause
    exit /b 1
)

REM --- Copia o .env ---
echo A criar ficheiro .env...
copy .env.example .env
echo.

REM --- Gera automaticamente o desinstalar.bat ---
echo A gerar ficheiro desinstalar.bat...
(
echo @echo off
echo setlocal enabledelayedexpansion
echo title Crew-Assistant-AI - Desinstalacao
echo color 0C
echo.
echo echo ============================================
echo echo         Crew-Assistant-AI - Desinstalar
echo echo ============================================
echo echo.
echo echo Isto vai remover o ambiente virtual ^(venv^) e os ficheiros temporarios.
echo set /p CONFIRMA="Tens a certeza que queres desinstalar? ^(S/N^): "
echo if /i not "%%CONFIRMA%%"=="S" ^(
echo     echo Operacao cancelada.
echo     pause
echo     exit /b 0
echo ^)
echo.
echo REM --- Termina processos python que possam estar a correr a partir desta pasta ---
echo taskkill /f /im python.exe ^>nul 2^>nul
echo.
echo if exist venv ^(
echo     echo A remover ambiente virtual...
echo     rmdir /s /q venv
echo     echo [OK] venv removido.
echo ^) else ^(
echo     echo [INFO] Nao existe venv para remover.
echo ^)
echo.
echo if exist __pycache__ rmdir /s /q __pycache__
echo for /d /r %%%%d in ^(__pycache__^) do @if exist "%%%%d" rmdir /s /q "%%%%d"
echo.
echo set /p APAGAENV="Queres tambem apagar o ficheiro .env com as tuas chaves/configuracoes? ^(S/N^): "
echo if /i "%%APAGAENV%%"=="S" ^(
echo     if exist .env del /q .env
echo     echo [OK] .env removido.
echo ^)
echo.
echo echo ============================================
echo echo   Desinstalacao concluida.
echo echo   Os ficheiros do programa ^(app.py, etc.^) mantiveram-se.
echo echo   Podes apagar a pasta manualmente se ja nao precisares.
echo echo ============================================
echo echo.
echo pause
echo endlocal
) > desinstalar.bat
echo [OK] desinstalar.bat criado.
echo.

echo.
echo ============================================
echo   Instalacao concluida com sucesso!
echo ============================================
echo.

REM --- Verifica se existe ficheiro .env ---
if not exist .env (
    echo [AVISO] Nao foi encontrado ficheiro .env
    echo Certifica-te de que criar/copiar o .env com as configuracoes
    echo (chaves Gmail, Replicate, etc.) antes de iniciar a app.
    echo.
)

REM --- Lembrete sobre o Ollama ---
echo [LEMBRETE] Confirma que o Ollama esta instalado e que o modelo
echo esta disponivel, correndo por exemplo: ollama pull qwen2.5
echo.

echo A iniciar o Crew-Assistant-AI (sem janela de consola)...
echo O browser vai abrir automaticamente assim que o servidor estiver pronto.
echo.

REM --- Lanca o app.py sem janela de consola visivel ---
REM --- (o iniciar_oculto.vbs espera o servidor responder antes de abrir o browser) ---
wscript.exe "%~dp0iniciar_oculto.vbs"

echo A app foi iniciada em segundo plano.
echo Para voltar a abrir a app no futuro, usa o ficheiro iniciar.bat
echo Para desinstalar, usa o ficheiro desinstalar.bat que foi criado nesta pasta.
echo.
pause
endlocal
