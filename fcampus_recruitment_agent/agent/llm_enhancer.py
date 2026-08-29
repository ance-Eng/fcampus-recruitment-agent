# -*- coding: utf-8 -*-
"""
LLM 增强模块：基于大模型生成智能评语、面试问题、候选人画像、深度分析等
"""
import json
from .llm_client import LLMClient


class LLMEnhancer:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def available(self) -> bool:
        return self.llm.is_ready()

    # ========== 1. 智能综合评语 ==========
    def generate_comment(self, resume: dict, job: dict, screen_result: dict) -> str:
        """生成一段自然语言的综合评价"""
        system = (
            "你是一位资深的校园招聘HR，擅长从简历和岗位匹配角度给出专业、客观的评价。"
            "请用中文回复，语气专业但不生硬，200字左右。"
        )
        user = f"""
请根据以下信息，为这位候选人写一段综合评价：

【候选人信息】
姓名：{resume.get('name')}
学历：{resume.get('education')}（{resume.get('school')}，{resume.get('major')}）
掌握技能：{', '.join(resume.get('skills', []))}
项目经验：{'; '.join(resume.get('projects', []))}
实习经历：{'; '.join(resume.get('internship', [])) or '无'}
加分项：{', '.join(resume.get('bonus_items', [])) or '无'}

【应聘岗位】
{job.get('title')}（{job.get('category')}方向）
要求技能：{', '.join(job.get('required_skills', []))}
学历要求：{job.get('education_required')}
经验要求：{job.get('experience_required')}

【匹配结果】
综合得分：{screen_result.get('total_score')}/100
评级：{screen_result.get('level')}
已匹配技能：{', '.join(screen_result.get('matched_skills', []))}
缺失技能：{', '.join(screen_result.get('missing_skills', []))}

请直接输出评价内容，不要加标题。
"""
        return self.llm.chat(system, user, temperature=0.5, max_tokens=500)

    # ========== 2. 面试问题生成 ==========
    def generate_interview_questions(self, resume: dict, job: dict, screen_result: dict) -> list:
        """生成针对性的面试问题列表"""
        system = (
            "你是一位资深技术面试官，请根据候选人简历和应聘岗位生成5个针对性面试问题。"
            "问题要覆盖：技术深度、项目经验、缺失技能考察、综合素质。"
            "只返回 JSON 数组，每个元素是一个字符串问题，不要其他文字。"
        )
        user = f"""
候选人：{resume.get('name')}，学历：{resume.get('education')}
掌握技能：{', '.join(resume.get('skills', []))}
项目：{'; '.join(resume.get('projects', []))}
实习：{'; '.join(resume.get('internship', [])) or '无'}

应聘岗位：{job.get('title')}
岗位要求技能：{', '.join(job.get('required_skills', []))}
候选人缺失技能：{', '.join(screen_result.get('missing_skills', [])) or '无'}

请生成5个面试问题，以 JSON 字符串数组格式返回，例如：
["问题1", "问题2", "问题3", "问题4", "问题5"]
"""
        result = self.llm.chat_json(system, user, temperature=0.4, max_tokens=800)
        if "error" in result:
            return [result["error"]]
        # 兼容返回 {"questions": [...]} 或直接数组
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for key in ("questions", "问题", "items"):
                if key in result and isinstance(result[key], list):
                    return result[key]
        return [str(result)]

    # ========== 3. 候选人画像 ==========
    def generate_profile(self, resume: dict, job: dict) -> dict:
        """生成候选人画像：优势、劣势、性格推测、发展潜力"""
        system = (
            "你是一位资深人才评估专家，请根据简历为候选人生成人才画像。"
            "只返回 JSON，包含以下字段："
            "strengths（优势，数组）、weaknesses（劣势，数组）、"
            "potential（发展潜力，字符串）、fit_type（适合岗位类型，字符串）、"
            "risk_points（风险提示，数组）。"
        )
        user = f"""
候选人简历摘要：
姓名：{resume.get('name')}
学历：{resume.get('education')}，学校：{resume.get('school')}，专业：{resume.get('major')}
技能：{', '.join(resume.get('skills', []))}
项目：{'; '.join(resume.get('projects', []))}
实习：{'; '.join(resume.get('internship', [])) or '无'}
加分项：{', '.join(resume.get('bonus_items', [])) or '无'}

应聘岗位方向：{job.get('category')}

请返回 JSON。
"""
        result = self.llm.chat_json(system, user, temperature=0.4, max_tokens=1000)
        if "error" in result:
            return {"error": result["error"]}
        return result

    # ========== 4. 岗位适配深度分析 ==========
    def deep_analysis(self, resume: dict, job: dict, screen_result: dict) -> str:
        """生成深度岗位适配分析报告"""
        system = (
            "你是一位资深招聘顾问，请对候选人与岗位的适配度进行深度分析。"
            "用中文回复，分点论述，300字左右。"
        )
        user = f"""
请深度分析以下候选人与岗位的适配度：

【候选人】
{resume.get('name')}，{resume.get('education')}，{resume.get('school')}
技能：{', '.join(resume.get('skills', []))}
项目经验：{'; '.join(resume.get('projects', []))}
实习：{'; '.join(resume.get('internship', [])) or '无'}

【岗位】
{job.get('title')}，{job.get('location')}，{job.get('salary')}
要求：{', '.join(job.get('required_skills', []))}
学历要求：{job.get('education_required')}，经验要求：{job.get('experience_required')}

【初步匹配】
得分：{screen_result.get('total_score')}，评级：{screen_result.get('level')}
匹配技能：{', '.join(screen_result.get('matched_skills', []))}
缺失技能：{', '.join(screen_result.get('missing_skills', []))}

请从以下角度分析：
1. 技能匹配深度（不仅是有没有，而是熟练度推测）
2. 项目经验与岗位的相关性
3. 学习能力和成长潜力
4. 可能存在的风险或不足
5. 总体录用建议

直接输出分析内容。
"""
        return self.llm.chat(system, user, temperature=0.4, max_tokens=1000)

    # ========== 5. 简历优化建议 ==========
    def resume_optimization(self, resume: dict, job: dict) -> list:
        """给出简历优化建议列表"""
        system = (
            "你是一位简历优化专家，请针对目标岗位给出简历改进建议。"
            "只返回 JSON 字符串数组，每条建议简洁具体。"
        )
        user = f"""
候选人当前简历提取信息：
技能：{', '.join(resume.get('skills', []))}
项目：{'; '.join(resume.get('projects', []))}
实习：{'; '.join(resume.get('internship', [])) or '无'}
学历：{resume.get('education')}

目标岗位：{job.get('title')}
岗位要求：{', '.join(job.get('required_skills', []))}

请给出5条具体的简历优化建议，以 JSON 字符串数组返回。
"""
        result = self.llm.chat_json(system, user, temperature=0.4, max_tokens=600)
        if "error" in result:
            return [result["error"]]
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for key in ("suggestions", "建议", "items"):
                if key in result and isinstance(result[key], list):
                    return result[key]
        return [str(result)]

    # ========== 6. 薪资建议 ==========
    def salary_suggestion(self, resume: dict, job: dict) -> str:
        """根据候选人背景和岗位给出薪资谈判建议"""
        system = (
            "你是一位薪酬顾问，请根据候选人背景和岗位信息给出合理的薪资范围建议。"
            "用中文回复，150字左右，要给出具体数字范围和谈判策略。"
        )
        user = f"""
候选人：{resume.get('name')}
学历：{resume.get('education')}，学校：{resume.get('school')}
技能：{', '.join(resume.get('skills', []))}
项目/实习：{'; '.join(resume.get('projects', []) + resume.get('internship', []))}
加分项：{', '.join(resume.get('bonus_items', [])) or '无'}

岗位：{job.get('title')}，地点：{job.get('location')}
岗位标注薪资：{job.get('salary')}

请给出薪资建议和谈判策略。
"""
        return self.llm.chat(system, user, temperature=0.4, max_tokens=400)

    # ========== 7. 简历智能改写 ==========
    def rewrite_resume(self, resume_text: str, resume: dict, job: dict) -> str:
        """基于目标岗位智能改写简历，突出匹配点，优化表述"""
        system = (
            "你是一位资深简历优化专家，请根据目标岗位要求改写候选人简历。"
            "要求：1. 保留真实信息，不虚构经历；2. 突出与目标岗位匹配的技能和项目；"
            "3. 使用专业术语和量化表述；4. 结构清晰，分模块呈现；5. 用中文回复。"
            "直接输出改写后的简历全文，不要加解释说明。"
        )
        user = f"""
【目标岗位】
{job.get('title')}（{job.get('category')}方向）
要求技能：{', '.join(job.get('required_skills', []))}
学历要求：{job.get('education_required')}
经验要求：{job.get('experience_required')}

【候选人原始简历】
{resume_text}

【简历解析摘要】
姓名：{resume.get('name')}
学历：{resume.get('education')}，学校：{resume.get('school')}，专业：{resume.get('major')}
已掌握技能：{', '.join(resume.get('skills', []))}
项目经验：{'; '.join(resume.get('projects', []))}
实习经历：{'; '.join(resume.get('internship', [])) or '无'}

请基于以上信息改写简历，使其更匹配目标岗位。直接输出改写后的完整简历。
"""
        return self.llm.chat(system, user, temperature=0.5, max_tokens=2000)

    # ========== 8. 一键生成全部增强内容 ==========
    def generate_all(self, resume: dict, job: dict, screen_result: dict) -> dict:
        """一次性生成所有 LLM 增强内容"""
        return {
            "comment": self.generate_comment(resume, job, screen_result),
            "interview_questions": self.generate_interview_questions(resume, job, screen_result),
            "profile": self.generate_profile(resume, job),
            "deep_analysis": self.deep_analysis(resume, job, screen_result),
            "resume_optimization": self.resume_optimization(resume, job),
            "salary_suggestion": self.salary_suggestion(resume, job),
        }
