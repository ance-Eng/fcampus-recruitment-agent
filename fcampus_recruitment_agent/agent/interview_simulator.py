# -*- coding: utf-8 -*-
"""
AI 面试模拟器：基于简历和岗位生成面试问题，支持多轮问答和回答评估
"""
import random


class InterviewSimulator:
    def __init__(self, llm_client=None):
        self.llm = llm_client
        self.questions = []
        self.current_idx = 0
        self.answers = []
        self.resume = {}
        self.job = {}

    def start(self, resume: dict, job: dict) -> list:
        """开始面试，生成面试问题列表"""
        self.resume = resume
        self.job = job
        self.current_idx = 0
        self.answers = []

        if self.llm and self.llm.is_ready():
            self.questions = self._generate_questions_llm(resume, job)
        else:
            self.questions = self._generate_questions_rule(resume, job)

        return self.questions

    def _generate_questions_rule(self, resume: dict, job: dict) -> list:
        """规则生成面试问题（无LLM时的降级方案）"""
        questions = []
        name = resume.get("name", "候选人")
        job_title = job.get("title", "目标岗位")
        skills = resume.get("skills", [])
        projects = resume.get("projects", [])
        missing = job.get("required_skills", [])

        # 1. 自我介绍
        questions.append({
            "type": "自我介绍",
            "question": f"你好，{name}。请先做一个简单的自我介绍，重点说说你为什么应聘{job_title}这个岗位。",
        })

        # 2. 项目经历
        if projects:
            proj = projects[0] if isinstance(projects[0], str) else projects[0].get("name", str(projects[0]))
            questions.append({
                "type": "项目经历",
                "question": f"我看到你简历里有「{proj}」这个项目，请详细说说你在其中承担了什么角色、遇到了什么难点、怎么解决的？",
            })

        # 3. 技能深挖
        if skills:
            skill = skills[0]
            questions.append({
                "type": "技术考察",
                "question": f"你提到熟悉{skill}，能说说你在实际项目中是怎么用的吗？有没有遇到过性能问题？",
            })

        # 4. 缺失技能
        if missing:
            miss = missing[0]
            questions.append({
                "type": "能力缺口",
                "question": f"这个岗位需要{miss}，但你简历里没提到相关经验，你怎么看？有没有学习计划？",
            })

        # 5. 岗位认知
        questions.append({
            "type": "岗位认知",
            "question": f"你对{job_title}这个岗位的日常工作是怎么理解的？你觉得做好这个岗位最重要的能力是什么？",
        })

        # 6. 职业规划
        questions.append({
            "type": "职业规划",
            "question": "你未来3-5年的职业规划是什么？为什么选择我们公司？",
        })

        return questions

    def _generate_questions_llm(self, resume: dict, job: dict) -> list:
        """用大模型生成面试问题"""
        prompt = f"""你是一位资深的{job.get('title', '技术')}面试官。请根据以下简历和岗位要求，生成5个面试问题。

岗位：{job.get('title', '')}
岗位要求：{', '.join(job.get('required_skills', [])[:5])}
候选人技能：{', '.join(resume.get('skills', [])[:5])}
候选人项目：{', '.join(str(p) for p in resume.get('projects', [])[:3])}

请按以下格式输出，每个问题一行：
[类型] 问题内容

问题类型包括：自我介绍、项目经历、技术考察、能力缺口、岗位认知、职业规划
"""
        try:
            resp = self.llm.chat([{"role": "user", "content": prompt}], temperature=0.7)
            text = resp.get("content", "")
            questions = []
            for line in text.strip().split("\n"):
                line = line.strip()
                if line and ("[" in line or "】" in line or "." in line[:5]):
                    q_type = "综合"
                    if "[" in line and "]" in line:
                        q_type = line[line.index("[")+1:line.index("]")]
                        line = line[line.index("]")+1:].strip()
                    elif "【" in line and "】" in line:
                        q_type = line[line.index("【")+1:line.index("】")]
                        line = line[line.index("】")+1:].strip()
                    if line:
                        questions.append({"type": q_type, "question": line})
            if questions:
                return questions[:6]
        except Exception:
            pass
        return self._generate_questions_rule(resume, job)

    def get_current_question(self) -> dict:
        """获取当前问题"""
        if self.current_idx < len(self.questions):
            q = self.questions[self.current_idx]
            return {
                "index": self.current_idx + 1,
                "total": len(self.questions),
                "type": q["type"],
                "question": q["question"],
            }
        return None

    def submit_answer(self, answer: str) -> dict:
        """提交回答，返回评估和下一个问题"""
        if not answer.strip():
            return {"error": "请输入回答内容"}

        self.answers.append({
            "question": self.questions[self.current_idx]["question"],
            "type": self.questions[self.current_idx]["type"],
            "answer": answer,
        })

        # 评估回答
        evaluation = self._evaluate_answer(answer)

        self.current_idx += 1
        next_q = self.get_current_question()

        return {
            "evaluation": evaluation,
            "next_question": next_q,
            "is_finished": next_q is None,
            "progress": f"{self.current_idx}/{len(self.questions)}",
        }

    def _evaluate_answer(self, answer: str) -> dict:
        """评估回答质量"""
        score = 0
        feedback = []

        # 长度评估
        if len(answer) < 20:
            score += 10
            feedback.append("回答过于简短，建议展开说明")
        elif len(answer) < 50:
            score += 25
            feedback.append("回答有一定内容，但可以更详细")
        elif len(answer) < 150:
            score += 45
            feedback.append("回答内容适中")
        else:
            score += 55
            feedback.append("回答内容充实")

        # 结构评估
        if any(w in answer for w in ["首先", "其次", "最后", "第一", "第二", "一方面", "另一方面"]):
            score += 15
            feedback.append("回答有条理性")
        else:
            feedback.append("建议使用分点结构，让回答更清晰")

        # 具体性评估
        if any(w in answer for w in ["具体", "例如", "比如", "实际", "项目中", "我负责", "我做了"]):
            score += 15
            feedback.append("有具体案例支撑")
        else:
            feedback.append("建议结合具体案例说明")

        # 数据/成果评估
        if any(w in answer for w in ["提升", "优化", "减少", "增加", "%", "倍", "效率"]):
            score += 15
            feedback.append("有量化成果，很好")

        score = min(100, score)

        if score >= 80:
            level = "优秀"
        elif score >= 60:
            level = "良好"
        elif score >= 40:
            level = "一般"
        else:
            level = "需要改进"

        return {
            "score": score,
            "level": level,
            "feedback": "；".join(feedback),
        }

    def get_summary(self) -> dict:
        """获取面试总结"""
        if not self.answers:
            return {"error": "尚未完成面试"}

        avg_score = sum(a.get("evaluation", {}).get("score", 0) for a in self.answers) / len(self.answers)
        avg_score = round(avg_score, 1)

        if avg_score >= 80:
            conclusion = "面试表现优秀，建议进入下一轮"
        elif avg_score >= 60:
            conclusion = "面试表现良好，可考虑录用"
        elif avg_score >= 40:
            conclusion = "面试表现一般，需进一步考察"
        else:
            conclusion = "面试表现欠佳，暂不推荐"

        return {
            "total_questions": len(self.questions),
            "answered": len(self.answers),
            "avg_score": avg_score,
            "conclusion": conclusion,
            "answers": self.answers,
        }
