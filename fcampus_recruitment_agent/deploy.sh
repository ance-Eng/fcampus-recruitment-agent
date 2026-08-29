#!/bin/bash
# ============================================
# 校园实习招聘 Agent 一键部署脚本（Linux 服务器）
# 适用：Ubuntu / Debian / CentOS
# 使用：bash deploy.sh
# ============================================

set -e

PROJECT_DIR="/opt/campus_recruitment_agent"
PORT=8501

echo "========================================"
echo "  校园实习招聘 Agent 部署脚本"
echo "========================================"

# 1. 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[1/6] 安装 Python3..."
    if command -v apt-get &> /dev/null; then
        apt-get update && apt-get install -y python3 python3-pip python3-venv
    elif command -v yum &> /dev/null; then
        yum install -y python3 python3-pip
    fi
else
    echo "[1/6] Python3 已安装: $(python3 --version)"
fi

# 2. 创建项目目录
echo "[2/6] 创建项目目录..."
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# 3. 创建虚拟环境
echo "[3/6] 创建 Python 虚拟环境..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# 4. 安装依赖
echo "[4/6] 安装 Python 依赖..."
pip install --upgrade pip
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 5. 配置防火墙
echo "[5/6] 开放端口 $PORT..."
if command -v ufw &> /dev/null; then
    ufw allow $PORT/tcp || true
elif command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=$PORT/tcp || true
    firewall-cmd --reload || true
fi

# 6. 启动服务
echo "[6/6] 启动服务..."
# 先杀掉旧进程
pkill -f "streamlit run app.py" || true

nohup venv/bin/streamlit run app.py \
    --server.address=0.0.0.0 \
    --server.port=$PORT \
    --server.headless=true \
    > /var/log/campus_agent.log 2>&1 &

echo ""
echo "========================================"
echo "  部署完成！"
echo "  访问地址: http://$(curl -s ifconfig.me 2>/dev/null || echo '你的服务器IP'):$PORT"
echo "  日志文件: /var/log/campus_agent.log"
echo "  停止服务: pkill -f 'streamlit run app.py'"
echo "========================================"
