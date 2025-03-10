import logging
from typing import Optional
from urllib.parse import urlencode

import requests
from open_webui.retrieval.web.main import SearchResult, get_filtered_results
from open_webui.env import SRC_LOG_LEVELS

import random
import time

import urllib.request
import ssl
import json

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

user_agents = [
    # Chrome 浏览器
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Firefox 浏览器
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:134.0) Gecko/20100101 Firefox/134.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0",
    # Edge 浏览器
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0"
]

last_request_time = 0

def send_request_with_retry(
    params: dict,
):
    global last_request_time

    base_url = "https://www.baidu.com/s"

    url = f"{base_url}?{urlencode(params)}"
    log.info(f"searching {url}")

    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-",
        "Accept-Encoding": "gzip, deflate, zstd",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Cookie": "BAIDUID=B863A09046D5D8CB6710A10ADC00C88E:FG=1; BIDUPSID=B863A09046D5D8CB6710A10ADC00C88E; PSTM=1730987767; BD_UPN=123253; BAIDUID_BFESS=B863A09046D5D8CB6710A10ADC00C88E:FG=1;"
    }

    # 获取当前时间
    current_time = time.time()
    # 计算距离上次请求经过的时间
    elapsed_time = current_time - last_request_time
    if elapsed_time < 1:
        # 若不足 1 秒，生成 1 到 3 秒的随机等待时间
        wait_time = random.randint(1, 3)
        log.info(f"Wait for {wait_time} second...")
        time.sleep(wait_time)
        
    response = requests.get(
        base_url,
        headers=headers,
        params=params,
        timeout=10,
    )
    last_request_time = time.time()
    response.raise_for_status() # 检查请求是否成功

    try:
        data = response.json()
        return data
    except Exception as e:
        log.info(f"Failed to parse response: {e}")
        log.info(response.text)

        log.info("Try to request via urllib.request")
        context = ssl._create_unverified_context()
        req = urllib.request.Request(url=url, headers=headers)
        wait_time = random.randint(1, 3)
        log.info(f"Wait for {wait_time} second...")
        time.sleep(wait_time)
        html = urllib.request.urlopen(req, context=context).read().decode('UTF-8')
        last_request_time = time.time()

        try:
            data = json.loads(html)
            return data
        except Exception as e:
            log.info(f"Failed to parse response: {e}")
            log.info(html)
            raise Exception(f"Failed to get json response")


def search_searxng(
    query_url: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
    **kwargs,
) -> list[SearchResult]:
    
    log.info("search via baidu")
    
    results = []
    original_count = count

    page_num = 0
    results_per_page = 15

    while count > 0:
        params = {
            "wd": query,
            "pn": page_num * results_per_page, 
            "rn": results_per_page,
            "tn": "json",
        }

        try:
            data = send_request_with_retry(params)
        except Exception as e:
            raise Exception(f"Invalid response: {e}") from e

        if "feed" not in data or "entry" not in data["feed"]:
            log.info(data)
            raise Exception("Invalid response: no feed or no entry in feed")

        for entry in data["feed"]["entry"]:
            if not entry.get("title") or not entry.get("url"):
                continue

            results.append(
                SearchResult(
                    link=entry["url"], 
                    title=entry["title"], 
                    snippet=entry.get("abs", ""),
                )
            )

            if len(results) >= original_count:
                break
        
        page_num += 1
        count -= results_per_page
    
    return results
