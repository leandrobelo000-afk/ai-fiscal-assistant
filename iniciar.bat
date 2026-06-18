@echo off
title AI Fiscal Assistant - Iniciador
echo ===================================================
echo       Iniciando o AI Fiscal Assistant...
echo ===================================================
echo.

:: 1. Liga o servidor do LM Studio em uma janela separada
echo [*] Ligando o motor de Inteligencia Artificial (LM Studio)...
start "Servidor LM Studio" cmd /k "lms server start"

timeout /t 5 /nobreak > nul

:: 2. Verifica se o ambiente virtual (.venv) existe. Se nao, cria.
if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo [!] Ambiente virtual nao encontrado. Criando um novo ^(isso pode demorar um pouco^)...
    python -m venv .venv
)

:: 3. Ativa o ambiente virtual
echo.
echo [*] Ativando o ambiente virtual...
call .venv\Scripts\activate.bat

:: 4. Instala/Atualiza as dependencias automaticamente
echo [*] Verificando atualizacoes e dependencias do projeto...
pip install -r requirements.txt > nul

:: 5. Inicia a interface do Streamlit
echo.
echo [*] Tudo pronto! Abrindo a interface do sistema...
echo ===================================================
streamlit run step4_interface/app.py

pause