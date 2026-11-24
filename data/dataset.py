"""
Phish360 数据集加载模块
"""
import random
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from config import TRAINVAL_DIR, TEST_DIR


@dataclass
class Sample:
    """单个样本的数据结构"""
    sample_id: str          # 如 "P10090_paypal"
    label: str              # "phish" 或 "legitimate"
    brand: str              # 品牌名（如 "paypal"），合法样本为 "legitimate"
    url: str
    html: str
    screenshot_path: str
    split: str              # "trainval" 或 "test"
    
    @property
    def is_phish(self) -> bool:
        return self.label == "phish"


def parse_sample_dir(sample_dir: Path, split: str) -> Optional[Sample]:
    """解析单个样本目录"""
    dir_name = sample_dir.name
    
    # 解析目录名：P10090_paypal / L01562_legitimate
    parts = dir_name.split("_", 1)
    if len(parts) != 2:
        return None
    
    prefix, category = parts
    # P 开头是钓鱼，L 开头是合法
    if prefix.startswith("P"):
        label = "phish"
        brand = category.lower()
    elif prefix.startswith("L"):
        label = "legitimate"
        brand = "legitimate"
    else:
        return None
    
    # 读取各文件
    url_file = sample_dir / "URL" / "url.txt"
    html_file = sample_dir / "RAW-HTML" / "index.html"
    img_file = sample_dir / "SCREEN-SHOT" / "screen_shoot.png"
    
    if not url_file.exists() or not html_file.exists():
        return None
    
    try:
        url = url_file.read_text(encoding="utf-8-sig").strip()
        html = html_file.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return None
    
    screenshot_path = str(img_file) if img_file.exists() else ""
    
    return Sample(
        sample_id=dir_name,
        label=label,
        brand=brand,
        url=url,
        html=html,
        screenshot_path=screenshot_path,
        split=split
    )


def load_samples(split: str = "trainval", 
                 limit: Optional[int] = None,
                 balanced: bool = True,
                 seed: int = 42) -> List[Sample]:
    """
    加载数据集样本
    
    Args:
        split: "trainval" 或 "test"
        limit: 最多加载多少样本（None=全部）
        balanced: 是否平衡加载（钓鱼和合法数量相近）
        seed: 随机种子
    
    Returns:
        Sample 列表
    """
    data_dir = TRAINVAL_DIR if split == "trainval" else TEST_DIR
    if not data_dir.exists():
        raise FileNotFoundError(f"数据集目录不存在: {data_dir}")
    
    sample_dirs = [d for d in data_dir.iterdir() if d.is_dir()]
    
    samples = []
    for d in sample_dirs:
        sample = parse_sample_dir(d, split)
        if sample is not None:
            samples.append(sample)
    
    random.seed(seed)
    random.shuffle(samples)
    
    if balanced and limit:
        # 按 limit 总数，平衡分配
        phish = [s for s in samples if s.is_phish]
        legit = [s for s in samples if not s.is_phish]
        per_class = limit // 2
        phish = phish[:per_class]
        legit = legit[:per_class]
        samples = phish + legit
        random.shuffle(samples)
    elif limit:
        samples = samples[:limit]
    # limit=None 且 balanced=True 时，返回全量打乱后的样本（不强制平衡）
    
    return samples


def load_sample_by_id(sample_id: str, split: str = "trainval") -> Optional[Sample]:
    """按 ID 加载单个样本"""
    data_dir = TRAINVAL_DIR if split == "trainval" else TEST_DIR
    sample_dir = data_dir / sample_id
    if not sample_dir.exists():
        return None
    return parse_sample_dir(sample_dir, split)


def get_dataset_stats() -> Dict:
    """获取数据集统计信息"""
    stats = {}
    for split in ["trainval", "test"]:
        data_dir = TRAINVAL_DIR if split == "trainval" else TEST_DIR
        dirs = [d for d in data_dir.iterdir() if d.is_dir()]
        phish = sum(1 for d in dirs if d.name.startswith("P"))
        legit = sum(1 for d in dirs if d.name.startswith("L"))
        
        # 钓鱼品牌统计
        brands = {}
        for d in dirs:
            if d.name.startswith("P"):
                parts = d.name.split("_", 1)
                if len(parts) == 2:
                    brand = parts[1].lower()
                    brands[brand] = brands.get(brand, 0) + 1
        
        stats[split] = {
            "total": len(dirs),
            "phish": phish,
            "legitimate": legit,
            "brands": dict(sorted(brands.items(), key=lambda x: -x[1]))
        }
    return stats


if __name__ == "__main__":
    stats = get_dataset_stats()
    for split, info in stats.items():
        print(f"\n=== {split} ===")
        print(f"总计: {info['total']} (钓鱼: {info['phish']}, 合法: {info['legitimate']})")
        print(f"品牌数: {len(info['brands'])}")
        print(f"Top-5品牌: {list(info['brands'].items())[:5]}")
