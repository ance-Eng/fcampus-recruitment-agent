# -*- coding: utf-8 -*-
"""
岗位解析器：从岗位文本/CSV行中提取岗位名称、要求技能、学历要求、经验要求
"""
import re
from config import SKILL_DICT, EDUCATION_LEVEL, JOB_CATEGORY_MAP


class JobParser:
    def __init__(self):
        self.all_skills = set()
        for skills in SKILL_DICT.values():
            for s in skills:
                self.all_skills.add(s.lower())

    def parse(self, job_text: str, title: str = "") -> dict:
        """解析岗位描述，返回结构化信息"""
        text = (title + " " + job_text).strip()
        text_lower = text.lower()

        result = {
            "title": title or self._extract_title(text),
            "category": self._detect_category(title or text),
            "required_skills": self._extract_required_skills(text_lower),
            "education_required": self._extract_education(text),
            "education_level": self._get_education_level(text),
            "experience_required": self._extract_experience(text),
            "salary": self._extract_salary(text),
            "location": self._extract_location(text),
            "raw_text": job_text,
        }
        return result

    def parse_csv_row(self, row: dict) -> dict:
        """从 CSV 行（字典）解析岗位，优先使用 CSV 已有列"""
        title = str(row.get("岗位名称", row.get("title", ""))).strip()
        desc = str(row.get("岗位描述", row.get("description", row.get("要求", "")))).strip()

        # 优先使用 CSV 列中的分类、学历、经验、薪资、地点
        category_raw = str(row.get("岗位分类", row.get("category", ""))).strip()
        education_raw = str(row.get("学历要求", row.get("education", ""))).strip()
        experience_raw = str(row.get("工作经验", row.get("experience", ""))).strip()
        salary_raw = str(row.get("薪资范围", row.get("salary", ""))).strip()
        location_raw = str(row.get("工作地点", row.get("location", ""))).strip()
        skills_raw = str(row.get("技能要求", row.get("skills", ""))).strip()

        # 把其他字段拼进文本用于技能提取
        extra = " ".join([
            str(row.get(k, "")) for k in row.keys()
            if k not in ("岗位名称", "title", "岗位描述", "description", "要求")
        ])
        full_text = (desc + " " + extra).strip()
        text_lower = full_text.lower()

        # 分类：优先用CSV列，否则从文本检测
        category = category_raw if category_raw and category_raw != "nan" else self._detect_category(title or full_text)

        # 学历：优先用CSV列
        if education_raw and education_raw != "nan":
            education_required = education_raw
            education_level = EDUCATION_LEVEL.get(education_raw, 2)
        else:
            education_required = self._extract_education(full_text)
            education_level = self._get_education_level(full_text)

        # 经验：优先用CSV列
        experience_required = experience_raw if experience_raw and experience_raw != "nan" else self._extract_experience(full_text)

        # 薪资：优先用CSV列
        salary = salary_raw if salary_raw and salary_raw != "nan" else self._extract_salary(full_text)

        # 地点：优先用CSV列
        location = location_raw if location_raw and location_raw != "nan" else self._extract_location(full_text)

        # 技能：CSV列技能 + 从文本提取的技能，合并去重
        csv_skills = []
        if skills_raw and skills_raw != "nan" and skills_raw != "见岗位描述":
            csv_skills = [s.strip().lower() for s in re.split(r'[、,，/]', skills_raw) if s.strip()]
        text_skills = self._extract_required_skills(text_lower)
        # 合并：CSV技能优先，文本提取补充
        required_skills = list(dict.fromkeys(csv_skills + text_skills))

        return {
            "title": title or "未知岗位",
            "category": category,
            "required_skills": required_skills,
            "education_required": education_required,
            "education_level": education_level,
            "experience_required": experience_required,
            "salary": salary,
            "location": location,
            "raw_text": full_text,
        }

    def _extract_title(self, text: str) -> str:
        first_line = text.split("\n")[0].strip()
        return first_line[:30] if first_line else "未知岗位"

    def _detect_category(self, text: str) -> str:
        text_lower = text.lower()
        for keyword, category in JOB_CATEGORY_MAP.items():
            if keyword in text_lower:
                return category
        return "通用"

    def _extract_required_skills(self, text_lower: str) -> list:
        found = set()
        for skill in self.all_skills:
            pattern = r"(?<![a-zA-Z])" + re.escape(skill) + r"(?![a-zA-Z])"
            if re.search(pattern, text_lower):
                found.add(skill)
        return sorted(found)

    def _extract_education(self, text: str) -> str:
        for edu in ["博士", "硕士", "研究生", "本科", "学士", "大专", "专科"]:
            if edu in text:
                return edu
        return "本科"  # 默认本科

    def _get_education_level(self, text: str) -> int:
        edu = self._extract_education(text)
        return EDUCATION_LEVEL.get(edu, 2)

    def _extract_experience(self, text: str) -> str:
        m = re.search(r"(\d+)\s*[-~到]\s*(\d+)\s*年", text)
        if m:
            return f"{m.group(1)}-{m.group(2)}年"
        m = re.search(r"(\d+)\s*年以上", text)
        if m:
            return f"{m.group(1)}年以上"
        if "应届" in text or "在校生" in text or "实习" in text:
            return "应届/在校生"
        return "不限"

    def _extract_salary(self, text: str) -> str:
        m = re.search(r"(\d+)[-~](\d+)\s*[kK千]", text)
        if m:
            return f"{m.group(1)}-{m.group(2)}K"
        m = re.search(r"(\d+)\s*[kK千]", text)
        if m:
            return f"{m.group(1)}K"
        return "面议"

    def _extract_location(self, text: str) -> str:
        cities = ["北京", "上海", "广州", "深圳", "杭州", "南京", "成都",
                  "武汉", "西安", "重庆", "苏州", "天津", "长沙", "郑州",
                  "哈尔滨", "长春", "沈阳", "大连", "青岛", "厦门"]
        for city in cities:
            if city in text:
                return city
        return "未知"
