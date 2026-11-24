"""
HTML 预处理模块
- 清洗 HTML（移除 style/script 等无关标签）
- 提取可见文本
- 提取跳转链接（a/form/iframe/script/meta/JS重定向）
参考 PhishDebate 的算法 2
"""
import re
from typing import Dict, List, Tuple
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from config import HTML_MAX_CHARS, TEXT_MAX_CHARS


def clean_html(raw_html: str) -> str:
    """
    清洗 HTML：移除 style/noscript/link 标签和 script 标签
    保留结构标签用于 HTML 结构分析
    
    Returns: 清洗后的 HTML
    """
    soup = BeautifulSoup(raw_html, "html.parser")
    
    # 移除不需要的标签
    for tag in soup.find_all(["style", "noscript", "link", "script"]):
        tag.decompose()
    
    return str(soup)


def extract_visible_text(html: str) -> str:
    """从 HTML 中提取可见文本"""
    soup = BeautifulSoup(html, "html.parser")
    # get_text 自动会跳过 script/style（如果还存在的话）
    text = soup.get_text(separator="\n", strip=True)
    # 合并多余空行
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)


def extract_redirect_links(raw_html: str) -> Dict[str, List[str]]:
    """
    从 HTML 中提取所有跳转链接（不实际访问）
    
    提取 6 类跳转：
    1. <a href> - 普通链接
    2. <form action> - 表单提交地址
    3. <iframe src> - 内嵌框架
    4. <script src> - 外部脚本
    5. <meta http-equiv="refresh"> - 重定向
    6. JS 跳转（location.href / window.location）
    
    Returns: 各类链接的字典
    """
    soup = BeautifulSoup(raw_html, "html.parser")
    
    links = {
        "a_href": [],
        "form_action": [],
        "iframe_src": [],
        "script_src": [],
        "meta_refresh": [],
        "js_redirect": []
    }
    
    # 1. <a href>
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href and href not in ("#", "javascript:void(0)", "javascript:;"):
            links["a_href"].append(href)
    
    # 2. <form action>
    for form in soup.find_all("form", action=True):
        links["form_action"].append(form["action"].strip())
    
    # 3. <iframe src>
    for iframe in soup.find_all("iframe", src=True):
        links["iframe_src"].append(iframe["src"].strip())
    
    # 4. <script src>（需要从原始HTML提取，因为clean_html会删掉script）
    for script in soup.find_all("script", src=True):
        links["script_src"].append(script["src"].strip())
    
    # 5. <meta http-equiv="refresh">
    for meta in soup.find_all("meta", attrs={"http-equiv": "refresh"}):
        content = meta.get("content", "")
        # 格式通常是 "5;url=http://example.com"
        if "url=" in content.lower():
            url_part = content.split("url=", 1)[-1].strip()
            links["meta_refresh"].append(url_part)
        else:
            links["meta_refresh"].append(content)
    
    # 6. JS 跳转（正则匹配原始 HTML）
    # 匹配 location.href = "..." / window.location = "..."
    js_pattern = r'(?:location\.href|window\.location(?:\.href)?)\s*=\s*["\']([^"\']+)["\']'
    for match in re.finditer(js_pattern, raw_html, re.IGNORECASE):
        links["js_redirect"].append(match.group(1))
    
    # 也匹配 location.replace("...")
    replace_pattern = r'location\.replace\(\s*["\']([^"\']+)["\']\s*\)'
    for match in re.finditer(replace_pattern, raw_html, re.IGNORECASE):
        links["js_redirect"].append(match.group(1))
    
    return links


def preprocess_sample(raw_html: str, url: str) -> Tuple[str, str, Dict]:
    """
    完整的样本预处理流程
    
    Returns: (cleaned_html, visible_text, redirect_links)
    """
    # 提取跳转链接（在清洗前，因为 script 标签会被删）
    redirect_links = extract_redirect_links(raw_html)
    
    # 清洗 HTML
    cleaned_html = clean_html(raw_html)
    
    # 截断 HTML（在标签边界处截断，避免截断到一半）
    if len(cleaned_html) > HTML_MAX_CHARS:
        cleaned_html = cleaned_html[:HTML_MAX_CHARS] + "\n<!-- truncated -->"
    
    # 提取可见文本
    visible_text = extract_visible_text(cleaned_html)
    
    # 截断文本
    if len(visible_text) > TEXT_MAX_CHARS:
        visible_text = visible_text[:TEXT_MAX_CHARS] + "...(truncated)"
    
    return cleaned_html, visible_text, redirect_links
