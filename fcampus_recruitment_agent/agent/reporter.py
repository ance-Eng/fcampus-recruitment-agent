# -*- coding: utf-8 -*-
"""
报告生成器：将筛选结果格式化为可读文本 / Markdown / 字典
"""
import json
from datetime import datetime


class Reporter:
    def to_text(self, result: dict) -> str:
        """生成纯文本报告"""
        lines = []
        lines.append("=" * 50)
        lines.append("        校园实习招聘智能筛选报告")
        lines.append("=" * 50)
        lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"候选人：{result['candidate']}")
        lines.append(f"应聘岗位：{result['job_title']}（{result['job_category']}方向）")
        lines.append("-" * 50)
        lines.append(f"综合得分：{result['total_score']} / 100")
        lines.append(f"评级：{result['level']}")
        lines.append(f"结论：{result['conclusion']}")
        lines.append("-" * 50)
        lines.append("【各维度得分】")

        dim_names = {
            "skill": "技能匹配",
            "education": "学历匹配",
            "experience": "经验/项目",
            "bonus": "加分项",
        }
        for key, name in dim_names.items():
            dim = result["dimensions"][key]
            lines.append(f"  {name}：{dim['score']} 分 — {dim['detail'].get('note', '')}")

        lines.append("-" * 50)
        if result.get("matched_skills"):
            lines.append(f"已匹配技能：{', '.join(result['matched_skills'])}")
        if result.get("missing_skills"):
            lines.append(f"缺失技能：{', '.join(result['missing_skills'])}")
        lines.append("-" * 50)
        lines.append(f"改进建议：{result['suggestion']}")
        lines.append("=" * 50)
        return "\n".join(lines)

    def to_markdown(self, result: dict) -> str:
        """生成 Markdown 报告"""
        md = []
        md.append(f"# 智能筛选报告 — {result['candidate']}")
        md.append("")
        md.append(f"- **应聘岗位**：{result['job_title']}（{result['job_category']}）")
        md.append(f"- **综合得分**：**{result['total_score']} / 100**")
        md.append(f"- **评级**：{result['level']}")
        md.append(f"- **结论**：{result['conclusion']}")
        md.append("")
        md.append("## 各维度得分")
        md.append("")
        md.append("| 维度 | 得分 | 说明 |")
        md.append("|------|------|------|")
        dim_names = {
            "skill": "技能匹配",
            "education": "学历匹配",
            "experience": "经验/项目",
            "bonus": "加分项",
        }
        for key, name in dim_names.items():
            dim = result["dimensions"][key]
            md.append(f"| {name} | {dim['score']} | {dim['detail'].get('note', '')} |")
        md.append("")
        if result.get("matched_skills"):
            md.append(f"**已匹配技能**：{', '.join(result['matched_skills'])}")
            md.append("")
        if result.get("missing_skills"):
            md.append(f"**缺失技能**：{', '.join(result['missing_skills'])}")
            md.append("")
        md.append(f"**改进建议**：{result['suggestion']}")
        return "\n".join(md)

    def to_dict(self, result: dict) -> dict:
        """返回原始字典（可直接 json.dumps）"""
        return result

    def to_json(self, result: dict) -> str:
        return json.dumps(result, ensure_ascii=False, indent=2)

    def save_report(self, result: dict, filepath: str, fmt: str = "text"):
        """保存报告到文件"""
        if fmt == "markdown":
            content = self.to_markdown(result)
        elif fmt == "json":
            content = self.to_json(result)
        else:
            content = self.to_text(result)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath
