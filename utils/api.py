"""
两个模型 API 的异步封装：文本 Agent 走方舟 glm-5.2，视觉 Agent 走多模态模型。
"""
import json
import time
import asyncio
import base64
from typing import Optional, Dict, List
from openai import AsyncOpenAI

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from config import (
    ARK_API_KEY, ARK_BASE_URL, ARK_MODEL, ARK_VISION_MODEL,
    ZHIPU_API_KEY, VISION_MODEL,
    API_MAX_RETRIES, API_RETRY_BASE_WAIT, API_TIMEOUT
)


class DualAPIClient:
    """文本与视觉共用方舟端点，视觉后端可通过 VISION_MODEL 切换。"""
    
    def __init__(self):
        # 方舟 Coding Plan 客户端（文本，异步）
        self.text_client = AsyncOpenAI(
            api_key=ARK_API_KEY,
            base_url=ARK_BASE_URL,
            timeout=API_TIMEOUT,
        )
        # 视觉客户端（异步）
        self.vision_client = AsyncOpenAI(
            api_key=ARK_API_KEY,
            base_url=ARK_BASE_URL,
            timeout=API_TIMEOUT,
        )
        # 当前视觉模型名
        self._vision_model = VISION_MODEL  # doubao-seed-2.1-turbo
    
    async def chat_text(self, prompt: str, max_retries: int = API_MAX_RETRIES) -> str:
        """文本对话（方舟 glm-5.2）"""
        for attempt in range(max_retries):
            try:
                response = await self.text_client.chat.completions.create(
                    model=ARK_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.choices[0].message.content
            except Exception as e:
                err = str(e)
                if "429" in err or "1305" in err:
                    wait = API_RETRY_BASE_WAIT * (attempt + 1)
                    await asyncio.sleep(wait)
                else:
                    # 其他错误也重试，但等待短一些
                    if attempt < max_retries - 1:
                        await asyncio.sleep(3)
                    else:
                        raise
        raise Exception(f"方舟API调用失败，重试{max_retries}次")
    
    async def chat_with_image(self, prompt: str, image_path: str,
                              max_retries: int = API_MAX_RETRIES) -> str:
        """带图片的多模态对话。截图编码放在线程池里，避免阻塞事件循环。"""
        # 截图编码放线程池，不阻塞事件循环
        loop = asyncio.get_event_loop()
        img_b64 = await loop.run_in_executor(None, self._encode_image, image_path)
        for attempt in range(max_retries):
            try:
                response = await self.vision_client.chat.completions.create(
                    model=self._vision_model,  # doubao-seed-2.1-turbo
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_b64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }],
                )
                return response.choices[0].message.content
            except Exception as e:
                err = str(e)
                if "429" in err or "1305" in err:
                    wait = API_RETRY_BASE_WAIT * (attempt + 1)
                    await asyncio.sleep(wait)
                else:
                    # 其他错误也重试，但等待短一些
                    if attempt < max_retries - 1:
                        await asyncio.sleep(3)
                    else:
                        raise
        raise Exception(f"方舟视觉API调用失败，重试{max_retries}次")
    
    @staticmethod
    def _encode_image(image_path: str) -> str:
        """将图片编码为 base64"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")


def parse_json_response(text: str) -> Optional[Dict]:
    """
    解析模型返回的 JSON（处理多种异常情况）
    
    处理：
    1. markdown 代码块包裹（```json ... ```）
    2. 双花括号 {{ }}（模型把花括号当转义符）
    3. JSON 被截断（只有开头没有结尾）
    4. JSON 前后有多余文字
    """
    if not text:
        return None
    
    clean = text.strip()
    
    # 1. 去除 markdown 代码块标记
    if clean.startswith("```"):
        lines = clean.split("\n")
        clean = "\n".join(lines[1:])
        if clean.rstrip().endswith("```"):
            clean = clean.rstrip()[:-3]
        clean = clean.strip()
    
    # 2. 修复双花括号问题
    if clean.startswith("{{"):
        clean = "{" + clean[2:]
        if clean.rstrip().endswith("}}"):
            clean = clean.rstrip()[:-2] + "}"
    
    # 3. 尝试直接解析
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass
    
    # 4. 提取第一个 { 到最后一个 } 之间的内容
    start = clean.find("{")
    end = clean.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = clean[start:end+1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        
        # 5. 修复双花括号后再试
        candidate_fixed = candidate.replace("{{", "{").replace("}}", "}")
        if candidate_fixed != candidate:
            try:
                return json.loads(candidate_fixed)
            except json.JSONDecodeError:
                pass
    
    # 6. 处理 JSON 被截断的情况
    if start != -1:
        candidate = clean[start:]
        open_count = candidate.count("{")
        close_count = candidate.count("}")
        if open_count > close_count:
            candidate = candidate + "}" * (open_count - close_count)
            candidate = candidate.replace("{{", "{").replace("}}", "}")
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
    
    return None
