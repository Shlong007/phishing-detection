"""
Agent 3: 文本语义 Agent
分析网页可见文本的语义特征（品牌、功能、紧迫感、凭据收割等）
使用方舟 Coding Plan 的 glm-5.2（文本模型）
"""
from typing import Dict, Optional

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from utils.api import parse_json_response


TEXT_AGENT_PROMPT = """你是一名专注于网络安全的语言专家。请分析以下从网页提取的可见文本内容，判断是否包含钓鱼相关的语义特征。

【可见文本内容】
{text}

请分析以下方面：

1. 品牌识别：
   - 文本中提到了哪些品牌名称？
   - 是否有品牌名称的拼写错误或变体？

2. 页面功能判断：
   - 这个页面的文本表明它是什么功能？
   - 从以下选一：login/email/shopping/banking/social_media/government/tech_support/entertainment/other

3. 钓鱼语义特征：
   - 是否有紧迫感语言（"立即验证"、"账户将被锁定"等）？
   - 是否有凭据收割请求（要求输入密码、银行卡号等）？
   - 是否有信任建立语言（"安全保障"、"官方认证"等）？
   - 是否有语法/拼写错误（钓鱼常见特征）？

请严格按以下JSON格式输出（只输出JSON，不要输出其他内容，不要用markdown代码块包裹）：
{{
  "text_claim": "PHISHING" 或 "LEGITIMATE",
  "text_confidence": 0.0到1.0的数字,
  "text_brand": ["品牌1", "品牌2"],
  "text_function": "功能类别",
  "has_urgency": true或false,
  "has_credential_request": true或false,
  "has_trust_language": true或false,
  "has_grammar_error": true或false,
  "text_key_info": ["文本中的关键信息1", "关键信息2"],
  "text_evidence": "关键证据描述"
}}"""


class TextAgent:
    """文本语义分析 Agent（异步）"""
    
    def __init__(self, api_client):
        self.api = api_client
    
    async def analyze(self, visible_text: str) -> Optional[Dict]:
        """分析可见文本的语义（异步）"""
        prompt = TEXT_AGENT_PROMPT.format(text=visible_text)
        
        response = await self.api.chat_text(prompt)
        result = parse_json_response(response)
        
        if result is None:
            print(f"  [Text Agent] JSON解析失败，原始回复: {response[:200]}")
            return self._fallback()
        
        result.setdefault("text_claim", "LEGITIMATE")
        result.setdefault("text_confidence", 0.5)
        result.setdefault("text_brand", [])
        result.setdefault("text_function", "other")
        result.setdefault("has_urgency", False)
        result.setdefault("has_credential_request", False)
        result.setdefault("has_trust_language", False)
        result.setdefault("has_grammar_error", False)
        result.setdefault("text_key_info", [])
        result.setdefault("text_evidence", "")
        
        return result
    
    def _fallback(self) -> Dict:
        return {
            "text_claim": "LEGITIMATE",
            "text_confidence": 0.3,
            "text_brand": [],
            "text_function": "other",
            "has_urgency": False,
            "has_credential_request": False,
            "has_trust_language": False,
            "has_grammar_error": False,
            "text_key_info": [],
            "text_evidence": "JSON解析失败，使用默认值",
        }
