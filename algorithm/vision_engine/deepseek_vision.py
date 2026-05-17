"""
DeepSeek 文本解析 — 将 OCR 提取的食品包装原始文本解析为结构化 JSON
"""

import json
import logging
import os
import re
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def _load_env():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))

_load_env()

API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

SYSTEM_PROMPT = """你是一个专业的食品包装信息解析助手。你的任务是根据 OCR 从食品包装图片中提取的原始文本，解析出三类结构化信息。

注意事项：
1. 配料表中忽略产品标准号、生产许可证编号、致敏原信息、食用方法、贮存条件、产地、地址、电话等非配料内容。
2. 营养成分表必须至少包含能量、蛋白质、脂肪、碳水化合物、钠五项。
3. 如果有子项（如饱和脂肪、糖），name 保持原文字标注。
4. 保质期提取数字+单位，如"见封口处"等文字直接保留。

请严格按以下 JSON 格式返回，不要输出任何其他内容：
{
  "ingredients": ["配料1", "配料2"],
  "nutrition": [
    {"name": "能量", "per_100g": "1505千焦(kJ)", "nrv": "18%"},
    {"name": "蛋白质", "per_100g": "0.6克(g)", "nrv": "1%"}
  ],
  "expiration": "12个月"
}
缺失的字段返回 null 或空数组 []。"""


def _clean_json(text: str) -> str:
    """去除 markdown 代码块标记。"""
    text = text.strip()
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    return m.group(1).strip() if m else text


def parse_ocr_text(ocr_text: str) -> dict:
    """调用 DeepSeek API 解析 OCR 文本为结构化数据。

    Args:
        ocr_text: Baidu OCR 从包装图片中提取的原始文本（每行一个文本块）。

    Returns:
        {"ingredients": [...], "nutrition": [...], "expiration": "..."}
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key or api_key == "your_deepseek_api_key_here":
        raise RuntimeError("请在 .env 中设置 DEEPSEEK_API_KEY")

    # 限制文本长度，避免超出 token 限制
    if len(ocr_text) > 6000:
        ocr_text = ocr_text[:6000]

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"请解析以下 OCR 文本：\n\n{ocr_text}"},
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }

    resp = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"DeepSeek API 错误 [{resp.status_code}]: {resp.text[:500]}")

    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    try:
        return json.loads(_clean_json(content))
    except json.JSONDecodeError:
        logger.warning("DeepSeek 返回非标准 JSON: %s", content[:300])
        raise RuntimeError(f"JSON 解析失败: {content[:300]}")
