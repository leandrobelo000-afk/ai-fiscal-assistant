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

:: 1b. Usa o Python mais novo instalado (lancador "py"), ou o "python" do PATH.
set "PYTHON=python"
where py > nul 2>&1 && set "PYTHON=py -3"

:: 2a. Se o .venv aponta para um Python que nao existe mais (Python atualizado ou
:: reinstalado), apaga para ser recriado com o Python atual.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" --version > nul 2>&1
    if errorlevel 1 (
        echo.
        echo [!] Ambiente virtual antigo detectado. Recriando com o Python atual...
        rmdir /s /q .venv
    )
)

:: 2. Verifica se o ambiente virtual (.venv) existe. Se nao, cria.
if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo [!] Ambiente virtual nao encontrado. Criando um novo ^(isso pode demorar um pouco^)...
    %PYTHON% -m venv .venv
)

:: 3. Ativa o ambiente virtual
echo.
echo [*] Ativando o ambiente virtual...
call .venv\Scripts\activate.bat

:: 4. Instala/Atualiza as dependencias automaticamente
echo [*] Verificando atualizacoes e dependencias do projeto...
python -m pip install --upgrade pip > nul
pip install -r requirements.txt > nul

:: 5. Inicia a interface do Streamlit
echo.
echo [*] Tudo pronto! Abrindo a interface do sistema...
echo ===================================================
streamlit run step5_dashboard/app.py

pause