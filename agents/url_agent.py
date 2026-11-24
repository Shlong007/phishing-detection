"""
Agent 1: URL 分析 Agent
分析目标 URL 特征 + HTML 中提取的跳转链接
使用方舟 Coding Plan 的 glm-5.2（文本模型）
"""
import json
from typing import Dict, List, Optional

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from utils.api import parse_json_response


# 提示模板
URL_AGENT_PROMPT = """你是一名网络安全专家，专门分析URL和跳转链路中的钓鱼特征。
请分析以下URL和从HTML中提取的跳转链接，提取关键结构化信息。

【目标 URL】{url}

【从HTML提取的跳转链接】
- a标签链接: {a_href}
- 表单action: {form_action}
- iframe src: {iframe_src}
- 外部脚本src: {script_src}
- meta重定向: {meta_refresh}
- JS跳转: {js_redirect}

请分析以下方面：

1. 目标URL特征：
   - 域名是否包含已知品牌名？
   - 是否有可疑的子域名结构？
   - 是否使用IP地址而非域名？
   - TLD是否可疑？
   - URL路径是否包含可疑关键词？

2. 跳转链路分析：
   - 共有多少个外部跳转链接？
   - 是否有跳转到IP地址的链接？
   - 跳转链接的TLD分布是否可疑？
   - 表单action指向的域名和当前页面域名是否一致？
   - 是否有隐藏的meta refresh或JS重定向？
   - 是否有跳转到已知可疑域名模式的链接？

请严格按以下JSON格式输出（只输出JSON，不要输出其他内容，不要用markdown代码块包裹）：
{{
  "url_claim": "PHISHING" 或 "LEGITIMATE",
  "url_confidence": 0.0到1.0的数字,
  "url_brand": ["从URL识别的品牌名"],
  "url_suspicious_redirects": ["可疑跳转链接1", "链接2"],
  "redirect_count": 跳转链接总数,
  "external_redirect_ratio": 0.0到1.0的数字,
  "form_action_external": true或false,
  "has_hidden_redirect": true或false,
  "url_evidence": "关键证据描述"
}}"""


class URLAgent:
    """URL 分析 Agent（异步）"""
    
    def __init__(self, api_client):
        self.api = api_client
    
    async def analyze(self, url: str, redirect_links: Dict[str, List[str]]) -> Optional[Dict]:
        """分析 URL 和跳转链路（异步）"""
        def fmt_list(lst):
            if not lst:
                return "无"
            return ", ".join(lst[:10])
        
        prompt = URL_AGENT_PROMPT.format(
            url=url,
            a_href=fmt_list(redirect_links.get("a_href", [])),
            form_action=fmt_list(redirect_links.get("form_action", [])),
            iframe_src=fmt_list(redirect_links.get("iframe_src", [])),
            script_src=fmt_list(redirect_links.get("script_src", [])),
            meta_refresh=fmt_list(redirect_links.get("meta_refresh", [])),
            js_redirect=fmt_list(redirect_links.get("js_redirect", [])),
        )
        
        response = await self.api.chat_text(prompt)
        result = parse_json_response(response)
        
        if result is None:
            print(f"  [URL Agent] JSON解析失败，原始回复: {response[:200]}")
            return self._fallback(url, redirect_links)
        
        result.setdefault("url_claim", "LEGITIMATE")
        result.setdefault("url_confidence", 0.5)
        result.setdefault("url_brand", [])
        result.setdefault("url_suspicious_redirects", [])
        result.setdefault("redirect_count", 0)
        result.setdefault("external_redirect_ratio", 0.0)
        result.setdefault("form_action_external", False)
        result.setdefault("has_hidden_redirect", False)
        result.setdefault("url_evidence", "")
        
        return result
    
    def _fallback(self, url: str, redirect_links: Dict) -> Dict:
        """JSON 解析失败时的简单规则化兜底"""
        redirect_count = sum(len(v) for v in redirect_links.values())
        has_hidden = bool(redirect_links.get("meta_refresh") or redirect_links.get("js_redirect"))
        
        return {
            "url_claim": "LEGITIMATE",
            "url_confidence": 0.3,
            "url_brand": [],
            "url_suspicious_redirects": [],
            "redirect_count": redirect_count,
            "external_redirect_ratio": 0.0,
            "form_action_external": False,
            "has_hidden_redirect": has_hidden,
            "url_evidence": "JSON解析失败，使用默认值",
        }
