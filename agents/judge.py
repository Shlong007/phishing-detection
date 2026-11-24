"""
裁判 Agent：综合四路 Agent 输出、一致性度量与 RAG 验证得到最终判定。
"""
from typing import Dict
from collections import Counter

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from agents.consistency import normalize_brand


def identify_brand(url_result: Dict, html_result: Dict,
                   text_result: Dict, vis_result: Dict) -> str:
    """
    从各 Agent 输出中识别目标品牌（取众数或最可信的）
    优先取视觉识别的（最可靠），其次文本
    """
    all_brands = []
    
    # 视觉识别的品牌（权重最高）
    vis_brands = vis_result.get("vis_brand", [])
    all_brands.extend(vis_brands * 2)  # 视觉识别权重 x2
    
    # 其他来源
    all_brands.extend(url_result.get("url_brand", []))
    all_brands.extend(html_result.get("html_brand", []))
    all_brands.extend(text_result.get("text_brand", []))
    
    if not all_brands:
        return ""
    
    # 归一化后取众数
    normed = [normalize_brand(b) for b in all_brands if b]
    normed = [b for b in normed if b]
    
    if not normed:
        return ""
    
    counter = Counter(normed)
    return counter.most_common(1)[0][0]


def final_judgment(url_result: Dict, html_result: Dict,
                   text_result: Dict, vis_result: Dict,
                   consistency: Dict, rag_result: Dict) -> Dict:
    """
    综合所有 Agent 输出做最终判定
    
    基于规则的裁决逻辑（按优先级）
    """
    # === 投票统计 ===
    votes = [
        url_result.get("url_claim", "LEGITIMATE"),
        html_result.get("html_claim", "LEGITIMATE"),
        text_result.get("text_claim", "LEGITIMATE"),
        vis_result.get("vis_claim", "LEGITIMATE")
    ]
    phishing_votes = sum(1 for v in votes if v == "PHISHING")
    
    # === 一致性得分 ===
    cs = consistency.get("CS", 0.0)
    bis = consistency.get("BIS", 0.0)
    fis = consistency.get("FIS", 0.0)
    igs = consistency.get("IGS", 0.0)
    
    # === RAG 验证 ===
    brand_match = rag_result.get("brand_match", True)
    brand_name = rag_result.get("brand_name", "")
    
    # === 跳转链路可疑 ===
    has_suspicious_redirect = (
        url_result.get("form_action_external", False) or
        url_result.get("has_hidden_redirect", False)
    )
    
    # 裁决规则，按优先级短路执行
    
    evidence = ""
    
    # 规则1：3+个Agent判钓鱼 -> 强烈钓鱼
    if phishing_votes >= 3:
        confidence = 0.9
        verdict = "PHISHING"
        evidence = f"{phishing_votes}个Agent判定为钓鱼；" + \
                   f"一致性得分={cs:.2f}"
    
    # 规则2.5：图像规避型（url+html 均判钓鱼、text 判合法、IGS≥0.5、≥2 票）
    elif (url_result.get("url_claim") == "PHISHING" and
          html_result.get("html_claim") == "PHISHING" and
          text_result.get("text_claim") != "PHISHING" and
          igs >= 0.5 and
          phishing_votes >= 2):
        confidence = 0.85
        verdict = "PHISHING"
        evidence = f"图像规避型：URL+HTML双结构判钓鱼且文本侧未发现(IGS={igs:.2f})，" + \
                   f"钓鱼信息可能藏在图片中（CS={cs:.2f}因BIS/FIS为0被稀释）"
    
    # 规则2：视觉判钓鱼且 IGS、CS 均较高，文本侧未判钓鱼 -> 图像规避型
    elif (vis_result.get("vis_claim") == "PHISHING" and
          igs >= 0.5 and
          phishing_votes >= 2 and
          cs >= 0.5 and
          url_result.get("url_claim") != "PHISHING"):
        confidence = 0.85
        verdict = "PHISHING"
        evidence = f"图像规避型：视觉判钓鱼(IGS={igs:.2f}, CS={cs:.2f})，" + \
                   f"但URL/文本侧未发现，钓鱼信息可能藏在图片中"
    
    # 规则3：CS高 + RAG品牌不匹配 -> 钓鱼（需要双重信号）
    elif cs >= 0.6 and brand_match is False and brand_name:
        confidence = 0.8
        verdict = "PHISHING"
        evidence = f"跨模态不一致(CS={cs:.2f})且品牌验证失败：" + \
                   f"{rag_result.get('reason', '')}"
    
    # 规则4：CS很高(≥0.8) + 至少2票钓鱼 -> 钓鱼
    elif cs >= 0.8 and phishing_votes >= 2:
        confidence = 0.75
        verdict = "PHISHING"
        evidence = f"强跨模态不一致(CS={cs:.2f})，{phishing_votes}个Agent判钓鱼"
    
    # 规则5：RAG 品牌不匹配 + 有品牌识别 -> 可疑
    elif brand_match is False and brand_name:
        confidence = 0.75
        verdict = "PHISHING"
        evidence = f"识别到品牌{brand_name}，但{rag_result.get('reason', '')}"
    
    # 规则6：跳转链路可疑 + 至少3票钓鱼 -> 钓鱼
    elif has_suspicious_redirect and phishing_votes >= 3:
        confidence = 0.75
        verdict = "PHISHING"
        redirect_reasons = []
        if url_result.get("form_action_external"):
            redirect_reasons.append("表单提交到外部域名")
        if url_result.get("has_hidden_redirect"):
            redirect_reasons.append("存在隐藏重定向")
        evidence = "可疑跳转：" + "、".join(redirect_reasons) + f"，{phishing_votes}票钓鱼"
    
    # 规则7：多数判合法且一致性可接受 -> 合法
    elif phishing_votes <= 1:
        confidence = 0.8
        verdict = "LEGITIMATE"
        evidence = f"{4-phishing_votes}个Agent判定为合法，" + \
                   f"CS={cs:.2f}"
    
    # 规则8：2票钓鱼但CS不高且RAG匹配 -> 合法
    elif phishing_votes == 2 and cs < 0.6 and brand_match is not False:
        confidence = 0.7
        verdict = "LEGITIMATE"
        evidence = f"虽有2票钓鱼，但跨模态一致(CS={cs:.2f})，品牌验证通过"
    
    # 规则9：默认保守判定
    else:
        confidence = 0.6
        verdict = "LEGITIMATE"
        evidence = f"证据不足以判定为钓鱼(投票={phishing_votes}/4, " + \
                   f"CS={cs:.2f})，默认判定为合法"
    
    return {
        "verdict": verdict,
        "confidence": round(confidence, 2),
        "votes": {
            "url": votes[0],
            "html": votes[1],
            "text": votes[2],
            "visual": votes[3]
        },
        "phishing_votes": phishing_votes,
        "BIS": bis,
        "FIS": fis,
        "IGS": igs,
        "CS": cs,
        "inconsistency_type": consistency.get("inconsistency_type", []),
        "rag_result": rag_result,
        "evidence": evidence
    }
