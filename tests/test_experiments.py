import unittest
from datetime import date

from agent.experiments import choose_slot_time, timing_recommendations
from agent.sources import valid_http_url


class ExperimentTests(unittest.TestCase):
    def test_time_experiment_is_stable_for_a_week(self):
        slot = {"time": "13:00", "time_candidates": ["13:00", "17:00"]}
        first, metadata = choose_slot_time(slot, date(2026, 9, 14))
        second, _ = choose_slot_time(slot, date(2026, 9, 15))
        self.assertEqual(first, second)
        self.assertTrue(metadata["active"])

    def test_timing_needs_three_posts_before_reporting(self):
        rows = [
            {"posted": "2026-09-03T13:00:00+05:30", "reach": 100, "saved": 2, "shares": 1},
            {"posted": "2026-09-10T13:00:00+05:30", "reach": 100, "saved": 3, "shares": 1},
        ]
        self.assertEqual(timing_recommendations(rows), [])

    def test_timing_uses_volume_normalised_saves_and_shares(self):
        rows = [
            {"posted": f"2026-09-{day:02d}T13:00:00+05:30", "reach": 100,
             "saved": 2, "shares": 1, "avg_watch_time": 12}
            for day in (3, 10, 17)
        ]
        result = timing_recommendations(rows)
        self.assertEqual(result[0]["median_save_share_per_1000_reach"], 30.0)
        self.assertEqual(result[0]["mean_avg_watch_time"], 12.0)

    def test_source_url_must_be_http(self):
        self.assertTrue(valid_http_url("https://example.com/report"))
        self.assertFalse(valid_http_url("not-a-url"))
