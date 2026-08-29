# -*- coding: utf-8 -*-
"""
多轮对话 Agent：基于筛选结果和 RAG 知识库，与 HR 进行多轮对话
无状态设计：对话历史由调用方（app.py session_state）管理，Agent 只负责生成回复
"""
from typing import List, Dict, Optional
from .llm_client import LLMClient
from .rag_engine import RAGEngine
from .cache_manager import CacheManager


class ChatAgent:
    def __init__(self, llm_client: LLMClient, rag_engine: RAGEngine = None,
                 cache: CacheManager = None):
        self.llm = llm_client
        self.rag = rag_engine
        self.cache = cache

    def available(self) -> bool:
        return self.llm.is_ready()

    def build_system_prompt(self, resume: dict, job: dict,
                            screen_result: dict, rag_context: str = "") -> str:
        """构建系统提示词"""
        context = f"""你是一位资深校园招聘顾问，正在协助 HR 进行候选人筛选。
请基于以下信息回答 HR 的问题，回答要专业、客观、有依据。

【候选人信息】
姓名：{resume.get('name')}
学历：{resume.get('education')}（{resume.get('school')}，{resume.get('major')}）
掌握技能：{', '.join(resume.get('skills', []))}
项目经验：{'; '.join(resume.get('projects', []))}
实习经历：{'; '.join(resume.get('internship', [])) or '无'}
加分项：{', '.join(resume.get('bonus_items', [])) or '无'}

【应聘岗位】
{job.get('title')}（{job.get('category')}方向）
地点：{job.get('location')}，薪资：{job.get('salary')}
要求技能：{', '.join(job.get('required_skills', []))}
学历要求：{job.get('education_required')}，经验要求：{job.get('experience_required')}

【筛选结果】
综合得分：{screen_result.get('total_score')}/100
评级：{screen_result.get('level')}
结论：{screen_result.get('conclusion')}
已匹配技能：{', '.join(screen_result.get('matched_skills', []))}
缺失技能：{', '.join(screen_result.get('missing_skills', [])) or '无'}
"""
        if rag_context:
            context += f"\n【知识库参考资料】\n{rag_context[:2000]}\n"

        context += """
回答规则：
1. 基于以上信息回答，不要编造不存在的事实
2. 如果信息不足，明确说明并给出建议
3. 涉及技术问题时，结合知识库资料回答
4. 回答简洁专业，分点论述
"""
        return context

    def chat(self, system_prompt: str, conversation_history: List[Dict],
             user_message: str) -> str:
        """
        发送一条消息，获取回复
        Args:
            system_prompt: 系统提示词（包含候选人、岗位、筛选结果）
            conversation_history: 之前的对话历史 [{"role": "user"/"assistant", "content": "..."}]
            user_message: 当前用户消息
        """
        if not self.llm.is_ready():
            return "大模型未配置，无法对话。请先在侧边栏配置 API Key。"

        # RAG 增强
        rag_supplement = ""
        if self.rag:
            try:
                results = self.rag.retrieve(user_message, top_k=3)
                if results:
                    rag_supplement = "\n\n【知识库参考】\n" + "\n".join(
                        [f"- [{r['source']}] {r['text'][:150]}" for r in results]
                    )
            except Exception:
                pass

        # 构建完整消息列表
        messages = [{"role": "system", "content": system_prompt}]
        for msg in conversation_history:
            messages.append(msg)
        augmented_user = user_message + rag_supplement if rag_supplement else user_message
        messages.append({"role": "user", "content": augmented_user})

        # 缓存检查
        cache_key = f"chat:{hash(system_prompt[:100])}:{len(conversation_history)}:{user_message}"
        if self.cache:
            cached = self.cache.get("chat", cache_key)
            if cached:
                return cached

        # 调用 LLM
        try:
            response = self.llm.chat(
                system_prompt=system_prompt,
                user_prompt="\n\n".join([
                    f"{m['role']}: {m['content']}" for m in messages[1:]
                ]),
                temperature=0.4,
                max_tokens=1000,
            )
        except Exception as e:
            response = f"对话出错：{str(e)}"

        # 写入缓存
        if self.cache and not response.startswith("对话出错"):
            self.cache.set("chat", cache_key, response, ttl=1800)

        return response

    def get_welcome_message(self, resume: dict, job: dict, screen_result: dict) -> str:
        return (
            f"你好！我是招聘顾问助手。\n\n"
            f"当前候选人 **{resume.get('name')}** 应聘 **{job.get('title')}**，"
            f"综合得分 **{screen_result.get('total_score')}** 分（{screen_result.get('level')}）。\n\n"
            f"你可以问我：\n"
            f"- 这个候选人有什么风险？\n"
            f"- 面试应该重点考察什么？\n"
            f"- 和其他候选人比怎么样？\n"
            f"- 这个岗位的核心要求是什么？\n"
            f"- 要不要给面试机会？\n\n"
            f"请随时提问。"
        )
