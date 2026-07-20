@echo off
:: Muda para a letra da unidade de disco (caso não estejas em C:)
cd /c "%~dp0"

:: Executa o comando python
python app.py

:: Mantém a janela aberta caso ocorra um erro
pause