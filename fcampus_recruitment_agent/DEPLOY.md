# 部署指南 — GitHub + Streamlit Cloud 免费部署

## 一、准备工作

1. 注册 GitHub：https://github.com
2. 注册 Streamlit Cloud：https://share.streamlit.io（用 GitHub 账号登录）
3. （可选）注册 Upstash 免费 Redis：https://upstash.com

---

## 二、上传代码到 GitHub

1. 在 GitHub 新建仓库，名字如 `campus-recruitment-agent`，选 Public
2. 把项目所有文件上传到仓库（可以直接网页拖拽上传，或用 git）

```bash
# 用 git 的方式（可选）
cd campus_recruitment_agent
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/你的用户名/campus-recruitment-agent.git
git push -u origin main
```

---

## 三、在 Streamlit Cloud 部署

1. 打开 https://share.streamlit.io
2. 点 "New app"
3. 选择你的 GitHub 仓库
4. Branch 选 `main`
5. Main file path 填 `app.py`
6. 点 "Advanced settings"（高级设置）
7. 在 Secrets 里填入大模型 API（见下方）
8. 点 "Deploy!"

等待 2-5 分钟，部署成功后得到网址，如 `https://xxx.streamlit.app`

---

## 四、配置 Secrets（必须）

在 Streamlit Cloud 的 App 设置 → Secrets 里填写：

```toml
# 大模型 API（必填）
API_KEY = "sk-你的key"
BASE_URL = "https://api.deepseek.com/v1"
MODEL = "deepseek-chat"
```

> 也可以用 Kimi、通义千问、OpenAI 等，改上面三个值即可。

配置后，打开网页侧边栏会自动填入 API Key，用户不需要手动输入。

---

## 五、配置 Redis（可选，推荐）

Streamlit Cloud 实例重启后内存缓存会清空，用 Redis 可以持久化缓存、节省 token。

### 5.1 注册免费 Redis

1. 打开 https://upstash.com，用 GitHub 登录
2. 点 "Create Database"，选 Redis，地区选就近的（如 Singapore）
3. 创建后复制 Endpoint（含密码的完整 URL），格式如：
   `redis://:password@xxx.upstash.io:6379`

### 5.2 在 Streamlit Secrets 里添加

```toml
# 大模型 API
API_KEY = "sk-你的key"
BASE_URL = "https://api.deepseek.com/v1"
MODEL = "deepseek-chat"

# Redis 缓存
REDIS_URL = "redis://:password@xxx.upstash.io:6379"
CACHE_BACKEND = "redis"
```

配置后侧边栏会显示"缓存后端：redis"，说明连接成功。

> 不配 Redis 也能用，自动降级为内存缓存，只是实例重启后缓存清空。

---

## 六、本地运行

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
streamlit run app.py
```

本地不需要 Redis，自动用内存缓存。

---

## 七、常见问题

**Q: 部署失败？**
A: 查看部署日志，通常是依赖问题。确认 requirements.txt 里的包都能安装。

**Q: 打开网址空白？**
A: 查看 App 日志，可能是代码报错。本地能跑通的话，云端一般也能跑通。

**Q: 想改网址名字？**
A: Streamlit Cloud 设置里可以自定义子域名。

**Q: API Key 安全吗？**
A: Secrets 存在 Streamlit 服务端，不会暴露在前端代码里。

**Q: 免费额度够吗？**
A: Streamlit Cloud 免费版适合小范围使用（几十人同时访问）。Upstash 免费版每月 10000 次请求，够用。

---

## 八、服务器部署（Nginx + FastAPI + Streamlit）

适合有自己服务器（阿里云/腾讯云/华为云等），想给朋友用域名访问的场景。

### 8.1 环境要求
- 服务器：2核4G以上，Ubuntu 22.04 / CentOS 7+
- Python 3.10+
- 域名（可选，没有就用 IP）

### 8.2 安装依赖
```bash
# 安装 Python 依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 安装 Nginx
sudo apt install nginx -y  # Ubuntu
# 或 sudo yum install nginx -y  # CentOS
```

### 8.3 配置 Nginx
```bash
# 复制配置文件
sudo cp nginx.conf /etc/nginx/conf.d/campus_recruitment.conf

# 修改 server_name 为你的域名或服务器IP
sudo vi /etc/nginx/conf.d/campus_recruitment.conf

# 测试配置
sudo nginx -t

# 重载 Nginx
sudo systemctl reload nginx
```

### 8.4 启动服务
```bash
# 方式一：用启动脚本
chmod +x start.sh
./start.sh

# 方式二：手动启动（推荐用 nohup 后台运行）
nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
nohup streamlit run app.py --server.port 8501 > frontend.log 2>&1 &
```

### 8.5 访问
- 前端：`http://你的域名或IP`（Nginx 自动转发到 8501）
- API 文档：`http://你的域名或IP/docs`
- 后端直连：`http://你的域名或IP:8000`
- 前端直连：`http://你的域名或IP:8501`

### 8.6 配置 HTTPS（推荐）
用免费的 Let's Encrypt 证书：
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d 你的域名
```
证书自动续期，浏览器显示安全锁。

---

## 九、Docker Compose 一键部署（推荐）

最简单的部署方式，一条命令启动所有服务。

### 9.1 安装 Docker
```bash
# Ubuntu
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER
# 重新登录后生效
```

### 9.2 配置环境变量
```bash
cp .env.example .env
vi .env  # 填入 API_KEY 等
```

### 9.3 启动
```bash
docker-compose up -d
```

### 9.4 访问
- 前端：`http://localhost` 或 `http://服务器IP`
- API 文档：`http://localhost/docs`
- 后端：`http://localhost:8000`
- 前端：`http://localhost:8501`
- Redis：`http://localhost:6379`

### 9.5 常用命令
```bash
docker-compose ps          # 查看状态
docker-compose logs -f     # 查看日志
docker-compose down        # 停止
docker-compose restart     # 重启
docker-compose pull        # 更新镜像
```

---

## 十、部署架构对比

| 方式 | 难度 | 成本 | 适合场景 |
|------|------|------|----------|
| Streamlit Cloud | 简单 | 免费 | 个人演示、小范围试用 |
| 服务器 + Nginx | 中等 | 服务器费用 | 给朋友用、有域名 |
| Docker Compose | 中等 | 服务器费用 | 快速部署、易维护 |
| 服务器 + Nginx + HTTPS | 中等 | 服务器费用 | 正式对外使用 |
