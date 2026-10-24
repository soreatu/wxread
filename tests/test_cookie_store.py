"""The Actions cache must contain only authenticated, credential-bound ciphertext."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cookie_store


class CookieStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "auth" / "cookies.enc"
        environment = patch.dict("os.environ", {"WXREAD_COOKIE_FILE": str(self.path)})
        environment.start()
        self.addCleanup(environment.stop)
        self.source = "curl -b 'wr_skey=original-key; wr_vid=test-user; wr_rt=source-refresh'"
        self.cookies = {"wr_skey": "renewed-key==", "wr_vid": "test-user", "wr_rt": "rotated-refresh=="}

    def test_roundtrip_is_encrypted_and_restricted_to_owner(self):
        self.assertTrue(cookie_store.save_cookie_state(self.source, self.cookies))
        self.assertEqual(cookie_store.load_cookie_state(self.source), self.cookies)
        stored = self.path.read_bytes()
        for value in self.cookies.values():
            self.assertNotIn(value.encode(), stored)
        self.assertNotIn(b"wr_skey", stored)
        if os.name == "posix":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_replacing_secret_invalidates_saved_state_and_cache_key(self):
        cookie_store.save_cookie_state(self.source, self.cookies)
        replacement = self.source + " -H 'User-Agent: replacement-browser'"
        with self.assertLogs(level="WARNING") as logs:
            self.assertEqual(cookie_store.load_cookie_state(replacement), {})
        self.assertNotEqual(cookie_store.cache_key(self.source), cookie_store.cache_key(replacement))
        self.assertNotIn(self.source, "\n".join(logs.output))

    def test_corrupt_state_falls_back_without_disclosing_contents(self):
        self.path.parent.mkdir()
        self.path.write_text("broken-file-with-sensitive-cookie")
        with self.assertLogs(level="WARNING") as logs:
            self.assertEqual(cookie_store.load_cookie_state(self.source), {})
        self.assertNotIn("sensitive-cookie", "\n".join(logs.output))

    def test_valid_ciphertext_with_invalid_schema_is_rejected(self):
        self.path.parent.mkdir()
        for state in ([], {"version": 2}, {"version": 1, "cookies": {"wr_skey": [1]}}):
            with self.subTest(state=state):
                self.path.write_bytes(cookie_store._cipher(self.source).encrypt(json.dumps(state).encode()))
                with self.assertLogs(level="WARNING"):
                    self.assertEqual(cookie_store.load_cookie_state(self.source), {})

    def test_missing_file_and_disabled_storage_do_not_change_credentials(self):
        self.assertEqual(cookie_store.load_cookie_state(self.source), {})
        with patch.dict("os.environ", {"WXREAD_COOKIE_FILE": ""}):
            self.assertFalse(cookie_store.save_cookie_state(self.source, self.cookies))
            self.assertEqual(cookie_store.load_cookie_state(self.source), {})
        self.assertFalse(self.path.exists())

    def test_failed_atomic_write_preserves_previous_state(self):
        cookie_store.save_cookie_state(self.source, self.cookies)
        previous = self.path.read_bytes()
        with patch("cookie_store.Path.replace", side_effect=OSError("disk full")):
            with self.assertLogs(level="WARNING"):
                self.assertFalse(cookie_store.save_cookie_state(self.source, {**self.cookies, "wr_skey": "another-key"}))
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_empty_credential_is_never_used_as_an_encryption_key(self):
        with self.assertRaises(ValueError):
            cookie_store.save_cookie_state("", self.cookies)
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
