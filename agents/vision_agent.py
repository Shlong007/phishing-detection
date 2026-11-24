"""
Agent 4: 视觉分析 Agent
分析网页截图的视觉特征（品牌logo、页面功能、视觉可疑度）
使用智谱 GLM-4.6v（多模态模型）
"""
from typing import Dict, Optional

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from utils.api import parse_json_response


VISION_AGENT_PROMPT = """分析这个网页截图，判断是否为钓鱼网站，并提取关键信息。

请输出JSON（只输出JSON，不要其他内容）：
{
  "vis_claim": "PHISHING" 或 "LEGITIMATE",
  "vis_confidence": 0.0到1.0,
  "vis_brand": ["识别到的品牌名"],
  "vis_function": "login/email/shopping/banking/social_media/government/tech_support/entertainment/other",
  "has_login_form": true或false,
  "form_prompt_text": "表单提示文字（无则空字符串）",
  "button_text": "按钮文字（无则空字符串）",
  "has_urgency": true或false,
  "vis_key_info": ["截图中看到的关键信息"],
  "vis_evidence": "判定依据简述"
}"""


class VisionAgent:
    """视觉分析 Agent（异步，多模态）"""
    
    def __init__(self, api_client):
        self.api = api_client
    
    async def analyze(self, screenshot_path: str) -> Optional[Dict]:
        """分析网页截图（异步）"""
        if not screenshot_path:
            print("  [Vision Agent] 无截图路径，跳过")
            return self._fallback()
        
        try:
            response = await self.api.chat_with_image(VISION_AGENT_PROMPT, screenshot_path)
            result = parse_json_response(response)
        except Exception as e:
            print(f"  [Vision Agent] API调用失败: {e}")
            return self._fallback()
        
        if result is None:
            print(f"  [Vision Agent] JSON解析失败，原始回复: {response[:200]}")
            return self._fallback()
        
        result.setdefault("vis_claim", "LEGITIMATE")
        result.setdefault("vis_confidence", 0.5)
        result.setdefault("vis_brand", [])
        result.setdefault("vis_function", "other")
        result.setdefault("has_login_form", False)
        result.setdefault("form_prompt_text", "")
        result.setdefault("button_text", "")
        result.setdefault("has_urgency", False)
        result.setdefault("vis_key_info", [])
        result.setdefault("vis_evidence", "")
        
        return result
    
    def _fallback(self) -> Dict:
        return {
            "vis_claim": "LEGITIMATE",
            "vis_confidence": 0.3,
            "vis_brand": [],
            "vis_function": "other",
            "has_login_form": False,
            "form_prompt_text": "",
            "button_text": "",
            "has_urgency": False,
            "vis_key_info": [],
            "vis_evidence": "视觉分析失败，使用默认值",
        }
