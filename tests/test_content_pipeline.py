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

    def test_same_send_prompt_is_not_recycled_across_different_topics(self):
        caption = 'Send this to whoever is defending the brand budget this quarter.'
        old = editorial.snapshot({'caption': caption, 'hook':'One topic'})
        issues = editorial.duplicate_problems({'caption':caption, 'hook':'Another topic'}, [old])
        self.assertTrue(any('Repeated cta' in issue for issue in issues))

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

    def test_invalid_generation_json_is_corrected_in_same_slot(self):
        brand = config.load_brand()
        with patch.object(generate.llm, 'generate', side_effect=[
                '{invalid', json.dumps(useful_post()), '{"approved":true,"issues":[]}']) as call:
            result = generate.generate_post(brand, 'system', brand.pillars['ai_marketing'],
                'reel', 'Monday', 'source', [], editorial_history=[])
        self.assertTrue(result['editorial_review']['approved'])
        self.assertEqual(call.call_count, 3)

    def test_source_attribution_preserves_caption_and_normalises_tag_prefix(self):
        post = {'caption':'Hook\n\nKeep the full first paragraph.', 'hashtags':['branding','#strategy']}
        source = {'link':'https://example.com/article/'}
        generate._normalise_attribution(post, source)
        self.assertTrue(post['caption'].startswith('Hook\n\nKeep the full first paragraph.'))
        self.assertEqual(post['hashtags'], ['#branding','#strategy'])
        generate._normalise_attribution(post, source)
        self.assertEqual(post['caption'].count(source['link']), 1)

    def test_takeaway_repair_selects_existing_text_without_changing_panels(self):
        post = useful_post()
        original = copy.deepcopy(post['reel_script'])
        post['useful_takeaway']['visible_steps'] = ['A paraphrase not actually shown', 'Another invented transcription']
        with patch.object(generate.llm, 'generate', return_value='{"indices":[1,2]}'):
            generate._repair_takeaway_quotes(post)
        self.assertEqual(post['reel_script'], original)
        self.assertEqual(editorial.payoff_problems(post), [])

    def test_takeaway_repair_cannot_invent_or_accept_out_of_range_quotes(self):
        post = useful_post()
        steps = ['A paraphrase not actually shown', 'Another invented transcription']
        post['useful_takeaway']['visible_steps'] = steps[:]
        with patch.object(generate.llm, 'generate', return_value='{"indices":[1,999]}'):
            generate._repair_takeaway_quotes(post)
        self.assertEqual(post['useful_takeaway']['visible_steps'], steps)
        self.assertTrue(editorial.payoff_problems(post))

    def test_visual_repair_rewrites_only_overlong_fields(self):
        post = {'slides':[{'body':'Preserve complete prose.', 'visual': {'items':[
            {'label':'A very long infographic label that will not fit', 'detail':'Keep this specific action'}]}}]}
        with patch.object(generate.llm, 'generate', return_value='{"replacements":{"0":"Short action label"}}'):
            generate._repair_visual_lengths(post)
        self.assertEqual(post['slides'][0]['visual']['items'][0],
                         {'label':'Short action label', 'detail':'Keep this specific action'})
        self.assertEqual(post['slides'][0]['body'], 'Preserve complete prose.')

    def test_visual_repair_never_truncates_an_invalid_replacement(self):
        label = 'This infographic label is much too long'
        post = {'slides':[{'visual':{'items':[{'label':label, 'detail':'Keep'}]}}]}
        with patch.object(generate.llm, 'generate', return_value=json.dumps({'replacements':{'0':label}})):
            generate._repair_visual_lengths(post)
        self.assertEqual(post['slides'][0]['visual']['items'][0]['label'], label)

    def test_recent_developments_keep_eight_blogs_and_persist_plan(self):
        brand = config.load_brand()
        news = [dict(article(20+i), source='recent_development') for i in range(2)]
        with tempfile.TemporaryDirectory() as folder:
            batch = Path(folder)/'2026-11-30'
            batch.mkdir()
            with patch.object(blog_pool, 'available_articles', return_value=[article(i) for i in range(10)]), \
                 patch('agent.daily_research.select', return_value=news):
                plan = blog_pool.week_plan(batch, brand.slots, brand.pillars, [])
            self.assertEqual(sum(a.get('source') == 'recent_development' for a in plan.values()), 2)
            self.assertEqual(len(plan), 10)
            with patch('agent.daily_research.select', side_effect=AssertionError('reselected on retry')):
                self.assertEqual(blog_pool.week_plan(batch, brand.slots, brand.pillars, []), plan)

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

    def test_partial_batch_recovers_only_failed_slot_then_skips_complete_week(self):
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
                if len(calls) == 3:
                    raise RuntimeError('simulated transient provider failure')
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
                self.assertEqual(run_batch.main(), 1)
                self.assertEqual(run_batch.main(), 0)
                self.assertEqual(run_batch.main(), 0)
            self.assertEqual(calls, [0,1,2,2,3,4,5,6,7,8,9])
            posts = [json.loads(p.read_text()) for p in queue.rglob('post.json')]
            self.assertEqual(len(posts), 10)
            self.assertEqual(len({p['source_url'] for p in posts}), 10)
            self.assertTrue(all(p['source'] == 'blog' and p['content_version'] == 3 for p in posts))
