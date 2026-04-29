@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════╗
echo ║   DANN — NextGen CRM Copilot          ║
echo ╚════════════════════════════════════════╝
echo.

set SCRIPT_DIR=%~dp0
set BACKEND_DIR=%SCRIPT_DIR%backend

:: ── 1. Kiểm tra Python ──────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python chưa được cài.
    echo    Tải tại: https://python.org  ^(nhớ tick "Add to PATH"^)
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo ✅ %%v

:: ── 2. Kiểm tra Ollama ──────────────────────
ollama --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ❌ Ollama chưa được cài.
    echo    Tải tại: https://ollama.com
    echo    Sau đó chạy: ollama pull llama3:8b
    pause
    exit /b 1
)
echo ✅ Ollama: installed

:: Kiểm tra Ollama server
curl -sf http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo.
    echo ⚡ Đang khởi động Ollama server...
    start /B ollama serve
    timeout /t 3 /nobreak >nul
)

:: Kiểm tra model llama3:8b
set OLLAMA_MODEL=llama3:8b
ollama list 2>nul | findstr /i "llama3" >nul
if errorlevel 1 (
    echo.
    echo 📥 Đang pull model %OLLAMA_MODEL% ^(lần đầu mất vài phút^)...
    ollama pull %OLLAMA_MODEL%
)
echo ✅ Model: %OLLAMA_MODEL%

:: ── 3. Tạo .env nếu chưa có ────────────────
cd /d "%BACKEND_DIR%"

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo.
    echo 📝 Đã tạo backend\.env từ .env.example
    echo    → Kiểm tra DATABASE_URL nếu cần chỉnh
)
echo ✅ .env: OK

:: ── 4. Tạo virtual environment ─────────────
if not exist ".venv" (
    echo.
    echo 📦 Tạo virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
echo ✅ Virtualenv: active

:: ── 5. Cài dependencies ─────────────────────
echo.
echo 📥 Cài Python packages...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
echo ✅ Dependencies: installed

:: ── 6. Kiểm tra PostgreSQL ──────────────────
echo.
python -c "
import asyncio, sys

async def check():
    try:
        import asyncpg
        # Đọc DATABASE_URL từ .env
        url = ''
        with open('.env') as f:
            for line in f:
                line = line.strip()
                if line.startswith('DATABASE_URL='):
                    url = line.split('=', 1)[1].strip()
                    break
        if not url:
            print('❌ Không tìm thấy DATABASE_URL trong .env')
            sys.exit(1)
        url = url.replace('postgresql+asyncpg://', '')
        user_pass, rest = url.split('@')
        user, password = user_pass.split(':')
        host_port, dbname = rest.split('/')
        parts = host_port.split(':')
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 5432
        conn = await asyncpg.connect(host=host, port=port, user=user, password=password, database=dbname, timeout=5)
        await conn.close()
        print('✅ PostgreSQL: kết nối OK')
    except Exception as e:
        print(f'❌ PostgreSQL lỗi: {e}')
        print('   Kiểm tra PostgreSQL đang chạy và DATABASE_URL trong backend\\.env')
        sys.exit(1)

asyncio.run(check())
"
if errorlevel 1 (
    pause
    exit /b 1
)

:: ── 7. Khởi động server ─────────────────────
echo.
echo ╔════════════════════════════════════════╗
echo ║  🚀 DANN đang khởi động...            ║
echo ║                                       ║
echo ║  Frontend : http://localhost:8000     ║
echo ║  API Docs : http://localhost:8000/docs║
echo ╚════════════════════════════════════════╝
echo.
echo   Nhấn Ctrl+C để dừng
echo.

cd /d "%BACKEND_DIR%\api"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-dir "%BACKEND_DIR%"

pause