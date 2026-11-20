#!/usr/bin/env python3
"""Tests for check_ai_model.smoke_test()'s response-shape handling.

Regression context (2026-11-20): smoke_test() read only `result.response`,
the old plain-string shape. Chat-style Workers AI models return an
OpenAI-compatible envelope at `result.choices[0].message.content`, so a
perfectly healthy candidate would have been scored dead -- the automation
would have refused to switch away from a deprecated model, failing closed in
the worst possible place.

No network: requests.post is mocked.
"""
import json
import unittest
from unittest import mock

import check_ai_model


def _resp(payload, ok=True, status=200):
    r = mock.Mock()
    r.ok = ok
    r.status_code = status
    r.json.return_value = payload
    return r


class ExtractResponseTextTest(unittest.TestCase):
    def test_plain_string_shape(self):
        self.assertEqual(
            check_ai_model._extract_response_text({"response": "OK"}), "OK"
        )

    def test_openai_envelope_shape(self):
        result = {"choices": [{"message": {"role": "assistant", "content": "OK"}}]}
        self.assertEqual(check_ai_model._extract_response_text(result), "OK")

    def test_unrecognized_shape_returns_empty_not_raises(self):
        self.assertEqual(check_ai_model._extract_response_text({"weird": 1}), "")

    def test_non_string_response_falls_through_to_choices(self):
        result = {
            "response": {"not": "a string"},
            "choices": [{"message": {"content": "OK"}}],
        }
        self.assertEqual(check_ai_model._extract_response_text(result), "OK")

    def test_empty_choices_is_empty(self):
        self.assertEqual(check_ai_model._extract_response_text({"choices": []}), "")


class SmokeTestShapeTest(unittest.TestCase):
    def _call(self, payload, ok=True, status=200):
        with mock.patch.object(
            check_ai_model.requests, "post", return_value=_resp(payload, ok, status)
        ):
            return check_ai_model.smoke_test("acct", "token", "@cf/meta/candidate")

    def test_accepts_old_shape(self):
        self.assertTrue(self._call({"result": {"response": "OK"}}))

    def test_accepts_openai_envelope(self):
        self.assertTrue(
            self._call({"result": {"choices": [{"message": {"content": "OK"}}]}})
        )

    def test_rejects_http_error(self):
        self.assertFalse(
            self._call({"errors": [{"message": "410 Gone"}]}, ok=False, status=410)
        )

    def test_rejects_empty_text(self):
        self.assertFalse(self._call({"result": {"response": "   "}}))

    def test_rejects_unrecognized_shape(self):
        self.assertFalse(self._call({"result": {"unexpected": True}}))

    def test_rejects_missing_result(self):
        self.assertFalse(self._call({}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
