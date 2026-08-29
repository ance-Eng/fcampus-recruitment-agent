# 校园实习招聘智能筛选 Agent

基于 Python + FastAPI + LangGraph + RAG 的校园招聘智能筛选系统，支持简历解析、岗位匹配、AI 面试模拟、多轮对话顾问等功能。采用前后端分离架构，FastAPI 提供 REST API，Streamlit 提供 Web 界面。

## 技术架构

```
┌─────────────────────────────────────────────────────┐
│                   Streamlit Web UI                   │
│              （前端界面，可独立运行）                  │
├─────────────────────────────────────────────────────┤
│                   FastAPI 后端服务                    │
│        （REST API，端口 8000，/docs 在线文档）         │
├──────────┬──────────┬──────────┬────────────────────┤
│ 简历解析  │ 岗位匹配  │ RAG检索  │  LangGraph Agent   │
│ (PDF/    │ (多维    │ (FAISS  │  (工作流编排/       │
│  DOCX/   │  评分)   │  向量库) │   ReAct推理)       │
│  TXT)    │          │          │                    │
├──────────┴──────────┴──────────┴────────────────────┤
│              缓存层 (Redis / 内存) + 限流             │
├─────────────────────────────────────────────────────┤
│              数据层 (SQLite + CSV + 知识库)           │
└─────────────────────────────────────────────────────┘
```

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | FastAPI | 高性能 REST API，自动生成 OpenAPI 文档 |
| Web 框架 | Streamlit | 快速构建交互式网页界面 |
| Agent 框架 | LangGraph | 工作流编排，多节点状态流转 |
| ReAct Agent | 自研 | 思考-行动-观察循环推理 |
| RAG 检索 | FAISS | 向量数据库，语义检索 |
| 大模型 | OpenAI 兼容 API | DeepSeek / Kimi / 通义千问等 |
| 缓存 | Redis / 内存 | 两级缓存，自动降级 |
| 数据库 | SQLite | 筛选记录、操作日志持久化 |
| 文档解析 | pdfplumber / python-docx | PDF/Word 简历解析 |
| 中文处理 | jieba | 中文分词 |
| 数据处理 | pandas | 岗位数据管理 |
| 导出 | openpyxl | Excel 报告导出 |

## 功能模块

### 1. 简历智能解析
- 支持 PDF / DOCX / TXT 格式简历上传
- 自动提取姓名、学历、专业、技能、项目经验、实习经历、证书、获奖、加分项（12项字段）
- 文本去重清洗

### 2. 岗位数据管理
- 内置 101 条真实招聘数据，覆盖 20 个行业
- 支持上传自定义岗位 CSV，自动去重
- 岗位分类：IT、金融、制造、医疗、教育、传媒、零售、能源、建筑等

### 3. 多维度智能筛选
- 技能匹配、学历匹配、经验/项目匹配、加分项四维加权评分
- 7 种岗位权重模板（技术/医疗/金融/教育/运营/制造/默认），支持自定义权重
- 输出匹配等级（A/B/C/D）、结论、已匹配/缺失技能、改进建议
- 支持规则引擎、LangGraph 工作流、ReAct Agent 三种筛选模式
- 低分自动推荐 Top-3 匹配岗位

### 4. RAG 知识库检索
- FAISS 向量库存储岗位资料，7 个行业知识库文档
- 支持上传/删除知识库文档，重建索引
- 相关性阈值过滤，低于阈值提示用户
- 检索增强生成，回答更精准

### 5. AI 多轮对话顾问
- 基于候选人上下文问答
- 支持提问风险点、面试考察点、是否推荐面试
- 会话状态持久化，刷新不丢失

### 6. AI 面试模拟器
- 基于简历和岗位生成个性化面试问题
- 6 类问题：自我介绍、项目经历、技术考察、能力缺口、岗位认知、职业规划
- 回答质量实时评估（得分+反馈）
- 面试结束生成总结报告

### 7. 缓存与限流
- Redis 优先，内存自动降级
- 大模型响应缓存，减少 Token 消耗
- 每分钟/每日调用次数限制，防止滥用

### 8. 筛选历史与统计
- SQLite 持久化存储筛选记录
- 侧边栏展示统计：累计次数、平均分、通过率、热门岗位、常见缺失技能
- 最近 5 条筛选记录

### 9. 报告导出
- 支持 TXT / Markdown / JSON / Excel 四种格式导出
- Excel 包含完整评分明细和改进建议

### 10. FastAPI REST API
- 14 个 API 端点，覆盖所有核心功能
- 自动生成 Swagger 在线文档（/docs）
- 支持第三方系统集成调用

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/health | 健康检查 |
| GET | /api/jobs | 岗位列表（支持按分类筛选） |
| GET | /api/jobs/categories | 岗位分类列表 |
| POST | /api/parse/resume | 解析简历文本 |
| POST | /api/parse/resume/file | 解析简历文件 |
| POST | /api/screen | 智能筛选（支持自定义权重） |
| POST | /api/chat | 多轮对话 |
| POST | /api/interview/start | 开始面试模拟 |
| POST | /api/interview/answer | 提交面试回答 |
| GET | /api/stats | 统计数据 |
| GET | /api/weights/templates | 评分权重模板 |
| POST | /api/rag/rebuild | 重建 RAG 索引 |
| GET | /api/knowledge/files | 知识库文件列表 |
| DELETE | /api/knowledge/files/{name} | 删除知识库文件 |

## 项目结构

```
campus_recruitment_agent/
├── app.py                  # 主程序入口（Streamlit 前端）
├── config.py               # 全局配置（技能库、权重、学历映射）
├── requirements.txt        # Python 依赖
├── start.bat               # Windows 一键启动（后端+前端）
├── start.sh                # Linux/Mac 一键启动
├── README.md               # 项目说明
├── DEPLOY.md               # 部署指南
├── backend/                # FastAPI 后端
│   ├── __init__.py
│   └── main.py             # REST API 服务
├── agent/                  # 核心业务模块
│   ├── __init__.py
│   ├── resume_parser.py    # 简历解析器
│   ├── job_parser.py       # 岗位解析器
│   ├── screener.py         # 多维度评分引擎
│   ├── reporter.py         # 报告生成器
│   ├── llm_client.py       # 大模型 API 客户端
│   ├── llm_enhancer.py     # 大模型增强分析
│   ├── rag_engine.py       # RAG 检索引擎
│   ├── graph_agent.py      # LangGraph 工作流 Agent
│   ├── react_agent.py      # ReAct 自主 Agent
│   ├── chat_agent.py       # 多轮对话顾问
│   ├── interview_simulator.py  # AI 面试模拟器
│   ├── cache_manager.py    # 缓存管理器（Redis/内存）
│   ├── rate_limiter.py     # 速率限制器
│   ├── database.py         # SQLite 数据库
│   └── tool_registry.py    # 工具注册表
├── utils/                  # 工具模块
│   ├── __init__.py
│   └── file_loader.py      # 文件读取工具
├── data/                   # 数据目录
│   ├── jobs.csv            # 岗位数据集（101条，20行业）
│   ├── knowledge/          # RAG 知识库文档（7个行业）
│   └── resumes/            # 示例简历
├── scripts/                # 数据脚本
│   ├── fetch_jobs.py       # 从腾讯招聘API拉取岗位
│   ├── clean_jobs.py       # 岗位数据清洗
│   └── add_non_it_jobs.py  # 补充非IT行业岗位
├── .streamlit/             # Streamlit 配置
│   ├── config.toml
│   └── secrets.toml.example  # Secrets 配置示例
├── assets/                 # 静态资源
│   └── style.css           # 自定义样式
└── output/                 # 输出目录（RAG索引缓存）
```

## 快速开始

### 环境要求
- Python 3.10+
- pip

### 安装依赖

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 方式一：一键启动（推荐）

Windows：
```bash
start.bat
```

Linux/Mac：
```bash
chmod +x start.sh
./start.sh
```

启动后访问：
- 前端界面：http://localhost:8501
- API 文档：http://localhost:8000/docs

### 方式二：仅启动前端（简单模式）

```bash
streamlit run app.py
```

前端会自动检测后端是否运行，未检测到时使用本地模式。

### 方式三：仅启动后端 API

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000/docs 查看在线 API 文档。

### 配置大模型 API

在网页侧边栏填入：
- API Key（如 DeepSeek 的 sk-xxx）
- Base URL（如 https://api.deepseek.com/v1）
- 模型名称（如 deepseek-chat）

或在 `.streamlit/secrets.toml` 中配置，启动后自动读取（推荐，更安全）。

## 部署

支持 Streamlit Cloud 免费部署，详见 [DEPLOY.md](DEPLOY.md)。

简要步骤：
1. 上传代码到 GitHub
2. 在 [share.streamlit.io](https://share.streamlit.io) 关联仓库
3. 配置 Secrets（API Key 等）
4. 部署完成，获得在线访问网址

FastAPI 后端可部署到 Render、Railway、阿里云等支持 Python 的平台。

## 数据说明

- 岗位数据来源于腾讯招聘公开 API 及各企业真实招聘公告
- 覆盖 20 个行业、46 家企业、101 个岗位（已去重）
- 数据仅供学习演示使用

## License

MIT
