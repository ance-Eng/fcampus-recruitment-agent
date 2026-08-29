# -*- coding: utf-8 -*-
"""
岗位数据清洗脚本
将从腾讯API拉取的原始岗位数据清洗成规范格式
使用方式：python clean_jobs.py
"""
import os
import re
import pandas as pd

INPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "jobs.csv")
OUTPUT_FILE = INPUT_FILE  # 覆盖原文件


def clean_title(title: str) -> str:
    """清洗岗位名称：去掉部门前缀、游戏名、地点、方向后缀"""
    if not title:
        return title

    # 1. 去掉部门/产品线前缀（"XXX-" 或 "XXX——"）
    # 常见前缀模式：部门名-岗位名
    title = re.sub(r'^[\u4e00-\u9fa5A-Za-z0-9]{2,15}[-—–]\s*', '', title)

    # 2. 去掉游戏名称（《XXX》或 XXX手游/XXX-）
    title = re.sub(r'《[^》]+》', '', title)
    title = re.sub(r'[\u4e00-\u9fa5A-Za-z0-9]{2,10}(?:手游|端游|网游)[-—–]?\s*', '', title)

    # 3. 去掉地点后缀（括号内的城市名）
    title = re.sub(r'[（(][\u4e00-\u9fa5/、,，\s]+[）)]', '', title)

    # 4. 去掉方向后缀（-XXX方向 / -XXX方向）
    title = re.sub(r'[-—–]\s*[\u4e00-\u9fa5A-Za-z]{2,10}\s*方向\s*$', '', title)

    # 5. 去掉"新星引力计划"等招聘计划名
    title = re.sub(r'[-—–]?\s*新星引力计划\s*$', '', title)
    title = re.sub(r'[-—–]?\s*顶尖应届\s*', '', title)

    # 6. 去掉"（数据飞轮）"等括号备注
    title = re.sub(r'[（(][^）)]{2,15}[）)]', '', title)

    # 7. 去掉多余的空格和连字符
    title = re.sub(r'\s+', ' ', title).strip()
    title = re.sub(r'[-—–]\s*$', '', title).strip()

    # 8. 统一常见岗位名称
    title = title.replace('TA', '技术美术')
    title = title.replace('TD', '技术导演')
    title = title.replace('infra', '基础架构')
    title = title.replace('Infra', '基础架构')
    title = title.replace('NLP', '自然语言处理')
    title = title.replace('CV', '计算机视觉')

    return title.strip()


def normalize_title(title: str) -> str:
    """将清洗后的岗位名称规范化，保留岗位特色但去掉混乱前缀"""
    title_lower = title.lower()

    # 算法类 - 保留方向
    if '推荐算法' in title or ('推荐' in title and '算法' in title):
        return '推荐算法工程师'
    if '大模型' in title or 'LLM' in title_lower or '大语言模型' in title:
        if '推理' in title or '部署' in title:
            return '大模型推理优化工程师'
        if '数据' in title or '训练' in title:
            return '大模型训练工程师'
        return '大模型算法工程师'
    if 'NLP' in title or '自然语言' in title:
        return 'NLP算法工程师'
    if 'CV' in title or '计算机视觉' in title or '图像' in title:
        return 'CV算法工程师'
    if '搜索' in title and '算法' in title:
        return '搜索算法工程师'
    if '算法' in title or '机器学习' in title or '深度学习' in title:
        if '游戏' in title:
            return '游戏AI算法工程师'
        if '安全' in title or '风控' in title:
            return '风控算法工程师'
        return '算法工程师'

    # 数据类
    if '数据工程' in title or '数据开发' in title or '大数据' in title or '数仓' in title:
        return '大数据开发工程师'
    if '数据分析' in title or '数据科学' in title or 'BI' in title:
        return '数据分析师'
    if '数据治理' in title or ('数据' in title and '质量' in title):
        return '数据治理工程师'
    if '数据' in title and '平台' in title:
        return '数据平台开发工程师'

    # 后端开发类 - 保留方向
    if '后台开发' in title or '后端开发' in title or '服务端开发' in title:
        if '安全' in title:
            return '后端安全开发工程师'
        if '游戏' in title:
            return '游戏后端开发工程师'
        if '交易' in title or '支付' in title:
            return '交易后端开发工程师'
        if '推荐' in title:
            return '推荐系统后端工程师'
        return '后端开发工程师'
    if 'Java' in title and ('开发' in title or '研发' in title):
        return 'Java后端开发工程师'
    if 'Python' in title and ('开发' in title or '研发' in title):
        return 'Python后端开发工程师'
    if ('Go' in title or 'Golang' in title) and ('开发' in title or '研发' in title):
        return 'Go后端开发工程师'
    if 'C++' in title and ('开发' in title or '研发' in title):
        if '游戏' in title:
            return '游戏C++开发工程师'
        return 'C++开发工程师'
    if '分布式' in title and ('研发' in title or '开发' in title):
        return '分布式系统开发工程师'
    if '存储' in title and ('开发' in title or '研发' in title):
        return '存储开发工程师'
    if '开发工程师' in title or '研发工程师' in title:
        if '游戏' in title and '后台' not in title:
            return '游戏客户端开发工程师'
        if '安全' in title:
            return '安全开发工程师'
        if 'AI' in title or '计算库' in title:
            return 'AI基础设施开发工程师'
        return '后端开发工程师'

    # 前端/客户端类
    if '前端' in title or 'Web开发' in title:
        return '前端开发工程师'
    if 'iOS' in title:
        return 'iOS开发工程师'
    if 'Android' in title or '安卓' in title:
        return 'Android开发工程师'
    if '客户端' in title:
        if '游戏' in title:
            return '游戏客户端开发工程师'
        return '客户端开发工程师'

    # 测试类
    if '测试开发' in title:
        if '游戏' in title:
            return '游戏测试开发工程师'
        if '性能' in title:
            return '性能测试开发工程师'
        return '测试开发工程师'
    if '测试' in title or 'QA' in title:
        if '性能' in title:
            return '性能测试工程师'
        if '安全' in title:
            return '安全测试工程师'
        return '测试工程师'

    # 运维/基础设施类
    if 'GPU' in title or ('训练' in title and '平台' in title):
        return 'GPU基础设施工程师'
    if '推理优化' in title or ('模型' in title and '部署' in title):
        return 'AI推理优化工程师'
    if '基础架构' in title or '基础设施' in title or '架构师' in title:
        return '基础架构工程师'
    if '运维' in title or 'DevOps' in title or 'SRE' in title:
        return '运维工程师'
    if '云原生' in title or '容器' in title or 'K8s' in title:
        return '云原生工程师'

    # 安全类
    if '安全运营' in title:
        return '安全运营工程师'
    if '风控' in title:
        return '风控工程师'
    if '安全' in title:
        return '安全工程师'

    # 产品类
    if '产品经理' in title or '产品策划' in title:
        if '游戏' in title:
            return '游戏产品经理'
        return '产品经理'

    # 运营类
    if '运营' in title:
        if '游戏' in title:
            return '游戏运营'
        if '安全' in title:
            return '安全运营工程师'
        return '运营专员'
    if '市场' in title or '用户增长' in title:
        return '市场运营专员'

    # 游戏技术美术
    if '技术美术' in title:
        return '游戏技术美术'

    # 固件/硬件
    if '固件' in title or 'SSD' in title:
        return '固件开发工程师'

    # 其他带"工程师/开发"的
    if '工程师' in title or '开发' in title or '研发' in title:
        return '研发工程师'

    return title if title else '其他岗位'


def categorize(title: str) -> str:
    """根据规范化后的岗位名称分类"""
    if any(w in title for w in ['算法', 'NLP', 'CV', '大模型', '推荐', '搜索', '机器学习', 'AI']):
        return '算法'
    if any(w in title for w in ['大数据', '数据分析', '数据治理', '数据科学', '数据平台']):
        return '数据'
    if any(w in title for w in ['后端', 'Java', 'Python', 'Go', 'C++', '分布式', '交易', '存储', '研发工程师']):
        return '后端'
    if any(w in title for w in ['前端', 'iOS', 'Android', '客户端']):
        return '前端'
    if any(w in title for w in ['测试', 'QA']):
        return '测试'
    if any(w in title for w in ['运维', 'DevOps', 'SRE', '基础架构', 'GPU', '推理优化', '云原生', '基础设施']):
        return '运维'
    if any(w in title for w in ['产品经理', '产品策划']):
        return '产品'
    if any(w in title for w in ['运营', '市场']):
        return '运营'
    if any(w in title for w in ['安全', '风控']):
        return '安全'
    if any(w in title for w in ['技术美术', '固件']):
        return '其他'
    return '其他'


def estimate_salary(title: str, experience: str) -> str:
    """根据岗位类型和经验估算薪资范围（腾讯校招/社招参考）"""
    base = {
        '算法': (25, 50),
        '大数据开发工程师': (20, 40),
        '数据分析师': (15, 30),
        '后端开发工程师': (20, 40),
        'Java后端开发工程师': (20, 40),
        'Python后端开发工程师': (18, 35),
        'Go后端开发工程师': (22, 42),
        'C++开发工程师': (22, 45),
        '前端开发工程师': (18, 35),
        '客户端开发工程师': (20, 38),
        '测试开发工程师': (18, 32),
        '测试工程师': (12, 25),
        '运维工程师': (15, 30),
        'DevOps工程师': (18, 35),
        '基础架构工程师': (25, 50),
        '安全工程师': (20, 40),
        '产品经理': (18, 35),
        '运营专员': (10, 20),
        '系统架构师': (40, 70),
        'GPU基础设施工程师': (30, 55),
        'AI推理优化工程师': (28, 50),
        '大模型算法工程师': (30, 60),
        '推荐算法工程师': (28, 55),
    }

    low, high = base.get(title, (15, 30))

    # 根据经验调整
    if '应届' in experience or '不限' in experience:
        low, high = int(low * 0.7), int(high * 0.7)
    elif '1' in experience and '3' in experience:
        low, high = int(low * 0.85), int(high * 0.85)
    elif '3' in experience and '5' in experience:
        pass  # 基准
    elif '5' in experience:
        low, high = int(low * 1.3), int(high * 1.3)

    return f"{low}-{high}K"


def extract_skills(title: str, desc: str, req: str) -> str:
    """从岗位名称、描述、要求中提取技能"""
    full_text = f"{title} {desc} {req}"
    skills = []

    skill_map = {
        'Python': r'\bPython\b',
        'Java': r'\bJava\b',
        'C++': r'C\+\+',
        'Go': r'\bGo\b|Golang',
        'MySQL': r'MySQL',
        'Redis': r'Redis',
        'Kafka': r'Kafka',
        'Docker': r'Docker',
        'Kubernetes': r'Kubernetes|K8s',
        'Linux': r'Linux',
        'TensorFlow': r'TensorFlow',
        'PyTorch': r'PyTorch',
        'Spark': r'Spark',
        'Flink': r'Flink',
        'Hadoop': r'Hadoop',
        'Hive': r'Hive',
        'Spring': r'Spring',
        'Django': r'Django',
        'Flask': r'Flask',
        'Vue': r'Vue',
        'React': r'React',
        '微服务': r'微服务',
        '分布式': r'分布式',
        '高并发': r'高并发',
        '机器学习': r'机器学习',
        '深度学习': r'深度学习',
        '大模型': r'大模型|LLM',
    }

    for skill, pattern in skill_map.items():
        if re.search(pattern, full_text, re.IGNORECASE):
            skills.append(skill)

    # 根据岗位名称补充
    if '算法' in title and '机器学习' not in skills:
        skills.append('机器学习')
    if '后端' in title and 'MySQL' not in skills:
        skills.append('MySQL')
    if '大数据' in title and 'Spark' not in skills:
        skills.append('Spark')
    if '测试' in title and 'Python' not in skills:
        skills.append('Python')
    if '运维' in title and 'Linux' not in skills:
        skills.append('Linux')

    return '、'.join(skills[:8]) if skills else '见岗位描述'


def main():
    print("=" * 50)
    print("  岗位数据清洗工具")
    print("=" * 50)

    df = pd.read_csv(INPUT_FILE)
    print(f"\n原始数据: {len(df)} 条")

    # 清洗
    df['岗位名称_原始'] = df['岗位名称']
    df['岗位名称'] = df['岗位名称'].apply(clean_title)
    df['岗位名称'] = df['岗位名称'].apply(normalize_title)
    df['岗位分类'] = df['岗位名称'].apply(categorize)
    df['薪资范围'] = df.apply(lambda r: estimate_salary(r['岗位名称'], r['工作经验']), axis=1)
    df['技能要求'] = df.apply(lambda r: extract_skills(r['岗位名称'], r['岗位描述'], ''), axis=1)

    # 去掉原始名称列
    df = df.drop(columns=['岗位名称_原始'])

    # 按分类排序
    cat_order = ['后端', '算法', '数据', '前端', '测试', '运维', '安全', '产品', '运营', '其他']
    df['_sort'] = df['岗位分类'].apply(lambda x: cat_order.index(x) if x in cat_order else 99)
    df = df.sort_values('_sort').drop(columns=['_sort']).reset_index(drop=True)

    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"清洗完成: {len(df)} 条")
    print(f"\n=== 岗位名称样例（前15条）===")
    for i, name in enumerate(df['岗位名称'].head(15), 1):
        print(f"{i}. {name}  [{df.loc[i-1, '岗位分类']}]  {df.loc[i-1, '薪资范围']}")

    print(f"\n=== 分类统计 ===")
    print(df['岗位分类'].value_counts().to_string())

    print(f"\n=== 薪资分布 ===")
    print(df['薪资范围'].value_counts().head(10).to_string())

    print(f"\n已保存到 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
