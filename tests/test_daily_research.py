import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent import daily_research as research, config


class ResearchTests(unittest.TestCase):
    def test_feed_rejects_old_future_undated_and_non_https(self):
        xml = '<rss><channel>' + ''.join(
            f'<item><title>Brand update</title><link>{url}</link><pubDate>{date}</pubDate></item>'
            for url, date in [
                ('https://example.com/current', 'Wed, 18 Nov 2026 08:00:00 GMT'),
                ('https://example.com/old', 'Wed, 04 Nov 2026 08:00:00 GMT'),
                ('https://example.com/future', 'Wed, 25 Nov 2026 08:00:00 GMT'),
                ('https://example.com/undated', ''),
                ('file:///secret', 'Wed, 18 Nov 2026 08:00:00 GMT')]) + '</channel></rss>'
        result = research.feed_items(xml, dt.date(2026,11,18))
        self.assertEqual([a['link'] for a in result], ['https://example.com/current'])

    def test_weekly_window_deduplicates_and_excludes_used_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            rows = [{'link':f'https://example.com/{d}', 'published':f'2026-11-{d}', 'words':200}
                    for d in (15,16,18,23)]
            for day in (18,19):
                (path/f'{day}.json').write_text(json.dumps({'articles':rows}))
            result = research.recent_candidates(dt.date(2026,11,23),
                [{'source_url':'https://example.com/18/'}], path)
            self.assertEqual([a['published'] for a in result], ['2026-11-16'])

    def test_selector_requires_verbatim_event_evidence(self):
        row = {'title':'Brand event', 'link':'https://example.com/event', 'body':'The company launched a new brand on November 18, 2026.', 'words':200}
        selection = {'index':0, 'event_date':'2026-11-18', 'event_evidence':'Invented supporting evidence that is not in the article.', 'angle':'Interpretation', 'tool':'Decision test'}
        with patch.object(research, 'recent_candidates', return_value=[row]), \
             patch.object(research.llm, 'generate', return_value=json.dumps({'selected':[selection]})):
            self.assertEqual(research.select(dt.date(2026,11,23), [], config.load_brand()), [])
        selection['event_evidence'] = row['body']
        with patch.object(research, 'recent_candidates', return_value=[row]), \
             patch.object(research.llm, 'generate', return_value=json.dumps({'selected':[selection,selection]})):
            self.assertEqual(len(research.select(dt.date(2026,11,23), [], config.load_brand())), 1)

    def test_quiet_week_and_provider_failure_keep_blog_fallback(self):
        with patch.object(research, 'recent_candidates', return_value=[]), patch.object(research.llm, 'generate') as model:
            self.assertEqual(research.select(dt.date(2026,11,23), [], config.load_brand()), [])
            model.assert_not_called()
        with patch.object(research, 'recent_candidates', return_value=[{'title':'event'}]), \
             patch.object(research.llm, 'generate', side_effect=RuntimeError('quota')):
            self.assertEqual(research.select(dt.date(2026,11,23), [], config.load_brand()), [])
