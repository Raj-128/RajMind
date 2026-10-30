from unittest import mock

from django.test import SimpleTestCase, override_settings

from . import ai_engine


class AnswerProviderOrderTests(SimpleTestCase):
    @override_settings(GROQ_API_KEYS=['g1'])
    @mock.patch.object(ai_engine, 'gemini_call')
    @mock.patch('groq.Groq')
    def test_groq_answers_first_when_configured(self, groq, gemini_call):
        groq.return_value.chat.completions.create.return_value.choices = [mock.Mock(message=mock.Mock(content='fast'))]
        self.assertEqual(ai_engine._complete('q'), 'fast')
        gemini_call.assert_not_called()

    @override_settings(GROQ_API_KEYS=['g1', 'g2'])
    @mock.patch.object(ai_engine, 'gemini_call')
    @mock.patch('groq.Groq')
    def test_gemini_takes_over_when_every_groq_key_fails(self, groq, gemini_call):
        groq.return_value.chat.completions.create.side_effect = RuntimeError('rate limited')
        gemini_call.return_value.text = 'from gemini'
        self.assertEqual(ai_engine._complete('q'), 'from gemini')
        self.assertEqual(groq.return_value.chat.completions.create.call_count, 2)
