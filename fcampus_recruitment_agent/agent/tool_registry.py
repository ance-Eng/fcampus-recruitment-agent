# -*- coding: utf-8 -*-
"""
工具注册系统：定义 Agent 可调用的所有工具（Function Calling）
每个工具包含：名称、描述、参数说明、执行函数
"""
import json
from typing import Callable, Dict, Any, Optional
from .resume_parser import ResumeParser
from .job_parser import JobParser
from .screener import Screener
from .reporter import Reporter
from .llm_enhancer import LLMEnhancer
from .rag_engine import RAGEngine
from .llm_client import LLMClient
class Tool:
    """工具定义"""
    def __init__(self, name: str, description: str, parameters: dict, func: Callable):
        self.name = name
        self.description = description
        self.parameters = parameters  # JSON Schema 格式
        self.func = func
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
    def execute(self, **kwargs) -> str:
        """执行工具，返回字符串结果"""
        try:
            result = self.func(**kwargs)
            if isinstance(result, (dict, list)):
                return json.dumps(result, ensure_ascii=False, indent=2)
            return str(result)
        except Exception as e:
            return f"[工具执行错误] {str(e)}"
class ToolRegistry:
    """工具注册器"""
    def __init__(self, llm_client: LLMClient = None, rag_engine: RAGEngine = None):
        self.tools: Dict[str, Tool] = {}
        self.llm_client = llm_client
        self.rag_engine = rag_engine
        self._register_default_tools()
    def register(self, tool: Tool):
        self.tools[tool.name] = tool
    def get(self, name: str) -> Optional[Tool]:
        return self.tools.get(name)
    def list_tools(self) -> list:
        return [t.to_dict() for t in self.tools.values()]
    def execute(self, name: str, **kwargs) -> str:
        tool = self.get(name)
        if not tool:
            return f"[错误] 未知工具: {name}，可用工具: {list(self.tools.keys())}"
        return tool.execute(**kwargs)
    def get_system_prompt(self) -> str:
        """生成工具列表的系统提示词（自然语言格式，LLM更容易理解参数要求）"""
        tools_desc = []
        for t in self.tools.values():
            props = t.parameters.get("properties", {})
            required = t.parameters.get("required", [])
            params_desc = []
            for pname, pinfo in props.items():
                req_mark = "【必填】" if pname in required else "【可选】"
                params_desc.append(f"    - {pname}: {req_mark}{pinfo.get('description', '')}")
            params_str = "\n".join(params_desc)
            tools_desc.append(
                f"【{t.name}】\n"
                f"  功能: {t.description}\n"
                f"  参数:\n{params_str}"
            )
        return "\n\n".join(tools_desc)
    def _register_default_tools(self):
        """注册所有默认工具"""
        # 工具1：解析简历
        def parse_resume(resume_text: str, **kwargs) -> dict:
            parser = ResumeParser()
            result = parser.parse(resume_text)
            # 只返回关键字段，避免太长
            return {
                "name": result["name"],
                "education": result["education"],
                "school": result["school"],
                "major": result["major"],
                "skills": result["skills"],
                "skill_categories": list(result["skill_categories"].keys()),
                "projects": result["projects"],
                "internship": result["internship"],
                "bonus_items": result["bonus_items"],
            }
        self.register(Tool(
            name="parse_resume",
            description="解析简历文本，提取姓名、学历、技能、项目经验、实习经历等结构化信息",
            parameters={
                "type": "object",
                "properties": {
                    "resume_text": {"type": "string", "description": "简历原始文本"}
                },
                "required": ["resume_text"],
            },
            func=parse_resume,
        ))
        # 工具2：岗位匹配打分
        def match_job(resume_text: str, job_text: str, job_title: str = "", **kwargs) -> dict:
            rp = ResumeParser()
            jp = JobParser()
            sc = Screener()
            resume = rp.parse(resume_text)
            job = jp.parse(job_text, title=job_title)
            result = sc.screen(resume, job)
            return {
                "candidate": result["candidate"],
                "job_title": result["job_title"],
                "total_score": result["total_score"],
                "level": result["level"],
                "conclusion": result["conclusion"],
                "matched_skills": result["matched_skills"],
                "missing_skills": result["missing_skills"],
                "dimension_scores": {
                    k: v["score"] for k, v in result["dimensions"].items()
                },
                "suggestion": result["suggestion"],
            }
        self.register(Tool(
            name="match_job",
            description="将简历与岗位进行匹配打分，返回综合得分、评级、匹配/缺失技能、各维度分数",
            parameters={
                "type": "object",
                "properties": {
                    "resume_text": {"type": "string", "description": "简历文本"},
                    "job_text": {"type": "string", "description": "岗位描述文本"},
                    "job_title": {"type": "string", "description": "岗位名称（可选）"},
                },
                "required": ["resume_text", "job_text"],
            },
            func=match_job,
        ))
        # 工具3：RAG 知识库检索
        def rag_search(query: str, top_k: int = 5, **kwargs) -> dict:
            if not self.rag_engine:
                return {"error": "RAG 引擎未初始化"}
            results = self.rag_engine.retrieve(query, top_k=top_k)
            return {
                "query": query,
                "results_count": len(results),
                "results": [
                    {"source": r["source"], "score": r["score"], "content": r["text"][:300]}
                    for r in results
                ],
            }
        self.register(Tool(
            name="rag_search",
            description="从知识库中检索与查询相关的岗位标准、面试题库、技术参考资料",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索查询词"},
                    "top_k": {"type": "integer", "description": "返回结果数量，默认5", "default": 5},
                },
                "required": ["query"],
            },
            func=rag_search,
        ))
        # 工具4：候选人深度分析
        def analyze_candidate(resume_text: str, job_text: str, job_title: str = "", **kwargs) -> str:
            if not self.llm_client or not self.llm_client.is_ready():
                return "大模型未配置，无法进行深度分析"
            rp = ResumeParser()
            jp = JobParser()
            sc = Screener()
            resume = rp.parse(resume_text)
            job = jp.parse(job_text, title=job_title)
            result = sc.screen(resume, job)
            enhancer = LLMEnhancer(self.llm_client)
            comment = enhancer.generate_comment(resume, job, result)
            profile = enhancer.generate_profile(resume, job)
            deep = enhancer.deep_analysis(resume, job, result)
            return f"【综合评语】{comment}\n\n【候选人画像】{json.dumps(profile, ensure_ascii=False)}\n\n【深度分析】{deep}"
        self.register(Tool(
            name="analyze_candidate",
            description="调用大模型对候选人进行深度分析，生成综合评语、候选人画像、岗位适配深度分析",
            parameters={
                "type": "object",
                "properties": {
                    "resume_text": {"type": "string", "description": "简历文本"},
                    "job_text": {"type": "string", "description": "岗位描述文本"},
                    "job_title": {"type": "string", "description": "岗位名称（可选）"},
                },
                "required": ["resume_text", "job_text"],
            },
            func=analyze_candidate,
        ))
        # 工具5：生成面试问题
        def generate_questions(resume_text: str, job_text: str, job_title: str = "", **kwargs) -> list:
            if not self.llm_client or not self.llm_client.is_ready():
                return ["大模型未配置，无法生成面试问题"]
            rp = ResumeParser()
            jp = JobParser()
            sc = Screener()
            resume = rp.parse(resume_text)
            job = jp.parse(job_text, title=job_title)
            result = sc.screen(resume, job)
            enhancer = LLMEnhancer(self.llm_client)
            return enhancer.generate_interview_questions(resume, job, result)
        self.register(Tool(
            name="generate_questions",
            description="根据候选人简历和岗位要求，生成5个针对性面试问题",
            parameters={
                "type": "object",
                "properties": {
                    "resume_text": {"type": "string", "description": "简历文本"},
                    "job_text": {"type": "string", "description": "岗位描述文本"},
                    "job_title": {"type": "string", "description": "岗位名称（可选）"},
                },
                "required": ["resume_text", "job_text"],
            },
            func=generate_questions,
        ))
        # 工具6：生成筛选报告
        def generate_report(resume_text: str, job_text: str, job_title: str = "", **kwargs) -> str:
            rp = ResumeParser()
            jp = JobParser()
            sc = Screener()
            rep = Reporter()
            resume = rp.parse(resume_text)
            job = jp.parse(job_text, title=job_title)
            result = sc.screen(resume, job)
            return rep.to_text(result)
        self.register(Tool(
            name="generate_report",
            description="生成完整的筛选报告文本，包含得分、各维度分析、技能匹配、改进建议",
            parameters={
                "type": "object",
                "properties": {
                    "resume_text": {"type": "string", "description": "简历文本"},
                    "job_text": {"type": "string", "description": "岗位描述文本"},
                    "job_title": {"type": "string", "description": "岗位名称（可选）"},
                },
                "required": ["resume_text", "job_text"],
            },
            func=generate_report,
        ))
        # 工具7：计算技能匹配度
        def skill_match(resume_text: str, job_text: str, **kwargs) -> dict:
            rp = ResumeParser()
            jp = JobParser()
            resume = rp.parse(resume_text)
            job = jp.parse(job_text)
            resume_skills = set(resume["skills"])
            job_skills = set(job["required_skills"])
            matched = resume_skills & job_skills
            missing = job_skills - resume_skills
            coverage = len(matched) / len(job_skills) if job_skills else 0
            return {
                "job_required_skills": sorted(job_skills),
                "candidate_skills": sorted(resume_skills),
                "matched": sorted(matched),
                "missing": sorted(missing),
                "coverage_rate": f"{coverage:.1%}",
            }
        self.register(Tool(
            name="skill_match",
            description="详细计算简历技能与岗位要求技能的匹配度，列出匹配和缺失的技能",
            parameters={
                "type": "object",
                "properties": {
                    "resume_text": {"type": "string", "description": "简历文本"},
                    "job_text": {"type": "string", "description": "岗位描述文本"},
                },
                "required": ["resume_text", "job_text"],
            },
            func=skill_match,
        ))
