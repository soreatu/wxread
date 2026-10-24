"""Persist renewed login cookies as authenticated ciphertext, never as plaintext."""

import base64
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import tempfile

from cryptography.fernet import Fernet, InvalidToken


def cache_key(source: str) -> str:
    """Partition saved state by the original credential; replacing it starts fresh."""
    if not source:
        raise ValueError("WXREAD_CURL_BASH 未配置。")
    return hashlib.sha256(source.encode()).hexdigest()


def _cipher(source: str) -> Fernet:
    cache_key(source)  # Never encrypt using an empty, publicly known credential.
    key = hashlib.sha256(b"wxread-cookie-state-v1\0" + source.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def load_cookie_state(source: str) -> dict[str, str]:
    filename = os.getenv("WXREAD_COOKIE_FILE")
    if not filename:
        return {}
    try:
        encrypted = Path(filename).read_bytes()
    except FileNotFoundError:
        return {}
    except OSError:
        logging.warning("无法读取已保存的登录态，将使用 WXREAD_CURL_BASH。")
        return {}

    try:
        state = json.loads(_cipher(source).decrypt(encrypted))
        if not isinstance(state, dict) or state.get("version") != 1:
            raise ValueError("Invalid state version")
        saved = state.get("cookies")
        if (
            not isinstance(saved, dict)
            or not saved.get("wr_skey")
            or not saved.get("wr_vid")
            or not all(isinstance(k, str) and isinstance(v, str) for k, v in saved.items())
        ):
            raise ValueError("Invalid cookies")
    except (InvalidToken, ValueError, TypeError):
        logging.warning("已保存的登录态无法解密或格式无效，将使用 WXREAD_CURL_BASH。")
        return {}

    logging.info("已恢复上次续期后的登录态。")
    return saved


def save_cookie_state(source: str, cookies: dict[str, str]) -> bool:
    filename = os.getenv("WXREAD_COOKIE_FILE")
    if not filename:
        return False
    if not cookies.get("wr_skey") or not cookies.get("wr_vid"):
        return False
    encrypted = _cipher(source).encrypt(
        json.dumps({"version": 1, "cookies": cookies}, separators=(",", ":")).encode()
    )
    destination = Path(filename)
    temporary = None
    try:
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # NamedTemporaryFile creates a mode-0600 file; replace is atomic.
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encrypted)
        temporary.replace(destination)
    except OSError:
        logging.warning("无法保存续期后的登录态，下次运行可能需要重新登录。")
        return False
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    logging.info("已加密保存续期后的登录态。")
    return True


if __name__ == "__main__":
    if sys.argv[1:] != ["cache-key"]:
        raise SystemExit("Usage: python cookie_store.py cache-key")
    from config import WXREAD_CURL_BASH

    try:
        print(cache_key(WXREAD_CURL_BASH))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
