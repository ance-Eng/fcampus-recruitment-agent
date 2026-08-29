# -*- coding: utf-8 -*-
"""
真实岗位数据获取脚本
从腾讯招聘公开 API 拉取真实岗位数据，转换成项目需要的 jobs.csv 格式
使用方式：python fetch_jobs.py
"""
import os
import re
import time
import json
import requests
import pandas as pd

# 搜索关键词（覆盖主要岗位方向）
SEARCH_KEYWORDS = [
    "Python", "Java", "前端", "后端", "测试", "运维",
    "数据", "算法", "产品", "运营", "C++", "Go",
]

# 每个关键词最多拉取页数
MAX_PAGES_PER_KEYWORD = 3
PAGE_SIZE = 10

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "jobs.csv")


def fetch_tencent_jobs(keyword: str, page: int = 1) -> list:
    """从腾讯招聘公开 API 获取岗位列表"""
    url = "https://careers.tencent.com/tencentcareer/api/post/Query"
    params = {
        "pageIndex": page,
        "pageSize": PAGE_SIZE,
        "keyword": keyword,
        "language": "zh-cn",
        "area": "cn",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://careers.tencent.com/",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()
        return data.get("Data", {}).get("Posts", [])
    except Exception as e:
        print(f"  [错误] 获取 {keyword} 第{page}页失败: {e}")
        return []


def parse_education(requirement: str) -> str:
    """从岗位要求中提取学历要求"""
    if not requirement:
        return "本科"
    req_lower = requirement.lower()
    if "博士" in requirement or "phd" in req_lower:
        return "博士"
    if "硕士" in requirement or "研究生" in requirement or "master" in req_lower:
        return "硕士"
    if "本科" in requirement or "学士" in requirement or "bachelor" in req_lower:
        return "本科"
    if "大专" in requirement or "专科" in requirement:
        return "大专"
    return "本科"


def parse_experience(requirement: str) -> str:
    """从岗位要求中提取经验要求"""
    if not requirement:
        return "不限"
    if "应届" in requirement or "毕业生" in requirement or "校招" in requirement:
        return "应届"
    match = re.search(r'(\d+)\s*[-~至]\s*(\d+)\s*年', requirement)
    if match:
        return f"{match.group(1)}-{match.group(2)}年"
    match = re.search(r'(\d+)\s*年以上', requirement)
    if match:
        return f"{match.group(1)}年以上"
    if "3年" in requirement:
        return "3年以上"
    if "5年" in requirement:
        return "5年以上"
    return "不限"


def extract_skills(text: str) -> str:
    """从职责/要求中提取技能关键词"""
    skill_patterns = [
        r'Python', r'Java', r'C\+\+', r'C#', r'Go(?:lang)?', r'Rust',
        r'JavaScript', r'TypeScript', r'Vue', r'React', r'Angular',
        r'MySQL', r'PostgreSQL', r'MongoDB', r'Redis', r'Elasticsearch',
        r'Docker', r'Kubernetes', r'K8s', r'Linux', r'Git',
        r'Spring', r'Django', r'Flask', r'FastAPI', r'MyBatis',
        r'Hadoop', r'Spark', r'Flink', r'Hive', r'Kafka',
        r'TensorFlow', r'PyTorch', r'深度学习', r'机器学习',
        r'微服务', r'分布式', r'高并发', r'微前端',
        r'自动化测试', r'性能测试', r'Selenium', r'JMeter',
        r'AWS', r'阿里云', r'腾讯云', r'华为云',
    ]
    found = []
    for pattern in skill_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            skill = pattern.replace(r'\+', '+').replace(r'(?:lang)?', '').replace(r'\s*', '')
            if skill not in found:
                found.append(skill)
    return "、".join(found[:10]) if found else "见岗位描述"


def categorize_job(title: str, keyword: str) -> str:
    """根据岗位名称和搜索关键词分类"""
    title_lower = title.lower()
    if any(w in title for w in ["测试", "QA", "质量"]):
        return "测试"
    if any(w in title for w in ["运维", "DevOps", "SRE", "基础设施"]):
        return "运维"
    if any(w in title for w in ["数据", "数据分析", "数据工程", "BI"]):
        return "数据"
    if any(w in title for w in ["算法", "AI", "机器学习", "深度学习", "NLP", "CV"]):
        return "算法"
    if any(w in title for w in ["产品", "PM", "产品经理"]):
        return "产品"
    if any(w in title for w in ["运营", "市场", "销售"]):
        return "运营"
    if any(w in title for w in ["前端", "Web", "UI", "交互"]):
        return "前端"
    if any(w in title for w in ["后端", "服务端", "开发工程师", "研发"]):
        return "后端"
    if keyword in ["Python", "Java", "C++", "Go"]:
        return "后端"
    return "其他"


def normalize_job(post: dict, keyword: str) -> dict:
    """将腾讯岗位数据转换成项目需要的格式"""
    title = post.get("RecruitPostName", "").strip()
    location = post.get("LocationName", "").strip()
    responsibility = post.get("Responsibility", "").strip()
    requirement = post.get("Requirement", "").strip()
    post_url = post.get("PostURL", "").strip()

    full_text = f"{responsibility} {requirement}"

    return {
        "岗位名称": title,
        "公司名称": "腾讯",
        "工作地点": location,
        "薪资范围": "面议",  # 腾讯API不返回薪资
        "学历要求": parse_education(requirement),
        "工作经验": parse_experience(requirement),
        "岗位描述": responsibility[:500] if responsibility else "详见投递链接",
        "技能要求": extract_skills(full_text),
        "岗位分类": categorize_job(title, keyword),
        "投递链接": post_url,
    }


def main():
    print("=" * 50)
    print("  真实岗位数据获取工具（来源：腾讯招聘公开API）")
    print("=" * 50)

    all_jobs = []
    seen_titles = set()

    for keyword in SEARCH_KEYWORDS:
        print(f"\n[搜索] {keyword}...")
        keyword_count = 0
        for page in range(1, MAX_PAGES_PER_KEYWORD + 1):
            posts = fetch_tencent_jobs(keyword, page)
            if not posts:
                break
            for post in posts:
                job = normalize_job(post, keyword)
                # 去重（按岗位名称+地点）
                dedup_key = f"{job['岗位名称']}_{job['工作地点']}"
                if dedup_key not in seen_titles and job["岗位名称"]:
                    seen_titles.add(dedup_key)
                    all_jobs.append(job)
                    keyword_count += 1
            time.sleep(0.5)  # 避免请求过快
        print(f"  获取 {keyword_count} 条（去重后）")

    print(f"\n[完成] 共获取 {len(all_jobs)} 条真实岗位数据")

    # 保存为 CSV
    df = pd.DataFrame(all_jobs)
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"[保存] 已保存到 {OUTPUT_FILE}")

    # 统计
    print("\n[统计]")
    print(f"  岗位分类分布:")
    for cat, count in df["岗位分类"].value_counts().items():
        print(f"    {cat}: {count}")
    print(f"  学历要求分布:")
    for edu, count in df["学历要求"].value_counts().items():
        print(f"    {edu}: {count}")
    print(f"  工作地点分布(前10):")
    for loc, count in df["工作地点"].value_counts().head(10).items():
        print(f"    {loc}: {count}")


if __name__ == "__main__":
    main()
