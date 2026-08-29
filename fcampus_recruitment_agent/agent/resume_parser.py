# -*- coding: utf-8 -*-
"""
简历解析器：从纯文本简历中提取姓名、学历、技能、项目经验、加分项
"""
import re
import jieba
from config import SKILL_DICT, EDUCATION_LEVEL, BONUS_KEYWORDS


class ResumeParser:
    def __init__(self):
        # 把所有技能词合并，用于匹配
        self.all_skills = set()
        for skills in SKILL_DICT.values():
            for s in skills:
                self.all_skills.add(s.lower())
        # 把多词技能加入 jieba 词典，避免被切散
        for s in self.all_skills:
            if len(s) > 1:
                jieba.add_word(s.lower())

    def parse(self, text: str) -> dict:
        """解析简历文本，返回结构化信息"""
        text = text.strip()
        text_lower = text.lower()

        result = {
            "name": self._extract_name(text),
            "education": self._extract_education(text),
            "education_level": self._get_education_level(text),
            "school": self._extract_school(text),
            "major": self._extract_major(text),
            "skills": self._extract_skills(text_lower),
            "skill_categories": self._match_skill_categories(text_lower),
            "projects": self._extract_projects(text),
            "internship": self._extract_internship(text),
            "bonus_items": self._extract_bonus(text),
            "certificates": self._extract_certificates(text),
            "awards": self._extract_awards(text),
            "raw_text": text,
        }
        return result

    # ---------- 姓名 ----------
    def _extract_name(self, text: str) -> str:
        # 常见简历开头 "姓名：张三" 或第一行就是名字
        m = re.search(r"姓\s*名[：:]\s*([\u4e00-\u9fa5]{2,4})", text)
        if m:
            return m.group(1)
        # 取第一行非空内容
        first_line = text.split("\n")[0].strip()
        if 2 <= len(first_line) <= 4 and re.match(r"^[\u4e00-\u9fa5]+$", first_line):
            return first_line
        return "未知"

    # ---------- 学历 ----------
    def _extract_education(self, text: str) -> str:
        for edu in ["博士", "硕士", "研究生", "本科", "学士", "大专", "专科"]:
            if edu in text:
                return edu
        return "未知"

    def _get_education_level(self, text: str) -> int:
        edu = self._extract_education(text)
        return EDUCATION_LEVEL.get(edu, 0)

    # ---------- 学校 ----------
    def _extract_school(self, text: str) -> str:
        m = re.search(r"([\u4e00-\u9fa5]{2,15}(大学|学院|学校))", text)
        return m.group(1) if m else "未知"

    # ---------- 专业 ----------
    def _extract_major(self, text: str) -> str:
        m = re.search(r"专\s*业[：:]\s*([\u4e00-\u9fa5A-Za-z]{2,20})", text)
        if m:
            return m.group(1)
        return "未知"

    # ---------- 技能 ----------
    def _extract_skills(self, text_lower: str) -> list:
        found = set()
        for skill in self.all_skills:
            # 用边界匹配，避免 "java" 匹配到 "javascript"
            pattern = r"(?<![a-zA-Z])" + re.escape(skill) + r"(?![a-zA-Z])"
            if re.search(pattern, text_lower):
                found.add(skill)
        return sorted(found)

    def _match_skill_categories(self, text_lower: str) -> dict:
        """返回每个方向匹配到的技能数量"""
        result = {}
        for category, skills in SKILL_DICT.items():
            count = 0
            matched = []
            for s in skills:
                pattern = r"(?<![a-zA-Z])" + re.escape(s) + r"(?![a-zA-Z])"
                if re.search(pattern, text_lower):
                    count += 1
                    matched.append(s)
            if count > 0:
                result[category] = {"count": count, "skills": matched}
        return result

    # ---------- 项目经验 ----------
    def _extract_projects(self, text: str) -> list:
        projects = []
        sections = re.split(r"(项目经历|项目经验|项目实践|科研项目)", text)
        for i in range(1, len(sections), 2):
            if i + 1 < len(sections):
                block = sections[i] + sections[i + 1]
                lines = [l.strip() for l in block.split("\n") if l.strip()]
                # 第一行可能是"项目经历：项目名"格式，先提取冒号后的内容
                if lines:
                    first = lines[0]
                    m = re.search(r"[：:]\s*(.+)", first)
                    if m and len(m.group(1).strip()) > 2:
                        projects.append(m.group(1).strip()[:40])
                        continue
                # 否则从后续行找项目标题
                for line in lines[1:6]:
                    if len(line) > 3 and not line.startswith(("负责", "使用", "实现", "完成", "参与", "实习", "工作")):
                        projects.append(line[:40])
                        break
        return projects if projects else ["未提取到明确项目"]

    # ---------- 实习经历 ----------
    def _extract_internship(self, text: str) -> list:
        internships = []
        sections = re.split(r"(实习经历|工作经历|实践经历)", text)
        for i in range(1, len(sections), 2):
            if i + 1 < len(sections):
                block = sections[i] + sections[i + 1]
                lines = [l.strip() for l in block.split("\n") if l.strip()]
                if lines:
                    first = lines[0]
                    m = re.search(r"[：:]\s*(.+)", first)
                    if m and len(m.group(1).strip()) > 2:
                        internships.append(m.group(1).strip()[:40])
                        continue
                for line in lines[1:5]:
                    if len(line) > 3 and not line.startswith(("项目", "技能", "证书", "获奖", "教育")):
                        internships.append(line[:40])
                        break
        return internships

    # ---------- 加分项 ----------
    def _extract_bonus(self, text: str) -> list:
        found = []
        for kw in BONUS_KEYWORDS:
            if kw in text:
                found.append(kw)
        return found

    # ---------- 证书 ----------
    def _extract_certificates(self, text: str) -> list:
        cert_patterns = [
            r"(?:证书|资格证|执业证|等级证)[：:]\s*([^\n，。；]+)",
            r"(CET[-\s]?[46]|四六级|英语[四6]级)",
            r"(计算机二级|计算机三级|计算机四级)",
            r"(教师资格证|护士执业证|医师资格证|法律职业资格|CPA|CFA|FRM|PMP|HCIA|HCIP|HCIE|CCNA|CCNP|CCIE|软考)",
            r"(初级会计|中级会计|注册会计师|银行从业|证券从业|基金从业)",
        ]
        found = set()
        for pattern in cert_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                if isinstance(m, tuple):
                    m = m[0]
                m = m.strip().strip("，。；、")
                if m and len(m) < 30:
                    found.add(m)
        return sorted(found)

    # ---------- 获奖 ----------
    def _extract_awards(self, text: str) -> list:
        award_patterns = [
            r"(?:奖学金|获奖|荣誉|奖项)[：:]\s*([^\n，。；]+)",
            r"(国家奖学金|国家励志奖学金|一等奖学金|二等奖学金|三等奖学金)",
            r"(优秀学生干部|三好学生|优秀毕业生|优秀团员)",
            r"获[得取]?\s*([^\n，。；：]{2,20}(?:奖|荣誉|冠军|亚军|季军|一等奖|二等奖|三等奖))",
        ]
        found = set()
        for pattern in award_patterns:
            matches = re.findall(pattern, text)
            for m in matches:
                if isinstance(m, tuple):
                    m = m[0]
                m = m.strip().strip("，。；、：")
                # 过滤掉包含"奖："这种不完整匹配
                if "：" in m or ":" in m:
                    continue
                if m and len(m) < 40 and len(m) > 2:
                    found.add(m)
        return sorted(found)
