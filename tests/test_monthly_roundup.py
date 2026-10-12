import datetime as dt
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from agent import config, monthly_roundup as monthly, wordpress
from agent.schema import validate


class MonthlyTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 10, 12, 9, tzinfo=ZoneInfo("Asia/Kolkata"))
        self.start, self.end = monthly.month_window("2026-09", self.now)

    def test_closed_month_and_year_boundary(self):
        with self.assertRaises(ValueError):
            monthly.month_window("2026-10", self.now)
        start, end = monthly.month_window(None, self.now.replace(year=2027, month=1))
        self.assertEqual(start.strftime("%Y-%m"), "2026-12")
        self.assertEqual(end.strftime("%Y-%m"), "2027-01")

    def test_extra_slot_and_late_recovery(self):
        when = monthly.schedule_time(self.end, self.now)
        self.assertGreater(when, self.now)
        self.assertEqual(when.strftime("%H:%M"), "19:30")
        next_month = self.now.replace(month=11, day=1, hour=0, minute=0)
        when = monthly.schedule_time(next_month, self.now)
        self.assertEqual(when.day, 2)

    def test_preview_matches_existing_contract(self):
        items = [{"title": f"Reading option {i}", "link": f"https://www.rachitmishra.in/blog-{i}"}
                 for i in range(15)]
        post = monthly.preview_post(items, self.start)
        self.assertEqual(validate(post), [])
        self.assertIn("15 blogs", post["caption"])
        self.assertEqual(len(post["slides"]), 6)

    def test_hourly_publisher_window_does_not_collide(self):
        december = self.now.replace(month=12, day=1, hour=0, minute=0)
        when = monthly.schedule_time(december, self.now, [
            {"day": "wed", "time": "20:00"}, {"day": "wed", "time": "08:30"}])
        self.assertEqual(when.strftime("%Y-%m-%d %H:%M"), "2026-12-02 20:30")

    def test_deduplication_in_approved_and_published_queues(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "post.json"
            target.write_text('{"newsletter_month":"2026-09"}', encoding="utf-8")
            with patch.object(config, "QUEUE_DIR", base), patch.object(config, "APPROVED_DIR", base), \
                 patch.object(config, "PUBLISHED_DIR", base), patch.object(config, "SKIPPED_DIR", base):
                self.assertEqual(monthly.existing_month("2026-09"), target)
                self.assertIsNone(monthly.existing_month("2026-08"))

    def test_pagination_and_ist_boundary(self):
        def row(i, date):
            return {"id": i, "status": "publish", "date_gmt": date,
                    "link": f"https://www.rachitmishra.in/p-{i}", "title": {"rendered": "A &amp; B"},
                    "excerpt": {"rendered": "Summary"}, "content": {"rendered": "Full body"}}
        responses = []
        for rows in [[row(1, "2026-08-31T18:30:00")],
                     [row(2, "2026-09-30T18:29:59"), row(3, "2026-09-30T18:30:00")]]:
            from unittest.mock import Mock
            response = Mock()
            response.headers = {"X-WP-TotalPages": "2"}
            response.json.return_value = rows
            responses.append(response)
        with patch.object(wordpress.requests, "get", side_effect=responses) as call:
            articles = wordpress.fetch_articles(monthly.SITE, start=self.start, end=self.end)
        self.assertEqual([a["id"] for a in articles], [1, 2])
        self.assertEqual(call.call_count, 2)
        self.assertEqual(articles[0]["title"], "A & B")

    def test_excerpt_feed_is_hydrated_for_weekly_posts(self):
        from agent import from_blog
        from unittest.mock import Mock
        response = Mock()
        response.content = b'<rss><channel><item><title>Public blog</title><link>https://www.rachitmishra.in/2026/09/01/public-blog/</link><description>Short excerpt.</description></item></channel></rss>'
        full = {"link": "https://www.rachitmishra.in/2026/09/01/public-blog/", "body": "word " * 200, "words": 200}
        with patch.object(from_blog.requests, "get", return_value=response), \
             patch.object(wordpress, "fetch_articles", return_value=[full]):
            articles = from_blog.fetch_feed()
        self.assertEqual(articles[0]["words"], 200)


if __name__ == "__main__":
    unittest.main()
