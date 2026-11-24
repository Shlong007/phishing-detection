"""
Agent 2: HTML 结构 Agent
分析 HTML 代码的结构特征（表单、隐藏元素、iframe 等）
使用方舟 Coding Plan 的 glm-5.2（文本模型）
"""
from typing import Dict, Optional

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from utils.api import parse_json_response


HTML_AGENT_PROMPT = """你是一名Web安全专家，专门分析HTML结构中的钓鱼特征。
请分析以下HTML代码的结构特征。

【HTML 内容（已清洗）】
{html}

请分析以下方面：

1. HTML结构特征：
   - 是否有登录表单（<form> + password input）？
   - 表单的action属性指向哪里？
   - 是否有隐藏元素（display:none, visibility:hidden）？
   - 是否有可疑的JavaScript代码？
   - 是否有iframe？iframe的src指向哪里？
   - 是否有外部资源加载（CSS, JS, img）？

2. 关键信息提取（从HTML文本中）：
   - 识别到的品牌名称列表
   - 页面功能分类（从以下选一）：login/email/shopping/banking/social_media/government/tech_support/entertainment/other
   - 是否有紧迫感语言？
   - 是否有凭据收割请求？

请严格按以下JSON格式输出（只输出JSON，不要输出其他内容，不要用markdown代码块包裹）：
{{
  "html_claim": "PHISHING" 或 "LEGITIMATE",
  "html_confidence": 0.0到1.0的数字,
  "html_brand": ["品牌1", "品牌2"],
  "html_function": "功能类别",
  "has_form": true或false,
  "form_action": "表单提交地址（如有，否则空字符串）",
  "has_hidden_element": true或false,
  "has_iframe": true或false,
  "iframe_src": "iframe地址（如有，否则空字符串）",
  "html_key_info": ["从HTML文本提取的关键信息1", "关键信息2"],
  "html_evidence": "关键证据描述"
}}"""


class HTMLAgent:
    """HTML 结构分析 Agent（异步）"""
    
    def __init__(self, api_client):
        self.api = api_client
    
    async def analyze(self, cleaned_html: str) -> Optional[Dict]:
        """分析 HTML 结构（异步）"""
        prompt = HTML_AGENT_PROMPT.format(html=cleaned_html)
        
        response = await self.api.chat_text(prompt)
        result = parse_json_response(response)
        
        if result is None:
            print(f"  [HTML Agent] JSON解析失败，原始回复: {response[:200]}")
            return self._fallback()
        
        result.setdefault("html_claim", "LEGITIMATE")
        result.setdefault("html_confidence", 0.5)
        result.setdefault("html_brand", [])
        result.setdefault("html_function", "other")
        result.setdefault("has_form", False)
        result.setdefault("form_action", "")
        result.setdefault("has_hidden_element", False)
        result.setdefault("has_iframe", False)
        result.setdefault("iframe_src", "")
        result.setdefault("html_key_info", [])
        result.setdefault("html_evidence", "")
        
        return result
    
    def _fallback(self) -> Dict:
        return {
            "html_claim": "LEGITIMATE",
            "html_confidence": 0.3,
            "html_brand": [],
            "html_function": "other",
            "has_form": False,
            "form_action": "",
            "has_hidden_element": False,
            "has_iframe": False,
            "iframe_src": "",
            "html_key_info": [],
            "html_evidence": "JSON解析失败，使用默认值",
        }
