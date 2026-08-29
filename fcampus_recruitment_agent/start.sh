#!/bin/bash
echo "========================================"
echo "  校园招聘智能筛选 - 启动脚本"
echo "========================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "[1/2] 启动 FastAPI 后端服务 (端口 8000)..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

sleep 3

echo "[2/2] 启动 Streamlit 前端 (端口 8501)..."
streamlit run app.py &
FRONTEND_PID=$!

echo ""
echo "启动完成！"
echo "  后端 API: http://localhost:8000/docs"
echo "  前端界面: http://localhost:8501"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
