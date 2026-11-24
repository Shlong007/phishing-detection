"""
通用批量测试脚本（多样本真并行版）
- 使用 detect_batch 启用 SAMPLE_CONCURRENCY=4 多样本并行
- 支持断点续跑（已完成的样本会跳过）
- 每完成一个样本就保存结果（避免中断丢失）
- 支持自定义样本数量
"""
import sys
import json
import time
import functools
import argparse
from pathlib import Path

print = functools.partial(print, flush=True)

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.dataset import load_samples
from agents.orchestrator import run_batch_sync


def compute_metrics(results):
    """计算评估指标"""
    tp = sum(1 for r in results if r["verdict"] == "PHISHING" and r["true_label"] == "phish")
    tn = sum(1 for r in results if r["verdict"] == "LEGITIMATE" and r["true_label"] == "legitimate")
    fp = sum(1 for r in results if r["verdict"] == "PHISHING" and r["true_label"] == "legitimate")
    fn = sum(1 for r in results if r["verdict"] == "LEGITIMATE" and r["true_label"] == "phish")
    
    total = len(results)
    accuracy = (tp + tn) / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    return {
        "TP": tp, "TN": tn, "FP": fp, "FN": fn,
        "Accuracy": accuracy, "Precision": precision,
        "Recall": recall, "F1": f1, "Total": total
    }


def save_results(results, results_file):
    """保存结果（每完成一个样本就调用）
    保存完整版（含agent_details，用于规则调优时重新裁决）
    和精简版（不含agent_details，文件小）
    """
    # results 可能含 None（尚未完成的占位），过滤掉
    completed = [r for r in results if r is not None]
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(completed, f, ensure_ascii=False, indent=2, default=str)
    # 精简版
    slim_file = results_file.parent / (results_file.stem + "_slim.json")
    slim_results = []
    for r in completed:
        slim = {k: v for k, v in r.items() if k != "agent_details"}
        slim_results.append(slim)
    with open(slim_file, "w", encoding="utf-8") as f:
        json.dump(slim_results, f, ensure_ascii=False, indent=2)


def load_existing_results(results_file):
    """加载已保存的结果（用于断点续跑）"""
    if results_file.exists():
        try:
            with open(results_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--num", type=int, default=20, help="样本数量")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--resume", action="store_true", help="断点续跑")
    parser.add_argument("-c", "--concurrency", type=int, default=None,
                        help="样本并发度（默认用 config.SAMPLE_CONCURRENCY）")
    parser.add_argument("--start", type=int, default=None, help="样本起始索引（全量模式用）")
    parser.add_argument("--end", type=int, default=None, help="样本结束索引（全量模式用）")
    parser.add_argument("--full", action="store_true", help="全量模式：加载trainval+test全部样本")
    parser.add_argument("--prefix", type=str, default="full", help="结果文件前缀（默认full，doubao版用doubao）")
    args = parser.parse_args()
    
    # 确定结果文件名
    if args.start is not None and args.end is not None:
        # 范围模式：结果文件按范围命名
        results_file = PROJECT_ROOT / "results" / f"{args.prefix}_{args.start}_{args.end}.json"
        batch_desc = f"全量样本 [{args.start}:{args.end})"
    elif args.full:
        # 全量模式（不分批，一次性跑全部）
        results_file = PROJECT_ROOT / "results" / "full_all.json"
        batch_desc = "全量样本（trainval+test）"
    else:
        NUM_SAMPLES = args.num
        results_file = PROJECT_ROOT / "results" / f"test_{NUM_SAMPLES}_samples.json"
        batch_desc = f"{NUM_SAMPLES} 样本"
    
    print("="*60)
    print(f"{batch_desc}（付费版 GLM-4.6v，多样本真并行）")
    print(f"结果文件: {results_file}")
    if args.resume:
        print("模式: 断点续跑")
    print("="*60)
    
    # 加载样本
    if args.full or (args.start is not None):
        # 全量模式：加载 trainval+test 全部，按 seed 打乱
        print(f"\n加载全量样本（trainval+test）...")
        from data.dataset import load_samples as _ls
        samples_tv = _ls(split="trainval", limit=None, balanced=True, seed=args.seed)
        samples_te = _ls(split="test", limit=None, balanced=True, seed=args.seed)
        samples = samples_tv + samples_te
        # 整体再打乱一次，让 trainval 和 test 混合
        import random as _r
        _r.seed(args.seed)
        _r.shuffle(samples)
        print(f"加载了 {len(samples)} 个样本（trainval {len(samples_tv)} + test {len(samples_te)}）")
        
        # 范围切片
        if args.start is not None and args.end is not None:
            samples = samples[args.start:args.end]
            print(f"范围切片 [{args.start}:{args.end}): 剩 {len(samples)} 个样本")
    else:
        # 有限样本模式
        NUM_SAMPLES = args.num
        print(f"\n加载 {NUM_SAMPLES} 个样本...")
        samples = load_samples(split="trainval", limit=NUM_SAMPLES, balanced=True, seed=args.seed)
        print(f"加载了 {len(samples)} 个样本")
    
    # 断点续跑：加载已完成的样本
    existing = []
    completed_ids = set()
    if args.resume and results_file.exists():
        existing = load_existing_results(results_file)
        completed_ids = {r["sample_id"] for r in existing}
        print(f"已完成: {len(completed_ids)} 个，跳过这些样本")
    
    # 构造已完成结果字典（按 sample_id 索引）
    results_by_id = {r["sample_id"]: r for r in existing}
    
    # 待处理样本（跳过已完成的）
    pending = [s for s in samples if s.sample_id not in completed_ids]
    print(f"待处理: {len(pending)} 个样本")
    if not pending:
        print("所有样本已完成，无需重跑")
        pending = []
    
    # 准备待处理样本的 results 占位数组（保持原 idx 顺序）
    # detect_batch 内部按 idx 写回 results[idx]，我们通过 on_result 回调收集
    pending_results = [None] * len(pending)
    done_count = [0]  # 用 list 包一下以便闭包修改
    
    total_start = time.time()
    
    def on_result(idx, result):
        """每完成一个样本的回调：保存结果 + 实时打印"""
        pending_results[idx] = result
        done_count[0] += 1
        sample = pending[idx]
        
        # 同步进 results_by_id（用于断点保存）
        results_by_id[sample.sample_id] = result
        
        verdict = result.get("verdict", "ERROR")
        true_label = result.get("true_label", "?")
        cs = result.get("consistency", {}).get("CS", 0)
        votes = result.get("phishing_votes", 0)
        
        if verdict == "PHISHING" and true_label == "phish":
            status = "✓ TP"
        elif verdict == "LEGITIMATE" and true_label == "legitimate":
            status = "✓ TN"
        elif verdict == "PHISHING" and true_label == "legitimate":
            status = "✗ FP"
        elif verdict == "LEGITIMATE" and true_label == "phish":
            status = "✗ FN"
        else:
            status = "?? ERROR"
        
        elapsed = time.time() - total_start
        print(f"  [完成 {done_count[0]}/{len(pending)}] {sample.sample_id:<25} "
              f"{true_label[:6]:<6s}->{verdict:<11s} CS={cs:.2f} v={votes}/4 {status} "
              f"(累计 {elapsed:.0f}s)")
        
        # 每完成一个就保存全部已知结果（防中断）
        # 按 samples 原顺序输出
        all_results = []
        for s in samples:
            if s.sample_id in results_by_id:
                all_results.append(results_by_id[s.sample_id])
        save_results(all_results, results_file)
    
    # 批量并行处理（detect_batch 内部 Semaphore 控制并行度）
    if pending:
        conc = args.concurrency
        conc_label = f"{conc}" if conc else "(config 默认)"
        print(f"\n开始批量并行检测（并发度={conc_label}，预计 {len(pending)*15//4//60}~{len(pending)*20//4//60} 分钟）...")
        try:
            run_batch_sync(pending, on_result=on_result, verbose=False, concurrency=conc)
        except Exception as e:
            print(f"批量检测中断: {e}")
    
    total_time = time.time() - total_start
    
    # 汇总所有结果（按原 samples 顺序）
    results = []
    for s in samples:
        if s.sample_id in results_by_id:
            results.append(results_by_id[s.sample_id])
    
    # === 汇总 ===
    print(f"\n\n{'='*60}")
    print(f"汇总")
    print(f"{'='*60}")
    
    metrics = compute_metrics(results)
    
    print(f"\n总样本: {metrics['Total']}")
    print(f"正确: {metrics['TP']+metrics['TN']}/{metrics['Total']}")
    print(f"新增耗时: {total_time:.1f}s "
          f"(平均{total_time/max(1,len(pending)):.1f}s/样本，"
          f"考虑并行实际墙钟速度约{total_time/max(1,len(pending)/4):.1f}s/样本)")
    print()
    print(f"混淆矩阵:")
    print(f"  TP={metrics['TP']}  FP={metrics['FP']}")
    print(f"  FN={metrics['FN']}  TN={metrics['TN']}")
    print()
    print(f"指标:")
    print(f"  Accuracy:  {metrics['Accuracy']:.4f} ({metrics['Accuracy']*100:.1f}%)")
    print(f"  Precision: {metrics['Precision']:.4f}")
    print(f"  Recall:    {metrics['Recall']:.4f}")
    print(f"  F1 Score:  {metrics['F1']:.4f}")
    
    # 详细结果表
    print(f"\n{'='*60}")
    print("详细结果")
    print(f"{'='*60}")
    print(f"{'样本ID':<25} {'真实':<8} {'判定':<12} {'CS':<6} {'BIS':<6} {'FIS':<6} {'IGS':<6} {'投票':<6} {'结果'}")
    print("-"*100)
    
    for r in results:
        correct = "✓" if ((r["verdict"] == "PHISHING" and r["true_label"] == "phish") or
                          (r["verdict"] == "LEGITIMATE" and r["true_label"] == "legitimate")) else "✗"
        c = r["consistency"]
        print(f"{r['sample_id']:<25} "
              f"{r['true_label'][:6]:<8} "
              f"{r['verdict']:<12} "
              f"{c['CS']:<6.2f} "
              f"{c['BIS']:<6.2f} "
              f"{c['FIS']:<6.2f} "
              f"{c['IGS']:<6.2f} "
              f"{r['phishing_votes']}/4   "
              f"{correct}")
    
    # 错误案例分析
    errors = [r for r in results if ((r["verdict"] == "PHISHING" and r["true_label"] == "legitimate") or
                                      (r["verdict"] == "LEGITIMATE" and r["true_label"] == "phish"))]
    if errors:
        print(f"\n{'='*60}")
        print(f"错误案例（{len(errors)}个）")
        print(f"{'='*60}")
        for r in errors:
            print(f"\n--- {r['sample_id']} ---")
            print(f"  真实: {r['true_label']} | 判定: {r['verdict']}")
            c = r["consistency"]
            print(f"  CS={c['CS']:.2f} BIS={c['BIS']:.2f} FIS={c['FIS']:.2f} IGS={c['IGS']:.2f}")
            print(f"  投票: {r['votes']}")
            print(f"  证据: {r['evidence']}")
    
    print(f"\n结果已保存到: {results_file}")


if __name__ == "__main__":
    main()
