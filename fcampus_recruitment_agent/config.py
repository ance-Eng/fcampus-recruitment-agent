# -*- coding: utf-8 -*-
"""
全局配置：技能词库、评分权重、学历等级等
"""

# ========== 技能词库（按岗位方向分类） ==========
SKILL_DICT = {
    "后端开发": [
        "java", "python", "spring", "springboot", "spring boot", "mybatis",
        "mysql", "redis", "linux", "docker", "git", "maven", "微服务",
        "django", "flask", "c++", "go", "golang", "kafka", "rabbitmq",
        "分布式", "高并发", "jvm", "多线程", "sql", "oracle", "mongodb"
    ],
    "前端开发": [
        "html", "css", "javascript", "js", "vue", "react", "typescript",
        "webpack", "node", "nodejs", "jquery", "ajax", "es6", "小程序",
        "uniapp", "sass", "less", "bootstrap", "elementui", "antd"
    ],
    "数据分析": [
        "python", "sql", "excel", "pandas", "numpy", "matplotlib",
        "tableau", "powerbi", "power bi", "统计学", "spss", "r语言",
        "数据可视化", "机器学习", "hive", "hadoop", "spark", "flink",
        "etl", "数据仓库", "bi"
    ],
    "测试": [
        "python", "java", "selenium", "appium", "jmeter", "postman",
        "接口测试", "自动化测试", "性能测试", "功能测试", "linux",
        "mysql", "git", "pytest", "unittest", "抓包", "fiddler",
        "charles", "测试用例", "缺陷管理", "jira"
    ],
    "运维": [
        "linux", "shell", "python", "docker", "kubernetes", "k8s",
        "jenkins", "nginx", "mysql", "redis", "git", "ci/cd", "监控",
        "zabbix", "prometheus", "ansible", "交换机", "路由器", "网络",
        "tcp/ip", "防火墙", "负载均衡"
    ],
    "产品": [
        "axure", "xmind", "visio", "需求分析", "原型设计", "用户研究",
        "数据分析", "项目管理", "竞品分析", "prd", "思维导图", "excel",
        "sql", "用户体验", "ux", "ui", "敏捷开发"
    ],
    "算法": [
        "python", "机器学习", "深度学习", "tensorflow", "pytorch",
        "算法", "数据结构", "nlp", "自然语言处理", "计算机视觉", "cv",
        "推荐系统", "搜索算法", "大模型", "llm", "数学", "统计学",
        "spark", "hadoop", "sql", "linux", "git", "c++", "java"
    ],
    "安全": [
        "渗透测试", "安全", "网络安全", "漏洞", "加密", "防火墙",
        "wireshark", "burpsuite", "nmap", "sql注入", "xss", "csrf",
        "linux", "python", "c语言", "汇编", "逆向", "代码审计"
    ],
    "运营": [
        "新媒体", "公众号", "短视频", "抖音", "小红书", "内容运营",
        "用户运营", "活动策划", "数据分析", "excel", "文案", "ps",
        "pr", "社群运营", "增长", "转化率", "用户增长"
    ],
    "金融": [
        "金融", "经济学", "会计", "财务", "审计", "cfa", "cpa",
        "frm", "银行", "证券", "保险", "风控", "信贷", "投资",
        "excel", "python", "sql", "数据分析", "英语", "经济法"
    ],
    "制造": [
        "机械设计", "cad", "solidworks", "ug", "proe", "自动化",
        "电气", "plc", "单片机", "嵌入式", "工艺", "模具", "质量",
        "六西格玛", "精益生产", "设备维护", "机械原理", "材料"
    ],
    "医疗": [
        "护理学", "临床医学", "医学", "药学", "中医学", "医学影像",
        "护士资格证", "执业医师", "药剂师", "医院", "诊疗", "处方",
        "生化检验", "病理", "康复", "预防医学", "公共卫生"
    ],
    "教育": [
        "教师资格证", "教学", "课程设计", "教育学", "心理学",
        "班主任", "教研", "课件制作", "ppt", "学科知识", "普通话",
        "思想政治", "学生管理", "就业指导"
    ],
    "传媒": [
        "新闻", "中文", "文案", "编辑", "记者", "摄影", "摄像",
        "pr", "ae", "ps", "短视频", "新媒体", "广告", "策划",
        "品牌", "传播", "市场营销", "公众号"
    ],
    "零售": [
        "零售", "连锁", "门店管理", "销售", "导购", "采购", "供应链",
        "库存管理", "商品管理", "客户服务", "pos", "数据分析",
        "快消", "fmcg", "市场营销", "谈判"
    ],
    "能源": [
        "化学工程", "化工", "环境工程", "水处理", "电力", "电气",
        "新能源", "电池", "电化学", "光伏", "风电", "节能", "环保",
        "安全工程", "工艺", "设备"
    ],
    "建筑": [
        "土木工程", "施工", "造价", "预算", "结构设计", "建筑学",
        "cad", "revit", "bim", "pkpm", "建造师", "监理", "测量",
        "给排水", "暖通", "电气设计", "项目管理"
    ],
    "职能": [
        "人力资源", "hr", "招聘", "培训", "绩效", "薪酬", "员工关系",
        "财务", "会计", "审计", "税务", "法务", "法学", "合同",
        "知识产权", "行政", "office", "excel", "ppt"
    ],
    "物流": [
        "物流管理", "供应链", "仓储", "配送", "运输", "库存",
        "wms", "tms", "erp", "采购", "国际贸易", "报关", "数据分析",
        "项目管理", "精益物流"
    ],
}

# 岗位分类别名映射（jobs.csv里的分类名 -> SKILL_DICT里的key）
CATEGORY_ALIAS = {
    "后端": "后端开发",
    "前端": "前端开发",
    "数据": "数据分析",
    "算法": "算法",
    "测试": "测试",
    "运维": "运维",
    "安全": "安全",
    "产品": "产品",
    "运营": "运营",
    "金融": "金融",
    "制造": "制造",
    "医疗": "医疗",
    "教育": "教育",
    "传媒": "传媒",
    "零售": "零售",
    "能源": "能源",
    "建筑": "建筑",
    "职能": "职能",
    "物流": "物流",
    "其他": "后端开发",  # 默认按后端宽松匹配
}

# ========== 评分权重（各维度占比，总和=100） ==========
WEIGHTS = {
    "skill": 40,        # 技能匹配
    "education": 20,    # 学历匹配
    "experience": 30,   # 经验/项目匹配
    "bonus": 10,        # 加分项（证书、奖项等）
}

# 不同岗位类型的权重模板
WEIGHT_TEMPLATES = {
    "默认": {"skill": 40, "education": 20, "experience": 30, "bonus": 10},
    "技术研发": {"skill": 50, "education": 15, "experience": 25, "bonus": 10},
    "医疗护理": {"skill": 20, "education": 25, "experience": 25, "bonus": 30},
    "金融财经": {"skill": 30, "education": 30, "experience": 25, "bonus": 15},
    "教育教学": {"skill": 25, "education": 30, "experience": 25, "bonus": 20},
    "运营市场": {"skill": 25, "education": 20, "experience": 35, "bonus": 20},
    "制造工程": {"skill": 35, "education": 20, "experience": 35, "bonus": 10},
}

# ========== 学历等级 ==========
EDUCATION_LEVEL = {
    "大专": 1,
    "专科": 1,
    "本科": 2,
    "学士": 2,
    "硕士": 3,
    "研究生": 3,
    "博士": 4,
}

# ========== 加分关键词 ==========
BONUS_KEYWORDS = [
    "奖学金", "优秀学生", "三好学生", "竞赛", "获奖", "一等奖", "二等奖",
    "三等奖", "证书", "认证", "四六级", "英语六级", "英语四级", "雅思",
    "托福", "专利", "论文", "开源", "github", "实习", "项目经验",
    "学生干部", "班长", "学生会", "社团", "志愿者"
]

# ========== 岗位-技能方向映射（用于自动匹配技能词库） ==========
JOB_CATEGORY_MAP = {
    "后端": "后端开发", "java": "后端开发", "python开发": "后端开发",
    "服务端": "后端开发", "研发": "后端开发",
    "前端": "前端开发", "web前端": "前端开发", "h5": "前端开发",
    "数据": "数据分析", "数据分析": "数据分析", "数据挖掘": "数据分析",
    "测试": "测试", "qa": "测试", "质量": "测试",
    "运维": "运维", "devops": "运维", "网络": "运维",
    "产品": "产品", "产品经理": "产品", "pm": "产品",
}

# ========== 大模型 API 配置 ==========
# 支持所有兼容 OpenAI 格式的 API：DeepSeek、Kimi(Moonshot)、通义千问、智谱、OpenAI 等
LLM_PROVIDERS = {
    "DeepSeek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "Kimi (Moonshot)": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
    },
    "通义千问": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "智谱 GLM": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
    },
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "自定义": {
        "base_url": "",
        "model": "",
    },
}

# 默认使用的模型（可在网页中切换）
DEFAULT_LLM_PROVIDER = "DeepSeek"

# ========== RAG 知识库配置 ==========
RAG_CONFIG = {
    # 知识库目录
    "knowledge_dir": "data/knowledge",
    # 向量索引保存路径
    "index_path": "output/rag_index",
    # 文本切分：每块最大字符数
    "chunk_size": 300,
    # 块之间重叠字符数
    "chunk_overlap": 50,
    # 检索返回 top-k 条
    "top_k": 5,
    # embedding 模型（sentence-transformers）
    "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
    # 向量维度（fallback 模式下的哈希向量维度）
    "fallback_dim": 512,
}

# ========== Redis 缓存配置 ==========
# 支持环境变量覆盖：REDIS_URL、REDIS_HOST、REDIS_PORT、REDIS_PASSWORD、REDIS_DB
# 优先使用 REDIS_URL（如 Upstash 提供的 redis://:password@host:port）
import os as _os

REDIS_CONFIG = {
    "url": _os.environ.get("REDIS_URL", ""),
    "host": _os.environ.get("REDIS_HOST", "localhost"),
    "port": int(_os.environ.get("REDIS_PORT", 6379)),
    "password": _os.environ.get("REDIS_PASSWORD", ""),
    "db": int(_os.environ.get("REDIS_DB", 0)),
    "default_ttl": 3600,  # 默认缓存1小时
    # 设 CACHE_BACKEND=redis 环境变量则强制启用 Redis
    "enabled": _os.environ.get("CACHE_BACKEND", "").lower() == "redis",
}
