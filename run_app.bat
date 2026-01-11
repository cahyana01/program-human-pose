@echo off
set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    echo Using Virtual Environment...
)

echo Installing dependencies...
"%PYTHON_EXE%" -m pip install -r requirements.txt
echo Starting App...
"%PYTHON_EXE%" app.py
pause
