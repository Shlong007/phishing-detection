"""
品牌知识库模块
- 预定义 46 个品牌的合法特征
"""
import json
from pathlib import Path
from typing import Dict, Optional, List
from urllib.parse import urlparse

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from config import BRAND_KB_PATH
from agents.consistency import normalize_brand, BRAND_ALIASES


# 预定义的品牌知识库（核心品牌）
# 后续可以用 build_brand_kb.py 从 trainval 的合法样本自动扩展
BUILT_IN_BRAND_KB = {
    "paypal": {
        "legitimate_domains": ["paypal.com", "paypalobjects.com", "paypal.me"],
        "legitimate_tld": [".com"],
        "legitimate_functions": ["banking", "login"],
        "description": "PayPal 在线支付平台",
    },
    "google": {
        "legitimate_domains": ["google.com", "googleapis.com", "gstatic.com", 
                                "accounts.google.com"],
        "legitimate_tld": [".com"],
        "legitimate_functions": ["login", "email", "tech_support"],
        "description": "Google 搜索和账户服务",
    },
    "apple": {
        "legitimate_domains": ["apple.com", "icloud.com", "appleid.apple.com"],
        "legitimate_tld": [".com"],
        "legitimate_functions": ["login", "tech_support"],
        "description": "Apple ID 和 iCloud 服务",
    },
    "microsoft": {
        "legitimate_domains": ["microsoft.com", "office.com", "outlook.com",
                                "live.com", "login.live.com"],
        "legitimate_tld": [".com"],
        "legitimate_functions": ["login", "email", "tech_support"],
        "description": "Microsoft 账户和 Office 服务",
    },
    "facebook": {
        "legitimate_domains": ["facebook.com", "fb.com", "meta.com"],
        "legitimate_tld": [".com"],
        "legitimate_functions": ["social_media", "login"],
        "description": "Facebook 社交平台",
    },
    "amazon": {
        "legitimate_domains": ["amazon.com", "amazonaws.com", "amazonpay.com"],
        "legitimate_tld": [".com"],
        "legitimate_functions": ["shopping", "login"],
        "description": "Amazon 电商平台",
    },
    "netflix": {
        "legitimate_domains": ["netflix.com"],
        "legitimate_tld": [".com"],
        "legitimate_functions": ["entertainment", "login"],
        "description": "Netflix 流媒体服务",
    },
    "yahoo": {
        "legitimate_domains": ["yahoo.com", "yahoo.co.jp"],
        "legitimate_tld": [".com"],
        "legitimate_functions": ["email", "login"],
        "description": "Yahoo 邮箱和门户",
    },
    "dropbox": {
        "legitimate_domains": ["dropbox.com"],
        "legitimate_tld": [".com"],
        "legitimate_functions": ["login", "tech_support"],
        "description": "Dropbox 云存储",
    },
    "adobe": {
        "legitimate_domains": ["adobe.com", "adobesign.com"],
        "legitimate_tld": [".com"],
        "legitimate_functions": ["login", "tech_support"],
        "description": "Adobe 创意云服务",
    },
    "linkedin": {
        "legitimate_domains": ["linkedin.com"],
        "legitimate_tld": [".com"],
        "legitimate_functions": ["social_media", "login"],
        "description": "LinkedIn 职业社交",
    },
    "ebay": {
        "legitimate_domains": ["ebay.com"],
        "legitimate_tld": [".com"],
        "legitimate_functions": ["shopping", "login"],
        "description": "eBay 电商平台",
    },
    "dhl": {
        "legitimate_domains": ["dhl.com", "dhl.de"],
        "legitimate_tld": [".com"],
        "legitimate_functions": ["tech_support"],
        "description": "DHL 物流",
    },
    "wellsfargo": {
        "legitimate_domains": ["wellsfargo.com"],
        "legitimate_tld": [".com"],
        "legitimate_functions": ["banking", "login"],
        "description": "Wells Fargo 银行",
    },
    "boa": {
        "legitimate_domains": ["bankofamerica.com"],
        "legitimate_tld": [".com"],
        "legitimate_functions": ["banking", "login"],
        "description": "Bank of America 银行",
    },
    "chase": {
        "legitimate_domains": ["chase.com"],
        "legitimate_tld": [".com"],
        "legitimate_functions": ["banking", "login"],
        "description": "Chase 银行",
    },
}


class BrandKnowledgeBase:
    """品牌知识库"""
    
    def __init__(self):
        # 先用内置知识库初始化
        self.kb = BUILT_IN_BRAND_KB.copy()
        self.aliases = dict(BRAND_ALIASES)  # 内置别名
        # 尝试从文件加载完整的知识库（46个品牌）
        self._load_from_file()
    
    def _load_from_file(self):
        """从文件加载完整的品牌知识库和别名表"""
        # 加载知识库
        if BRAND_KB_PATH.exists():
            try:
                with open(BRAND_KB_PATH, "r", encoding="utf-8") as f:
                    extra = json.load(f)
                self.kb.update(extra)
                print(f"  [RAG] 从文件加载了 {len(extra)} 个品牌知识，共 {len(self.kb)} 个")
            except Exception as e:
                print(f"  [RAG] 加载品牌知识文件失败: {e}")
        
        # 加载别名表（如果存在）
        aliases_path = BRAND_KB_PATH.parent / "brand_aliases.json"
        if aliases_path.exists():
            try:
                with open(aliases_path, "r", encoding="utf-8") as f:
                    file_aliases = json.load(f)
                self.aliases.update(file_aliases)
            except Exception as e:
                print(f"  [RAG] 加载别名表失败: {e}")
    
    def lookup(self, brand_name: str) -> Optional[Dict]:
        """查找品牌知识"""
        if not brand_name:
            return None
        normed = normalize_brand(brand_name)
        return self.kb.get(normed)
    
    def verify(self, brand_name: str, target_url: str, 
               vis_function: str = "other") -> Dict:
        """
        验证目标网站是否和合法品牌特征一致
        
        Args:
            brand_name: 识别到的品牌名
            target_url: 目标网站 URL
            vis_function: 视觉判断的页面功能
        
        Returns:
            品牌验证结果
        """
        if not brand_name:
            return {
                "brand_name": "",
                "brand_match": True,  # 无品牌不验证
                "url_pattern_match": 1.0,
                "function_match": True,
                "brand_confidence": 0.5,
                "reason": "未识别到品牌，无需验证"
            }
        
        brand_info = self.lookup(brand_name)
        if brand_info is None:
            return {
                "brand_name": brand_name,
                "brand_match": None,
                "url_pattern_match": 0.0,
                "function_match": None,
                "brand_confidence": 0.3,
                "reason": f"品牌 {brand_name} 不在知识库中"
            }
        
        # 验证 URL 模式
        target_domain = self._extract_domain(target_url)
        legit_domains = brand_info.get("legitimate_domains", [])
        url_match = any(
            target_domain == d or target_domain.endswith("." + d)
            for d in legit_domains
        )
        
        # 验证功能
        legit_functions = brand_info.get("legitimate_functions", [])
        function_match = vis_function in legit_functions if vis_function != "other" else None
        
        # 综合
        if url_match and (function_match is None or function_match):
            brand_match = True
            confidence = 0.85
            reason = "URL模式和功能与合法品牌一致"
        elif not url_match and function_match is False:
            brand_match = False
            confidence = 0.3
            reason = f"URL({target_domain})与合法域名({legit_domains})不匹配，功能也不一致"
        elif not url_match:
            brand_match = False
            confidence = 0.3
            reason = f"URL({target_domain})与合法域名({legit_domains})不匹配"
        else:
            brand_match = True
            confidence = 0.7
            reason = "URL匹配但功能不确定"
        
        return {
            "brand_name": brand_name,
            "brand_match": brand_match,
            "url_pattern_match": 1.0 if url_match else 0.0,
            "function_match": function_match,
            "expected_domains": legit_domains,
            "actual_domain": target_domain,
            "brand_confidence": confidence,
            "reason": reason
        }
    
    @staticmethod
    def _extract_domain(url: str) -> str:
        """从 URL 提取域名"""
        try:
            if not url.startswith("http"):
                url = "http://" + url
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # 去掉 www. 前缀
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return ""
    
    def list_brands(self) -> List[str]:
        """列出知识库中所有品牌"""
        return list(self.kb.keys())


if __name__ == "__main__":
    # 测试
    kb = BrandKnowledgeBase()
    print(f"知识库包含 {len(kb.list_brands())} 个品牌:")
    for brand in kb.list_brands():
        info = kb.lookup(brand)
        print(f"  {brand}: {info['description']}")
    
    print("\n=== 验证测试 ===")
    # 合法 PayPal
    result = kb.verify("paypal", "https://www.paypal.com/login", "login")
    print(f"合法 PayPal: {result['brand_match']}, {result['reason']}")
    
    # 钓鱼 PayPal（域名不匹配）
    result = kb.verify("paypal", "https://www.pay-koppel-beveiliging.nl/", "login")
    print(f"钓鱼 PayPal: {result['brand_match']}, {result['reason']}")
