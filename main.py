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
PUBLIC_CHAPTER_INFOS_URL = "https://weread.qq.com/web/book/publicchapterInfos"
FIX_SYNCKEY_URL = "https://weread.qq.com/web/book/chapterInfos"
FIX_SYNCKEY_BOOK_ID = "695233"

COOKIE_DATA_VARIANTS = [
    {"rq": "%2Fweb%2Fbook%2Fread", "ql": False},
    {"rq": "%2Fweb%2Fbook%2Fread", "ql": True},
    {"rq": "%2Fweb%2Fbook%2Fread"},
]

READ_INTERVAL_MIN = 20                          # 每次阅读间隔随机范围（秒）lower bound
READ_INTERVAL_MAX = 40                          # 每次阅读间隔随机范围（秒）upper bound
MAX_TOTAL_RUNS = READ_NUM + 30                  # 兜底上限，避免异常响应导致死循环
REQUEST_TIMEOUT = 10
RETRY_AFTER_NETWORK_ERROR = 5

ERROR_MSG_NO_SKEY = "无法获取新密钥或者 WXREAD_CURL_BASH 配置有误，终止运行。"


# ---- 基础工具 ----
def _post_json(url: str, payload: dict, timeout: int = REQUEST_TIMEOUT) -> requests.Response:
    """统一 POST，复用 config 里的 headers/cookies。"""
    request_headers = dict(headers)
    if not any(key.lower() == "content-type" for key in request_headers):
        request_headers["Content-Type"] = "application/json;charset=UTF-8"

    return requests.post(
        url,
        headers=request_headers,
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


def encode_weread_id(raw_id: object) -> str:
    """按微信读书前端规则把原始 bookId/chapterUid 编码成 read 接口使用的 b/c。"""
    raw = str(raw_id)
    md5 = hashlib.md5(raw.encode()).hexdigest()
    chunks = []

    if raw.isdigit():
        id_type = "3"
        for i in range(0, len(raw), 9):
            chunks.append(hex(int(raw[i : i + 9]))[2:])
    else:
        id_type = "4"
        chunks.append("".join(hex(ord(ch))[2:] for ch in raw))

    encoded = f"{md5[:3]}{id_type}2{md5[-2:]}"
    encoded += "g".join(f"{len(chunk):02x}{chunk}" for chunk in chunks)

    if len(encoded) < 20:
        encoded += md5[: 20 - len(encoded)]

    return f"{encoded}{hashlib.md5(encoded.encode()).hexdigest()[:3]}"


def decode_weread_id(encoded_id: object) -> Optional[str]:
    """把 read 接口里的 b/c 还原成 chapterInfos 使用的原始 ID；无法识别则返回 None。"""
    value = str(encoded_id)
    if len(value) < 12 or value[3] not in ("3", "4") or value[4] != "2":
        return None

    id_type = value[3]
    pos = 7
    chunks = []
    checksum_start = len(value) - 3

    while pos + 2 <= checksum_start:
        try:
            chunk_len = int(value[pos : pos + 2], 16)
        except ValueError:
            break

        chunk_start = pos + 2
        chunk_end = chunk_start + chunk_len
        if chunk_len <= 0 or chunk_end > checksum_start:
            break

        chunk = value[chunk_start:chunk_end]
        try:
            int(chunk, 16)
        except ValueError:
            break

        chunks.append(chunk)
        pos = chunk_end

        if pos < checksum_start and value[pos] == "g":
            pos += 1
            continue
        break

    if not chunks:
        return None

    if id_type == "3":
        decimal_chunks = [str(int(chunk, 16)) for chunk in chunks]
        if len(decimal_chunks) == 1:
            decoded = decimal_chunks[0]
        else:
            decoded = (
                decimal_chunks[0]
                + "".join(chunk.zfill(9) for chunk in decimal_chunks[1:-1])
                + decimal_chunks[-1]
            )
        return decoded if encode_weread_id(decoded) == value else None

    hex_text = "".join(chunks)
    if len(hex_text) % 2 != 0:
        return None
    decoded = "".join(chr(int(hex_text[i : i + 2], 16)) for i in range(0, len(hex_text), 2))
    return decoded if encode_weread_id(decoded) == value else None


def normalize_read_id(raw_or_encoded_id: object) -> str:
    """保证返回值是 read 接口使用的编码 ID。"""
    text = str(raw_or_encoded_id)
    if decode_weread_id(text) is not None:
        return text
    return encode_weread_id(text)


def normalize_raw_id(raw_or_encoded_id: object) -> str:
    """保证返回值是 chapterInfos 接口使用的原始 ID。"""
    text = str(raw_or_encoded_id)
    return decode_weread_id(text) or text


def _chapter_items_from_response(response_data: dict, requested_book_ids: list[str]) -> dict[str, list[dict]]:
    """解析 chapterInfos/publicchapterInfos 响应，返回 raw_book_id -> chapter item 列表。"""
    result = {}

    for index, book_info in enumerate(response_data.get("data", [])):
        raw_book_id = (
            book_info.get("bookId")
            or book_info.get("book", {}).get("bookId")
            or (requested_book_ids[index] if index < len(requested_book_ids) else None)
        )
        if raw_book_id is None:
            continue

        chapters = (
            book_info.get("updated")
            or book_info.get("chapters")
            or book_info.get("chapterInfos")
            or []
        )
        if chapters:
            result[str(raw_book_id)] = chapters

    return result


def get_book_chapter_mapping(book_ids: list[str]) -> dict[str, list[str]]:
    """
    获取 read 接口可直接使用的 {encoded_book_id: [encoded_chapter_id, ...]}。

    config.book 里可以继续放现有 encoded book id；这里会先解码成原始 bookId 调
    chapterInfos，再把返回的 chapterUid 编码回 read 接口需要的 c 字段。
    """
    raw_book_ids = [normalize_raw_id(book_id) for book_id in book_ids]
    encoded_book_by_raw = {
        normalize_raw_id(book_id): normalize_read_id(book_id) for book_id in book_ids
    }
    remaining = set(raw_book_ids)
    mapping: dict[str, list[str]] = {}

    for raw_book_id in raw_book_ids:
        if raw_book_id not in remaining:
            continue

        for url in (PUBLIC_CHAPTER_INFOS_URL, FIX_SYNCKEY_URL):
            payload = {
                "bookIds": [raw_book_id],
                "synckeys": [0],
                "teenmode": 0,
            }

            try:
                response_data = _post_json(url, payload).json()
            except (requests.RequestException, ValueError) as exc:
                logging.warning(f"获取章节列表失败，url={url}，bookId={raw_book_id}，原因：{exc}")
                continue

            err_code = response_data.get("errCode")
            if err_code is not None:
                logging.warning(
                    "获取章节列表失败，url=%s，bookId=%s，errCode=%s，errMsg=%s",
                    url,
                    raw_book_id,
                    err_code,
                    response_data.get("errMsg", ""),
                )
                continue

            chapter_items_by_book = _chapter_items_from_response(response_data, [raw_book_id])
            chapter_items = chapter_items_by_book.get(raw_book_id)
            if not chapter_items:
                continue

            encoded_book_id = encoded_book_by_raw.get(raw_book_id, encode_weread_id(raw_book_id))
            encoded_chapter_ids = []
            seen = set()

            for chapter_info in chapter_items:
                chapter_uid = (
                    chapter_info.get("chapterUid")
                    or chapter_info.get("chapterId")
                    or chapter_info.get("uid")
                    or chapter_info.get("id")
                )
                if chapter_uid is None:
                    continue

                encoded_chapter_id = normalize_read_id(chapter_uid)
                if encoded_chapter_id not in seen:
                    encoded_chapter_ids.append(encoded_chapter_id)
                    seen.add(encoded_chapter_id)

            if encoded_chapter_ids:
                mapping[encoded_book_id] = encoded_chapter_ids
                remaining.discard(raw_book_id)
                break

    if remaining:
        logging.warning("以下书籍未获取到章节列表：%s", ", ".join(sorted(remaining)))
    if not mapping:
        raise RuntimeError("无法获取任何书籍章节映射，终止运行。")

    logging.info(
        "章节映射获取完成：%s",
        {book_id: len(chapter_ids) for book_id, chapter_ids in mapping.items()},
    )
    return mapping


def build_read_payload(last_time: int, book_chapter_mapping: dict[str, list[str]]) -> int:
    """就地更新 data 为本次阅读的签名请求体，返回本次时间戳。"""
    this_time = int(time.time())
    data.pop("s", None)  # 签名字段留到最后计算
    selected_book = random.choice(list(book_chapter_mapping.keys()))
    data["b"] = selected_book
    data["c"] = random.choice(book_chapter_mapping[selected_book])
    data["ct"] = this_time
    data["rt"] = this_time - last_time
    data["ts"] = int(this_time * 1000) + random.randint(0, 1000)
    data["rn"] = random.randint(0, 1000)
    data["sg"] = hashlib.sha256(f"{data['ts']}{data['rn']}{KEY}".encode()).hexdigest()
    data["s"] = cal_hash(encode_data(data))
    return this_time


# ---- Cookie 刷新 ----
def get_renewed_cookies() -> Optional[dict[str, str]]:
    """尝试各种 payload 变体调用 renewal 接口，拿到新的 wr_* cookie。"""
    for variant in COOKIE_DATA_VARIANTS:
        try:
            response = _post_json(RENEW_URL, variant)
            logging.info(response.headers)
        except requests.RequestException as exc:
            logging.warning(f"renewal 请求失败，payload={variant}，原因：{exc}")
            continue

        renewed_cookies = response.cookies.get_dict()
        if renewed_cookies.get("wr_skey"):
            return renewed_cookies
    return None


def get_wr_skey() -> Optional[str]:
    """兼容旧调用：只返回 renewal 接口拿到的 wr_skey。"""
    renewed_cookies = get_renewed_cookies()
    if not renewed_cookies:
        return None
    return renewed_cookies["wr_skey"]


def refresh_cookie() -> None:
    logging.info("刷新 cookie")
    renewed_cookies = get_renewed_cookies()
    if not renewed_cookies:
        logging.error(ERROR_MSG_NO_SKEY)
        push(ERROR_MSG_NO_SKEY, PUSH_METHOD)
        raise RuntimeError(ERROR_MSG_NO_SKEY)
    cookies.update(renewed_cookies)
    logging.info(f"密钥刷新成功，新密钥：{renewed_cookies['wr_skey']}")


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
    book_chapter_mapping = get_book_chapter_mapping(book)
    logging.info(f"一共需要阅读 {READ_NUM} 次。")

    done = 0
    elapsed_seconds = 0
    last_time = int(time.time()) - next_interval()
    total_runs = 0

    while done < READ_NUM and total_runs < MAX_TOTAL_RUNS:
        total_runs += 1

        this_time = build_read_payload(last_time, book_chapter_mapping)
        logging.debug("data: %s", data)

        try:
            res_data = _post_json(READ_URL, data).json()
        except (requests.RequestException, ValueError) as exc:
            logging.warning(f"阅读请求失败，{RETRY_AFTER_NETWORK_ERROR}s 后重试：{exc}")
            time.sleep(RETRY_AFTER_NETWORK_ERROR)
            continue

        logging.debug("response: %s", res_data)

        if res_data.get("succ") != 1:
            logging.warning("cookie 已过期，尝试刷新...")
            refresh_cookie()
            continue

        if "synckey" not in res_data:
            logging.warning("无 synckey，尝试修复...")
            fix_no_synckey()
            continue

        done += 1
        last_time = this_time
        if done >= READ_NUM:
            show_progress(done, elapsed_seconds)
            break

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
