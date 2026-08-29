# -*- coding: utf-8 -*-
"""
ReAct 模式自主 Agent
核心：Thought（思考）→ Action（调用工具）→ Observation（观察结果）→ 循环 → Final Answer
大模型自主决定下一步调用什么工具，而非固定流程
"""
import json
import re
import time
from typing import Dict, List, Any, Optional

from .llm_client import LLMClient
from .tool_registry import ToolRegistry
from .rag_engine import RAGEngine
from .cache_manager import CacheManager


class ReActAgent:
    """ReAct 模式自主决策 Agent"""

    def __init__(self, llm_client: LLMClient, tool_registry: ToolRegistry = None,
                 rag_engine: RAGEngine = None, cache: CacheManager = None,
                 max_iterations: int = 6):
        self.llm = llm_client
        self.rag = rag_engine
        self.cache = cache
        self.max_iterations = max_iterations
        self.tool_registry = tool_registry or ToolRegistry(
            llm_client=llm_client, rag_engine=rag_engine
        )
        self.trace: List[Dict] = []  # 记录完整思考过程

    def available(self) -> bool:
        return self.llm.is_ready()

    @property
    def backend(self) -> str:
        return "react" if self.available() else "fallback"

    def run(self, resume_text: str, job_dict: dict,
            use_rag: bool = True) -> Dict[str, Any]:
        """
        执行 ReAct 自主筛选流程
        返回：{result, trace, final_answer, iterations}
        """
        self.trace = []
        job_text = self._job_dict_to_text(job_dict)
        job_title = job_dict.get("岗位名称", job_dict.get("title", ""))

        # 如果大模型不可用，降级为顺序执行
        if not self.llm.is_ready():
            return self._fallback_run(resume_text, job_dict, use_rag)

        # 构建系统提示词
        system_prompt = self._build_system_prompt()

        # 构建初始用户消息
        user_prompt = self._build_initial_prompt(resume_text, job_text, job_title, use_rag)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        final_answer = ""
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            # 缓存检查
            cache_key = f"react:{hash(resume_text[:100])}:{job_title}:{iteration}"
            if self.cache:
                cached = self.cache.get("react", cache_key)
                if cached:
                    parsed = cached
                    self.trace.append({
                        "iteration": iteration,
                        "thought": parsed.get("thought", "(缓存)"),
                        "action": parsed.get("action", ""),
                        "observation": "(从缓存读取)",
                    })
                    if "final_answer" in parsed:
                        final_answer = parsed["final_answer"]
                        break
                    continue

            # 调用大模型
            response = self.llm.chat(
                system_prompt=system_prompt,
                user_prompt="\n\n".join([m["content"] for m in messages[1:]]),
                temperature=0.3,
                max_tokens=1500,
            )

            # 解析 LLM 输出
            parsed = self._parse_response(response)

            if not parsed:
                self.trace.append({
                    "iteration": iteration,
                    "thought": "解析失败，使用原始输出",
                    "action": "none",
                    "observation": response[:500],
                })
                final_answer = response
                break

            thought = parsed.get("thought", "")
            action = parsed.get("action", "")
            action_input = parsed.get("action_input", {})
            answer = parsed.get("final_answer", "")

            # 如果是最终答案，结束
            if answer:
                final_answer = answer
                self.trace.append({
                    "iteration": iteration,
                    "thought": thought,
                    "action": "final_answer",
                    "observation": answer[:500],
                })
                break

            # 执行工具
            self.trace.append({
                "iteration": iteration,
                "thought": thought,
                "action": action,
                "action_input": action_input,
            })

            observation = self.tool_registry.execute(action, **action_input)

            self.trace[-1]["observation"] = observation[:1000]

            # 写入缓存
            if self.cache:
                self.cache.set("react", cache_key, parsed, ttl=1800)

            # 将思考和观察加入对话历史
            messages.append({
                "role": "assistant",
                "content": json.dumps({"thought": thought, "action": action, "action_input": action_input}, ensure_ascii=False),
            })
            messages.append({
                "role": "user",
                "content": f"Observation: {observation}",
            })

        # 如果循环结束还没有最终答案，让 LLM 总结
        if not final_answer and self.trace:
            summary_prompt = (
                "基于以上工具调用结果，请给出最终的筛选结论。"
                "包括：综合得分、评级、是否推荐面试、核心优势、主要不足、改进建议。"
            )
            messages.append({"role": "user", "content": summary_prompt})
            final_answer = self.llm.chat(
                system_prompt=system_prompt,
                user_prompt="\n\n".join([m["content"] for m in messages[1:]]),
                temperature=0.3,
                max_tokens=1000,
            )

        # 从 trace 中提取筛选结果（如果调用了 match_job）
        result = self._extract_result_from_trace()

        return {
            "final_answer": final_answer,
            "trace": self.trace,
            "iterations": iteration,
            "result": result,
            "backend": self.backend,
        }

    def _build_system_prompt(self) -> str:
        tools_desc = self.tool_registry.get_system_prompt()
        return f"""你是一个专业的校园招聘筛选 Agent，采用 ReAct（Reasoning + Acting）模式自主工作。

你可以使用以下工具：
{tools_desc}

工作流程：
1. Thought：思考当前需要做什么
2. Action：选择一个工具并给出参数
3. Observation：工具返回的结果
4. 重复 1-3，直到信息足够
5. 给出 Final Answer

输出格式（必须是严格的 JSON）：
{{
  "thought": "你当前的思考",
  "action": "要调用的工具名称",
  "action_input": {{"参数名": "参数值"}}
}}

或者当你认为信息足够时，输出：
{{
  "thought": "总结思考",
  "final_answer": "最终的筛选结论，包含得分、评级、推荐意见、优势、不足、建议"
}}

规则：
- 每次只调用一个工具
- 必须先解析简历和岗位，再进行匹配
- 匹配后可以进行深度分析或生成面试问题
- 不要重复调用相同参数的工具
- final_answer 要详细、专业、有依据
- 必须输出合法 JSON，不要输出 JSON 以外的内容
"""

    def _build_initial_prompt(self, resume_text: str, job_text: str,
                              job_title: str, use_rag: bool) -> str:
        prompt = f"""请对以下候选人进行招聘筛选。

【应聘岗位】{job_title}
【岗位描述】
{job_text}

【候选人简历】
{resume_text}

请自主决定分析步骤，最终给出完整的筛选结论。
"""
        if use_rag and self.rag:
            prompt += "\n提示：你可以使用 rag_search 工具检索知识库中的岗位标准和面试题参考。"
        return prompt

    def _parse_response(self, response: str) -> Optional[dict]:
        """解析 LLM 输出，提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 块
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取第一个 { 到最后一个 }
        brace_match = re.search(r'\{.*\}', response, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        # 尝试用正则提取 thought/action/final_answer
        thought = re.search(r'"thought"\s*:\s*"([^"]*)"', response)
        action = re.search(r'"action"\s*:\s*"([^"]*)"', response)
        final = re.search(r'"final_answer"\s*:\s*"([^"]*)"', response)

        if final:
            return {"thought": thought.group(1) if thought else "", "final_answer": final.group(1)}
        if action:
            params = {}
            params_match = re.search(r'"action_input"\s*:\s*(\{.*?\})', response, re.DOTALL)
            if params_match:
                try:
                    params = json.loads(params_match.group(1))
                except json.JSONDecodeError:
                    pass
            return {
                "thought": thought.group(1) if thought else "",
                "action": action.group(1),
                "action_input": params,
            }

        return None

    def _extract_result_from_trace(self) -> dict:
        """从 trace 中提取 match_job 的结果"""
        for step in self.trace:
            if step.get("action") == "match_job" and step.get("observation"):
                try:
                    obs = step["observation"]
                    if isinstance(obs, str):
                        return json.loads(obs)
                    return obs
                except (json.JSONDecodeError, TypeError):
                    pass
        return {}

    def _fallback_run(self, resume_text: str, job_dict: dict,
                      use_rag: bool) -> dict:
        """大模型不可用时的降级执行（顺序执行）"""
        from .resume_parser import ResumeParser
        from .job_parser import JobParser
        from .screener import Screener
        from .reporter import Reporter

        rp = ResumeParser()
        jp = JobParser()
        sc = Screener()
        rep = Reporter()

        resume = rp.parse(resume_text)
        job = jp.parse_csv_row(job_dict)  # 使用CSV列直接解析
        result = sc.screen(resume, job)

        self.trace = [
            {"iteration": 1, "thought": "解析简历", "action": "parse_resume", "observation": "完成"},
            {"iteration": 2, "thought": "岗位匹配打分", "action": "match_job", "observation": "完成"},
            {"iteration": 3, "thought": "生成报告", "action": "generate_report", "observation": "完成"},
        ]

        return {
            "final_answer": rep.to_text(result),
            "trace": self.trace,
            "iterations": 3,
            "result": result,
            "backend": "fallback",
        }

    @staticmethod
    def _job_dict_to_text(job_dict: dict) -> str:
        """将岗位字典转为文本"""
        lines = []
        for k, v in job_dict.items():
            if v and str(v).strip():
                lines.append(f"{k}: {v}")
        return "\n".join(lines)
