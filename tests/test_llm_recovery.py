import sys
import types
import unittest
from unittest.mock import Mock, patch

from agent import llm


class RecoveryTests(unittest.TestCase):
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
