@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -m venv .venv
  call .venv\Scripts\activate
  python -m pip install --upgrade pip
  pip install -r backend\requirements.txt
) else (
  call .venv\Scripts\activate
)
if not exist ".env" copy backend\env.example .env
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
pause
