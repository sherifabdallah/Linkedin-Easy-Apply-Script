@echo off
chcp 65001 >nul
cls
echo ========================================
echo LinkedIn AI Job Application Agent
echo ========================================
echo.

REM Check if Ollama is installed
where ollama >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Ollama not found!
    echo Please install Ollama from: https://ollama.ai/download
    echo.
    pause
    exit /b 1
)

echo [1/5] Checking Ollama status...
echo.

REM Check if Ollama is running
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if %ERRORLEVEL% EQU 0 (
    echo [OK] Ollama is already running
) else (
    echo [INFO] Starting Ollama server...
    start "Ollama Server" /MIN ollama serve
    timeout /t 5 /nobreak >nul
    echo [OK] Ollama server started
)

echo.
echo [2/5] Checking if llama3 model is available...
ollama list | find "llama3" >nul
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Llama3 model not found. Downloading...
    echo This may take several minutes (about 4GB)...
    ollama pull llama3
) else (
    echo [OK] Llama3 model is ready
)

echo.
echo [3/5] Warming up Ollama (loading model into memory)...
echo This is important for first run - please wait...
ollama run llama3 "test" >nul 2>&1
timeout /t 5 /nobreak >nul
echo [OK] Ollama warmed up

echo.
echo [4/5] Testing Ollama connection...
timeout /t 2 /nobreak >nul

REM Test with curl if available
curl --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    curl -s --max-time 5 http://localhost:11434/api/tags >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo [OK] Ollama is responding
    ) else (
        echo [WARNING] Ollama may still be loading...
        echo Waiting 10 more seconds...
        timeout /t 10 /nobreak >nul
    )
) else (
    echo [INFO] Curl not found, skipping connection test
    echo Waiting 10 seconds for Ollama to be ready...
    timeout /t 10 /nobreak >nul
)

echo.
echo [5/5] Starting LinkedIn Job Agent...
echo.
echo ========================================
echo.

REM Set UTF-8 encoding for Python
set PYTHONIOENCODING=utf-8

python main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo [ERROR] Application exited with error
    echo Check the logs above for details
    echo ========================================
    echo.
    echo Common fixes:
    echo 1. Make sure .env file exists with LinkedIn credentials
    echo 2. Make sure profile.txt exists with your info
    echo 3. Check job_agent.log for detailed errors
    echo 4. Try running: ollama run llama3 "hello" first
)

echo.
pause