# -*- coding: utf-8 -*-
"""
FastAPI 后端服务：提供校园招聘智能筛选的 REST API
启动方式：uvicorn backend.main:app --host 0.0.0.0 --port 8000
"""
import os
import sys
import uuid
import io
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import (
    ResumeParser, JobParser, Screener, Reporter,
    LLMClient, LLMEnhancer, RAGEngine, RecruitmentAgent,
    CacheManager, ChatAgent, InterviewSimulator, database,
)
from utils import FileLoader
from config import LLM_PROVIDERS, DEFAULT_LLM_PROVIDER, REDIS_CONFIG, WEIGHT_TEMPLATES

# ========== 初始化 ==========
app = FastAPI(title="校园招聘智能筛选 API", version="2.0.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局 Agent 实例
resume_parser = ResumeParser()
job_parser = JobParser()
screener = Screener()
reporter = Reporter()
rag_engine = RAGEngine()
rag_status = rag_engine.initialize()
cache = CacheManager(
    redis_host=REDIS_CONFIG["host"],
    redis_port=REDIS_CONFIG["port"],
    redis_db=REDIS_CONFIG["db"],
    redis_url=REDIS_CONFIG.get("url", ""),
    redis_password=REDIS_CONFIG.get("password", ""),
    default_ttl=REDIS_CONFIG["default_ttl"],
    use_redis=bool(REDIS_CONFIG.get("url", "")),
)
llm_client = LLMClient(
    api_key=os.environ.get("API_KEY", ""),
    base_url=os.environ.get("BASE_URL", ""),
    model=os.environ.get("MODEL", ""),
    provider=os.environ.get("LLM_PROVIDER", DEFAULT_LLM_PROVIDER),
)
chat_agent = ChatAgent(llm_client=llm_client)

# 会话存储（多轮对话、面试模拟）
sessions: Dict[str, Dict[str, Any]] = {}

# 岗位数据
JOBS_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "jobs.csv")


def load_jobs() -> pd.DataFrame:
    if os.path.exists(JOBS_CSV):
        df = pd.read_csv(JOBS_CSV)
        if "岗位名称" in df.columns:
            df = df.drop_duplicates(subset=["岗位名称"], keep="first").reset_index(drop=True)
        return df
    return pd.DataFrame()


# ========== 请求模型 ==========
class ParseRequest(BaseModel):
    text: str


class ScreenRequest(BaseModel):
    resume_text: str
    job_title: str
    use_rag: bool = True
    use_llm: bool = False
    use_graph: bool = True
    use_react: bool = False
    weights: Optional[Dict[str, int]] = None
    llm_config: Optional[Dict[str, str]] = None


class ChatRequest(BaseModel):
    session_id: str
    message: str
    resume_text: Optional[str] = None
    job_title: Optional[str] = None


class InterviewStartRequest(BaseModel):
    session_id: str
    resume_text: str
    job_title: str


class InterviewAnswerRequest(BaseModel):
    session_id: str
    answer: str


# ========== API 端点 ==========

@app.get("/api/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "version": "2.0.0",
        "llm_ready": llm_client.is_ready(),
        "rag_ready": rag_status["status"] in ("built", "loaded"),
        "cache_backend": cache.stats()["backend"],
        "jobs_count": len(load_jobs()),
    }


@app.get("/api/jobs")
async def get_jobs(category: Optional[str] = None):
    """获取岗位列表"""
    df = load_jobs()
    if df.empty:
        return {"jobs": [], "count": 0}
    if category and "岗位分类" in df.columns:
        df = df[df["岗位分类"] == category]
    jobs = []
    for _, row in df.iterrows():
        jobs.append({
            "title": str(row.get("岗位名称", "")),
            "company": str(row.get("公司名称", "")),
            "location": str(row.get("工作地点", "")),
            "category": str(row.get("岗位分类", "")),
            "education": str(row.get("学历要求", "")),
            "experience": str(row.get("工作经验", "")),
            "salary": str(row.get("薪资范围", "")),
        })
    return {"jobs": jobs, "count": len(jobs)}


@app.get("/api/jobs/categories")
async def get_job_categories():
    """获取岗位分类列表"""
    df = load_jobs()
    if df.empty or "岗位分类" not in df.columns:
        return {"categories": []}
    categories = sorted(df["岗位分类"].dropna().unique().tolist())
    return {"categories": categories}


@app.post("/api/parse/resume")
async def parse_resume(req: ParseRequest):
    """解析简历文本"""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="简历内容不能为空")
    try:
        parsed = resume_parser.parse(req.text)
        return {
            "name": parsed.get("name", ""),
            "education": parsed.get("education", ""),
            "school": parsed.get("school", ""),
            "major": parsed.get("major", ""),
            "skills": parsed.get("skills", []),
            "projects": parsed.get("projects", []),
            "internship": parsed.get("internship", []),
            "certificates": parsed.get("certificates", []),
            "awards": parsed.get("awards", []),
            "bonus_items": parsed.get("bonus_items", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败：{str(e)}")


@app.post("/api/parse/resume/file")
async def parse_resume_file(file: UploadFile = File(...)):
    """解析简历文件（PDF/DOCX/TXT）"""
    try:
        content = await file.read()
        text = FileLoader.read_text_from_bytes(content, file.filename)
        if not text.strip():
            raise HTTPException(status_code=400, detail="无法从文件中提取文本")
        parsed = resume_parser.parse(text)
        return {
            "name": parsed.get("name", ""),
            "education": parsed.get("education", ""),
            "school": parsed.get("school", ""),
            "major": parsed.get("major", ""),
            "skills": parsed.get("skills", []),
            "projects": parsed.get("projects", []),
            "internship": parsed.get("internship", []),
            "certificates": parsed.get("certificates", []),
            "awards": parsed.get("awards", []),
            "raw_text": text[:5000],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件解析失败：{str(e)}")


@app.post("/api/screen")
async def screen_candidate(req: ScreenRequest):
    """智能筛选候选人"""
    try:
        # 查找岗位
        df = load_jobs()
        if df.empty:
            raise HTTPException(status_code=404, detail="岗位数据不存在")
        job_rows = df[df["岗位名称"] == req.job_title]
        if job_rows.empty:
            raise HTTPException(status_code=404, detail=f"未找到岗位：{req.job_title}")
        job_row = job_rows.iloc[0]

        # 应用自定义权重
        if req.weights:
            screener.weights = req.weights

        # 配置大模型
        current_llm = llm_client
        if req.llm_config:
            current_llm = LLMClient(
                api_key=req.llm_config.get("api_key", ""),
                base_url=req.llm_config.get("base_url", ""),
                model=req.llm_config.get("model", ""),
                provider=req.llm_config.get("provider", DEFAULT_LLM_PROVIDER),
            )

        # 解析简历和岗位
        parsed_resume = resume_parser.parse(req.resume_text)
        parsed_job = job_parser.parse_csv_row(job_row.to_dict())

        # RAG 检索
        rag_results = []
        rag_context = ""
        if req.use_rag:
            query = f"{parsed_job.get('title','')} {' '.join(parsed_resume.get('skills',[]))}"
            rag_results = rag_engine.retrieve(query)
            rag_context = rag_engine.retrieve_as_context(query)

        # 评分
        result = screener.screen(parsed_resume, parsed_job)

        # LLM 增强分析
        llm_analysis = None
        if req.use_llm and current_llm.is_ready():
            enhancer = LLMEnhancer(current_llm)
            llm_analysis = enhancer.generate_all(parsed_resume, parsed_job, result)

        # 生成报告
        final_report = reporter.to_text(result)

        # 保存到数据库
        try:
            database.add_screen_record(result)
        except Exception:
            pass

        return {
            "candidate": result.get("candidate", ""),
            "job_title": result.get("job_title", ""),
            "total_score": result.get("total_score", 0),
            "level": result.get("level", ""),
            "conclusion": result.get("conclusion", ""),
            "dimensions": result.get("dimensions", {}),
            "matched_skills": result.get("matched_skills", []),
            "missing_skills": result.get("missing_skills", []),
            "suggestion": result.get("suggestion", ""),
            "rag_results": [{"text": r["text"][:500], "source": r["source"], "score": r["score"]} for r in rag_results],
            "llm_analysis": llm_analysis,
            "report": final_report,
            "parsed_resume": {
                "name": parsed_resume.get("name", ""),
                "skills": parsed_resume.get("skills", []),
                "major": parsed_resume.get("major", ""),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"筛选失败：{str(e)}")


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """多轮对话"""
    try:
        if req.session_id not in sessions:
            sessions[req.session_id] = {
                "chat_history": [],
                "system_prompt": "",
            }

        sess = sessions[req.session_id]

        # 首次对话构建系统提示
        if not sess["system_prompt"] and req.resume_text and req.job_title:
            df = load_jobs()
            job_rows = df[df["岗位名称"] == req.job_title]
            if not job_rows.empty:
                parsed_resume = resume_parser.parse(req.resume_text)
                parsed_job = job_parser.parse_csv_row(job_rows.iloc[0].to_dict())
                result = screener.screen(parsed_resume, parsed_job)
                rag_context = rag_engine.retrieve_as_context(
                    f"{parsed_job.get('title','')} {' '.join(parsed_resume.get('skills',[]))}"
                )
                sess["system_prompt"] = chat_agent.build_system_prompt(
                    parsed_resume, parsed_job, result, rag_context
                )
                welcome = chat_agent.get_welcome_message(parsed_resume, parsed_job, result)
                sess["chat_history"].append({"role": "assistant", "content": welcome})

        if not llm_client.is_ready():
            return {"reply": "大模型未配置，无法对话。请先配置 API Key。", "history": sess["chat_history"]}

        sess["chat_history"].append({"role": "user", "content": req.message})
        response = chat_agent.chat(sess["chat_history"], sess["system_prompt"])
        reply = response.get("content", response.get("reply", ""))
        sess["chat_history"].append({"role": "assistant", "content": reply})

        return {"reply": reply, "history": sess["chat_history"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"对话失败：{str(e)}")


@app.post("/api/interview/start")
async def interview_start(req: InterviewStartRequest):
    """开始面试模拟"""
    try:
        df = load_jobs()
        job_rows = df[df["岗位名称"] == req.job_title]
        if job_rows.empty:
            raise HTTPException(status_code=404, detail=f"未找到岗位：{req.job_title}")

        parsed_resume = resume_parser.parse(req.resume_text)
        parsed_job = job_parser.parse_csv_row(job_rows.iloc[0].to_dict())

        interviewer = InterviewSimulator(llm_client=llm_client if llm_client.is_ready() else None)
        questions = interviewer.start(parsed_resume, parsed_job)

        sessions[req.session_id] = {
            "interviewer": interviewer,
            "answers": [],
        }

        current = interviewer.get_current_question()
        return {
            "session_id": req.session_id,
            "total_questions": len(questions),
            "current": current,
            "questions": [{"type": q["type"], "question": q["question"]} for q in questions],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"面试启动失败：{str(e)}")


@app.post("/api/interview/answer")
async def interview_answer(req: InterviewAnswerRequest):
    """提交面试回答"""
    try:
        if req.session_id not in sessions or "interviewer" not in sessions[req.session_id]:
            raise HTTPException(status_code=404, detail="面试会话不存在，请先开始面试")

        interviewer = sessions[req.session_id]["interviewer"]
        result = interviewer.submit_answer(req.answer)
        sessions[req.session_id]["answers"].append({
            "question": interviewer.questions[interviewer.current_idx - 1]["question"] if interviewer.current_idx > 0 else "",
            "answer": req.answer,
            "evaluation": result["evaluation"],
        })

        if result["is_finished"]:
            summary = interviewer.get_summary()
            return {
                "is_finished": True,
                "evaluation": result["evaluation"],
                "summary": summary,
            }
        return {
            "is_finished": False,
            "evaluation": result["evaluation"],
            "next_question": result["next_question"],
            "progress": result["progress"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回答提交失败：{str(e)}")


@app.get("/api/stats")
async def get_stats():
    """获取统计数据"""
    try:
        count = database.get_record_count()
        recent = database.get_recent_records(50)
        if not recent:
            return {"total": count, "avg_score": 0, "pass_rate": 0, "top_jobs": [], "top_missing": []}

        avg_score = sum(r["total_score"] for r in recent) / len(recent)
        pass_count = sum(1 for r in recent if r["total_score"] >= 60)
        pass_rate = pass_count / len(recent) * 100

        job_counts = {}
        for r in recent:
            jt = r.get("job_title", "未知")
            job_counts[jt] = job_counts.get(jt, 0) + 1
        top_jobs = sorted(job_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total": count,
            "avg_score": round(avg_score, 1),
            "pass_rate": round(pass_rate, 1),
            "top_jobs": [{"job": j, "count": c} for j, c in top_jobs],
            "recent": recent[:10],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"统计获取失败：{str(e)}")


@app.get("/api/weights/templates")
async def get_weight_templates():
    """获取评分权重模板"""
    return {"templates": WEIGHT_TEMPLATES}


@app.post("/api/rag/rebuild")
async def rebuild_rag():
    """重建 RAG 索引"""
    try:
        status = rag_engine.initialize(force_rebuild=True)
        return {"status": status["status"], "message": status["message"], "chunk_count": status.get("chunk_count", 0)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"索引重建失败：{str(e)}")


@app.get("/api/knowledge/files")
async def list_knowledge_files():
    """列出知识库文档"""
    kb_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "knowledge")
    if not os.path.exists(kb_dir):
        return {"files": []}
    files = []
    for f in os.listdir(kb_dir):
        if f.endswith((".md", ".txt")):
            fpath = os.path.join(kb_dir, f)
            files.append({"name": f, "size": os.path.getsize(fpath)})
    return {"files": files}


@app.delete("/api/knowledge/files/{filename}")
async def delete_knowledge_file(filename: str):
    """删除知识库文档"""
    kb_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "knowledge")
    fpath = os.path.join(kb_dir, filename)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        os.remove(fpath)
        return {"status": "ok", "message": f"已删除 {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败：{str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
