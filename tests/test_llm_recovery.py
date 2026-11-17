import sys
import types
import unittest
from unittest.mock import Mock, patch

from agent import llm, video


class RecoveryTests(unittest.TestCase):
    def test_visible_infographic_gets_reading_time(self):
        beats = [{'timecode':'0:00-0:03', 'onscreen':'Use this checklist',
                  'visual': {'items':[{'label':'Read', 'detail':'word ' * 25}]}}]
        self.assertGreater(video.beat_durations(beats, readable=True)[0], 10)
        self.assertEqual(video.beat_durations(beats), [3.0])

    def test_dense_reel_is_not_sped_up_to_hide_excess_copy(self):
        beats = [{'onscreen':'word ' * 30}] * 10
        with self.assertRaisesRegex(video.VideoError, 'shorten or split'):
            video.beat_durations(beats, readable=True)

    def test_truncated_text_is_not_accepted_as_complete_json(self):
        response = types.SimpleNamespace(text='{"partial":', candidates=[
            types.SimpleNamespace(finish_reason='MAX_TOKENS')])
        with self.assertRaisesRegex(llm.LLMError, 'truncated'):
            llm._gemini_text(response)

    def test_fourth_available_model_is_actually_attempted(self):
        client = Mock()
        def respond(**kwargs):
            if kwargs['model'] != 'fourth':
                error = RuntimeError('429 exhausted')
                error.code = 429
                raise error
            return types.SimpleNamespace(text='{"ok":true}', candidates=[])
        client.models.generate_content.side_effect = respond
        fake_types = types.SimpleNamespace(**{
            name: (lambda **kwargs: kwargs)
            for name in ('Content', 'Part', 'ThinkingConfig', 'GenerateContentConfig')})
        genai = types.ModuleType('google.genai')
        genai.Client = Mock(return_value=client)
        genai.types = fake_types
        google = types.ModuleType('google')
        google.genai = genai
        with patch.dict(sys.modules, {'google': google, 'google.genai': genai,
                                      'google.genai.types': fake_types}), \
             patch.object(llm, '_gemini_candidates', return_value=['first','second','third','fourth']), \
             patch.object(llm, '_pace'), patch.object(llm.time, 'sleep'):
            result = llm._gemini_generate('system', [{'role':'user','content':'draft'}], 100)
        self.assertEqual(result, '{"ok":true}')
        self.assertEqual(client.models.generate_content.call_args.kwargs['model'], 'fourth')
