# -*- coding: utf-8 -*-
"""
智能筛选核心：将简历与岗位进行多维度匹配打分，给出匹配结论和理由
"""
from config import WEIGHTS, SKILL_DICT, CATEGORY_ALIAS


class Screener:
    def __init__(self):
        self.weights = WEIGHTS

    def screen(self, resume: dict, job: dict) -> dict:
        """
        执行筛选，返回包含各维度得分、总分、结论、理由的字典
        """
        # 1. 技能匹配
        skill_score, skill_detail = self._score_skills(resume, job)

        # 2. 学历匹配
        edu_score, edu_detail = self._score_education(resume, job)

        # 3. 经验/项目匹配
        exp_score, exp_detail = self._score_experience(resume, job)

        # 4. 加分项
        bonus_score, bonus_detail = self._score_bonus(resume)

        # 加权总分
        total = (
            skill_score * self.weights["skill"] / 100
            + edu_score * self.weights["education"] / 100
            + exp_score * self.weights["experience"] / 100
            + bonus_score * self.weights["bonus"] / 100
        )
        total = round(total, 1)

        # 结论
        conclusion, level = self._conclude(total)

        return {
            "candidate": resume.get("name", "未知"),
            "job_title": job.get("title", "未知岗位"),
            "job_category": job.get("category", "通用"),
            "total_score": total,
            "level": level,
            "conclusion": conclusion,
            "dimensions": {
                "skill": {"score": skill_score, "detail": skill_detail},
                "education": {"score": edu_score, "detail": edu_detail},
                "experience": {"score": exp_score, "detail": exp_detail},
                "bonus": {"score": bonus_score, "detail": bonus_detail},
            },
            "matched_skills": skill_detail.get("matched", []),
            "missing_skills": skill_detail.get("missing", []),
            "suggestion": self._generate_suggestion(resume, job, skill_detail),
        }

    # ---------- 技能匹配 ----------
    def _score_skills(self, resume: dict, job: dict):
        required = set(job.get("required_skills", []))
        has = set(resume.get("skills", []))

        # 如果岗位技能要求太少（<5个），合并行业技能库，避免漏匹配
        category = job.get("category", "通用")
        dict_key = CATEGORY_ALIAS.get(category, category)
        category_skills = set(SKILL_DICT.get(dict_key, []))
        if len(required) < 5 and category_skills:
            required = required | category_skills

        if not required:
            return 50.0, {"matched": [], "missing": [], "note": "岗位无技能要求，给50分"}

        matched = required & has
        missing = required - has
        coverage = len(matched) / len(required) if required else 1.0
        score = round(coverage * 100, 1)

        detail = {
            "matched": sorted(matched),
            "missing": sorted(missing)[:10],
            "note": f"岗位要求 {len(required)} 项技能，候选人具备 {len(matched)} 项",
        }
        return score, detail

    # ---------- 学历匹配 ----------
    def _score_education(self, resume: dict, job: dict):
        r_level = resume.get("education_level", 0)
        j_level = job.get("education_level", 2)
        r_edu = resume.get("education", "未知")
        j_edu = job.get("education_required", "本科")

        if r_level >= j_level:
            score = 100.0
            note = f"候选人学历（{r_edu}）满足岗位要求（{j_edu}）"
        elif r_level == j_level - 1:
            score = 60.0
            note = f"候选人学历（{r_edu}）略低于岗位要求（{j_edu}），可考虑"
        else:
            score = 30.0
            note = f"候选人学历（{r_edu}）不满足岗位要求（{j_edu}）"
        return score, {"note": note, "resume_edu": r_edu, "job_edu": j_edu}

    # ---------- 经验/项目匹配 ----------
    def _score_experience(self, resume: dict, job: dict):
        projects = resume.get("projects", [])
        internships = resume.get("internship", [])
        job_exp = job.get("experience_required", "不限")

        score = 30.0  # 基础分降低，避免无关经验也高分
        notes = []

        # 收集岗位相关关键词，用于判断经验相关性
        category = job.get("category", "通用")
        dict_key = CATEGORY_ALIAS.get(category, category)
        job_keywords = set(job.get("required_skills", [])) | set(SKILL_DICT.get(dict_key, []))
        # 过滤掉过于通用的词，避免误判（如"管理"匹配"学生管理系统"）
        GENERIC_WORDS = {"管理", "系统", "开发", "设计", "工程", "技术", "应用", "服务", "平台", "项目", "工作", "专业", "相关", "能力", "经验"}
        job_keywords = {kw for kw in job_keywords if kw.lower() not in GENERIC_WORDS and len(kw) > 1}
        # 把项目和实习文本拼起来检查相关性
        exp_text = " ".join(str(p) for p in projects) + " " + " ".join(str(i) for i in internships)
        exp_text_lower = exp_text.lower()
        relevant_count = sum(1 for kw in job_keywords if kw.lower() in exp_text_lower)
        has_relevant = relevant_count > 0

        if projects and projects != ["未提取到明确项目"]:
            if has_relevant:
                score += 35
                notes.append(f"有 {len(projects)} 个项目，其中 {relevant_count} 项与岗位相关")
            else:
                score += 15
                notes.append(f"有 {len(projects)} 个项目，但与岗位方向关联度低")
        else:
            notes.append("未提取到明确项目经验")

        if internships:
            if has_relevant:
                score += 35
                notes.append(f"有 {len(internships)} 段实习，与岗位方向匹配")
            else:
                score += 15
                notes.append(f"有 {len(internships)} 段实习，但与岗位方向关联度低")
        else:
            notes.append("无实习经历")

        # 完全没有相关经验的惩罚
        if not has_relevant and not projects and not internships:
            score = max(20, score - 10)
            notes.append("无相关项目或实习经历")

        # 岗位要求经验年限
        if "应届" in job_exp or "在校生" in job_exp or "不限" in job_exp:
            score = min(100, score)
            notes.append("岗位接受应届生/在校生")
        elif "年以上" in job_exp:
            score = max(20, score - 20)
            notes.append(f"岗位要求{job_exp}，在校生可能不满足")

        score = min(100, round(score, 1))
        return score, {"note": "；".join(notes), "projects": projects, "internships": internships}

    # ---------- 加分项 ----------
    def _score_bonus(self, resume: dict):
        bonus = resume.get("bonus_items", [])
        if not bonus:
            return 50.0, {"note": "无明显加分项", "items": []}
        # 每个加分项加10分，上限100
        score = min(100, 50 + len(bonus) * 10)
        return round(score, 1), {"note": f"具备 {len(bonus)} 项加分要素", "items": bonus}

    # ---------- 结论 ----------
    def _conclude(self, total: float):
        if total >= 80:
            return "强烈推荐，候选人与岗位高度匹配，建议优先面试", "A 强烈推荐"
        elif total >= 65:
            return "比较匹配，建议进入面试环节进一步考察", "B 推荐"
        elif total >= 50:
            return "基本匹配，部分能力有欠缺，可作为备选", "C 备选"
        else:
            return "匹配度较低，不建议进入下一轮", "D 不推荐"

    # ---------- 改进建议 ----------
    def _generate_suggestion(self, resume: dict, job: dict, skill_detail: dict) -> str:
        matched = skill_detail.get("matched", [])
        missing = skill_detail.get("missing", [])
        suggestions = []
        if not matched and missing:
            suggestions.append(f"岗位核心技能均未匹配，差距较大，建议优先学习：{', '.join(missing[:5])}")
        elif missing:
            suggestions.append(f"建议补充学习：{', '.join(missing[:5])}")
        if not resume.get("internship"):
            suggestions.append("建议增加相关实习经历")
        if resume.get("education_level", 0) < job.get("education_level", 2):
            suggestions.append("学历未达标，可考虑提升学历或寻找学历要求更宽松的岗位")
        if not suggestions:
            suggestions.append("候选人整体条件较好，保持现有优势即可")
        return "；".join(suggestions)
