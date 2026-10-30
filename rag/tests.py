from unittest import mock

from django.test import SimpleTestCase
from google.genai import errors as genai_errors

from . import vector_store


def quota_error():
    return genai_errors.ClientError(429, {'error': {'message': 'quota exceeded'}})


class GeminiKeySwitchTests(SimpleTestCase):
    def test_switches_to_next_key_when_limit_exceeded(self):
        first, second = mock.Mock(), mock.Mock()
        first.models.embed_content.side_effect = quota_error()
        second.models.embed_content.return_value = 'ok'
        with mock.patch.object(vector_store, 'gemini_clients', [first, second]), \
                mock.patch.object(vector_store, '_active_key', 0):
            self.assertEqual(vector_store.gemini_call('embed_content', retries=0, contents=['x']), 'ok')
            # The working key stays active, so the next call skips the exhausted one.
            self.assertEqual(vector_store._active_key, 1)

    def test_raises_when_every_key_is_over_its_limit(self):
        only = mock.Mock()
        only.models.embed_content.side_effect = quota_error()
        with mock.patch.object(vector_store, 'gemini_clients', [only]), \
                mock.patch.object(vector_store, '_active_key', 0):
            with self.assertRaises(genai_errors.ClientError):
                vector_store.gemini_call('embed_content', retries=0, contents=['x'])
