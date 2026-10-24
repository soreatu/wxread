"""Offline regressions for renewal, reading retries, and local chapter mapping."""

import importlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests


# Never read a developer's real cookie or contact WeRead when importing the app.
with (
    patch.dict(
        "os.environ",
        {
            "WXREAD_CURL_BASH": (
                "curl 'https://weread.qq.com/web/book/read' "
                "-H 'Content-Type: application/json' "
                "-b 'wr_skey=existing-test-key; wr_vid=test-user'"
            ),
            "READ_NUM": "1",
            "PUSH_METHOD": "",
        },
    ),
    patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected network request")),
    patch("log_utils.setup_logging", return_value=Mock()),
):
    main = importlib.import_module("main")


def response(payload=None, *, status=200, cookies=None, text=None):
    result = requests.Response()
    result.status_code = status
    result.url = main.READ_URL
    result.encoding = "utf-8"
    result._content = (text if text is not None else json.dumps(payload or {})).encode()
    result.headers["Content-Type"] = "text/html" if text is not None else "application/json"
    result.cookies = requests.cookies.cookiejar_from_dict(cookies or {})
    return result


class MainRegressionTests(unittest.TestCase):
    def setUp(self):
        # Patching post in individual tests is allowed; every other HTTP path fails.
        self.start_patch(
            "requests.sessions.Session.request",
            side_effect=AssertionError("Unexpected network request"),
        )
        self.sleep = self.start_patch("main.time.sleep")
        self.start_patch("main.time.time", return_value=1_700_000_000)
        self.push = self.start_patch("main.push")
        self.start_patch("main.show_progress")
        self.start_patch("main.READ_NUM", 1)
        self.start_patch("main.MAX_TOTAL_RUNS", 6)
        self.start_patch("main.PUSH_METHOD", "telegram")
        self.start_patch("main.WXREAD_CURL_BASH", "curl -b 'wr_skey=source-test-key; wr_vid=test-user'")
        environment = patch.dict("os.environ", {"WXREAD_COOKIE_FILE": ""})
        environment.start()
        self.addCleanup(environment.stop)
        cookie_patch = patch.dict(main.cookies, {"wr_skey": "existing-test-key", "wr_vid": "test-user"}, clear=True)
        cookie_patch.start()
        self.addCleanup(cookie_patch.stop)
        data_patch = patch.dict(main.data, main.data.copy(), clear=True)
        data_patch.start()
        self.addCleanup(data_patch.stop)
        self.mapping = {main.encode_weread_id("695233"): [main.encode_weread_id("1")]}

    def start_patch(self, target, *args, **kwargs):
        patcher = patch(target, *args, **kwargs)
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def prepare_reading(self):
        self.start_patch("main.refresh_cookie", return_value=True)
        self.start_patch("main.get_book_chapter_mapping", return_value=self.mapping)

    def assert_only_failure_notifications(self):
        self.assertTrue(self.push.called, "An incomplete run must send a failure notification")
        for call in self.push.call_args_list:
            self.assertIs(call.kwargs.get("is_success"), False, call)

    def test_startup_without_renewed_cookie_reads_using_existing_cookie(self):
        self.start_patch("main.get_book_chapter_mapping", return_value=self.mapping)
        reads = []

        def post(url, **kwargs):
            if url == main.RENEW_URL:
                return response({"succ": 1})
            self.assertEqual(url, main.READ_URL)
            reads.append(kwargs)
            self.assertEqual(kwargs["cookies"]["wr_skey"], "existing-test-key")
            return response({"succ": 1, "synckey": "new-sync"})

        self.start_patch("requests.post", side_effect=post)
        main.main()
        self.assertEqual(len(reads), 1)
        self.push.assert_called_once()
        self.assertIsNot(self.push.call_args.kwargs.get("is_success"), False)

    def test_rotated_login_survives_a_new_actions_process(self):
        # Each interpreter starts with the original Secret. Only the encrypted file
        # survives between jobs; the mock server rejects the obsolete refresh token.
        script = '''
import json
import sys
from unittest.mock import Mock, patch
import requests
with patch("log_utils.setup_logging", return_value=Mock()):
    import main
current_refresh = sys.argv[1]
reads = []
def post(url, **kwargs):
    global current_refresh
    result = requests.Response()
    result.status_code = 200
    payload = {"errCode": -2012, "errMsg": "登录超时"}
    if kwargs["cookies"].get("wr_rt") == current_refresh:
        if url == main.RENEW_URL:
            current_refresh = "rotated-refresh"
            payload = {"succ": 1}
            result.cookies = requests.cookies.cookiejar_from_dict({
                "wr_skey": "rotated-key", "wr_vid": "test-user", "wr_rt": current_refresh,
            })
        else:
            assert url == main.READ_URL
            reads.append(kwargs["cookies"].copy())
            payload = {"succ": 1, "synckey": "new-sync"}
    result._content = json.dumps(payload).encode()
    return result
with (
    patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected network request")),
    patch("requests.post", side_effect=post),
    patch("main.get_book_chapter_mapping", return_value={"book": ["chapter"]}),
):
    main.main()
assert len(reads) == 1
assert reads[0]["wr_rt"] == "rotated-refresh"
'''
        with tempfile.TemporaryDirectory() as directory:
            environment = {
                **os.environ,
                "WXREAD_COOKIE_FILE": str(Path(directory) / "cookies.enc"),
                "WXREAD_CURL_BASH": "curl -b 'wr_skey=initial-key;wr_vid=test-user;wr_rt=initial-refresh'",
                "READ_NUM": "1", "PUSH_METHOD": "",
            }
            for refresh in ("initial-refresh", "rotated-refresh"):
                completed = subprocess.run(
                    [sys.executable, "-c", script, refresh],
                    cwd=Path(__file__).resolve().parents[1], env=environment,
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_missing_synckey_stops_after_three_repairs_without_success(self):
        self.prepare_reading()
        post = self.start_patch("requests.post", return_value=response({"succ": 1}))
        repair = self.start_patch("main.fix_no_synckey")

        with self.assertRaises(RuntimeError):
            main.main()

        self.assertEqual(repair.call_count, 3)
        self.assertLessEqual(post.call_count, 4)
        self.assertEqual(self.sleep.call_args_list.count(unittest.mock.call(5)), 3)
        self.assert_only_failure_notifications()

    def test_synckey_repair_budget_resets_after_a_successful_read(self):
        self.prepare_reading()
        self.start_patch("main.READ_NUM", 2)
        self.start_patch("main.MAX_TOTAL_RUNS", 8)
        episode = [response({"succ": 1}) for _ in range(3)]
        episode.append(response({"succ": 1, "synckey": "recovered"}))
        post = self.start_patch("requests.post", side_effect=episode + episode)
        repair = self.start_patch("main.fix_no_synckey")

        main.main()

        self.assertEqual(post.call_count, 8)
        self.assertEqual(repair.call_count, 6)
        self.push.assert_called_once()
        self.assertIs(self.push.call_args.kwargs.get("is_success"), True)

    def test_exhausted_run_limit_raises_and_sends_failure(self):
        self.prepare_reading()
        self.start_patch("main.MAX_TOTAL_RUNS", 2)
        post = self.start_patch("requests.post", side_effect=requests.ConnectionError("offline"))

        with self.assertRaises(RuntimeError):
            main.main()

        self.assertEqual(post.call_count, 2)
        self.assert_only_failure_notifications()

    def test_network_failure_is_retried_and_can_finish(self):
        self.prepare_reading()
        post = self.start_patch(
            "requests.post",
            side_effect=[requests.Timeout("temporary timeout"), response({"succ": 1, "synckey": "new-sync"})],
        )
        main.main()

        self.assertEqual(post.call_count, 2)
        self.sleep.assert_called_once_with(main.RETRY_AFTER_NETWORK_ERROR)
        self.push.assert_called_once()
        self.assertIsNot(self.push.call_args.kwargs.get("is_success"), False)

    def test_non_json_http_error_has_status_diagnostic_and_fails(self):
        self.prepare_reading()
        self.start_patch("main.MAX_TOTAL_RUNS", 1)
        self.start_patch("requests.post", return_value=response(status=502, text="<html>Bad Gateway</html>"))

        with self.assertLogs(level="WARNING") as logs, self.assertRaises(RuntimeError):
            main.main()

        self.assertIn("502", "\n".join(logs.output))
        self.assert_only_failure_notifications()

    def test_cookie_refresh_preserves_every_cookie_and_full_values(self):
        renewed = {
            "wr_skey": "new-test-key-with-a-long-untruncated-suffix==",
            "wr_vid": "renewed-test-user",
            "wr_rt": "complete-refresh-token==",
            "wr_local": "additional-cookie",
        }
        self.start_patch("requests.post", return_value=response(cookies=renewed))
        main.cookies["other_cookie"] = "preserved"

        self.assertIs(main.refresh_cookie(strict=True), True)
        self.assertEqual(main.cookies, {**renewed, "other_cookie": "preserved"})

    def test_optional_cookie_refresh_reports_false_without_failing(self):
        self.start_patch("requests.post", return_value=response({"succ": 1}))

        self.assertIs(main.refresh_cookie(strict=False), False)
        self.assertEqual(main.cookies["wr_skey"], "existing-test-key")
        self.push.assert_not_called()

    def test_renewal_login_rejection_has_diagnostic_without_secrets(self):
        secret = "sensitive-server-response"
        self.start_patch("requests.post", return_value=response({
            "errCode": -2012, "errMsg": secret, "wr_rt": secret,
        }))

        with self.assertLogs(level="WARNING") as logs:
            self.assertIsNone(main.get_renewed_cookies())

        output = "\n".join(logs.output)
        self.assertIn("HTTP 200", output)
        self.assertIn("errCode=-2012", output)
        self.assertIn("继续尝试其他参数", output)
        self.assertNotIn(secret, output)

    def test_invalid_renewal_body_is_diagnosed_without_crashing(self):
        for invalid in ([1], {"errCode": []}, None):
            with self.subTest(invalid=invalid):
                result = response(invalid) if invalid is not None else response(text="<html>secret</html>")
                self.start_patch("requests.post", return_value=result)
                with self.assertLogs(level="WARNING") as logs:
                    self.assertIsNone(main.get_renewed_cookies())
                self.assertIn("renewal 未返回 wr_skey", "\n".join(logs.output))

    def test_expired_login_fails_with_recapture_instructions_without_success(self):
        self.start_patch("main.get_book_chapter_mapping", return_value=self.mapping)
        self.start_patch("requests.post", return_value=response({"errCode": -2012, "errMsg": "登录超时"}))

        with self.assertRaisesRegex(RuntimeError, "更新 WXREAD_CURL_BASH"):
            main.main()
        self.assert_only_failure_notifications()

    def test_partial_cookie_configuration_fails_before_network(self):
        post = self.start_patch("requests.post")
        with patch.dict(main.cookies, {"wr_skey": "test-key"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "wr_vid"):
                main.main()
        post.assert_not_called()
        self.assert_only_failure_notifications()

    def test_requests_have_separate_connect_and_read_timeouts(self):
        post = self.start_patch("requests.post", return_value=response())
        main._post_json(main.READ_URL, {"test": "payload"})

        self.assertEqual(post.call_args.kwargs["timeout"], (10, 30))

    def test_missing_cookie_configuration_reports_the_setting_before_network(self):
        post = self.start_patch("requests.post")
        for environment in ({}, {"WXREAD_CURL_BASH": ""}):
            with self.subTest(environment=environment), patch.dict("os.environ", environment, clear=True):
                configuration = runpy.run_path(str(Path(__file__).resolve().parents[1] / "config.py"))
                self.assertEqual(configuration["cookies"], {})
                with patch.dict(main.cookies, configuration["cookies"], clear=True):
                    with self.assertRaisesRegex(RuntimeError, "WXREAD_CURL_BASH"):
                        main.main()
        post.assert_not_called()
        self.assert_only_failure_notifications()

    def test_dynamic_mapping_encodes_chapters_and_falls_back_per_book(self):
        encoded_first = main.encode_weread_id("695233")
        requested = []

        def post(url, **kwargs):
            payload = json.loads(kwargs["data"])
            requested.append((url, payload["bookIds"]))
            raw_id = payload["bookIds"][0]
            if raw_id == "695233":
                return response({"data": [{"bookId": raw_id, "updated": [{"chapterUid": 1}, {"chapterUid": 1}, {"chapterId": 2}]}]})
            self.assertEqual(raw_id, "7258825")
            if url == main.PUBLIC_CHAPTER_INFOS_URL:
                return response({"data": []})
            self.assertEqual(url, main.FIX_SYNCKEY_URL)
            return response({"data": [{"book": {"bookId": raw_id}, "chapters": [{"uid": 9}]}]})

        self.start_patch("requests.post", side_effect=post)
        mapping = main.get_book_chapter_mapping([encoded_first, "7258825"])

        self.assertEqual(
            mapping,
            {
                encoded_first: [main.encode_weread_id("1"), main.encode_weread_id("2")],
                main.encode_weread_id("7258825"): [main.encode_weread_id("9")],
            },
        )
        self.assertEqual(
            requested,
            [
                (main.PUBLIC_CHAPTER_INFOS_URL, ["695233"]),
                (main.PUBLIC_CHAPTER_INFOS_URL, ["7258825"]),
                (main.FIX_SYNCKEY_URL, ["7258825"]),
            ],
        )

    def test_weread_id_roundtrip_and_normalization(self):
        for raw_id in ("0", "1", "695233", "7258825", "123456789987654321", "book-A_1"):
            with self.subTest(raw_id=raw_id):
                encoded = main.encode_weread_id(raw_id)
                self.assertEqual(main.decode_weread_id(encoded), raw_id)
                self.assertEqual(main.normalize_read_id(encoded), encoded)
                self.assertEqual(main.normalize_raw_id(encoded), raw_id)
                self.assertEqual(main.normalize_read_id(raw_id), encoded)
        self.assertIsNone(main.decode_weread_id("invalid-id"))


if __name__ == "__main__":
    unittest.main()
