# -*- coding: utf-8 -*-
"""
校园实习招聘 Agent 智能筛选助手 — Streamlit 网页入口
运行方式：streamlit run app.py
技术架构：规则引擎 + RAG 检索增强 + LangGraph 工作流 + 大模型 API + Redis缓存 + 多轮对话
"""
import os
import sys
import uuid
import traceback
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from agent import (
    ResumeParser, JobParser, Screener, Reporter,
    LLMClient, LLMEnhancer, RAGEngine, RecruitmentAgent,
    CacheManager, ChatAgent, ToolRegistry, ReActAgent, RateLimiter,
    InterviewSimulator, database,
)
from utils import FileLoader
from config import LLM_PROVIDERS, DEFAULT_LLM_PROVIDER, REDIS_CONFIG, WEIGHT_TEMPLATES

# ========== 页面配置 ==========
st.set_page_config(
    page_title="校园招聘智能筛选",
    page_icon="📋",
    layout="wide",
)

# ========== 加载自定义样式 ==========
def load_css():
    css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# ========== 全局异常处理 ==========
def safe_execute(func, error_msg="操作失败", default=None):
    """安全执行函数，捕获异常并显示友好提示"""
    try:
        return func()
    except Exception as e:
        st.error(f"{error_msg}：{str(e)}")
        return default

# ========== Excel 导出 ==========
def to_excel(df: pd.DataFrame) -> bytes:
    """DataFrame 转 Excel 字节流"""
    import io
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="筛选结果")
    return output.getvalue()

# 得分进度条组件
def score_bar(label, score, max_score=100, color="#1a56db"):
    pct = min(score / max_score * 100, 100)
    st.markdown(f"""
    <div style="margin-bottom:12px;">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span style="font-size:14px;color:#475569;font-weight:500;">{label}</span>
            <span style="font-size:14px;color:#1e293b;font-weight:700;">{score}/{max_score}</span>
        </div>
        <div style="background:#e2e8f0;border-radius:6px;height:10px;overflow:hidden;">
            <div style="background:{color};width:{pct}%;height:100%;border-radius:6px;transition:width 0.5s;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ========== 初始化基础 Agent ==========
@st.cache_resource
def get_agents():
    return ResumeParser(), JobParser(), Screener(), Reporter()

resume_parser, job_parser, screener, reporter = get_agents()

# ========== 初始化 RAG 引擎 ==========
@st.cache_resource
def get_rag_engine():
    rag = RAGEngine()
    status = rag.initialize()
    return rag, status

rag_engine, rag_status = get_rag_engine()

# ========== 初始化缓存管理器 ==========
@st.cache_resource
def get_cache():
    # 默认用内存缓存，启动快；配置了 Redis URL 时才自动启用
    use_redis = bool(REDIS_CONFIG.get("url", ""))
    return CacheManager(
        redis_host=REDIS_CONFIG["host"],
        redis_port=REDIS_CONFIG["port"],
        redis_db=REDIS_CONFIG["db"],
        redis_url=REDIS_CONFIG.get("url", ""),
        redis_password=REDIS_CONFIG.get("password", ""),
        default_ttl=REDIS_CONFIG["default_ttl"],
        use_redis=use_redis,
    )

cache = get_cache()

# ========== 速率限制器（防滥用、省token）==========
rate_limiter = RateLimiter(cache, max_per_minute=10, max_per_day=100)

# 用户标识（用 session_id 区分不同用户）
if "user_id" not in st.session_state:
    st.session_state["user_id"] = str(uuid.uuid4())[:8]
user_id = st.session_state["user_id"]

# ========== 对话 Agent（不缓存，因为依赖 llm_client 状态）==========
def get_chat_agent(llm_client):
    return ChatAgent(llm_client=llm_client, rag_engine=rag_engine, cache=cache)

# ========== 预创建 LLM 客户端（必须在侧边栏之前，侧边栏 ReAct 区域会用到）==========
llm_provider = st.session_state.get("llm_provider", DEFAULT_LLM_PROVIDER)
llm_client = LLMClient(
    api_key=st.session_state.get("api_key", ""),
    base_url=st.session_state.get("base_url", ""),
    model=st.session_state.get("model", ""),
    provider=llm_provider,
)
chat_agent = get_chat_agent(llm_client)

# ========== 侧边栏 ==========
with st.sidebar:
    st.header("设置")

    # API 后端状态检测
    api_url = os.environ.get("API_URL", "http://localhost:8000")
    try:
        import requests as req
        resp = req.get(f"{api_url}/api/health", timeout=2)
        if resp.status_code == 200:
            health = resp.json()
            st.success(f"后端服务已连接（{health.get('version', '')}）")
            st.caption(f"API: {api_url}")
            st.session_state["api_available"] = True
        else:
            st.caption("后端服务未启动，使用本地模式")
            st.session_state["api_available"] = False
    except Exception:
        st.caption("后端服务未启动，使用本地模式")
        st.session_state["api_available"] = False

    mode = st.radio("功能模式", ["单个简历筛选", "批量简历筛选"])

    st.divider()
    st.subheader("岗位数据")
    default_jobs_path = os.path.join("data", "jobs.csv")
    if os.path.exists(default_jobs_path):
        jobs_df = pd.read_csv(default_jobs_path)
    else:
        jobs_df = pd.DataFrame()
        st.warning("未找到 data/jobs.csv")

    uploaded_jobs = st.file_uploader("上传岗位 CSV（可选）", type=["csv"])
    if uploaded_jobs is not None:
        jobs_df = pd.read_csv(uploaded_jobs)

    # 按岗位名称去重，避免下拉框出现重复岗位
    if not jobs_df.empty and "岗位名称" in jobs_df.columns:
        before = len(jobs_df)
        jobs_df = jobs_df.drop_duplicates(subset=["岗位名称"], keep="first").reset_index(drop=True)
        after = len(jobs_df)
        if before > after:
            st.caption(f"已自动去除 {before - after} 条重复岗位")
    if not jobs_df.empty:
        st.caption(f"当前共 {len(jobs_df)} 个岗位")

    # ========== RAG 配置 ==========
    st.divider()
    st.subheader("知识库")
    rag_info = rag_engine.backend_info()
    st.caption(f"文本块数：{rag_info['chunk_count']}")
    if rag_status["status"] in ("built", "loaded"):
        st.caption("索引已就绪")
    else:
        st.warning(rag_status["message"])

    # 知识库文档管理
    knowledge_dir = os.path.join("data", "knowledge")
    if os.path.exists(knowledge_dir):
        kb_files = [f for f in os.listdir(knowledge_dir) if f.endswith(('.md', '.txt'))]
        if kb_files:
            with st.expander(f"文档列表（{len(kb_files)}篇）", expanded=False):
                for kb_file in kb_files:
                    fpath = os.path.join(knowledge_dir, kb_file)
                    fsize = os.path.getsize(fpath)
                    col_f1, col_f2 = st.columns([4, 1])
                    with col_f1:
                        st.caption(f"📄 {kb_file}（{fsize//1024}KB）")
                    with col_f2:
                        if st.button("删除", key=f"del_{kb_file}"):
                            os.remove(fpath)
                            st.success(f"已删除 {kb_file}，请重建索引")
                            st.rerun()

    uploaded_kb = st.file_uploader("上传知识文档", type=["md", "txt"], key="kb_upload")
    if uploaded_kb is not None:
        save_path = os.path.join(knowledge_dir, uploaded_kb.name)
        os.makedirs(knowledge_dir, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(uploaded_kb.getbuffer())
        st.success(f"已上传 {uploaded_kb.name}，请重建索引")

    if st.button("重建知识库索引", use_container_width=True):
        try:
            rag_status_new = rag_engine.initialize(force_rebuild=True)
            get_rag_engine.clear()
            st.success("索引重建完成")
            st.rerun()
        except Exception as e:
            st.error(f"重建失败：{str(e)}")

    use_rag = st.checkbox("启用 RAG 检索增强", value=True)

    # ========== 缓存状态 ==========
    st.divider()
    st.subheader("缓存状态")
    cache_stats = cache.stats()
    st.caption(f"缓存后端：{cache_stats['backend']}")
    st.caption(f"缓存条数：{cache_stats.get('keys', 'unknown')}")
    if cache_stats["backend"] == "redis":
        st.caption(f"Redis 内存：{cache_stats.get('memory_used', 'unknown')}")
    else:
        st.caption("（未检测到 Redis，使用内存缓存）")

    # 速率限制显示
    usage = rate_limiter.get_usage(user_id)
    st.caption(f"今日调用：{usage['day_used']}/{usage['day_limit']}")
    st.caption(f"本分钟调用：{usage['minute_used']}/{usage['minute_limit']}")

    if st.button("清空缓存", use_container_width=True):
        count = cache.clear()
        st.success(f"已清空 {count} 条缓存")
        st.rerun()

    # ========== 筛选历史与统计 ==========
    st.divider()
    st.subheader("筛选统计")
    try:
        record_count = database.get_record_count()
        recent = database.get_recent_records(50)
        if recent:
            avg_score = sum(r["total_score"] for r in recent) / len(recent)
            pass_count = sum(1 for r in recent if r["total_score"] >= 60)
            pass_rate = pass_count / len(recent) * 100
            # 热门岗位
            job_counts = {}
            for r in recent:
                jt = r.get("job_title", "未知")
                job_counts[jt] = job_counts.get(jt, 0) + 1
            top_job = max(job_counts, key=job_counts.get) if job_counts else "无"
            # 常见缺失技能
            all_missing = []
            for r in recent:
                try:
                    missing = eval(r.get("missing_skills", "[]")) if isinstance(r.get("missing_skills"), str) else r.get("missing_skills", [])
                    all_missing.extend(missing)
                except Exception:
                    pass
            missing_counts = {}
            for s in all_missing:
                missing_counts[s] = missing_counts.get(s, 0) + 1
            top_missing = sorted(missing_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            top_missing_str = ", ".join([f"{s}({c}次)" for s, c in top_missing]) if top_missing else "无"

            stat_cols = st.columns(2)
            with stat_cols[0]:
                st.metric("累计筛选", f"{record_count}次")
                st.metric("平均分", f"{avg_score:.1f}")
            with stat_cols[1]:
                st.metric("通过率", f"{pass_rate:.0f}%")
                st.metric("热门岗位", top_job[:8])
            st.caption(f"常见缺失技能：{top_missing_str}")
        else:
            st.caption(f"累计筛选：{record_count} 次")
            st.caption("暂无统计数据")
        # 最近记录
        recent5 = database.get_recent_records(5)
        if recent5:
            st.caption("最近记录：")
            for r in recent5:
                st.caption(f"{r['candidate_name']} → {r['job_title']}：{r['total_score']}分")
    except Exception:
        st.caption("统计数据加载中...")

    # ========== 大模型 API 配置 ==========
    st.divider()
    st.subheader("大模型配置")


    def _get_secret(key, default=""):
        try:
            return st.secrets.get(key, default)
        except Exception:
            return default


    secrets_api_key = _get_secret("api_key")
    secrets_base_url = _get_secret("base_url")
    secrets_model = _get_secret("model")
    secrets_provider = _get_secret("provider")

    if secrets_api_key:
        # Secrets 已配置，只显示状态
        st.success("已通过安全配置连接大模型")
        st.caption(f"服务商：{secrets_provider or DEFAULT_LLM_PROVIDER}")
        st.caption(f"模型：{secrets_model or '默认'}")
        api_key = secrets_api_key
        base_url = secrets_base_url or LLM_PROVIDERS.get(secrets_provider or DEFAULT_LLM_PROVIDER, {}).get("base_url", "")
        model = secrets_model or LLM_PROVIDERS.get(secrets_provider or DEFAULT_LLM_PROVIDER, {}).get("model", "")
        llm_provider = secrets_provider or DEFAULT_LLM_PROVIDER
        st.session_state["api_key"] = api_key
        st.session_state["base_url"] = base_url
        st.session_state["model"] = model
        st.session_state["llm_provider"] = llm_provider
        use_llm = True
    else:
        # 未配置 Secrets，显示输入表单
        llm_provider = st.selectbox(
            "选择服务商",
            list(LLM_PROVIDERS.keys()),
            index=list(LLM_PROVIDERS.keys()).index(DEFAULT_LLM_PROVIDER)
            if DEFAULT_LLM_PROVIDER in LLM_PROVIDERS else 0,
        )
        st.session_state["llm_provider"] = llm_provider
        provider_config = LLM_PROVIDERS.get(llm_provider, {})

        env_api_key = os.environ.get("API_KEY", "")
        api_key = st.text_input("API Key", type="password",
                                value=st.session_state.get("api_key", env_api_key),
                                placeholder="sk-xxxxxxxx")
        base_url = st.text_input("Base URL",
                                 value=st.session_state.get("base_url", provider_config.get("base_url", "")),
                                 placeholder="https://api.deepseek.com/v1")
        model = st.text_input("模型名称",
                              value=st.session_state.get("model", provider_config.get("model", "")),
                              placeholder="deepseek-chat")

        st.session_state["api_key"] = api_key
        st.session_state["base_url"] = base_url
        st.session_state["model"] = model

        if st.button("测试连接", use_container_width=True):
            test_client = LLMClient(api_key=api_key, base_url=base_url, model=model, provider=llm_provider)
            ok, msg = test_client.test_connection()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

        use_llm = st.checkbox("启用 AI 分析", value=bool(api_key and base_url and model))

    # ========== LangGraph 状态 ==========
    st.divider()
    with st.expander("高级设置", expanded=False):
        st.subheader("筛选引擎")
        try:
            import langgraph
            try:
                from importlib.metadata import version
                lg_ver = version("langgraph")
                st.caption(f"LangGraph 已就绪 (v{lg_ver})")
            except Exception:
                st.caption("LangGraph 已就绪")
            use_graph = st.checkbox("使用 LangGraph 编排", value=True)
        except ImportError:
            st.caption("未安装 langgraph，将使用顺序执行模式")
            use_graph = False

        st.divider()
        if llm_client.is_ready():
            st.caption("大模型已就绪，ReAct 可用")
        else:
            st.caption("需配置大模型 API 才能使用 ReAct")
        use_react = st.checkbox("使用 ReAct 自主决策模式", value=False,
                                help="Agent 自主决定调用哪些工具，展示完整思考过程")

        st.divider()
        st.subheader("评分权重")
        weight_template = st.selectbox("岗位类型模板", list(WEIGHT_TEMPLATES.keys()), index=0)
        custom_weights = WEIGHT_TEMPLATES[weight_template].copy()
        st.caption("可根据岗位特点调整各维度权重")
        custom_weights["skill"] = st.slider("技能匹配", 0, 100, custom_weights["skill"], 5)
        custom_weights["education"] = st.slider("学历匹配", 0, 100, custom_weights["education"], 5)
        custom_weights["experience"] = st.slider("经验/项目", 0, 100, custom_weights["experience"], 5)
        custom_weights["bonus"] = st.slider("加分项", 0, 100, custom_weights["bonus"], 5)
        total_w = sum(custom_weights.values())
        if total_w != 100:
            st.caption(f"权重合计 {total_w}%，建议调整为 100%")
        st.session_state["custom_weights"] = custom_weights

# ========== 主页面 ==========
st.title("校园招聘智能筛选")
st.caption("上传简历，匹配岗位，获取智能筛选报告与面试建议。")

if jobs_df.empty:
    st.error("请先在侧边栏上传岗位 CSV 文件，或确保 data/jobs.csv 存在。")
    st.stop()

# ---------- 单个简历筛选模式 ----------
if mode == "单个简历筛选":
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("上传简历")
        uploaded_resume = st.file_uploader(
            "选择简历文件（支持 .txt / .docx / .pdf，最大20MB）",
            type=["txt", "docx", "pdf"],
            help="支持文本、Word和PDF格式，单个文件不超过20MB",
        )
        if uploaded_resume and uploaded_resume.size > 20 * 1024 * 1024:
            st.error("文件超过20MB限制，请压缩后重新上传")
            st.stop()
        resume_text_input = st.text_area(
            "或直接粘贴简历内容",
            height=200,
            placeholder="在此粘贴简历文本...",
        )
        if resume_text_input.strip() and st.button("解析简历内容", use_container_width=True):
            parsed_preview = resume_parser.parse(resume_text_input)
            st.session_state["parsed_preview"] = parsed_preview
            st.success(f"解析完成：{parsed_preview.get('name','未知')}，提取到 {len(parsed_preview.get('skills',[]))} 项技能")

    with col2:
        st.subheader("选择岗位")
        # 生成下拉选项：岗位名（公司·城市），并按岗位名去重
        job_col = jobs_df.get("岗位名称", jobs_df.iloc[:, 0])
        company_col = jobs_df.get("公司名称", pd.Series([""] * len(jobs_df)))
        location_col = jobs_df.get("工作地点", pd.Series([""] * len(jobs_df)))
        job_options = []
        seen_titles = set()
        for idx, row in jobs_df.iterrows():
            title = str(row.get("岗位名称", row.iloc[0]))
            if title in seen_titles:
                continue
            seen_titles.add(title)
            company = str(row.get("公司名称", ""))
            location = str(row.get("工作地点", ""))
            if company and location and company != "nan" and location != "nan":
                label = f"{title}（{company}·{location}）"
            elif company and company != "nan":
                label = f"{title}（{company}）"
            else:
                label = title
            job_options.append((label, title))
        selected_label = st.selectbox("选择目标岗位", [opt[0] for opt in job_options])
        selected_job_title = dict(job_options)[selected_label]
        job_row = jobs_df[jobs_df.get("岗位名称", jobs_df.iloc[:, 0]) == selected_job_title].iloc[0]
        with st.expander("查看岗位详情", expanded=False):
            st.dataframe(job_row.to_frame().T, use_container_width=True)

    if st.button("开始筛选", type="primary", use_container_width=True):
        resume_text = ""
        if uploaded_resume is not None:
            resume_text = FileLoader.read_text_from_bytes(
                uploaded_resume.getvalue(), uploaded_resume.name
            )
        elif resume_text_input.strip():
            resume_text = resume_text_input

        if not resume_text.strip():
            st.error("请上传简历文件或粘贴简历内容！")
            st.stop()

        # 应用自定义评分权重
        custom_w = st.session_state.get("custom_weights", {})
        if custom_w:
            screener.weights = custom_w

        # 文本自动去重（减少重复内容，节省token）
        original_len = len(resume_text)
        resume_text = FileLoader.deduplicate_text(resume_text)
        dedup_saved = original_len - len(resume_text)
        if dedup_saved > 0:
            st.caption(f"文本去重：去除重复内容 {dedup_saved} 字符")

        # 速率限制检查（使用大模型时才限流）
        needs_llm = (use_react or use_llm) and llm_client.is_ready()
        if needs_llm:
            rl = rate_limiter.check(user_id)
            if not rl["allowed"]:
                st.error(rl["reason"])
                st.stop()

        progress_bar = st.progress(0, text="准备中...")
        try:
            progress_bar.progress(15, text="解析简历中...")
            if use_react and llm_client.is_ready():
                # ===== ReAct 自主 Agent 模式 =====
                tool_reg = ToolRegistry(llm_client=llm_client, rag_engine=rag_engine)
                react_agent = ReActAgent(
                    llm_client=llm_client,
                    tool_registry=tool_reg,
                    rag_engine=rag_engine,
                    cache=cache,
                    max_iterations=6,
                )
                react_result = react_agent.run(
                    resume_text=resume_text,
                    job_dict=job_row.to_dict(),
                    use_rag=use_rag,
                )
                # 始终用规则引擎的完整结果做展示（含 dimensions 等完整结构）
                parsed_resume = resume_parser.parse(resume_text)
                parsed_job = job_parser.parse_csv_row(job_row.to_dict())
                result = screener.screen(parsed_resume, parsed_job)
                rag_results = []
                rag_context = ""
                llm_analysis = None
                final_report = react_result["final_answer"]
                workflow_backend = f"react ({react_result['iterations']}轮)"
                st.session_state["react_trace"] = react_result["trace"]
            elif use_graph:
                agent = RecruitmentAgent(llm_client=llm_client, rag_engine=rag_engine)
                state = agent.run(
                    resume_text=resume_text,
                    job_dict=job_row.to_dict(),
                    use_rag=use_rag,
                    use_llm=use_llm,
                )
                result = state["screen_result"]
                rag_results = state.get("rag_results", [])
                rag_context = state.get("rag_context", "")
                llm_analysis = state.get("llm_analysis")
                final_report = state.get("final_report", "")
                workflow_backend = agent.backend
                parsed_resume = state.get("parsed_resume", {})
                parsed_job = state.get("parsed_job", {})
            else:
                parsed_resume = resume_parser.parse(resume_text)
                parsed_job = job_parser.parse_csv_row(job_row.to_dict())
                result = screener.screen(parsed_resume, parsed_job)
                rag_results = []
                rag_context = ""
                if use_rag:
                    query = f"{parsed_job.get('title','')} {' '.join(parsed_resume.get('skills',[]))}"
                    rag_results = rag_engine.retrieve(query)
                    rag_context = rag_engine.retrieve_as_context(query)
                llm_analysis = None
                if use_llm and llm_client.is_ready():
                    enhancer = LLMEnhancer(llm_client)
                    llm_analysis = enhancer.generate_all(parsed_resume, parsed_job, result)
                final_report = reporter.to_text(result)
                workflow_backend = "sequential"

            # 保存到 session
            st.session_state["resume_text"] = resume_text
            st.session_state["parsed_resume"] = parsed_resume
            st.session_state["parsed_job"] = parsed_job
            st.session_state["screen_result"] = result
            st.session_state["rag_results"] = rag_results
            st.session_state["rag_context"] = rag_context
            st.session_state["llm_analysis"] = llm_analysis
            st.session_state["final_report"] = final_report
            st.session_state["workflow_backend"] = workflow_backend
            # 保存到SQLite数据库
            try:
                database.add_screen_record(result)
                database.add_log("screen", f"{result.get('candidate','')} - {result.get('job_title','')} - {result.get('total_score',0)}分")
            except Exception:
                pass
            # 初始化对话（无状态：系统提示词和历史都存 session_state）
            if chat_agent.available():
                chat_system_prompt = chat_agent.build_system_prompt(
                    parsed_resume, parsed_job, result, rag_context
                )
                welcome = chat_agent.get_welcome_message(parsed_resume, parsed_job, result)
                st.session_state["chat_system_prompt"] = chat_system_prompt
                st.session_state["chat_history"] = [{"role": "assistant", "content": welcome}]
            else:
                st.session_state["chat_system_prompt"] = ""
                st.session_state["chat_history"] = []

            progress_bar.progress(100, text="完成")
            st.rerun()
        except Exception as e:
            progress_bar.empty()
            st.error(f"筛选过程出错：{str(e)}")
            st.caption("建议检查简历内容或切换为规则引擎模式")

    # ===== 展示筛选结果 =====
    if "screen_result" in st.session_state:
        result = st.session_state["screen_result"]
        rag_results = st.session_state.get("rag_results", [])
        llm_analysis = st.session_state.get("llm_analysis")
        final_report = st.session_state.get("final_report", "")
        workflow_backend = st.session_state.get("workflow_backend", "")

        st.divider()
        st.subheader("筛选结果")

        # ===== ReAct 思考过程展示 =====
        if st.session_state.get("react_trace"):
            with st.expander("查看 Agent 决策过程", expanded=False):
                st.markdown("Agent 自主决定每一步调用什么工具，以下是完整的思考-行动-观察循环：")
                for step in st.session_state["react_trace"]:
                    iteration = step.get("iteration", "?")
                    thought = step.get("thought", "")
                    action = step.get("action", "")
                    observation = step.get("observation", "")

                    st.markdown(f"""
                    <div style="border-left:3px solid #2563eb;padding-left:16px;margin-bottom:16px;">
                        <div style="background:#2563eb;color:white;padding:2px 10px;border-radius:12px;
                        display:inline-block;font-size:12px;font-weight:600;">第 {iteration} 轮</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if thought:
                        st.markdown(f"**思考**：{thought}")
                    if action and action != "final_answer":
                        params = step.get("action_input", {})
                        params_str = ", ".join([f"{k}={str(v)[:50]}" for k, v in params.items()]) if params else ""
                        st.markdown(f"**行动**：调用 `{action}`({params_str})")
                    if observation:
                        with st.container():
                            st.markdown("**观察结果**：")
                            st.code(observation[:800], language="json")
                    st.markdown("---")

        # 结果卡片
        level_class = f"level-{result['level'][0]}" if result.get("level") else "level-D"
        st.markdown(f"""
        <div class="result-card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                <div>
                    <div style="font-size:13px;color:#94a3b8;margin-bottom:4px;">候选人</div>
                    <div style="font-size:20px;font-weight:600;color:#1a202c;">{result['candidate']}</div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:13px;color:#94a3b8;margin-bottom:4px;">综合得分</div>
                    <div style="font-size:28px;font-weight:700;color:#1a202c;">{result['total_score']}<span style="font-size:14px;color:#94a3b8;font-weight:400;"> / 100</span></div>
                </div>
            </div>
            <div style="display:flex;align-items:center;gap:12px;padding-top:12px;border-top:1px solid #eef0f4;">
                <span class="level-badge {level_class}">{result['level']}</span>
                <span style="font-size:14px;color:#475569;">{result['conclusion']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.subheader("各维度得分")
        dims = result.get("dimensions", {})
        if dims:
            score_bar("技能匹配（权重40%）", dims.get("skill", {}).get("score", 0), color="#2563eb")
            if dims.get("skill", {}).get("detail", {}).get("note"):
                st.caption(dims["skill"]["detail"]["note"])
            score_bar("学历匹配（权重20%）", dims.get("education", {}).get("score", 0), color="#0891b2")
            if dims.get("education", {}).get("detail", {}).get("note"):
                st.caption(dims["education"]["detail"]["note"])
            score_bar("经验/项目（权重30%）", dims.get("experience", {}).get("score", 0), color="#059669")
            if dims.get("experience", {}).get("detail", {}).get("note"):
                st.caption(dims["experience"]["detail"]["note"])
            score_bar("加分项（权重10%）", dims.get("bonus", {}).get("score", 0), color="#d97706")
            if dims.get("bonus", {}).get("detail", {}).get("note"):
                st.caption(dims["bonus"]["detail"]["note"])
        else:
            st.info("维度得分数据暂不可用")

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("已匹配技能")
            if result["matched_skills"]:
                tags = "".join([
                    f'<span style="display:inline-block;background:#dcfce7;color:#166534;'
                    f'padding:4px 12px;border-radius:16px;margin:3px;font-size:13px;">{s}</span>'
                    for s in result["matched_skills"]
                ])
                st.markdown(tags, unsafe_allow_html=True)
            else:
                st.write("无")
        with col_b:
            st.subheader("待提升技能")
            if result["missing_skills"]:
                tags = "".join([
                    f'<span style="display:inline-block;background:#fee2e2;color:#991b1b;'
                    f'padding:4px 12px;border-radius:16px;margin:3px;font-size:13px;">{s}</span>'
                    for s in result["missing_skills"]
                ])
                st.markdown(tags, unsafe_allow_html=True)
            else:
                st.write("无")

        st.subheader("改进建议")
        st.warning(result["suggestion"])

        # ===== 推荐岗位（低分时推荐其他更匹配的岗位）=====
        if result["total_score"] < 60:
            st.divider()
            st.subheader("为你推荐其他岗位")
            st.caption("基于你的技能背景，以下岗位可能更匹配")
                        try:
                p_resume_rec = st.session_state.get("parsed_resume", {})
                p_job_rec = st.session_state.get("parsed_job", {})
                candidate_skills = set(s.lower() for s in p_resume_rec.get("skills", []))
                if not candidate_skills:
                    st.caption("未识别到技能，无法推荐岗位。请确保简历中包含技能信息。")
                elif jobs_df.empty:
                    st.caption("岗位数据为空，无法推荐。")
                else:
                    job_scores = []
                    for _, jrow in jobs_df.iterrows():
                        jparsed = job_parser.parse_csv_row(jrow.to_dict())
                        jskills = set(s.lower() for s in jparsed.get("required_skills", []))
                        if jskills:
                            match = len(candidate_skills & jskills) / len(jskills) * 100
                        else:
                            match = 0
                        current_title = p_job_rec.get("title", "") if p_job_rec else ""
                        if jparsed.get("title", "") != current_title:
                            company = str(jrow.get("公司名称", jrow.get("company", "")))
                            location = str(jrow.get("工作地点", jrow.get("location", "")))
                            job_scores.append((jparsed.get("title", "未知"), jparsed.get("category", ""), match, company, location))
                    job_scores.sort(key=lambda x: x[2], reverse=True)
                    top3 = job_scores[:3]
                    if top3 and top3[0][2] > 0:
                        rec_cols = st.columns(3)
                        for i, (title, cat, match, company, location) in enumerate(top3):
                            with rec_cols[i]:
                                st.markdown(f"**{title}**")
                                st.caption(f"{cat} | {company} | {location}")
                                st.caption(f"技能匹配度：{match:.0f}%")
                    else:
                        st.caption("暂未找到更匹配的岗位，建议提升核心技能后再尝试。")
            except Exception as e:
                st.caption(f"岗位推荐暂不可用：{str(e)}")


        # ===== RAG 检索结果 =====
        if use_rag and rag_results:
            st.divider()
            st.subheader("知识库参考")
            for i, r in enumerate(rag_results, 1):
                with st.expander(f"参考资料 {i} — {r['source']}（相关度 {r['score']}）"):
                    st.write(r["text"])

        # ===== LLM 增强分析 =====
        if llm_analysis and "error" not in llm_analysis:
            st.divider()
            st.subheader("智能分析")

            st.markdown("### 智能综合评语")
            st.write(llm_analysis.get("comment", ""))

            profile = llm_analysis.get("profile", {})
            if profile and "error" not in profile:
                st.markdown("### 👤 候选人画像")
                pcol1, pcol2 = st.columns(2)
                with pcol1:
                    st.markdown("**优势**")
                    for s in profile.get("strengths", []):
                        st.write(f"- {s}")
                    st.markdown("**发展潜力**")
                    st.write(profile.get("potential", ""))
                with pcol2:
                    st.markdown("**劣势/不足**")
                    for w in profile.get("weaknesses", []):
                        st.write(f"- {w}")
                    st.markdown("**风险提示**")
                    for r in profile.get("risk_points", []):
                        st.write(f"- {r}")
                st.markdown(f"**适合岗位类型**：{profile.get('fit_type', '')}")

            st.markdown("### 🔍 岗位适配深度分析")
            st.write(llm_analysis.get("deep_analysis", ""))

            st.markdown("### ❓ 推荐面试问题")
            for i, q in enumerate(llm_analysis.get("interview_questions", []), 1):
                st.write(f"{i}. {q}")

            st.markdown("### 简历优化建议")
            for i, opt in enumerate(llm_analysis.get("resume_optimization", []), 1):
                st.write(f"{i}. {opt}")

            st.markdown("### 💰 薪资建议")
            st.write(llm_analysis.get("salary_suggestion", ""))

        # ===== 简历智能改写 =====
        st.divider()
        st.subheader("简历优化建议")
        if not llm_client.is_ready():
            st.warning("请先配置大模型 API Key 才能使用简历改写功能。")
        else:
            rewrite_col1, rewrite_col2 = st.columns([1, 3])
            with rewrite_col1:
                if st.button("✨ 一键改写简历", type="secondary", use_container_width=True):
                    rl = rate_limiter.check(user_id)
                    if not rl["allowed"]:
                        st.error(rl["reason"])
                    else:
                        with st.spinner("AI 正在改写简历..."):
                            enhancer = LLMEnhancer(llm_client)
                            rewritten = enhancer.rewrite_resume(
                                st.session_state.get("resume_text", ""),
                                st.session_state.get("parsed_resume", {}),
                                st.session_state.get("parsed_job", {}),
                            )
                            st.session_state["rewritten_resume"] = rewritten
                    st.rerun()

            if "rewritten_resume" in st.session_state and st.session_state["rewritten_resume"]:
                st.markdown("### 改写后的简历")
                st.text_area(
                    "改写结果（可复制编辑）",
                    value=st.session_state["rewritten_resume"],
                    height=400,
                )
                st.download_button(
                    "下载优化后的简历（.txt）",
                    st.session_state["rewritten_resume"],
                    file_name=f"{result['candidate']}_改写简历.txt",
                    mime="text/plain",
                )

        # ===== 多轮对话 =====
        st.divider()
        st.subheader("招聘顾问对话")

        if not chat_agent.available():
            st.warning("请先配置大模型 API Key 才能使用对话功能。")
        else:
            # 显示对话历史
            for msg in st.session_state.get("chat_history", []):
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

        # 对话输入框（放在条件外面，确保始终渲染）
        prompt = st.chat_input("向 AI 顾问提问，例如：这个候选人有什么风险？")
        if prompt:
            if not chat_agent.available():
                st.error("请先在侧边栏配置大模型 API Key")
            else:
                rl = rate_limiter.check(user_id)
                if not rl["allowed"]:
                    st.error(rl["reason"])
                else:
                    history = st.session_state.get("chat_history", [])
                    system_prompt = st.session_state.get("chat_system_prompt", "")
                    st.session_state.setdefault("chat_history", []).append(
                        {"role": "user", "content": prompt}
                    )
                    with st.chat_message("user"):
                        st.write(prompt)
                    with st.chat_message("assistant"):
                        try:
                            with st.spinner("思考中..."):
                                response = chat_agent.chat(
                                    system_prompt=system_prompt,
                                    conversation_history=history,
                                    user_message=prompt,
                                )
                            st.write(response)
                            st.session_state["chat_history"].append(
                                {"role": "assistant", "content": response}
                            )
                        except Exception as e:
                            err_msg = f"对话出错：{str(e)}"
                            st.error(err_msg)
                            st.session_state["chat_history"].append(
                                {"role": "assistant", "content": err_msg}
                            )

        # 重新开始对话按钮
        if chat_agent.available():
            if st.button("重新开始对话", key="restart_chat"):
                try:
                    parsed_resume = st.session_state.get("parsed_resume", {})
                    parsed_job = st.session_state.get("parsed_job", {})
                    result = st.session_state.get("screen_result", {})
                    rag_context = st.session_state.get("rag_context", "")
                    chat_system_prompt = chat_agent.build_system_prompt(
                        parsed_resume, parsed_job, result, rag_context
                    )
                    welcome = chat_agent.get_welcome_message(parsed_resume, parsed_job, result)
                    st.session_state["chat_system_prompt"] = chat_system_prompt
                    st.session_state["chat_history"] = [
                        {"role": "assistant", "content": welcome}
                    ]
                    st.rerun()
                except Exception as e:
                    st.error(f"重启对话失败：{str(e)}")

        # ===== 导出报告 =====
        st.divider()
        st.subheader("导出报告")
        col_d1, col_d2, col_d3, col_d4 = st.columns(4)
        with col_d1:
            st.download_button("TXT", final_report,
                               file_name="智能筛选报告.txt", mime="text/plain")
        with col_d2:
            st.download_button("Markdown", reporter.to_markdown(result),
                               file_name="智能筛选报告.md", mime="text/markdown")
        with col_d3:
            st.download_button("JSON", reporter.to_json(result),
                               file_name="智能筛选报告.json", mime="application/json")
        with col_d4:
            # Excel 导出
            try:
                export_df = pd.DataFrame([{
                    "候选人": result.get("candidate", ""),
                    "目标岗位": result.get("job_title", ""),
                    "综合得分": result.get("total_score", 0),
                    "评级": result.get("level", ""),
                    "结论": result.get("conclusion", ""),
                    "技能分": result.get("dimensions", {}).get("skill", {}).get("score", 0),
                    "学历分": result.get("dimensions", {}).get("education", {}).get("score", 0),
                    "经验分": result.get("dimensions", {}).get("experience", {}).get("score", 0),
                    "已匹配技能": ", ".join(result.get("matched_skills", [])),
                    "待提升技能": ", ".join(result.get("missing_skills", [])),
                    "改进建议": result.get("suggestion", ""),
                }])
                st.download_button("Excel", to_excel(export_df),
                                   file_name="智能筛选报告.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception:
                st.caption("Excel导出需安装openpyxl")

        # ===== AI 面试模拟器 =====
        st.divider()
        st.subheader("面试模拟")
        st.caption("基于候选人简历和目标岗位，生成个性化面试问题并评估回答")

        if "interview" not in st.session_state:
            st.session_state["interview"] = None
            st.session_state["interview_answers"] = []

                if st.button("开始模拟面试", use_container_width=True):
            p_resume = st.session_state.get("parsed_resume", {})
            p_job = st.session_state.get("parsed_job", {})
            if not p_resume or not p_job:
                st.warning("请先完成简历筛选，再开始面试模拟。")
            else:
                interviewer = InterviewSimulator(llm_client=llm_client if llm_client.is_ready() else None)
                questions = interviewer.start(p_resume, p_job)
                st.session_state["interview"] = interviewer
                st.session_state["interview_answers"] = []
                st.rerun()


        interviewer = st.session_state.get("interview")
        if interviewer is not None:
            current = interviewer.get_current_question()
            if current:
                st.markdown(f"**第 {current['index']}/{current['total']} 题** ｜ 类型：{current['type']}")
                st.info(current["question"])

                user_answer = st.text_area("你的回答", height=120, key=f"q_{current['index']}")
                if st.button("提交回答", key=f"submit_{current['index']}"):
                    if user_answer.strip():
                        result_int = interviewer.submit_answer(user_answer)
                        st.session_state["interview_answers"].append({
                            "q": current["question"],
                            "a": user_answer,
                            "eval": result_int["evaluation"],
                        })
                        st.success(f"回答评估：{result_int['evaluation']['level']}（{result_int['evaluation']['score']}分）")
                        st.caption(result_int["evaluation"]["feedback"])
                        if result_int["is_finished"]:
                            st.rerun()
                        else:
                            st.rerun()
                    else:
                        st.warning("请输入回答内容")
            else:
                # 面试完成，显示总结
                summary = interviewer.get_summary()
                st.success(f"面试完成！平均得分：{summary['avg_score']}分")
                st.markdown(f"**结论：{summary['conclusion']}**")
                with st.expander("查看面试记录", expanded=True):
                    for i, ans in enumerate(st.session_state.get("interview_answers", []), 1):
                        st.markdown(f"**Q{i}: {ans['q'][:50]}...**")
                        st.markdown(f"回答：{ans['a'][:100]}...")
                        st.caption(f"评估：{ans['eval']['level']}（{ans['eval']['score']}分）- {ans['eval']['feedback']}")
                        st.divider()
                if st.button("重新开始面试"):
                    st.session_state["interview"] = None
                    st.session_state["interview_answers"] = []
                    st.rerun()

# ---------- 批量筛选模式 ----------
else:
    st.subheader("批量简历筛选")
    st.markdown("上传多份简历（支持 .txt / .docx / .pdf），一次性对目标岗位进行匹配排序。")

    uploaded_resumes = st.file_uploader(
        "上传多份简历",
        type=["txt", "docx", "pdf"],
        accept_multiple_files=True,
    )

    # 生成去重的岗位选项
    job_options_batch = []
    seen_titles_batch = set()
    for idx, row in jobs_df.iterrows():
        title = str(row.get("岗位名称", row.iloc[0]))
        if title in seen_titles_batch:
            continue
        seen_titles_batch.add(title)
        company = str(row.get("公司名称", ""))
        location = str(row.get("工作地点", ""))
        if company and location and company != "nan" and location != "nan":
            label = f"{title}（{company}·{location}）"
        elif company and company != "nan":
            label = f"{title}（{company}）"
        else:
            label = title
        job_options_batch.append((label, title))

    selected_label_batch = st.selectbox(
        "选择目标岗位",
        [opt[0] for opt in job_options_batch],
    )
    selected_job_title = dict(job_options_batch)[selected_label_batch]

    if st.button("开始批量筛选", type="primary", use_container_width=True):
        if not uploaded_resumes:
            st.error("请至少上传一份简历！")
            st.stop()

        job_row = jobs_df[jobs_df.get("岗位名称", jobs_df.iloc[:, 0]) == selected_job_title].iloc[0]
        agent = RecruitmentAgent(llm_client=llm_client, rag_engine=rag_engine)

        results = []
        progress = st.progress(0)
        for i, up_file in enumerate(uploaded_resumes):
            text = FileLoader.read_text_from_bytes(up_file.getvalue(), up_file.name)
            state = agent.run(
                resume_text=text,
                job_dict=job_row.to_dict(),
                use_rag=use_rag,
                use_llm=False,
            )
            results.append(state["screen_result"])
            progress.progress((i + 1) / len(uploaded_resumes))

        results.sort(key=lambda x: x["total_score"], reverse=True)
        st.success(f"筛选完成，共处理 {len(results)} 份简历（工作流：{agent.backend}）")

        summary = pd.DataFrame([
            {
                "排名": i + 1,
                "候选人": r["candidate"],
                "综合得分": r["total_score"],
                "评级": r["level"],
                "技能分": r["dimensions"]["skill"]["score"],
                "学历分": r["dimensions"]["education"]["score"],
                "经验分": r["dimensions"]["experience"]["score"],
                "结论": r["conclusion"],
            }
            for i, r in enumerate(results)
        ])
        st.dataframe(summary, use_container_width=True, hide_index=True)

        # 导出 Excel
        st.download_button(
            "导出筛选结果",
            summary.to_csv(index=False).encode("utf-8-sig"),
            file_name="批量筛选结果.csv",
            mime="text/csv",
        )

        st.subheader("逐人详情")
        for r in results:
            with st.expander(f"{r['candidate']} — {r['total_score']}分 — {r['level']}"):
                st.write(f"**结论**：{r['conclusion']}")
                st.write(f"**已匹配技能**：{', '.join(r['matched_skills']) if r['matched_skills'] else '无'}")
                st.write(f"**缺失技能**：{', '.join(r['missing_skills']) if r['missing_skills'] else '无'}")
                st.write(f"**改进建议**：{r['suggestion']}")
