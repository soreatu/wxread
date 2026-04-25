# main.py 主逻辑：包括字段拼接、模拟请求
import hashlib
import json
import logging
import random
import time
import urllib.parse
from typing import Optional

import requests

from config import (
    PUSH_METHOD,
    READ_NUM,
    book,
    chapter,
    cookies,
    data,
    headers,
)
from log_utils import setup_logging
from push import push


# ---- 常量 ----
KEY = "3c5c8717f3daf09iop3423zafeqoi"
READ_URL = "https://weread.qq.com/web/book/read"
RENEW_URL = "https://weread.qq.com/web/login/renewal"
FIX_SYNCKEY_URL = "https://weread.qq.com/web/book/chapterInfos"
FIX_SYNCKEY_BOOK_ID = "695233"

COOKIE_DATA_VARIANTS = [
    {"rq": "%2Fweb%2Fbook%2Fread", "ql": False},
    {"rq": "%2Fweb%2Fbook%2Fread", "ql": True},
    {"rq": "%2Fweb%2Fbook%2Fread"},
]

READ_INTERVAL_MIN = 30                          # 每次阅读间隔随机范围（秒）lower bound
READ_INTERVAL_MAX = 90                          # 每次阅读间隔随机范围（秒）upper bound
MAX_TOTAL_RUNS = READ_NUM + 30                  # 兜底上限，避免异常响应导致死循环
REQUEST_TIMEOUT = 10
RETRY_AFTER_NETWORK_ERROR = 5

ERROR_MSG_NO_SKEY = "无法获取新密钥或者 WXREAD_CURL_BASH 配置有误，终止运行。"


# ---- 基础工具 ----
def _post_json(url: str, payload: dict, timeout: int = REQUEST_TIMEOUT) -> requests.Response:
    """统一 POST，复用 config 里的 headers/cookies。"""
    return requests.post(
        url,
        headers=headers,
        cookies=cookies,
        data=json.dumps(payload, separators=(",", ":")),
        timeout=timeout,
    )


def encode_data(payload: dict) -> str:
    """按 key 排序后 url-encode 拼接，用于后续哈希计算。"""
    return "&".join(
        f"{k}={urllib.parse.quote(str(payload[k]), safe='')}"
        for k in sorted(payload.keys())
    )


def cal_hash(input_string: str) -> str:
    """JS 端同款字符串哈希算法。"""
    h1 = 0x15051505
    h2 = h1
    length = len(input_string)
    i = length - 1

    while i > 0:
        h1 = 0x7FFFFFFF & (h1 ^ ord(input_string[i]) << (length - i) % 30)
        h2 = 0x7FFFFFFF & (h2 ^ ord(input_string[i - 1]) << i % 30)
        i -= 2

    return hex(h1 + h2)[2:].lower()


def build_read_payload(last_time: int) -> int:
    """就地更新 data 为本次阅读的签名请求体，返回本次时间戳。"""
    this_time = int(time.time())
    data.pop("s", None)  # 签名字段留到最后计算
    data["b"] = random.choice(book)
    data["c"] = random.choice(chapter)
    data["ct"] = this_time
    data["rt"] = this_time - last_time
    data["ts"] = int(this_time * 1000) + random.randint(0, 1000)
    data["rn"] = random.randint(0, 1000)
    data["sg"] = hashlib.sha256(f"{data['ts']}{data['rn']}{KEY}".encode()).hexdigest()
    data["s"] = cal_hash(encode_data(data))
    return this_time


# ---- Cookie 刷新 ----
def get_wr_skey() -> Optional[str]:
    """尝试各种 payload 变体调用 renewal 接口，拿到新的 wr_skey。"""
    for variant in COOKIE_DATA_VARIANTS:
        try:
            response = _post_json(RENEW_URL, variant)
            logging.info(response.headers)
        except requests.RequestException as exc:
            logging.warning(f"renewal 请求失败，payload={variant}，原因：{exc}")
            continue

        skey = response.cookies.get("wr_skey")
        if skey:
            return skey
    return None


def refresh_cookie() -> None:
    logging.info("刷新 cookie")
    new_skey = get_wr_skey()
    if not new_skey:
        logging.error(ERROR_MSG_NO_SKEY)
        push(ERROR_MSG_NO_SKEY, PUSH_METHOD)
        raise RuntimeError(ERROR_MSG_NO_SKEY)
    cookies["wr_skey"] = new_skey
    logging.info(f"密钥刷新成功，新密钥：{new_skey}")


def fix_no_synckey() -> None:
    try:
        _post_json(FIX_SYNCKEY_URL, {"bookIds": [FIX_SYNCKEY_BOOK_ID]})
    except requests.RequestException as exc:
        logging.warning(f"fix_no_synckey 请求失败：{exc}")


# ---- 主流程 ----
refresh_print = setup_logging()


def next_interval() -> int:
    """每次阅读后的随机等待秒数。"""
    return random.randint(READ_INTERVAL_MIN, READ_INTERVAL_MAX)


def show_progress(done: int, elapsed_seconds: int) -> None:
    refresh_print(
        f"阅读进度: 第 {done}/{READ_NUM} 次，已完成 {elapsed_seconds / 60:.1f} 分钟"
    )


def main() -> None:
    refresh_cookie()
    logging.info(f"一共需要阅读 {READ_NUM} 次。")

    done = 0
    elapsed_seconds = 0
    last_time = int(time.time()) - next_interval()
    total_runs = 0

    while done < READ_NUM and total_runs < MAX_TOTAL_RUNS:
        total_runs += 1

        this_time = build_read_payload(last_time)
        logging.debug("data: %s", data)

        try:
            res_data = _post_json(READ_URL, data).json()
        except (requests.RequestException, ValueError) as exc:
            logging.warning(f"阅读请求失败，{RETRY_AFTER_NETWORK_ERROR}s 后重试：{exc}")
            time.sleep(RETRY_AFTER_NETWORK_ERROR)
            continue

        logging.debug("response: %s", res_data)

        if "succ" not in res_data:
            logging.warning("cookie 已过期，尝试刷新...")
            refresh_cookie()
            continue

        if "synckey" not in res_data:
            logging.warning("无 synckey，尝试修复...")
            fix_no_synckey()
            continue

        done += 1
        last_time = this_time
        interval = next_interval()
        elapsed_seconds += interval
        show_progress(done, elapsed_seconds)
        time.sleep(interval)

    if done < READ_NUM:
        logging.warning(
            f"达到兜底上限 {MAX_TOTAL_RUNS} 次仍未完成（{done}/{READ_NUM}），提前结束。"
        )
    else:
        logging.info("阅读脚本已完成。")

    if PUSH_METHOD:
        logging.info("开始推送...")
        push(
            f"微信读书自动阅读完成。\n阅读时长：{elapsed_seconds / 60:.1f} 分钟。",
            PUSH_METHOD,
        )
    else:
        logging.info("未配置推送渠道，跳过推送。")


if __name__ == "__main__":
    main()
