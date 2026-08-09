# -*- coding: utf-8 -*-
import pandas as pd
import requests
from newspaper import Article
from urllib.parse import urljoin
import time
import re
from bs4 import BeautifulSoup

EXCEL_FILE = "white (2).xlsx"
SHEET_NAME = "Sheet1"
COL_NAME = "服务地址"
OUTPUT_CSV = "媒体文章数据.csv"
ARTICLES_PER_MEDIA = 5             #每个网站采集的文章数
REQUEST_DELAY = 1                  #响应时间

def parse_domains(cell_value):
    if pd.isna(cell_value) or str(cell_value).strip() == "" or str(cell_value).strip() == "无":
        return []
    items = re.split(r'[;；,，\s]+', str(cell_value))
    domains = []
    for item in items:
        item = item.strip()
        if item and item != "无":
            if item.startswith(('http://', 'https://')):
                item = item.split('//')[1]
            domains.append(item)
    return domains

def domain_to_media_name(domain):
    name_map = {    # 常见媒体映射
        "people.com.cn": "人民网",
        "thepaper.cn": "澎湃新闻",
        "news.cn": "新华网",
        "xinhuanet.com": "新华网",
        "xinhua.org": "新华网",
        "cctv.com": "央视网",
        "cntv.cn": "央视网",
        "china.com.cn": "中国网",
        "chinadaily.com.cn": "中国日报",
        "gmw.cn": "光明网",
        "huanqiu.com": "环球网",
        "ahnews.com.cn": "安徽新闻网",
        "anhuinews.com": "安徽新闻网",
        "dzwww.com": "大众网",
        "iqilu.com": "齐鲁网",
        "cnr.cn": "央广网",
        "youth.cn": "中国青年网",
    }
    for key, name in name_map.items():
        if key in domain:
            return name
    parts = domain.split('.')
    if len(parts) >= 2:
        if parts[0] == 'www':
            return parts[1].capitalize()
        else:
            return parts[0].capitalize()
    return domain

def get_article_urls_from_homepage(domain, limit=10):
    try:
        protocol = "https" if requests.get(f"https://{domain}", timeout=5).status_code == 200 else "http"
    except:
        protocol = "http"
    homepage_url = f"{protocol}://{domain}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(homepage_url, headers=headers, timeout=10)
        resp.raise_for_status()
    except:
        return []
    soup = BeautifulSoup(resp.text, 'html.parser')
    urls = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        full_url = urljoin(homepage_url, href)
        # 简单过滤：包含常见新闻路径关键词
        if any(pattern in full_url for pattern in ['/news', '/article', '/p-', '/a/', '/story', '/content']):
            if full_url.startswith(('http://', 'https://')):
                urls.add(full_url)
        if len(urls) >= limit * 2:
            break
    return list(urls)[:limit]

def extract_article(url):
    try:
        article = Article(url, language='zh')
        article.download()
        article.parse()
        title = article.title
        # 正文取前500字（足够匹配关键词）
        content = (article.text or "")[:500]
        if title and content and len(content) > 50:
            return title, content
    except Exception as e:
        # print(f"  提取失败: {url} - {e}")
        pass
    return None, None

def main():
    print("=" * 60)
    print("开始读取名单 Excel 文件...")
    try:
        df_domains = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
    except Exception as e:
        print(f"读取 Excel 失败: {e}")
        return

    if COL_NAME not in df_domains.columns:
        print(f"Excel 中未找到列 '{COL_NAME}'，实际列有: {df_domains.columns.tolist()}")
        return

    all_domains = []
    for val in df_domains[COL_NAME]:
        domains = parse_domains(val)
        all_domains.extend(domains)
    all_domains = sorted(set(all_domains))
    print(f"共解析出 {len(all_domains)} 个唯一域名")

    articles = []
    for idx, domain in enumerate(all_domains):      # all_domains = all_domains[:50]
        media_name = domain_to_media_name(domain)
        print(f"[{idx+1}/{len(all_domains)}] 正在处理: {media_name} ({domain})")
        urls = get_article_urls_from_homepage(domain, limit=ARTICLES_PER_MEDIA*2)
        if not urls:
            print(f"未找到文章链接，跳过")
            time.sleep(REQUEST_DELAY)
            continue

        collected = 0
        for url in urls:
            if collected >= ARTICLES_PER_MEDIA:
                break
            title, content = extract_article(url)
            if title and content:
                articles.append({
                    "media_name": media_name,
                    "title": title,
                    "content": content,
                    "publish_date": ""
                })
                collected += 1
                print(f"已采集 {collected}/{ARTICLES_PER_MEDIA}: {title[:30]}...")
            time.sleep(0.5)
        time.sleep(REQUEST_DELAY)

    # 保存结果
    if articles:
        df_out = pd.DataFrame(articles)
        df_out.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
        print(f"\n采集完成！共获得 {len(articles)} 篇文章，已保存至 {OUTPUT_CSV}")
    else:
        print("\n未采集到任何文章，请检查网络")

if __name__ == "__main__":
    main()