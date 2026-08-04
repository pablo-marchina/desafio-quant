@echo off
set PYTHONPATH=%~dp0src
cd /d "%~dp0"
"C:\Users\Inteli\Desktop\Ligas\InteliAcademy\ProjetoNvidia\InteliAcademy-ProjetoNvidia\venv\Scripts\python.exe" -m uvicorn radar.api.app:app --host 0.0.0.0 --port 8000
