"""Offline tests for credentials copied from a browser as a cURL command."""

import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch


with patch.dict(os.environ, {"WXREAD_CURL_BASH": ""}):
    convert = runpy.run_path(str(Path(__file__).resolve().parents[1] / "config.py"))["convert"]


class CurlParsingTests(unittest.TestCase):
    def test_cookie_pairs_without_spaces_are_preserved(self):
        command = (
            "curl 'https://weread.qq.com/web/book/read' "
            "-b 'wr_vid=reader;wr_skey=key==;wr_rt=refresh=='"
        )

        _, cookies = convert(command)

        self.assertEqual(
            cookies,
            {"wr_vid": "reader", "wr_skey": "key==", "wr_rt": "refresh=="},
        )

    def test_double_quoted_long_options_and_line_continuations(self):
        command = (
            "curl 'https://weread.qq.com/web/book/read' \\\n"
            "  --header='Content-Type: application/json;charset=UTF-8' \\\n"
            '  --header "User-Agent: Example Browser" \\\n'
            '  --cookie="wr_vid=reader;wr_skey=key==;wr_rt=refresh=="'
        )

        headers, cookies = convert(command)

        self.assertEqual(
            headers,
            {"Content-Type": "application/json;charset=UTF-8", "User-Agent": "Example Browser"},
        )
        self.assertEqual(
            cookies,
            {"wr_vid": "reader", "wr_skey": "key==", "wr_rt": "refresh=="},
        )

    def test_cookie_header_is_removed_and_cookie_option_takes_precedence(self):
        command = (
            "curl https://weread.qq.com/web/book/read "
            "--header 'cOoKiE: wr_vid=stale;wr_skey=stale' "
            "-H 'Accept: application/json' "
            "-b 'wr_vid=reader; wr_skey=key==; wr_rt=refresh=='"
        )

        headers, cookies = convert(command)

        self.assertEqual(headers, {"Accept": "application/json"})
        self.assertEqual(
            cookies,
            {"wr_vid": "reader", "wr_skey": "key==", "wr_rt": "refresh=="},
        )

    def test_cookie_header_alone_supplies_credentials(self):
        command = (
            "curl https://weread.qq.com/web/book/read "
            "-H 'Cookie: wr_vid=reader; wr_skey=key==; wr_rt=refresh==' "
            "-H 'Referer: https://weread.qq.com/web/reader'"
        )

        headers, cookies = convert(command)

        self.assertEqual(headers, {"Referer": "https://weread.qq.com/web/reader"})
        self.assertEqual(
            cookies,
            {"wr_vid": "reader", "wr_skey": "key==", "wr_rt": "refresh=="},
        )

    def test_malformed_quotes_do_not_expose_cookie_values(self):
        headers, cookies = convert("curl -b 'wr_skey=private-example-value")

        self.assertEqual((headers, cookies), ({}, {}))


if __name__ == "__main__":
    unittest.main()
