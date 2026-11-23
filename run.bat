
@echo off
title Project Launcher

echo Starting FastAPI backend...

:: Open FastAPI in a new terminal
start "FastAPI Backend" cmd /k "uvicorn main_2:app --reload --host 127.0.0.1 --port 8000"

echo Waiting for FastAPI to become ready...

:: Wait until FastAPI responds successfully
:WAIT_API
timeout /t 2 /nobreak >nul
curl -s -f http://127.0.0.1:8000/openapi.json >nul

if errorlevel 1 (
    echo FastAPI is not ready yet...
    goto WAIT_API
)

echo FastAPI is ready!
echo Starting Streamlit frontend...

:: Open Streamlit in a separate terminal
start "Streamlit Frontend" cmd /k "streamlit run streamlit_app_2.py"

echo Both services started successfully!
exit
