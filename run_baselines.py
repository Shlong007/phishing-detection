"""
离线基线统一运行脚本（B1/B2/B4/B5/B7）
- B1: URL特征+随机森林（5折CV）
- B2: HTML特征+随机森林（5折CV）
- B4: 单模态LLM文本（复用TextAgent输出）
- B5: 单模态LLM视觉（复用VisionAgent输出）
- B7: 多Agent投票（≥2和≥3两种阈值）
"""
import json
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_predict, StratifiedKFold
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

PROJECT_ROOT = Path(__file__).parent
RESULTS_FILE = PROJECT_ROOT / "results" / "full_all_merged.json"
FEATURES_DIR = Path(__file__).parent / "features"
OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(exist_ok=True)


def compute_metrics(y_true, y_pred):
    """计算指标"""
    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    tn = int(np.sum((y_pred == 0) & (y_true == 1)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))
    return {
        "TP": tp, "TN": tn, "FP": fp, "FN": fn,
        "Accuracy": float(accuracy_score(y_true, y_pred)),
        "Precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "Recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "F1": float(f1_score(y_true, y_pred, zero_division=0)),
    }


def run_b1_url_rf():
    """B1: URL特征 + 随机森林（5折CV）"""
    print("\n=== B1: URL特征 + 随机森林 ===")
    X = np.load(FEATURES_DIR / "url_features.npy")
    y = np.load(FEATURES_DIR / "labels.npy")
    print(f"特征矩阵: {X.shape}, 标签分布: {np.bincount(y)}")

    clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    y_pred = cross_val_predict(clf, X, y, cv=cv, n_jobs=-1)

    metrics = compute_metrics(y, y_pred)
    print(f"  Acc={metrics['Accuracy']:.4f} P={metrics['Precision']:.4f} "
          f"R={metrics['Recall']:.4f} F1={metrics['F1']:.4f}")
    print(f"  TP={metrics['TP']} TN={metrics['TN']} FP={metrics['FP']} FN={metrics['FN']}")
    return metrics


def run_b2_html_rf():
    """B2: HTML特征 + 随机森林（5折CV）"""
    print("\n=== B2: HTML特征 + 随机森林 ===")
    X = np.load(FEATURES_DIR / "html_features.npy")
    y = np.load(FEATURES_DIR / "labels.npy")
    print(f"特征矩阵: {X.shape}, 标签分布: {np.bincount(y)}")

    clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    y_pred = cross_val_predict(clf, X, y, cv=cv, n_jobs=-1)

    metrics = compute_metrics(y, y_pred)
    print(f"  Acc={metrics['Accuracy']:.4f} P={metrics['Precision']:.4f} "
          f"R={metrics['Recall']:.4f} F1={metrics['F1']:.4f}")
    print(f"  TP={metrics['TP']} TN={metrics['TN']} FP={metrics['FP']} FN={metrics['FN']}")
    return metrics


def run_b4_text_llm(results):
    """B4: 单模态LLM文本（复用TextAgent输出）"""
    print("\n=== B4: 单模态LLM文本（复用TextAgent） ===")
    y_true = []
    y_pred = []
    for r in results:
        claim = r.get("agent_details", {}).get("text", {}).get("text_claim", "LEGITIMATE")
        y_true.append(1 if r["true_label"] == "phish" else 0)
        y_pred.append(1 if claim == "PHISHING" else 0)
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)

    metrics = compute_metrics(y_true, y_pred)
    print(f"  Acc={metrics['Accuracy']:.4f} P={metrics['Precision']:.4f} "
          f"R={metrics['Recall']:.4f} F1={metrics['F1']:.4f}")
    print(f"  TP={metrics['TP']} TN={metrics['TN']} FP={metrics['FP']} FN={metrics['FN']}")
    return metrics


def run_b5_vision_llm(results):
    """B5: 单模态LLM视觉（复用VisionAgent输出）"""
    print("\n=== B5: 单模态LLM视觉（复用VisionAgent） ===")
    y_true = []
    y_pred = []
    for r in results:
        claim = r.get("agent_details", {}).get("vision", {}).get("vis_claim", "LEGITIMATE")
        y_true.append(1 if r["true_label"] == "phish" else 0)
        y_pred.append(1 if claim == "PHISHING" else 0)
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)

    metrics = compute_metrics(y_true, y_pred)
    print(f"  Acc={metrics['Accuracy']:.4f} P={metrics['Precision']:.4f} "
          f"R={metrics['Recall']:.4f} F1={metrics['F1']:.4f}")
    print(f"  TP={metrics['TP']} TN={metrics['TN']} FP={metrics['FP']} FN={metrics['FN']}")
    return metrics


def run_b7_vote(results):
    """B7: 多Agent投票（无一致性校验，两种阈值）"""
    print("\n=== B7: 多Agent投票（无一致性校验） ===")
    y_true = np.array([1 if r["true_label"] == "phish" else 0 for r in results])

    # 阈值≥3（严格）
    y_pred_3 = np.array([1 if r["phishing_votes"] >= 3 else 0 for r in results])
    metrics_3 = compute_metrics(y_true, y_pred_3)
    print(f"  [≥3票] Acc={metrics_3['Accuracy']:.4f} P={metrics_3['Precision']:.4f} "
          f"R={metrics_3['Recall']:.4f} F1={metrics_3['F1']:.4f}")
    print(f"         TP={metrics_3['TP']} TN={metrics_3['TN']} FP={metrics_3['FP']} FN={metrics_3['FN']}")

    # 阈值≥2（宽松）
    y_pred_2 = np.array([1 if r["phishing_votes"] >= 2 else 0 for r in results])
    metrics_2 = compute_metrics(y_true, y_pred_2)
    print(f"  [≥2票] Acc={metrics_2['Accuracy']:.4f} P={metrics_2['Precision']:.4f} "
          f"R={metrics_2['Recall']:.4f} F1={metrics_2['F1']:.4f}")
    print(f"         TP={metrics_2['TP']} TN={metrics_2['TN']} FP={metrics_2['FP']} FN={metrics_2['FN']}")

    return {"vote_ge3": metrics_3, "vote_ge2": metrics_2}


def generate_comparison_table(all_metrics):
    """生成对比表"""
    print("\n" + "=" * 80)
    print("基线对比表")
    print("=" * 80)
    header = f"{'方法':<30} {'Acc':<8} {'Prec':<8} {'Rec':<8} {'F1':<8} {'TP':<6} {'TN':<6} {'FP':<6} {'FN':<6}"
    print(header)
    print("-" * 80)

    lines = [header, "-" * 80]

    rows = [
        ("B1: URL特征+RF", all_metrics["b1"]),
        ("B2: HTML特征+RF", all_metrics["b2"]),
        ("B4: 单模态LLM文本", all_metrics["b4"]),
        ("B5: 单模态LLM视觉", all_metrics["b5"]),
        ("B7: 多Agent投票(≥3)", all_metrics["b7"]["vote_ge3"]),
        ("B7: 多Agent投票(≥2)", all_metrics["b7"]["vote_ge2"]),
        ("Ours: 完整方法", all_metrics["ours"]),
    ]

    for name, m in rows:
        line = f"{name:<30} {m['Accuracy']:.4f}  {m['Precision']:.4f}  {m['Recall']:.4f}  {m['F1']:.4f}  {m['TP']:<6} {m['TN']:<6} {m['FP']:<6} {m['FN']:<6}"
        print(line)
        lines.append(line)

    table_text = "\n".join(lines)
    with open(OUTPUT_DIR / "comparison_table.txt", "w", encoding="utf-8") as f:
        f.write(table_text)
    print(f"\n对比表已保存到: {OUTPUT_DIR / 'comparison_table.txt'}")


def main():
    print("加载全量结果...")
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        results = json.load(f)
    print(f"加载了 {len(results)} 个样本")

    all_metrics = {}

    # B1
    all_metrics["b1"] = run_b1_url_rf()

    # B2
    all_metrics["b2"] = run_b2_html_rf()

    # B4
    all_metrics["b4"] = run_b4_text_llm(results)

    # B5
    all_metrics["b5"] = run_b5_vision_llm(results)

    # B7
    all_metrics["b7"] = run_b7_vote(results)

    # 我们的方法（从全量结果直接算）
    y_true = np.array([1 if r["true_label"] == "phish" else 0 for r in results])
    y_pred = np.array([1 if r["verdict"] == "PHISHING" else 0 for r in results])
    all_metrics["ours"] = compute_metrics(y_true, y_pred)

    # 生成对比表
    generate_comparison_table(all_metrics)

    # 保存所有指标
    with open(OUTPUT_DIR / "all_baselines_metrics.json", "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, ensure_ascii=False, indent=2)
    print(f"\n所有指标已保存到: {OUTPUT_DIR / 'all_baselines_metrics.json'}")


if __name__ == "__main__":
    main()
