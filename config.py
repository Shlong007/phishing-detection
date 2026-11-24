"""
项目配置。

路径、模型和度量参数集中在这里；API 密钥从环境变量读取，
也可以写在同目录下的 config_local.py 里（该文件已在 .gitignore 中忽略）。
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

# ===== 路径 =====
# 下载 Phish360 后，把该变量指向数据集根目录
DATASET_PATH = Path(os.environ.get("PHISH360_PATH", PROJECT_ROOT / "Phish360"))
TRAINVAL_DIR = DATASET_PATH / "trainval"
TEST_DIR = DATASET_PATH / "test"

RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)

BRAND_KB_PATH = PROJECT_ROOT / "knowledge_base" / "brand_kb.json"
BRAND_ALIASES_PATH = PROJECT_ROOT / "knowledge_base" / "brand_aliases.json"

# ===== API =====
# 方舟（文本 + 视觉）
ARK_API_KEY = os.environ.get("ARK_API_KEY", "YOUR_ARK_API_KEY")
ARK_BASE_URL = os.environ.get("ARK_BASE_URL",
                              "https://ark.cn-beijing.volces.com/api/coding/v3")
ARK_MODEL = "glm-5.2"
ARK_VISION_MODEL = "doubao-seed-2.1-turbo"

# 智谱（备用视觉模型）
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "YOUR_ZHIPU_API_KEY")
ZHIPU_MODEL_FLASH = "glm-4.6v-flash"
ZHIPU_MODEL_PRO = "glm-4.6v"

# 视觉 Agent 使用的后端："doubao" 或 "zhipu"
VISION_MODEL = os.environ.get("VISION_MODEL", "doubao")

# ===== 调用参数 =====
API_MAX_RETRIES = 3
API_RETRY_BASE_WAIT = 5      # 秒
API_TIMEOUT = 300            # 秒

SAMPLE_CONCURRENCY = 4       # 同时处理的样本数
AGENT_CONCURRENCY = 4        # 单个样本内并行的 Agent 数

# ===== 输入长度 =====
HTML_MAX_CHARS = 6000
TEXT_MAX_CHARS = 3000

# ===== 一致性度量 =====
# CS = W_BIS * BIS + W_FIS * FIS + W_IGS * IGS
W_BIS = 0.4
W_FIS = 0.3
W_IGS = 0.3

CS_THRESHOLD = 0.5

# ===== 类别 =====
FUNCTION_CATEGORIES = [
    "login", "email", "shopping", "banking", "social_media",
    "government", "tech_support", "entertainment", "other"
]

SUSPICIOUS_TLDS = [".tk", ".ml", ".ga", ".cf", ".gq", ".top", ".xyz", ".click", ".country"]

# 本地私有配置（可覆盖上面的默认值），该文件不纳入版本管理
try:
    from config_local import *  # noqa: F401,F403
except ImportError:
    pass
