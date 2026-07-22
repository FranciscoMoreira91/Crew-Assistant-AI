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

REM --- Copia o .env (correção issue #2: nunca sobrescrever um .env --- 
REM --- ja existente, para nao apagar configuracoes/tokens do utilizador ---
REM --- numa reinstalacao) ---
if exist .env (
    echo [OK] Ja existe um ficheiro .env - mantido sem alteracoes.
) else (
    echo A criar ficheiro .env a partir do modelo...
    copy .env.example .env
)
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
echo.

REM --- Abre o browser passado alguns segundos, para dar tempo ao servidor arrancar ---
start "" cmd /c "timeout /t 5 /nobreak >nul && start http://127.0.0.1:5000"

REM --- Lanca o app.py sem janela de consola visivel ---
wscript.exe "%~dp0iniciar_oculto.vbs"

echo A app foi iniciada em segundo plano.
echo Para voltar a abrir a app no futuro, usa o ficheiro iniciar.bat
echo.
pause
endlocal
