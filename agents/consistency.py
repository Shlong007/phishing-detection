"""
Agent 5: 跨模态一致性校验 Agent
核心创新模块 - 计算 BIS/FIS/IGS 三个不一致性度量

这是纯计算模块，不需要调用 LLM
基于 4 个专门 Agent 的结构化输出直接计算
"""
import json
from typing import Dict, List, Set, Tuple
from difflib import SequenceMatcher

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from config import W_BIS, W_FIS, W_IGS, CS_THRESHOLD, BRAND_ALIASES_PATH


# ============ 品牌归一化 ============

# 品牌别名表（常见变体 -> 标准名）
BRAND_ALIASES = {
    # PayPal
    "paypal": "paypal",
    "paypal inc": "paypal",
    "paypal.com": "paypal",
    "pay pal": "paypal",
    # Google
    "google": "google",
    "google llc": "google",
    "google.com": "google",
    # Apple
    "apple": "apple",
    "apple id": "apple",
    "apple.com": "apple",
    "icloud": "apple",
    # Microsoft
    "microsoft": "microsoft",
    "microsoft account": "microsoft",
    "microsoft.com": "microsoft",
    "outlook": "microsoft",
    "office": "microsoft",
    "office365": "microsoft",
    # Facebook
    "facebook": "facebook",
    "meta": "facebook",
    "fb": "facebook",
    # Amazon
    "amazon": "amazon",
    "amazon.com": "amazon",
    # Netflix
    "netflix": "netflix",
    # Yahoo
    "yahoo": "yahoo",
    "yahoo mail": "yahoo",
    # Others
    "dropbox": "dropbox",
    "adobe": "adobe",
    "linkedin": "linkedin",
    "ebay": "ebay",
    "dhl": "dhl",
    "wells fargo": "wellsfargo",
    "wellsfargo": "wellsfargo",
    "bank of america": "boa",
    "boa": "boa",
    "chase": "chase",
    "cibc": "cibc",
    "bmo": "bmo",
    "natwest": "natwest",
    "hsbc": "hsbc",
    "santander": "santander",
    "bradesco": "bradesco",
    "caixa": "caixa",
    "itau": "itau",
    "sparkasse": "sparkasse",
    "nab": "nab",
    "usaa": "usaa",
    "xfinity": "xfinity",
    "comcast": "xfinity",
    "tmobile": "tmobile",
    "cox": "cox",
    "bt": "bt",
    "aol": "aol",
    "irs": "irs",
    "match": "match",
    "navy": "navy",
    "capitalone": "capitalone",
    "capital one": "capitalone",
    "allegro": "allegro",
    "amex": "amex",
    "american express": "amex",
    "att": "att",
    "orange": "orange",
    "sfr": "sfr",
    "mic": "mic",
    "impots": "impots",
}


def _load_aliases_from_file():
    """从文件加载完整的别名表"""
    global BRAND_ALIASES
    if BRAND_ALIASES_PATH.exists():
        try:
            with open(BRAND_ALIASES_PATH, "r", encoding="utf-8") as f:
                file_aliases = json.load(f)
            BRAND_ALIASES = {**BRAND_ALIASES, **file_aliases}
        except Exception:
            pass

# 模块加载时自动合并文件版别名
_load_aliases_from_file()


def normalize_brand(brand: str) -> str:
    """品牌名归一化"""
    if not brand:
        return ""
    key = brand.lower().strip()
    # 去除常见后缀（Inc, LLC, Corp等）
    for suffix in [" inc", " llc", " corp", " corporation", " company"]:
        if key.endswith(suffix):
            key = key[:-len(suffix)]
    return BRAND_ALIASES.get(key, key)


def normalize_brands(brands: List[str]) -> Set[str]:
    """品牌列表归一化"""
    result = set()
    for b in brands:
        normed = normalize_brand(b)
        if normed:
            result.add(normed)
    return result


def fuzzy_brand_match(brand_a: str, brand_b: str, threshold: float = 0.7) -> bool:
    """
    模糊品牌匹配（处理OCR识别错误/大小写/空格差异）
    如 "shoptyt" vs "s-hyotp" 应能匹配
    """
    if not brand_a or not brand_b:
        return False
    a = brand_a.lower().replace(" ", "").replace("-", "").replace("_", "")
    b = brand_b.lower().replace(" ", "").replace("-", "").replace("_", "")
    if a == b:
        return True
    # 完全包含
    if a in b or b in a:
        return True
    # 字符序列相似度
    ratio = SequenceMatcher(None, a, b).ratio()
    if ratio >= threshold:
        return True
    # 字符集相似度（处理字母相同但顺序不同的情况，如OCR错误）
    set_a = set(a)
    set_b = set(b)
    if len(set_a) > 0 and len(set_b) > 0:
        jaccard = len(set_a & set_b) / len(set_a | set_b)
        # 字符集高度重合且长度相近，可能是同一品牌的不同识别
        if jaccard >= 0.85 and abs(len(a) - len(b)) <= 2:
            return True
    return False


def fuzzy_set_intersect(set_a: Set[str], set_b: Set[str], threshold: float = 0.7) -> Set[str]:
    """
    两个品牌集合的模糊交集
    返回模糊匹配上的品牌对
    """
    matched = set()
    for a in set_a:
        for b in set_b:
            if fuzzy_brand_match(a, b, threshold):
                matched.add(a)
                break
    return matched


# ============ 语义匹配工具 ============

def semantic_match(item: str, target_list: List[str], threshold: float = 0.6) -> bool:
    """
    检查 item 是否在 target_list 中（支持模糊匹配）
    用 SequenceMatcher 做字符串相似度
    """
    item_lower = item.lower().strip()
    for target in target_list:
        target_lower = target.lower().strip()
        # 精确包含
        if item_lower in target_lower or target_lower in item_lower:
            return True
        # 模糊匹配
        ratio = SequenceMatcher(None, item_lower, target_lower).ratio()
        if ratio >= threshold:
            return True
    return False


def find_missing_items(source: Set[str], target: List[str]) -> List[str]:
    """
    找出 source 中有但 target 中没有的项目（语义匹配）
    """
    target_list = list(target)
    missing = []
    for item in source:
        if not semantic_match(item, target_list):
            missing.append(item)
    return missing


# ============ BIS 计算：品牌不一致度 ============

def compute_bis(url_result: Dict, html_result: Dict, 
                text_result: Dict, vis_result: Dict) -> Tuple[float, Dict]:
    """
    多源品牌不一致度计算
    
    文本侧品牌集合（URL + HTML + Text）vs 视觉侧品牌集合（Visual）
    使用模糊匹配处理OCR识别错误
    """
    B_url = normalize_brands(url_result.get("url_brand", []))
    B_html = normalize_brands(html_result.get("html_brand", []))
    B_text = normalize_brands(text_result.get("text_brand", []))
    B_vis = normalize_brands(vis_result.get("vis_brand", []))
    
    # 文本侧合并
    B_text_all = B_url | B_html | B_text
    B_visual = B_vis
    
    if len(B_text_all) == 0 and len(B_visual) == 0:
        bis = 0.0  # 都没识别到品牌
    elif len(B_text_all) == 0 or len(B_visual) == 0:
        bis = 0.5  # 一方有品牌，另一方缺失
    else:
        # 用模糊匹配计算交集（处理OCR错误如ShopTYT vs S-HyOtP）
        intersection = fuzzy_set_intersect(B_text_all, B_visual, threshold=0.7)
        union = B_text_all | B_visual
        
        # 如果有模糊匹配，说明可能是OCR误差，不是真不一致
        if len(intersection) > 0:
            bis = 0.0  # 模糊匹配上了，认为一致
        else:
            bis = 1.0 - (len(intersection) / len(union))
    
    # 检测文本侧内部一致性
    text_internal_consistent = B_url <= B_text_all  # URL品牌应在文本集合中
    
    detail = {
        "B_url": list(B_url),
        "B_html": list(B_html),
        "B_text": list(B_text),
        "B_vis": list(B_vis),
        "B_text_all": list(B_text_all),
        "B_visual": list(B_visual),
        "text_internal_consistent": text_internal_consistent,
    }
    
    return bis, detail


# ============ FIS 计算：功能不一致度 ============

def compute_fis(html_result: Dict, text_result: Dict, vis_result: Dict) -> Tuple[float, Dict]:
    """
    多源功能不一致度计算
    
    对比 HTML、文本、视觉三方的功能判断
    """
    F_html = html_result.get("html_function", "other")
    F_text = text_result.get("text_function", "other")
    F_vis = vis_result.get("vis_function", "other")
    
    # 归一化（去掉中文描述，保留类别名）
    def normalize_function(f):
        f = f.lower().strip()
        for cat in ["login", "email", "shopping", "banking", "social_media",
                     "government", "tech_support", "entertainment", "other"]:
            if cat in f:
                return cat
        return "other"
    
    F_html = normalize_function(F_html)
    F_text = normalize_function(F_text)
    F_vis = normalize_function(F_vis)
    
    text_functions = {F_html, F_text} - {"other"}
    vis_functions = {F_vis} - {"other"}
    
    if len(text_functions) == 0 and len(vis_functions) == 0:
        fis = 0.5  # 信息不足
    elif len(text_functions) == 0 or len(vis_functions) == 0:
        fis = 0.5  # 一方缺失
    elif text_functions == vis_functions:
        fis = 0.0  # 一致
    else:
        fis = 1.0  # 矛盾
    
    detail = {
        "F_html": F_html,
        "F_text": F_text,
        "F_vis": F_vis,
    }
    
    return fis, detail


# ============ IGS 计算：信息缺失度 ============

def compute_igs(url_result: Dict, html_result: Dict, 
                text_result: Dict, vis_result: Dict) -> Tuple[float, Dict]:
    """
    信息缺失度计算
    
    视觉信息 vs 文本信息（URL + HTML + Text）
    检查截图中的关键信息在 HTML 文本中是否缺失
    """
    K_vis = set(vis_result.get("vis_key_info", []))
    K_url = set(url_result.get("url_suspicious_redirects", []))
    K_html = set(html_result.get("html_key_info", []))
    K_text = set(text_result.get("text_key_info", []))
    
    # 文本侧合并
    K_text_all = list(K_url | K_html | K_text)
    
    if len(K_vis) == 0:
        igs = 0.0
        missing = []
    else:
        # 语义匹配：检查文本侧是否覆盖了视觉侧的信息
        missing = find_missing_items(K_vis, K_text_all)
        igs = len(missing) / len(K_vis)
    
    detail = {
        "K_vis_count": len(K_vis),
        "K_text_count": len(K_text_all),
        "missing_items": missing,
    }
    
    return igs, detail


# ============ 综合一致性校验 ============

def compute_consistency(url_result: Dict, html_result: Dict,
                        text_result: Dict, vis_result: Dict) -> Dict:
    """
    综合一致性校验：整合 4 个 Agent 的输出
    
    Returns:
        {
            "BIS": 品牌不一致度,
            "FIS": 功能不一致度,
            "IGS": 信息缺失度,
            "CS": 综合一致性得分,
            "inconsistency_type": [不一致类型列表],
            "details": 详细信息
        }
    """
    bis, bis_detail = compute_bis(url_result, html_result, text_result, vis_result)
    fis, fis_detail = compute_fis(html_result, text_result, vis_result)
    igs, igs_detail = compute_igs(url_result, html_result, text_result, vis_result)
    
    # 综合得分
    cs = W_BIS * bis + W_FIS * fis + W_IGS * igs
    
    # 不一致类型分类
    types = []
    if bis >= 0.5:
        types.append("brand_mismatch")
    if fis >= 1.0:
        types.append("function_contradiction")
    if igs >= 0.5:
        types.append("image_hidden_info")
    if not bis_detail.get("text_internal_consistent", True):
        types.append("text_internal_inconsistency")
    
    return {
        "BIS": round(bis, 4),
        "FIS": round(fis, 4),
        "IGS": round(igs, 4),
        "CS": round(cs, 4),
        "inconsistency_type": types if types else ["consistent"],
        "details": {
            "bis": bis_detail,
            "fis": fis_detail,
            "igs": igs_detail,
        }
    }


def classify_inconsistency(cs: float, bis: float, fis: float, igs: float) -> str:
    """对不一致性做人类可读的分类"""
    if cs < 0.2:
        return "一致（低风险）"
    elif igs >= 0.5:
        return "图像规避型（信息藏在图片中）"
    elif fis >= 1.0:
        return "功能矛盾型（文本和视觉功能不一致）"
    elif bis >= 0.5:
        return "品牌不一致型（文本和视觉品牌不匹配）"
    else:
        return "轻度不一致（需进一步检查）"
