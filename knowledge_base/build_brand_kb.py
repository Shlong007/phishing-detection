"""
生成完整的 46 品牌知识库
从 Phish360 的品牌列表 + 合法域名信息构建
"""
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import BRAND_KB_PATH, BRAND_ALIASES_PATH

# 完整的 46 品牌知识库
# 合法域名和功能信息来自公开知识
COMPLETE_BRAND_KB = {
    # === 已有的16个（保留） ===
    "paypal": {
        "legitimate_domains": ["paypal.com", "paypalobjects.com", "paypal.me"],
        "legitimate_functions": ["banking", "login"],
        "description": "PayPal 在线支付平台"
    },
    "google": {
        "legitimate_domains": ["google.com", "googleapis.com", "gstatic.com", "accounts.google.com"],
        "legitimate_functions": ["login", "email", "tech_support"],
        "description": "Google 搜索和账户服务"
    },
    "apple": {
        "legitimate_domains": ["apple.com", "icloud.com", "appleid.apple.com"],
        "legitimate_functions": ["login", "tech_support"],
        "description": "Apple ID 和 iCloud 服务"
    },
    "microsoft": {
        "legitimate_domains": ["microsoft.com", "office.com", "outlook.com", "live.com", "login.live.com"],
        "legitimate_functions": ["login", "email", "tech_support"],
        "description": "Microsoft 账户和 Office 服务"
    },
    "facebook": {
        "legitimate_domains": ["facebook.com", "fb.com", "meta.com"],
        "legitimate_functions": ["social_media", "login"],
        "description": "Facebook 社交平台"
    },
    "amazon": {
        "legitimate_domains": ["amazon.com", "amazonaws.com", "amazonpay.com"],
        "legitimate_functions": ["shopping", "login"],
        "description": "Amazon 电商平台"
    },
    "netflix": {
        "legitimate_domains": ["netflix.com"],
        "legitimate_functions": ["entertainment", "login"],
        "description": "Netflix 流媒体服务"
    },
    "yahoo": {
        "legitimate_domains": ["yahoo.com", "yahoo.co.jp"],
        "legitimate_functions": ["email", "login"],
        "description": "Yahoo 邮箱和门户"
    },
    "dropbox": {
        "legitimate_domains": ["dropbox.com"],
        "legitimate_functions": ["login", "tech_support"],
        "description": "Dropbox 云存储"
    },
    "adobe": {
        "legitimate_domains": ["adobe.com", "adobesign.com"],
        "legitimate_functions": ["login", "tech_support"],
        "description": "Adobe 创意云服务"
    },
    "linkedin": {
        "legitimate_domains": ["linkedin.com"],
        "legitimate_functions": ["social_media", "login"],
        "description": "LinkedIn 职业社交"
    },
    "ebay": {
        "legitimate_domains": ["ebay.com"],
        "legitimate_functions": ["shopping", "login"],
        "description": "eBay 电商平台"
    },
    "dhl": {
        "legitimate_domains": ["dhl.com", "dhl.de", "dhl.co.uk"],
        "legitimate_functions": ["tech_support"],
        "description": "DHL 物流"
    },
    "wellsfargo": {
        "legitimate_domains": ["wellsfargo.com"],
        "legitimate_functions": ["banking", "login"],
        "description": "Wells Fargo 银行"
    },
    "boa": {
        "legitimate_domains": ["bankofamerica.com"],
        "legitimate_functions": ["banking", "login"],
        "description": "Bank of America 银行"
    },
    "chase": {
        "legitimate_domains": ["chase.com"],
        "legitimate_functions": ["banking", "login"],
        "description": "Chase 银行"
    },
    
    # 补充品牌
    "office": {
        "legitimate_domains": ["office.com", "office365.com", "login.microsoftonline.com"],
        "legitimate_functions": ["login", "email", "tech_support"],
        "description": "Microsoft Office 365（别名 microsoft）"
    },
    "orange": {
        "legitimate_domains": ["orange.fr", "orange.com"],
        "legitimate_functions": ["login", "email", "tech_support"],
        "description": "Orange 电信运营商（法国）"
    },
    "alibaba": {
        "legitimate_domains": ["alibaba.com", "aliexpress.com", "alipay.com"],
        "legitimate_functions": ["shopping", "login", "banking"],
        "description": "Alibaba 阿里巴巴电商平台"
    },
    "itau": {
        "legitimate_domains": ["itau.com.br", "itau.com"],
        "legitimate_functions": ["banking", "login"],
        "description": "Itaú Unibanco 伊塔乌银行（巴西）"
    },
    "outlook": {
        "legitimate_domains": ["outlook.com", "outlook.live.com", "outlook.office.com"],
        "legitimate_functions": ["email", "login"],
        "description": "Microsoft Outlook 邮箱（别名 microsoft）"
    },
    "att": {
        "legitimate_domains": ["att.com", "att.net"],
        "legitimate_functions": ["login", "email", "tech_support"],
        "description": "AT&T 电信运营商"
    },
    "santander": {
        "legitimate_domains": ["santander.com", "santander.co.uk", "santander.com.br"],
        "legitimate_functions": ["banking", "login"],
        "description": "Santander 桑坦德银行"
    },
    "amex": {
        "legitimate_domains": ["americanexpress.com", "amex.com"],
        "legitimate_functions": ["banking", "login"],
        "description": "American Express 美国运通"
    },
    "bradesco": {
        "legitimate_domains": ["bradesco.com.br", "bradesco.com"],
        "legitimate_functions": ["banking", "login"],
        "description": "Banco Bradesco 布拉德斯科银行（巴西）"
    },
    "sparkasse": {
        "legitimate_domains": ["sparkasse.de", "sparkasse.de"],
        "legitimate_functions": ["banking", "login"],
        "description": "Sparkasse 德国储蓄银行"
    },
    "sfr": {
        "legitimate_domains": ["sfr.fr", "sfr.com"],
        "legitimate_functions": ["login", "email", "tech_support"],
        "description": "SFR 电信运营商（法国）"
    },
    "nab": {
        "legitimate_domains": ["nab.com.au"],
        "legitimate_functions": ["banking", "login"],
        "description": "National Australia Bank 澳洲国民银行"
    },
    "usaa": {
        "legitimate_domains": ["usaa.com"],
        "legitimate_functions": ["banking", "login"],
        "description": "USAA 金融服务（美国军人银行）"
    },
    "xfinity": {
        "legitimate_domains": ["xfinity.com", "comcast.net"],
        "legitimate_functions": ["login", "email", "tech_support"],
        "description": "Xfinity by Comcast 康卡斯特电信"
    },
    "cibc": {
        "legitimate_domains": ["cibc.com"],
        "legitimate_functions": ["banking", "login"],
        "description": "CIBC 加拿大帝国商业银行"
    },
    "bmo": {
        "legitimate_domains": ["bmo.com"],
        "legitimate_functions": ["banking", "login"],
        "description": "BMO 蒙特利尔银行"
    },
    "aol": {
        "legitimate_domains": ["aol.com", "aolmail.com"],
        "legitimate_functions": ["email", "login"],
        "description": "AOL 邮箱"
    },
    "natwest": {
        "legitimate_domains": ["natwest.com"],
        "legitimate_functions": ["banking", "login"],
        "description": "NatWest 国民西敏寺银行（英国）"
    },
    "irs": {
        "legitimate_domains": ["irs.gov"],
        "legitimate_functions": ["government", "login"],
        "description": "IRS 美国国税局"
    },
    "match": {
        "legitimate_domains": ["match.com"],
        "legitimate_functions": ["social_media", "login"],
        "description": "Match.com 约会网站"
    },
    "tmobile": {
        "legitimate_domains": ["t-mobile.com", "tmobile.com"],
        "legitimate_functions": ["login", "tech_support"],
        "description": "T-Mobile 电信运营商"
    },
    "caixa": {
        "legitimate_domains": ["caixa.gov.br", "caixa.com.br"],
        "legitimate_functions": ["banking", "login"],
        "description": "Caixa Econômica Federal 巴西联邦储蓄银行"
    },
    "mic": {
        "legitimate_domains": ["mic.co.jp", "mufg.jp"],
        "legitimate_functions": ["banking", "login"],
        "description": "Mitsubishi UFJ 三菱日联银行"
    },
    "cox": {
        "legitimate_domains": ["cox.com", "cox.net"],
        "legitimate_functions": ["login", "email", "tech_support"],
        "description": "Cox Communications 电信运营商"
    },
    "bt": {
        "legitimate_domains": ["bt.com", "btinternet.com"],
        "legitimate_functions": ["login", "email", "tech_support"],
        "description": "BT 英国电信"
    },
    "impots": {
        "legitimate_domains": ["impots.gouv.fr"],
        "legitimate_functions": ["government", "login"],
        "description": "Impots 法国税务局"
    },
    "hsbc": {
        "legitimate_domains": ["hsbc.com", "hsbc.co.uk"],
        "legitimate_functions": ["banking", "login"],
        "description": "HSBC 汇丰银行"
    },
    "navy": {
        "legitimate_domains": ["navyfederal.org", "navy.com"],
        "legitimate_functions": ["banking", "login"],
        "description": "Navy Federal Credit Union 海军联邦信用社"
    },
    "capitalone": {
        "legitimate_domains": ["capitalone.com"],
        "legitimate_functions": ["banking", "login"],
        "description": "Capital One 资本一银行"
    },
    "alllegro": {
        "legitimate_domains": ["allegro.pl"],
        "legitimate_functions": ["shopping", "login"],
        "description": "Allegro 波兰电商平台（注意数据集中拼写为alllegro）"
    },
}

# 品牌别名表（扩展版）
COMPLETE_BRAND_ALIASES = {
    # PayPal
    "paypal": "paypal",
    "paypal inc": "paypal",
    "paypal.com": "paypal",
    "pay pal": "paypal",
    # Google
    "google": "google",
    "google llc": "google",
    "google.com": "google",
    "gmail": "google",
    # Apple
    "apple": "apple",
    "apple id": "apple",
    "apple.com": "apple",
    "icloud": "apple",
    # Microsoft / Office / Outlook（都归到 microsoft 域名验证，但独立标识）
    "microsoft": "microsoft",
    "microsoft account": "microsoft",
    "microsoft.com": "microsoft",
    "office": "office",
    "office365": "office",
    "office.com": "office",
    "outlook": "outlook",
    "outlook.com": "outlook",
    "hotmail": "outlook",
    "live.com": "microsoft",
    "login.live.com": "microsoft",
    # Facebook / Meta
    "facebook": "facebook",
    "meta": "facebook",
    "fb": "facebook",
    # Amazon
    "amazon": "amazon",
    "amazon.com": "amazon",
    # Netflix
    "netflix": "netflix",
    # Yahoo
    "yahoo": "yahoo",
    "yahoo mail": "yahoo",
    "yahoo.com": "yahoo",
    # Others
    "dropbox": "dropbox",
    "adobe": "adobe",
    "adobe id": "adobe",
    "linkedin": "linkedin",
    "ebay": "ebay",
    "dhl": "dhl",
    "wells fargo": "wellsfargo",
    "wellsfargo": "wellsfargo",
    "bank of america": "boa",
    "boa": "boa",
    "chase": "chase",
    "orange": "orange",
    "alibaba": "alibaba",
    "aliexpress": "alibaba",
    "itau": "itau",
    "itau unibanco": "itau",
    "santander": "santander",
    "amex": "amex",
    "american express": "amex",
    "bradesco": "bradesco",
    "sparkasse": "sparkasse",
    "sfr": "sfr",
    "nab": "nab",
    "national australia bank": "nab",
    "usaa": "usaa",
    "xfinity": "xfinity",
    "comcast": "xfinity",
    "cibc": "cibc",
    "bmo": "bmo",
    "bank of montreal": "bmo",
    "aol": "aol",
    "natwest": "natwest",
    "irs": "irs",
    "match": "match",
    "match.com": "match",
    "tmobile": "tmobile",
    "t-mobile": "tmobile",
    "caixa": "caixa",
    "mic": "mic",
    "cox": "cox",
    "bt": "bt",
    "british telecom": "bt",
    "impots": "impots",
    "hsbc": "hsbc",
    "navy": "navy",
    "navy federal": "navy",
    "capitalone": "capitalone",
    "capital one": "capitalone",
    "allegro": "alllegro",
    "alllegro": "alllegro",
    "att": "att",
    "at&t": "att",
}


def main():
    print(f"生成品牌知识库...")
    print(f"品牌数量: {len(COMPLETE_BRAND_KB)}")
    print(f"别名数量: {len(COMPLETE_BRAND_ALIASES)}")
    
    # 确保目录存在
    BRAND_KB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # 保存品牌知识库
    with open(BRAND_KB_PATH, "w", encoding="utf-8") as f:
        json.dump(COMPLETE_BRAND_KB, f, ensure_ascii=False, indent=2)
    print(f"品牌知识库已保存到: {BRAND_KB_PATH}")
    
    # 保存别名表
    with open(BRAND_ALIASES_PATH, "w", encoding="utf-8") as f:
        json.dump(COMPLETE_BRAND_ALIASES, f, ensure_ascii=False, indent=2)
    print(f"品牌别名表已保存到: {BRAND_ALIASES_PATH}")
    
    # 验证覆盖
    dataset_brands = [
        "facebook", "paypal", "chase", "office", "boa", "orange", "wellsfargo",
        "dhl", "alibaba", "apple", "itau", "yahoo", "outlook", "att", "google",
        "adobe", "dropbox", "microsoft", "amazon", "santander", "netflix",
        "amex", "bradesco", "sparkasse", "sfr", "nab", "usaa", "xfinity",
        "cibc", "linkedin", "bmo", "aol", "natwest", "irs", "ebay", "match",
        "tmobile", "caixa", "mic", "cox", "bt", "impots", "hsbc", "navy",
        "capitalone", "alllegro"
    ]
    
    missing = [b for b in dataset_brands if b not in COMPLETE_BRAND_KB]
    print(f"\n数据集品牌覆盖: {len(dataset_brands) - len(missing)}/{len(dataset_brands)}")
    if missing:
        print(f"缺失: {missing}")
    else:
        print("✓ 全部46个品牌已覆盖")


if __name__ == "__main__":
    main()
