"""Tests of accounting rules, never measurements of a model."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import quality
from summarize_real import latency, location_match


class RealSummary(unittest.TestCase):
    def test_cross_version_location_is_not_strict_equality(self):
        target = {
            "document_id": "vt-segunda-via",
            "source_version": "snapshot-local-v1",
            "section_or_row": "89",
            "page": 2,
            "benefit_code": "89",
        }
        actual = dict(target, source_version="actual-runtime-v1", section_or_row="89 · SPTrans")
        unchanged = deepcopy(actual)
        self.assertFalse(quality.reference_matches(actual, target))
        self.assertTrue(location_match(actual, target))
        self.assertEqual(actual, unchanged)
        self.assertFalse(location_match(dict(actual, benefit_code="9156"), target))
        self.assertFalse(location_match(dict(actual, page=1), target))

    def test_latency_nearest_rank_and_missing_data(self):
        self.assertIsNone(latency([])["p95_ms"])
        self.assertEqual(latency(list(range(1, 21)))["p95_ms"], 19)
        self.assertEqual(latency([7])["p50_ms"], 7)


if __name__ == "__main__":
    unittest.main()
