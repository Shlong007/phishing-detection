"""
把分批跑出来的结果合并成一个文件，供 run_ablations.py 使用。

用法:
    python merge_results.py                                  # 默认合并 results/full_*.json
    python merge_results.py --pattern "mixed_ours_*.json" -o results/mixed_all_merged.json
"""
import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", default="full_[0-9]*_[0-9]*.json")
    ap.add_argument("-o", "--out", default="results/full_all_merged.json")
    args = ap.parse_args()

    files = sorted((PROJECT_ROOT / "results").glob(args.pattern))
    files = [f for f in files if not f.stem.endswith(("_slim", "_merged"))]
    if not files:
        print("没找到匹配的结果文件:", args.pattern)
        return

    merged, seen = [], set()
    for f in files:
        data = json.load(open(f, encoding="utf-8"))
        for r in data:
            sid = r.get("sample_id")
            if sid in seen:
                continue
            seen.add(sid)
            merged.append(r)
        print("%-40s %5d 条" % (f.name, len(data)))

    out = PROJECT_ROOT / args.out
    out.parent.mkdir(exist_ok=True)
    json.dump(merged, open(out, "w", encoding="utf-8"), ensure_ascii=False, default=str)
    print("合并完成: %s (%d 条)" % (out, len(merged)))


if __name__ == "__main__":
    main()
