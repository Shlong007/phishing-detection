"""
消融实验 E1-E19（离线实现，不调API）
从 full_all_merged.json 的 agent_details 重算 consistency + judgment

E1-E4: 单Agent模态（直接用claim作verdict）
E5: 纯文本三Agent（视觉置空，重算+rejudge，阈值调整）
E6: 4Agent简单投票（无一致性/RAG）
E7-E10: 去某个Agent（字段置空，重算+rejudge）
E11-E13: 仅单个度量（覆盖CS）
E14: 完整一致性无RAG（brand_match强制True）
E15: +RAG（当前默认rejudge）
E17: 完整方法（规则化裁决基准）
E18: 含跳转链路（=E17）
E19: 去跳转链路（跳转特征置False）
E16: 跳过（需重跑API）
"""
import json
import sys
import numpy as np
from pathlib import Path
from copy import deepcopy

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.consistency import compute_consistency, normalize_brand
from agents.judge import identify_brand, final_judgment
from agents.rag import BrandKnowledgeBase

RESULTS_FILE = PROJECT_ROOT / "results" / "full_all_merged.json"
OUTPUT_DIR = Path(__file__).parent / "ablation_results"
OUTPUT_DIR.mkdir(exist_ok=True)


def compute_metrics(y_true, y_pred):
    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))
    total = tp + tn + fp + fn
    acc = (tp + tn) / total if total else 0
    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
    return {"TP": tp, "TN": tn, "FP": fp, "FN": fn,
            "Accuracy": acc, "Precision": prec, "Recall": rec, "F1": f1}


def empty_agent():
    """空Agent输出（claim=LEGITIMATE，所有字段置空/默认）"""
    return {
        "url_claim": "LEGITIMATE", "url_brand": [], "url_confidence": 0,
        "url_suspicious_redirects": [], "redirect_count": 0,
        "external_redirect_ratio": 0, "form_action_external": False,
        "has_hidden_redirect": False, "url_evidence": "",
        "url_function": "other",
    }


def empty_html_agent():
    return {
        "html_claim": "LEGITIMATE", "html_brand": [], "html_confidence": 0,
        "html_function": "other", "has_form": False, "form_action": "",
        "has_hidden_element": False, "has_iframe": False, "iframe_src": "",
        "html_key_info": [], "html_evidence": "",
    }


def empty_text_agent():
    return {
        "text_claim": "LEGITIMATE", "text_brand": [], "text_confidence": 0,
        "text_function": "other", "has_urgency": False,
        "has_credential_request": False, "has_trust_language": False,
        "has_grammar_error": False, "text_key_info": [], "text_evidence": "",
    }


def empty_vision_agent():
    return {
        "vis_claim": "LEGITIMATE", "vis_brand": [], "vis_confidence": 0,
        "vis_function": "other", "has_login_form": False,
        "form_prompt_text": "", "button_text": "", "has_urgency": False,
        "vis_key_info": [], "vis_evidence": "",
    }


# ============ E1-E4: 单Agent模态 ============

def run_single_agent(results, agent_key, claim_key, exp_id, exp_name):
    """E1-E4: 只用单个Agent的claim作为verdict"""
    y_true, y_pred = [], []
    for r in results:
        claim = r.get("agent_details", {}).get(agent_key, {}).get(claim_key, "LEGITIMATE")
        y_true.append(1 if r["true_label"] == "phish" else 0)
        y_pred.append(1 if claim == "PHISHING" else 0)
    m = compute_metrics(np.array(y_true), np.array(y_pred))
    print(f"  {exp_id} {exp_name}: Acc={m['Accuracy']:.4f} F1={m['F1']:.4f}")
    return m


# ============ E5/E7-E10/E14/E15/E17-E19: 重算+rejudge ============

def rejudge_with_config(sample, kb, config):
    """参数化消融重判
    
    config支持:
        remove_url/html/text/vision: 屏蔽对应Agent
        bis_only/fis_only/igs_only: 仅用单个度量
        disable_rag: 禁用RAG（brand_match强制True）
        disable_redirect: 禁用跳转链路特征
        vote_threshold: 投票阈值（默认用judge.py的规则）
    """
    ad = sample.get("agent_details", {})
    url_r = deepcopy(ad.get("url", {}))
    html_r = deepcopy(ad.get("html", {}))
    text_r = deepcopy(ad.get("text", {}))
    vis_r = deepcopy(ad.get("vision", {}))

    # 屏蔽Agent
    if config.get("remove_url"):
        url_r = empty_agent()
    if config.get("remove_html"):
        html_r = empty_html_agent()
    if config.get("remove_text"):
        text_r = empty_text_agent()
    if config.get("remove_vision"):
        vis_r = empty_vision_agent()

    # 重算consistency
    consistency = compute_consistency(url_r, html_r, text_r, vis_r)

    # 度量消融
    if config.get("bis_only"):
        consistency["FIS"] = 0.0
        consistency["IGS"] = 0.0
        consistency["CS"] = consistency["BIS"]
    elif config.get("fis_only"):
        consistency["BIS"] = 0.0
        consistency["IGS"] = 0.0
        consistency["CS"] = consistency["FIS"]
    elif config.get("igs_only"):
        consistency["BIS"] = 0.0
        consistency["FIS"] = 0.0
        consistency["CS"] = consistency["IGS"]

    # 品牌识别+RAG
    brand_name = identify_brand(url_r, html_r, text_r, vis_r)
    vis_function = vis_r.get("vis_function", "other")
    rag_result = kb.verify(brand_name, sample.get("url", ""), vis_function)

    # 禁用RAG
    if config.get("disable_rag"):
        rag_result = {"brand_name": "", "brand_match": True, "reason": ""}

    # 禁用跳转链路
    if config.get("disable_redirect"):
        url_r["form_action_external"] = False
        url_r["has_hidden_redirect"] = False

    # rejudge
    judgment = final_judgment(url_r, html_r, text_r, vis_r, consistency, rag_result)
    return judgment


def run_rejudge_ablation(results, kb, config, exp_id, exp_name):
    """通用重判消融"""
    y_true, y_pred = [], []
    for r in results:
        try:
            j = rejudge_with_config(r, kb, config)
            verdict = j["verdict"]
        except Exception:
            verdict = "LEGITIMATE"
        y_true.append(1 if r["true_label"] == "phish" else 0)
        y_pred.append(1 if verdict == "PHISHING" else 0)
    m = compute_metrics(np.array(y_true), np.array(y_pred))
    print(f"  {exp_id} {exp_name}: Acc={m['Accuracy']:.4f} F1={m['F1']:.4f}")
    return m


# ============ E5: 纯文本三Agent（需调整投票阈值）============

def final_judgment_3agent(url_result, html_result, text_result, vis_result,
                          consistency, rag_result):
    """3-Agent版本裁决（规则1从≥3改为≥2，因为只有3票）"""
    votes = [
        url_result.get("url_claim", "LEGITIMATE"),
        html_result.get("html_claim", "LEGITIMATE"),
        text_result.get("text_claim", "LEGITIMATE"),
        # vis_result被置空，claim=LEGITIMATE
    ]
    phishing_votes = sum(1 for v in votes if v == "PHISHING")
    cs = consistency.get("CS", 0.0)
    igs = consistency.get("IGS", 0.0)
    brand_match = rag_result.get("brand_match", True)
    brand_name = rag_result.get("brand_name", "")
    has_suspicious_redirect = (
        url_result.get("form_action_external", False) or
        url_result.get("has_hidden_redirect", False)
    )

    # 规则1（调整）：≥2票钓鱼（3-Agent下≥2即过半）
    if phishing_votes >= 2:
        return {"verdict": "PHISHING"}
    # 规则3
    if cs >= 0.6 and brand_match is False and brand_name:
        return {"verdict": "PHISHING"}
    # 规则4
    if cs >= 0.8 and phishing_votes >= 1:
        return {"verdict": "PHISHING"}
    # 规则5
    if brand_match is False and brand_name:
        return {"verdict": "PHISHING"}
    # 规则6
    if has_suspicious_redirect and phishing_votes >= 2:
        return {"verdict": "PHISHING"}
    # 默认合法
    return {"verdict": "LEGITIMATE"}


def run_e5_text3agent(results, kb):
    """E5: 纯文本三Agent（PhishDebate对标）"""
    y_true, y_pred = [], []
    for r in results:
        ad = r.get("agent_details", {})
        url_r = deepcopy(ad.get("url", {}))
        html_r = deepcopy(ad.get("html", {}))
        text_r = deepcopy(ad.get("text", {}))
        vis_r = empty_vision_agent()  # 视觉置空

        consistency = compute_consistency(url_r, html_r, text_r, vis_r)
        brand_name = identify_brand(url_r, html_r, text_r, vis_r)
        rag_result = kb.verify(brand_name, r.get("url", ""), "other")

        j = final_judgment_3agent(url_r, html_r, text_r, vis_r, consistency, rag_result)
        y_true.append(1 if r["true_label"] == "phish" else 0)
        y_pred.append(1 if j["verdict"] == "PHISHING" else 0)
    m = compute_metrics(np.array(y_true), np.array(y_pred))
    print(f"  E5 纯文本三Agent: Acc={m['Accuracy']:.4f} F1={m['F1']:.4f}")
    return m


# ============ E6: 4Agent简单投票 ============

def run_e6_vote(results):
    """E6: 4Agent简单投票（≥2判钓鱼，无一致性/RAG）"""
    y_true, y_pred = [], []
    for r in results:
        y_true.append(1 if r["true_label"] == "phish" else 0)
        y_pred.append(1 if r["phishing_votes"] >= 2 else 0)
    m = compute_metrics(np.array(y_true), np.array(y_pred))
    print(f"  E6 4Agent简单投票(≥2): Acc={m['Accuracy']:.4f} F1={m['F1']:.4f}")
    return m


# ============ E17/E18: 完整方法基准 ============

def run_full_method(results):
    """E17/E18: 完整方法（直接用verdict）"""
    y_true = np.array([1 if r["true_label"] == "phish" else 0 for r in results])
    y_pred = np.array([1 if r["verdict"] == "PHISHING" else 0 for r in results])
    m = compute_metrics(y_true, y_pred)
    print(f"  E17/E18 完整方法: Acc={m['Accuracy']:.4f} F1={m['F1']:.4f}")
    return m


# ============ 主函数 ============

def main():
    print("加载全量结果...")
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        results = json.load(f)
    print(f"加载了 {len(results)} 个样本")

    print("加载品牌知识库...")
    kb = BrandKnowledgeBase()

    all_metrics = {}

    # === 第一组：模态消融 ===
    print("\n=== 第一组：模态消融 E1-E6 ===")
    all_metrics["E1"] = run_single_agent(results, "url", "url_claim", "E1", "仅URL")
    all_metrics["E2"] = run_single_agent(results, "html", "html_claim", "E2", "仅HTML")
    all_metrics["E3"] = run_single_agent(results, "text", "text_claim", "E3", "仅文本")
    all_metrics["E4"] = run_single_agent(results, "vision", "vis_claim", "E4", "仅视觉")
    all_metrics["E5"] = run_e5_text3agent(results, kb)
    all_metrics["E6"] = run_e6_vote(results)

    # === 第二组：Agent消融 ===
    print("\n=== 第二组：Agent消融 E7-E10 ===")
    all_metrics["E7"] = run_rejudge_ablation(results, kb, {"remove_url": True}, "E7", "去URL")
    all_metrics["E8"] = run_rejudge_ablation(results, kb, {"remove_html": True}, "E8", "去HTML")
    all_metrics["E9"] = run_rejudge_ablation(results, kb, {"remove_text": True}, "E9", "去文本")
    all_metrics["E10"] = run_rejudge_ablation(results, kb, {"remove_vision": True}, "E10", "去视觉")

    # === 第三组：核心模块消融 ===
    print("\n=== 第三组：核心模块消融 E11-E15/E17 ===")
    all_metrics["E11"] = run_rejudge_ablation(results, kb, {"bis_only": True}, "E11", "仅BIS")
    all_metrics["E12"] = run_rejudge_ablation(results, kb, {"fis_only": True}, "E12", "仅FIS")
    all_metrics["E13"] = run_rejudge_ablation(results, kb, {"igs_only": True}, "E13", "仅IGS")
    all_metrics["E14"] = run_rejudge_ablation(results, kb, {"disable_rag": True}, "E14", "一致性无RAG")
    all_metrics["E15"] = run_rejudge_ablation(results, kb, {}, "E15", "+RAG")
    all_metrics["E17"] = run_full_method(results)

    # === 第四组：跳转链路消融 ===
    print("\n=== 第四组：跳转链路消融 E18-E19 ===")
    all_metrics["E18"] = run_full_method(results)  # 同E17
    all_metrics["E19"] = run_rejudge_ablation(results, kb, {"disable_redirect": True}, "E19", "去跳转链路")

    # === 生成对比表 ===
    print("\n" + "=" * 90)
    print("消融实验对比表")
    print("=" * 90)
    header = f"{'编号':<6} {'实验名称':<22} {'Acc':<8} {'Prec':<8} {'Rec':<8} {'F1':<8} {'TP':<6} {'TN':<6} {'FP':<6} {'FN':<6}"
    print(header)
    print("-" * 90)

    lines = [header, "-" * 90]
    exp_names = {
        "E1": "仅URL", "E2": "仅HTML", "E3": "仅文本", "E4": "仅视觉",
        "E5": "纯文本三Agent", "E6": "4Agent简单投票",
        "E7": "去URL", "E8": "去HTML", "E9": "去文本", "E10": "去视觉",
        "E11": "仅BIS", "E12": "仅FIS", "E13": "仅IGS",
        "E14": "一致性无RAG", "E15": "+RAG",
        "E17": "完整方法", "E18": "含跳转链路", "E19": "去跳转链路",
    }

    for eid in ["E1","E2","E3","E4","E5","E6","E7","E8","E9","E10",
                 "E11","E12","E13","E14","E15","E17","E18","E19"]:
        m = all_metrics[eid]
        name = exp_names[eid]
        line = f"{eid:<6} {name:<22} {m['Accuracy']:.4f}  {m['Precision']:.4f}  {m['Recall']:.4f}  {m['F1']:.4f}  {m['TP']:<6} {m['TN']:<6} {m['FP']:<6} {m['FN']:<6}"
        print(line)
        lines.append(line)

    table_text = "\n".join(lines)
    with open(OUTPUT_DIR / "ablation_table.txt", "w", encoding="utf-8") as f:
        f.write(table_text)
    print(f"\n对比表已保存到: {OUTPUT_DIR / 'ablation_table.txt'}")

    with open(OUTPUT_DIR / "all_ablation_metrics.json", "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, ensure_ascii=False, indent=2)
    print(f"所有指标已保存到: {OUTPUT_DIR / 'all_ablation_metrics.json'}")


if __name__ == "__main__":
    main()
