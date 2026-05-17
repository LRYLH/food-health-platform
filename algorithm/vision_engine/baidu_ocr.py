"""
Baidu OCR API 封装 — 通用文字识别（高精度含位置版）

调用链: API Key + Secret Key → access_token (缓存30天) → OCR 识别
"""

import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import List

import cv2
import numpy as np
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

TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate"
TOKEN_CACHE = Path(__file__).resolve().parent.parent / ".baidu_token_cache"


class BaiduOCR:
    def __init__(self):
        self.api_key = os.environ.get("BAIDU_OCR_API_KEY", "")
        self.secret_key = os.environ.get("BAIDU_OCR_SECRET_KEY", "")
        self._token: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.secret_key)

    # ── token 管理 ──────────────────────────────────────────────────────

    def _get_token(self) -> str:
        # 1) 内存缓存
        if self._token:
            return self._token

        # 2) 文件缓存（有效期 29 天，留 1 天余量）
        if TOKEN_CACHE.exists():
            try:
                cache = json.loads(TOKEN_CACHE.read_text())
                if time.time() - cache["ts"] < 29 * 86400:
                    self._token = cache["token"]
                    return self._token
            except (json.JSONDecodeError, KeyError):
                pass

        # 3) 请求新 token
        resp = requests.get(TOKEN_URL, params={
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key,
        }, timeout=10)
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"获取百度 OCR access_token 失败: {data}")

        self._token = data["access_token"]
        TOKEN_CACHE.write_text(json.dumps({"token": self._token, "ts": time.time()}))
        logger.info("已获取新的百度 OCR access_token")
        return self._token

    # ── 图片编码 ────────────────────────────────────────────────────────

    @staticmethod
    def _encode_image(image: np.ndarray) -> str:
        """RGB numpy → JPEG → base64，超过 4MB 则等比缩小（百度限制）。"""
        _, buf = cv2.imencode(".jpg", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        if len(buf) > 3.8 * 1024 * 1024:
            h, w = image.shape[:2]
            scale = (3.8 * 1024 * 1024 / len(buf)) ** 0.5
            image = cv2.resize(image, (int(w * scale), int(h * scale)))
            _, buf = cv2.imencode(".jpg", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        return base64.b64encode(buf).decode("utf-8")

    # ── OCR 识别 ────────────────────────────────────────────────────────

    def extract(self, image: np.ndarray) -> List[dict]:
        """识别图片中的文字，返回与 layout_analyzer 兼容的 text_blocks。

        Returns:
            [{"text": str, "box": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]], "confidence": float}, ...]
        """
        if not self.available:
            raise RuntimeError("百度 OCR 未配置，请在 algorithm/.env 中设置 BAIDU_OCR_API_KEY 和 BAIDU_OCR_SECRET_KEY")

        img_b64 = self._encode_image(image)
        token = self._get_token()

        resp = requests.post(
            f"{OCR_URL}?access_token={token}",
            data={"image": img_b64},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        data = resp.json()

        if "error_code" in data:
            logger.error("百度 OCR API 错误响应: error_code=%s, error_msg=%s",
                         data.get("error_code"), data.get("error_msg"))
            # token 过期则清缓存重试一次
            if data["error_code"] == 110:
                TOKEN_CACHE.unlink(missing_ok=True)
                self._token = None
                token = self._get_token()
                resp = requests.post(
                    f"{OCR_URL}?access_token={token}",
                    data={"image": img_b64},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30,
                )
                data = resp.json()
                if "error_code" in data:
                    logger.error("重试后仍失败: error_code=%s, error_msg=%s",
                                 data.get("error_code"), data.get("error_msg"))
                    raise RuntimeError(f"百度 OCR API 错误 [code={data.get('error_code')}]: {data.get('error_msg', data)}")
            else:
                raise RuntimeError(f"百度 OCR API 错误 [code={data.get('error_code')}]: {data.get('error_msg', data)}")

        return self._convert(data)

    # ── 响应转换 ────────────────────────────────────────────────────────

    @staticmethod
    def _convert(data: dict) -> List[dict]:
        """百度响应 → 标准 text_blocks 格式。

        百度 accurate 高精度含位置版 返回:
          {"words_result": [
             {"words": "文本", "location": {"left":N,"top":N,"width":N,"height":N}},
             ...
           ]}

        转换为:
          [{"text": str, "box": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]], "confidence": float}, ...]
        """
        results = []
        for item in data.get("words_result", []):
            text = item.get("words", "")
            loc = item.get("location", {})
            if loc:
                l, t, w, h = loc.get("left", 0), loc.get("top", 0), loc.get("width", 0), loc.get("height", 0)
                box = [[l, t], [l + w, t], [l + w, t + h], [l, t + h]]
            else:
                box = [[0, 0], [0, 0], [0, 0], [0, 0]]

            prob = item.get("probability", {})
            confidence = float(prob.get("average", 0.95)) if prob else 0.95

            results.append({"text": text, "box": box, "confidence": confidence})

        return results
