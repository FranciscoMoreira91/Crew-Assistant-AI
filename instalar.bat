@echo off
title Crew Assistant - Instalador

echo ==========================================
echo         Crew Assistant v2.0
echo ==========================================
echo.

python --version >nul 2>&1

if errorlevel 1 (
    echo.
    echo Python nao encontrado.
    echo.
    echo Instale o Python 3.11 ou superior.
    echo https://www.python.org/downloads/
    pause
    exit
)

echo Python encontrado.
echo.

if not exist venv (

    echo A criar ambiente virtual...
    python -m venv venv

)

call venv\Scripts\activate

echo.
echo A atualizar pip...
python -m pip install --upgrade pip

echo.
echo A instalar dependencias...
pip install -r requirements.txt

if not exist .env (

    echo.
    echo A criar ficheiro .env...
    copy .env.example .env

)

if not exist imagens mkdir imagens
if not exist videos mkdir videos
if not exist uploads mkdir uploads

echo.
echo ==========================================
echo Instalacao concluida com sucesso.
echo ==========================================
echo.

python app.py

pause