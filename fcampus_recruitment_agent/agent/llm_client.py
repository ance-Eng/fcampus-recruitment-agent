# -*- coding: utf-8 -*-
"""
大模型 API 客户端：封装 OpenAI 兼容格式的调用，支持 DeepSeek/Kimi/通义/智谱/OpenAI
"""
import json
import requests


class LLMClient:
    def __init__(self, api_key: str = "", base_url: str = "", model: str = "", provider: str = ""):
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.provider = provider
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def is_ready(self) -> bool:
        """检查是否配置了 API Key 和 base_url"""
        return bool(self.api_key and self.base_url and self.model)

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3,
             max_tokens: int = 2000, timeout: int = 60) -> str:
        """
        调用大模型聊天接口，返回纯文本结果
        """
        if not self.is_ready():
            return "[ERROR] 未配置 API Key / base_url / model，请先在侧边栏配置大模型"

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            resp = requests.post(url, headers=self.headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except requests.exceptions.Timeout:
            return "[ERROR] 大模型请求超时，请检查网络或稍后重试"
        except requests.exceptions.HTTPError as e:
            return f"[ERROR] API 请求失败：{e.response.status_code} {e.response.text[:200]}"
        except Exception as e:
            return f"[ERROR] 调用大模型出错：{str(e)[:200]}"

    def chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.2,
                  max_tokens: int = 2000, timeout: int = 60) -> dict:
        """
        调用大模型并尝试解析为 JSON，失败返回 {"error": 原始文本}
        """
        raw = self.chat(system_prompt, user_prompt, temperature, max_tokens, timeout)
        if raw.startswith("[ERROR]"):
            return {"error": raw}
        # 去掉可能的 markdown 代码块包裹
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取第一个 { 到最后一个 }
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            return {"error": "大模型返回的不是有效 JSON", "raw": raw}

    def test_connection(self) -> tuple:
        """测试 API 连接是否正常，返回 (是否成功, 消息)"""
        if not self.is_ready():
            return False, "API Key、base_url 或 model 未填写"
        try:
            result = self.chat(
                "你是一个连接测试助手",
                "请只回复两个字：正常",
                max_tokens=10,
                timeout=15,
            )
            if result.startswith("[ERROR]"):
                return False, result
            return True, f"连接成功，模型回复：{result}"
        except Exception as e:
            return False, f"连接失败：{str(e)[:100]}"
