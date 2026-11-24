"""
多 Agent 异步编排器
- 单样本内：4个Agent真正并行（asyncio + 异步HTTP客户端）
- 多样本间：同时处理多个样本（SAMPLE_CONCURRENCY）
- 文本Agent用方舟glm-5.2，视觉Agent用智谱glm-4.6v
"""
import asyncio
import time
import json
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from config import SAMPLE_CONCURRENCY
from data.dataset import Sample
from data.preprocess import preprocess_sample
from utils.api import DualAPIClient
from agents.url_agent import URLAgent
from agents.html_agent import HTMLAgent
from agents.text_agent import TextAgent
from agents.vision_agent import VisionAgent
from agents.consistency import compute_consistency
from agents.rag import BrandKnowledgeBase
from agents.judge import identify_brand, final_judgment


class PhishDetectionOrchestrator:
    """多 Agent 异步编排器"""
    
    def __init__(self, api_client: DualAPIClient = None,
                 brand_kb: BrandKnowledgeBase = None):
        self.api = api_client or DualAPIClient()
        self.brand_kb = brand_kb or BrandKnowledgeBase()
        
        # 初始化各 Agent（共享同一个 API 客户端）
        self.url_agent = URLAgent(self.api)
        self.html_agent = HTMLAgent(self.api)
        self.text_agent = TextAgent(self.api)
        self.vision_agent = VisionAgent(self.api)
    
    async def detect_single(self, sample: Sample, verbose: bool = False) -> Dict:
        """检测单个样本（4个Agent真正并行）"""
        start_time = time.time()
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"样本: {sample.sample_id} | URL: {sample.url[:60]}")
            print(f"真实标签: {sample.label} | 品牌: {sample.brand}")
            print(f"{'='*60}")
        
        # HTML 预处理（CPU密集，放线程池）
        loop = asyncio.get_event_loop()
        cleaned_html, visible_text, redirect_links = await loop.run_in_executor(
            None, preprocess_sample, sample.html, sample.url
        )
        
        # 第一阶段：4个Agent真正并行（异步HTTP）
        stage1_start = time.time()
        
        url_result, html_result, text_result, vis_result = await asyncio.gather(
            self.url_agent.analyze(sample.url, redirect_links),
            self.html_agent.analyze(cleaned_html),
            self.text_agent.analyze(visible_text),
            self.vision_agent.analyze(sample.screenshot_path),
        )
        
        stage1_time = time.time() - stage1_start
        
        if verbose:
            print(f"\n[阶段1完成] 耗时 {stage1_time:.1f}s")
            print(f"  URL Agent: {url_result.get('url_claim', '?')} "
                  f"(conf={url_result.get('url_confidence', 0):.2f})")
            print(f"  HTML Agent: {html_result.get('html_claim', '?')} "
                  f"(conf={html_result.get('html_confidence', 0):.2f})")
            print(f"  Text Agent: {text_result.get('text_claim', '?')} "
                  f"(conf={text_result.get('text_confidence', 0):.2f})")
            print(f"  Vision Agent: {vis_result.get('vis_claim', '?')} "
                  f"(conf={vis_result.get('vis_confidence', 0):.2f})")
        
        # 第二阶段：一致性校验（纯计算）
        consistency = compute_consistency(url_result, html_result,
                                          text_result, vis_result)
        
        if verbose:
            print(f"\n[阶段2] BIS={consistency['BIS']:.3f} "
                  f"FIS={consistency['FIS']:.3f} IGS={consistency['IGS']:.3f} "
                  f"CS={consistency['CS']:.3f}")
        
        # 第三阶段：RAG + 裁决
        brand_name = identify_brand(url_result, html_result,
                                    text_result, vis_result)
        vis_function = vis_result.get("vis_function", "other")
        rag_result = self.brand_kb.verify(brand_name, sample.url, vis_function)
        
        judgment = final_judgment(url_result, html_result, text_result,
                                  vis_result, consistency, rag_result)
        
        total_time = time.time() - start_time
        
        if verbose:
            print(f"\n[判定] {judgment['verdict']} "
                  f"(conf={judgment['confidence']:.2f})")
            print(f"  证据: {judgment['evidence']}")
            print(f"  总耗时: {total_time:.1f}s")
        
        return {
            "sample_id": sample.sample_id,
            "url": sample.url,
            "true_label": sample.label,
            "true_brand": sample.brand,
            "verdict": judgment["verdict"],
            "confidence": judgment["confidence"],
            "evidence": judgment["evidence"],
            "votes": judgment["votes"],
            "phishing_votes": judgment["phishing_votes"],
            "consistency": {
                "BIS": judgment["BIS"],
                "FIS": judgment["FIS"],
                "IGS": judgment["IGS"],
                "CS": judgment["CS"],
                "inconsistency_type": judgment["inconsistency_type"],
            },
            "rag_result": {
                "brand_name": rag_result.get("brand_name", ""),
                "brand_match": rag_result.get("brand_match"),
                "reason": rag_result.get("reason", ""),
            },
            "agent_details": {
                "url": url_result,
                "html": html_result,
                "text": text_result,
                "vision": vis_result,
            },
            "timing": {
                "total": round(total_time, 2),
                "stage1_parallel": round(stage1_time, 2),
            }
        }
    
    async def detect_batch(self, samples: List[Sample], 
                          on_result=None,
                          verbose: bool = False,
                          concurrency: Optional[int] = None) -> List[Dict]:
        """
        批量检测多样本（多样本并行）
        
        Args:
            samples: 样本列表
            on_result: 每完成一个样本的回调
            verbose: 是否打印详细过程
            concurrency: 并发度（None 时用 config.SAMPLE_CONCURRENCY）
        """
        concurrency = concurrency if concurrency is not None else SAMPLE_CONCURRENCY
        semaphore = asyncio.Semaphore(concurrency)
        results = [None] * len(samples)
        
        async def process_one(idx: int, sample: Sample):
            async with semaphore:
                try:
                    result = await self.detect_single(sample, verbose=verbose)
                    results[idx] = result
                    if on_result:
                        on_result(idx, result)
                except Exception as e:
                    print(f"  [错误] {sample.sample_id}: {e}")
                    results[idx] = {
                        "sample_id": sample.sample_id,
                        "url": sample.url,
                        "true_label": sample.label,
                        "verdict": "ERROR",
                        "evidence": str(e),
                    }
        
        # 并发处理所有样本
        tasks = [process_one(i, s) for i, s in enumerate(samples)]
        await asyncio.gather(*tasks)
        
        return [r for r in results if r is not None]


async def run_detection_async(sample: Sample, verbose: bool = False) -> Dict:
    """异步运行单个样本检测"""
    orchestrator = PhishDetectionOrchestrator()
    return await orchestrator.detect_single(sample, verbose=verbose)


def run_detection_sync(sample: Sample, verbose: bool = False) -> Dict:
    """同步运行检测（方便脚本调用）"""
    return asyncio.run(run_detection_async(sample, verbose=verbose))


def run_batch_sync(samples: List[Sample], on_result=None,
                   verbose: bool = False, concurrency: Optional[int] = None) -> List[Dict]:
    """同步运行批量检测
    concurrency: 并发度（None 时用 config.SAMPLE_CONCURRENCY）
    """
    orchestrator = PhishDetectionOrchestrator()
    return asyncio.run(orchestrator.detect_batch(
        samples, on_result, verbose, concurrency=concurrency))


if __name__ == "__main__":
    # 快速测试
    from data.dataset import load_samples
    
    print("加载数据...")
    samples = load_samples(split="trainval", limit=4, balanced=True)
    print(f"加载了 {len(samples)} 个样本，并行检测...")
    
    start = time.time()
    results = run_batch_sync(samples, verbose=True)
    total = time.time() - start
    
    print(f"\n总耗时: {total:.1f}s (平均{total/len(samples):.1f}s/样本)")
