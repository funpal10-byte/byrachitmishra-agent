import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent import blog_pool, config, editorial, generate, metrics, run_batch
from agent.schema import POST_SCHEMA, VISUAL_SCHEMA, validate
from tests.test_schema import reel_post


def article(i):
    return {"title": f"Customer decision {i}", "link": f"https://example.com/article-{i}/",
            "body": "A full source article. " * 100, "words": 400,
            "published": f"2026-11-{i + 1:02d}T00:00:00+00:00"}


def useful_post():
    post = reel_post()
    post["content_version"] = 3
    post["useful_takeaway"] = {"kind": "checklist", "visible_steps": ["Name the decision", "Name the approver"]}
    return post


class ContentPipelineTests(unittest.TestCase):
    def test_renamed_title_does_not_hide_duplicate_hook(self):
        old = {"hook": "Why pay more for identical steel?", "title": "old"}
        new = {"hook": "WHY pay more for identical steel!", "title": "new"}
        self.assertTrue(editorial.duplicate_problems(new, [old]))

    def test_different_hook_does_not_hide_same_claim(self):
        old = {"claim": "Brand value comes from delivery reliability and lower buyer risk."}
        self.assertTrue(editorial.duplicate_problems({"claim": old["claim"], "hook": "New words"}, [old]))

    def test_unrelated_claim_is_not_blocked(self):
        self.assertEqual(editorial.duplicate_problems(
            {"claim": "Assign a customer update owner separately from the repair owner."},
            [{"claim": "Price premiums require documented delivery reliability."}]), [])

    def test_history_uses_dates_and_includes_future_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            for name, when in [('z', '2026-01-01'), ('a', '2026-11-15'), ('b', '2026-12-01')]:
                target = base / name / 'post.json'
                target.parent.mkdir()
                target.write_text(json.dumps({'hook': name, 'scheduled_for': when}), encoding='utf-8')
            with patch.multiple(config, PUBLISHED_DIR=base, APPROVED_DIR=base, QUEUE_DIR=base):
                rows = editorial.history(dt.datetime(2026, 11, 16, tzinfo=dt.timezone.utc))
            self.assertEqual([p['hook'] for p in rows], ['b', 'a'])

    def test_payoff_must_be_visible_not_only_narration(self):
        post = useful_post()
        self.assertEqual(editorial.payoff_problems(post), [])
        post['useful_takeaway']['visible_steps'][0] = 'Record the agreed next customer update time'
        post['reel_script'][0]['voiceover'] += ' Record the agreed next customer update time'
        self.assertTrue(editorial.payoff_problems(post))

    def test_v3_requires_payoff_but_legacy_posts_remain_valid(self):
        post = reel_post()
        self.assertEqual(validate(post), [])
        post['content_version'] = 3
        self.assertTrue(any('useful_takeaway' in p for p in validate(post)))
        self.assertIn('useful_takeaway', POST_SCHEMA['properties'])
        self.assertNotIn('useful_takeaway', VISUAL_SCHEMA['properties'])

    def test_plan_has_ten_distinct_articles_and_keeps_formats(self):
        brand = config.load_brand()
        slots = copy.deepcopy(brand.slots)
        plan = blog_pool.plan_articles([article(i) for i in range(15)], slots, brand.pillars, [])
        self.assertEqual(len({p['link'] for p in plan}), 10)
        self.assertEqual(slots, brand.slots)
        self.assertEqual(sum(s['format'] == 'reel' for s in slots), 5)

    def test_unused_source_beats_recently_used_source(self):
        brand = config.load_brand()
        old, fresh = article(0), article(1)
        chosen = blog_pool.plan_articles([old, fresh], brand.slots[:1], brand.pillars,
                                        [{'source_url': fresh['link'].rstrip('/')}])
        self.assertEqual(chosen[0]['link'], old['link'])

    def test_source_shortage_is_explicit_not_evergreen(self):
        brand = config.load_brand()
        with self.assertRaisesRegex(ValueError, 'distinct full blog sources'):
            blog_pool.plan_articles([article(0)], brand.slots, brand.pillars, [])

    def test_fresh_article_beats_familiar_pillar_keywords(self):
        brand = config.load_brand()
        old, fresh = article(0), article(1)
        old['title'] = ' '.join(brand.pillars[brand.slots[0]['pillar']].keywords)
        chosen = blog_pool.plan_articles([old, fresh], brand.slots[:1], brand.pillars, [])
        self.assertEqual(chosen[0]['link'], fresh['link'])

    def test_retry_keeps_original_source_plan_without_network(self):
        brand = config.load_brand()
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(blog_pool, 'available_articles', return_value=[article(i) for i in range(10)]):
                first = blog_pool.week_plan(Path(folder), brand.slots, brand.pillars, [])
            with patch.object(blog_pool, 'available_articles', side_effect=AssertionError('network on retry')):
                second = blog_pool.week_plan(Path(folder), brand.slots, brand.pillars, [])
            self.assertEqual(first, second)

    def test_semantic_review_rejection_causes_correction(self):
        brand = config.load_brand()
        post = useful_post()
        responses = [json.dumps(post), '{"approved":false,"issues":["Show a concrete pass condition"]}',
                     json.dumps(post), '{"approved":true,"issues":[]}']
        with patch.object(generate.llm, 'generate', side_effect=responses) as call, \
             patch.object(generate, 'brief_context', return_value=''):
            result = generate.generate_post(brand, 'system', brand.pillars['ai_marketing'],
                                            'reel', 'Monday', 'source', [], editorial_history=[])
        self.assertTrue(result['editorial_review']['approved'])
        self.assertEqual(call.call_count, 4)
        self.assertIn('Show a concrete pass condition', call.call_args_list[2].kwargs['messages'][-1]['content'])

    def test_malformed_reviewer_cannot_approve(self):
        for raw in ('{}', '{"approved":"true","issues":[]}', '{"approved":false,"issues":[]}'):
            with self.assertRaises(ValueError):
                editorial.review_result(raw)

    def test_repeated_hook_is_rejected_before_critic(self):
        brand = config.load_brand()
        post = useful_post()
        with patch.object(generate.llm, 'generate', return_value=json.dumps(post)) as call:
            with self.assertRaisesRegex(ValueError, 'Repeated hook'):
                generate.generate_post(brand, 'system', brand.pillars['ai_marketing'], 'reel',
                                       'Monday', 'source', [], editorial_history=[editorial.snapshot(post)])
        self.assertEqual(call.call_count, 3)

    def test_low_engagement_is_not_a_hook_reuse_instruction(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'metrics.json'
            path.write_text(json.dumps({'posts': [{'hook': 'Copy me', 'reach': 10, 'saved': 1}] * 20}))
            with patch.object(metrics, 'JSON_PATH', path):
                prompt = metrics.brief_context()
            self.assertNotIn('Copy me', prompt)
            self.assertIn('do not establish', prompt)

    def test_complete_batch_and_retry_preserve_ten_posts(self):
        brand = config.load_brand()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            queue = root / 'queue'
            queue.mkdir()
            calls = []
            def draft(*args, **kwargs):
                p = useful_post()
                p.update(title=f'post {len(calls)}', format=args[3], pillar=args[2].id)
                calls.append(len(kwargs['editorial_history']))
                p['source_url'] = kwargs['source_article']['link']
                return p
            def pictures(post, brand, target, **kwargs):
                path = target / 'image.jpg'
                path.write_bytes(b'fixture')
                return [path]
            def reel(post, brand, target, **kwargs):
                (target / 'reel.mp4').write_bytes(b'fixture')
                return True
            with patch.multiple(config, ROOT=root, QUEUE_DIR=queue, APPROVED_DIR=root/'approved', PUBLISHED_DIR=root/'published'), \
                 patch.object(config, 'api_key', return_value='test-only'), \
                 patch.object(blog_pool, 'available_articles', return_value=[article(i) for i in range(10)]), \
                 patch.object(generate, 'generate_post', side_effect=draft), \
                 patch.object(run_batch.render, 'render_carousel', side_effect=pictures), \
                 patch.object(run_batch.render, 'render_reel_cover', side_effect=lambda p,b,t: pictures(p,b,t)[0]), \
                 patch.object(run_batch.video, 'build_reel', side_effect=reel), \
                 patch.object(run_batch.sources, 'preflight', return_value={}), \
                 patch.object(run_batch, 'validate', return_value=[]), \
                 patch.object(run_batch, 'check_voice', return_value=[]), \
                 patch.dict('os.environ', {'BATCH_WEEK_START': '2026-11-23'}):
                self.assertEqual(run_batch.main(), 0)
                self.assertEqual(run_batch.main(), 0)
            self.assertEqual(calls, list(range(10)))
            posts = [json.loads(p.read_text()) for p in queue.rglob('post.json')]
            self.assertEqual(len(posts), 10)
            self.assertEqual(len({p['source_url'] for p in posts}), 10)
            self.assertTrue(all(p['source'] == 'blog' and p['content_version'] == 3 for p in posts))
