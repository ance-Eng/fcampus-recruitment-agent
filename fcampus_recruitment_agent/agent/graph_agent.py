# -*- coding: utf-8 -*-
"""
LangGraph 工作流 Agent：将简历筛选全流程编排为有向图
节点流程：
  解析简历 → 解析岗位 → 规则筛选 → (RAG检索) → (LLM增强分析) → 生成报告
条件分支：
  - 高分候选人(>=80)可跳过 LLM 深度分析
  - RAG / LLM 均可独立开关
"""
from typing import TypedDict, Optional, Dict, Any

from .resume_parser import ResumeParser
from .job_parser import JobParser
from .screener import Screener
from .reporter import Reporter
from .llm_client import LLMClient
from .llm_enhancer import LLMEnhancer
from .rag_engine import RAGEngine


# ========== 工作流状态定义 ==========
class AgentState(TypedDict):
    resume_text: str
    job_dict: dict               # 岗位原始数据（CSV行字典）
    parsed_resume: Optional[dict]
    parsed_job: Optional[dict]
    screen_result: Optional[dict]
    rag_context: Optional[str]
    rag_results: Optional[list]
    llm_analysis: Optional[dict]
    final_report: Optional[str]
    use_rag: bool
    use_llm: bool
    llm_client: Optional[object]
    rag_engine: Optional[object]
    errors: list


# ========== 节点函数 ==========
def parse_resume_node(state: AgentState) -> AgentState:
    """节点1：解析简历"""
    parser = ResumeParser()
    parsed = parser.parse(state["resume_text"])
    state["parsed_resume"] = parsed
    return state


def parse_job_node(state: AgentState) -> AgentState:
    """节点2：解析岗位"""
    parser = JobParser()
    parsed = parser.parse_csv_row(state["job_dict"])
    state["parsed_job"] = parsed
    return state


def rule_screen_node(state: AgentState) -> AgentState:
    """节点3：规则引擎筛选打分"""
    screener = Screener()
    result = screener.screen(state["parsed_resume"], state["parsed_job"])
    state["screen_result"] = result
    return state


def rag_retrieve_node(state: AgentState) -> AgentState:
    """节点4：RAG 检索相关知识库"""
    rag: RAGEngine = state.get("rag_engine")
    if rag is None:
        state["rag_context"] = ""
        state["rag_results"] = []
        return state

    resume = state["parsed_resume"]
    job = state["parsed_job"]
    # 构造检索查询：岗位名称 + 候选人技能 + 缺失技能
    query = f"{job.get('title', '')} {job.get('category', '')} " \
            f"{' '.join(resume.get('skills', []))} " \
            f"{' '.join(state['screen_result'].get('missing_skills', []))}"

    results = rag.retrieve(query, top_k=5)
    context = rag.retrieve_as_context(query, top_k=5)
    state["rag_results"] = results
    state["rag_context"] = context
    return state


def llm_enhance_node(state: AgentState) -> AgentState:
    """节点5：LLM 增强分析（结合 RAG 上下文）"""
    llm_client: LLMClient = state.get("llm_client")
    if llm_client is None or not llm_client.is_ready():
        state["llm_analysis"] = {"error": "LLM 未配置或不可用"}
        return state

    enhancer = LLMEnhancer(llm_client)
    resume = state["parsed_resume"]
    job = state["parsed_job"]
    result = state["screen_result"]
    rag_context = state.get("rag_context", "")

    # 如果有 RAG 上下文，在生成分析时注入
    analysis = enhancer.generate_all(resume, job, result)

    # 把 RAG 检索到的资料也附在分析结果里
    if rag_context:
        analysis["rag_context"] = rag_context
        analysis["rag_sources"] = list(set(
            r["source"] for r in state.get("rag_results", [])
        ))
    state["llm_analysis"] = analysis
    return state


def report_node(state: AgentState) -> AgentState:
    """节点6：生成最终报告"""
    reporter = Reporter()
    result = state["screen_result"]

    # 基础文本报告
    report = reporter.to_text(result)

    # 追加 RAG 检索来源
    if state.get("rag_results"):
        report += "\n\n【RAG 检索参考资料】\n"
        for i, r in enumerate(state["rag_results"], 1):
            report += f"{i}. [{r['source']}] (相关度 {r['score']}) {r['text'][:80]}...\n"

    # 追加 LLM 分析
    llm = state.get("llm_analysis")
    if llm and "error" not in llm:
        report += "\n\n【AI 智能评语】\n" + llm.get("comment", "")
        if llm.get("interview_questions"):
            report += "\n\n【推荐面试问题】\n"
            for i, q in enumerate(llm["interview_questions"], 1):
                report += f"{i}. {q}\n"

    state["final_report"] = report
    return state


# ========== 条件路由 ==========
def after_screen_route(state: AgentState) -> str:
    """规则筛选后路由：高分且不要求LLM则直接出报告，否则继续"""
    score = state["screen_result"]["total_score"]
    if state.get("use_rag"):
        return "rag"
    if state.get("use_llm"):
        return "llm"
    return "report"


def after_rag_route(state: AgentState) -> str:
    """RAG 检索后路由：有 LLM 则继续增强，否则直接报告"""
    if state.get("use_llm"):
        return "llm"
    return "report"


# ========== 工作流构建 ==========
def build_graph():
    """构建 LangGraph 工作流图"""
    from langgraph.graph import StateGraph, END

    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("parse_resume", parse_resume_node)
    workflow.add_node("parse_job", parse_job_node)
    workflow.add_node("rule_screen", rule_screen_node)
    workflow.add_node("rag_retrieve", rag_retrieve_node)
    workflow.add_node("llm_enhance", llm_enhance_node)
    workflow.add_node("report", report_node)

    # 设置入口
    workflow.set_entry_point("parse_resume")

    # 线性边
    workflow.add_edge("parse_resume", "parse_job")
    workflow.add_edge("parse_job", "rule_screen")

    # 条件边：筛选后决定下一步
    workflow.add_conditional_edges(
        "rule_screen",
        after_screen_route,
        {
            "rag": "rag_retrieve",
            "llm": "llm_enhance",
            "report": "report",
        },
    )

    # 条件边：RAG 后决定下一步
    workflow.add_conditional_edges(
        "rag_retrieve",
        after_rag_route,
        {
            "llm": "llm_enhance",
            "report": "report",
        },
    )

    # LLM 后到报告
    workflow.add_edge("llm_enhance", "report")
    workflow.add_edge("report", END)

    return workflow.compile()


# ========== 对外入口 ==========
class RecruitmentAgent:
    """
    校园实习招聘智能筛选 Agent（LangGraph 工作流封装）
    如果未安装 langgraph，自动降级为顺序执行
    """

    def __init__(self, llm_client: LLMClient = None, rag_engine: RAGEngine = None):
        self.llm_client = llm_client
        self.rag_engine = rag_engine
        self._graph = None
        self._langgraph_available = self._check_langgraph()

    def _check_langgraph(self) -> bool:
        try:
            import langgraph
            return True
        except ImportError:
            return False

    @property
    def backend(self) -> str:
        return "langgraph" if self._langgraph_available else "sequential(fallback)"

    def run(self, resume_text: str, job_dict: dict,
            use_rag: bool = True, use_llm: bool = True) -> AgentState:
        """
        执行完整筛选工作流
        返回最终状态（包含解析结果、筛选结果、RAG上下文、LLM分析、最终报告）
        """
        initial_state: AgentState = {
            "resume_text": resume_text,
            "job_dict": job_dict,
            "parsed_resume": None,
            "parsed_job": None,
            "screen_result": None,
            "rag_context": "",
            "rag_results": [],
            "llm_analysis": None,
            "final_report": "",
            "use_rag": use_rag and self.rag_engine is not None,
            "use_llm": use_llm and self.llm_client is not None and self.llm_client.is_ready(),
            "llm_client": self.llm_client,
            "rag_engine": self.rag_engine,
            "errors": [],
        }

        if self._langgraph_available:
            if self._graph is None:
                self._graph = build_graph()
            return self._graph.invoke(initial_state)
        else:
            return self._run_sequential(initial_state)

    def _run_sequential(self, state: AgentState) -> AgentState:
        """langgraph 不可用时的顺序执行 fallback"""
        state = parse_resume_node(state)
        state = parse_job_node(state)
        state = rule_screen_node(state)

        route = after_screen_route(state)
        if route == "rag":
            state = rag_retrieve_node(state)
            route = after_rag_route(state)
        if route == "llm":
            state = llm_enhance_node(state)

        state = report_node(state)
        return state
