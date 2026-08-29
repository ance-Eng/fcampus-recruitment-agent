@echo off
echo ========================================
echo   校园招聘智能筛选 - 启动脚本
echo ========================================
echo.

echo [1/2] 启动 FastAPI 后端服务 (端口 8000)...
start "FastAPI Backend" cmd /k "cd /d %~dp0 && uvicorn backend.main:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

echo [2/2] 启动 Streamlit 前端 (端口 8501)...
start "Streamlit Frontend" cmd /k "cd /d %~dp0 && streamlit run app.py"

echo.
echo 启动完成！
echo   后端 API: http://localhost:8000/docs
echo   前端界面: http://localhost:8501
echo.
pause
