"""
基线特征提取（B1 URL特征 + B2 HTML特征）
从全量结果JSON + 磁盘原始HTML提取传统ML特征
"""
import json
import re
import os
import numpy as np
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).parent
from config import DATASET_PATH as DATASET_DIR
RESULTS_FILE = PROJECT_ROOT / "results" / "full_all_merged.json"

# 可疑TLD列表（来自config.py）
SUSPICIOUS_TLDS = [".tk", ".ml", ".ga", ".cf", ".gq", ".top", ".xyz", ".click", ".country"]


# ============ B1: URL 特征 ============

def extract_url_features(url, url_agent_detail=None):
    """从URL提取特征，返回特征向量（list of float）"""
    features = []

    # 基础长度特征
    features.append(float(len(url)))                        # URL总长度
    features.append(float(url.count("/")))                  # 斜杠数
    features.append(float(url.count(".")))                  # 点数（子域名深度）

    # 特殊字符
    for ch in ["@", "-", "_", "%", "&", "=", "?", "//"]:
        features.append(float(url.count(ch)))

    # 数字占比
    digits = sum(1 for c in url if c.isdigit())
    features.append(digits / max(1, len(url)))

    # 协议
    features.append(1.0 if url.startswith("https://") else 0.0)

    # IP地址检测
    parsed = urlparse(url)
    netloc = parsed.netloc or parsed.path.split("/")[0]
    ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    features.append(1.0 if ip_pattern.match(netloc.split(":")[0]) else 0.0)

    # 可疑TLD
    tld_suspicious = any(netloc.lower().endswith(tld) for tld in SUSPICIOUS_TLDS)
    features.append(1.0 if tld_suspicious else 0.0)

    # @符号在URL中（可疑重定向）
    features.append(1.0 if "@" in url else 0.0)

    # 域名长度
    domain = netloc.split(":")[0]
    features.append(float(len(domain)))

    # 路径长度
    path = parsed.path
    features.append(float(len(path)))

    # 从Agent补充特征（如果有）
    if url_agent_detail:
        features.append(float(url_agent_detail.get("redirect_count", 0)))
        features.append(float(url_agent_detail.get("external_redirect_ratio", 0)))
        features.append(1.0 if url_agent_detail.get("form_action_external", False) else 0.0)
        features.append(1.0 if url_agent_detail.get("has_hidden_redirect", False) else 0.0)
    else:
        features.extend([0.0, 0.0, 0.0, 0.0])

    return features


# ============ B2: HTML 特征 ============

def extract_html_features(html_content):
    """从HTML源码提取特征，返回特征向量"""
    features = []

    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # 表单相关
        forms = soup.find_all("form")
        features.append(float(len(forms)))                  # 表单数
        inputs = soup.find_all("input")
        features.append(float(len(inputs)))                 # 输入框数
        pwd_inputs = soup.find_all("input", {"type": "password"})
        features.append(float(len(pwd_inputs)))             # 密码输入框数
        hidden_inputs = soup.find_all("input", {"type": "hidden"})
        features.append(float(len(hidden_inputs)))         # 隐藏输入框

        # 脚本和iframe
        scripts = soup.find_all("script")
        features.append(float(len(scripts)))                # 脚本数
        external_scripts = [s for s in scripts if s.get("src")]
        features.append(float(len(external_scripts)))       # 外部脚本数
        iframes = soup.find_all("iframe")
        features.append(float(len(iframes)))               # iframe数

        # 链接
        links = soup.find_all("a", href=True)
        features.append(float(len(links)))                  # 链接数
        external_links = [a for a in links if a.get("href", "").startswith("http") and
                          a.get("href", "") != ""]
        features.append(float(len(external_links)))         # 外部链接数

        # 文本特征
        visible_text = soup.get_text()
        features.append(float(len(visible_text)))           # 可见文本长度
        features.append(float(len(html_content)))           # HTML总长度

        # CSS隐藏元素（display:none, visibility:hidden）
        hidden_style = len(re.findall(r'display:\s*none|visibility:\s*hidden',
                                       html_content, re.IGNORECASE))
        features.append(float(hidden_style))                # CSS隐藏元素数

        # 登录相关关键词
        login_keywords = ["login", "password", "account", "verify", "secure",
                          "confirm", "update", "sign in", "log in"]
        text_lower = visible_text.lower()
        login_count = sum(1 for kw in login_keywords if kw in text_lower)
        features.append(float(login_count))                 # 登录关键词数

        # 表单action（外部域名提交）
        external_form = 0
        for form in forms:
            action = form.get("action", "")
            if action.startswith("http") and action != "":
                external_form += 1
        features.append(float(external_form))              # 外部表单提交

    except Exception as e:
        # 解析失败，返回全0特征
        features = [0.0] * 16

    return features


# ============ 加载数据 ============

def load_all_data():
    """加载全量结果"""
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_sample_path_index():
    """建立 sample_id -> 磁盘路径 的索引（遍历trainval+test）"""
    index = {}
    for split in ["trainval", "test"]:
        split_dir = DATASET_DIR / split
        if split_dir.exists():
            for d in split_dir.iterdir():
                if d.is_dir():
                    index[d.name] = d  # sample_id -> Path
    return index


def get_html_path(sample_id, path_index):
    """获取HTML文件路径"""
    if sample_id in path_index:
        return path_index[sample_id] / "RAW-HTML" / "index.html"
    return None


# ============ 主函数 ============

def main():
    print("加载全量结果...")
    results = load_all_data()
    print(f"加载了 {len(results)} 个样本")

    # B1: URL特征提取
    print("\n=== B1: URL特征提取 ===")
    url_features = []
    labels = []
    for r in results:
        url = r.get("url", "")
        url_detail = r.get("agent_details", {}).get("url", {})
        feat = extract_url_features(url, url_detail)
        url_features.append(feat)
        labels.append(1 if r["true_label"] == "phish" else 0)
    url_features = np.array(url_features)
    labels = np.array(labels)
    print(f"URL特征矩阵: {url_features.shape}, 标签分布: {np.bincount(labels)}")

    # B2: HTML特征提取（需读磁盘）
    print("\n=== B2: HTML特征提取 ===")
    print("建立样本路径索引...")
    path_index = build_sample_path_index()
    print(f"索引了 {len(path_index)} 个样本路径")

    html_features = []
    html_missing = 0
    for i, r in enumerate(results):
        sid = r["sample_id"]
        html_path = get_html_path(sid, path_index)
        if html_path and html_path.exists():
            try:
                html_content = html_path.read_text(encoding="utf-8-sig", errors="ignore")
                feat = extract_html_features(html_content)
            except Exception:
                feat = [0.0] * 16
                html_missing += 1
        else:
            feat = [0.0] * 16
            html_missing += 1
        html_features.append(feat)

        if (i + 1) % 2000 == 0:
            print(f"  已处理 {i+1}/{len(results)} (缺失{html_missing})")

    html_features = np.array(html_features)
    print(f"HTML特征矩阵: {html_features.shape}, 缺失: {html_missing}")

    # 保存特征矩阵
    output_dir = Path(__file__).parent / "features"
    output_dir.mkdir(exist_ok=True)
    np.save(output_dir / "url_features.npy", url_features)
    np.save(output_dir / "html_features.npy", html_features)
    np.save(output_dir / "labels.npy", labels)
    print(f"\n特征矩阵已保存到: {output_dir}")
    print(f"  url_features.npy: {url_features.shape}")
    print(f"  html_features.npy: {html_features.shape}")
    print(f"  labels.npy: {labels.shape}")


if __name__ == "__main__":
    main()
