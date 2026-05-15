import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from login.lib import runtime_config


class RuntimeConfigTests(unittest.TestCase):
    def test_get_setting_reads_local_dotenv_when_env_is_blank(self):
        with tempfile.NamedTemporaryFile('w+', delete=False) as handle:
            handle.write('CRAWLA_MAIL_HOST=smtp.dotenv.example\n')
            dotenv_path = handle.name

        self.addCleanup(lambda: Path(dotenv_path).unlink(missing_ok=True))

        with patch.dict(os.environ, {'CRAWLA_MAIL_HOST': ''}, clear=True):
            with patch('login.lib.runtime_config.DOTENV_PATH', Path(dotenv_path)):
                self.assertEqual(
                    runtime_config.get_setting('CRAWLA_MAIL_HOST', config_path='mail_host'),
                    'smtp.dotenv.example',
                )

    def test_get_setting_without_config_path_does_not_return_entire_legacy_document(self):
        with patch.dict(os.environ, {}, clear=False):
            with patch('login.lib.runtime_config.load_legacy_config', return_value={'mail_host': 'smtp.config.example'}):
                self.assertIsNone(runtime_config.get_setting('CRAWLA_MONGO_URI'))

    def test_get_setting_prefers_env_over_legacy_config(self):
        with patch.dict(os.environ, {'CRAWLA_MAIL_HOST': 'smtp.env.example'}, clear=False):
            with patch('login.lib.runtime_config.load_legacy_config', return_value={'mail_host': 'smtp.config.example'}):
                self.assertEqual(
                    runtime_config.get_setting('CRAWLA_MAIL_HOST', config_path='mail_host'),
                    'smtp.env.example',
                )

    def test_get_secret_setting_reads_file_variant(self):
        with tempfile.NamedTemporaryFile('w+', delete=False) as handle:
            handle.write('file-secret\n')
            file_path = handle.name

        self.addCleanup(lambda: Path(file_path).unlink(missing_ok=True))

        with patch.dict(os.environ, {'CRAWLA_MAIL_PASSWORD_FILE': file_path}, clear=False):
            self.assertEqual(runtime_config.get_secret_setting('CRAWLA_MAIL_PASSWORD'), 'file-secret')

    def test_get_secret_setting_reads_local_dotenv_when_env_is_blank(self):
        with tempfile.NamedTemporaryFile('w+', delete=False) as handle:
            handle.write('GOOGLE_API_KEY=dotenv-secret\n')
            dotenv_path = handle.name

        self.addCleanup(lambda: Path(dotenv_path).unlink(missing_ok=True))

        with patch.dict(os.environ, {'GOOGLE_API_KEY': ''}, clear=True):
            with patch('login.lib.runtime_config.DOTENV_PATH', Path(dotenv_path)):
                self.assertEqual(runtime_config.get_secret_setting('GOOGLE_API_KEY'), 'dotenv-secret')

    def test_get_secret_setting_without_config_path_does_not_return_entire_legacy_document(self):
        with patch.dict(os.environ, {}, clear=False):
            with patch('login.lib.runtime_config.load_legacy_config', return_value={'redis_pw': 'ciphertext'}):
                self.assertIsNone(runtime_config.get_secret_setting('CRAWLA_MONGO_URI'))

    def test_get_secret_setting_decrypts_legacy_config_when_needed(self):
        with patch.dict(os.environ, {}, clear=False):
            with patch('login.lib.runtime_config.load_legacy_config', return_value={'redis_pw': 'ciphertext'}):
                with patch.object(runtime_config.crypto, 'decrypt_message', return_value='legacy-secret') as decrypt_message:
                    self.assertEqual(
                        runtime_config.get_secret_setting(
                            'CRAWLA_REDIS_PASSWORD',
                            config_path='redis_pw',
                            decrypt_legacy=True,
                        ),
                        'legacy-secret',
                    )
                    decrypt_message.assert_called_once_with(b'ciphertext')

    def test_get_int_setting_supports_nested_config_paths(self):
        with patch.dict(os.environ, {}, clear=False):
            with patch(
                'login.lib.runtime_config.load_legacy_config',
                return_value={'llm': {'gemini': {'max_output_tokens': 256}}},
            ):
                self.assertEqual(
                    runtime_config.get_int_setting(
                        'CRAWLA_GEMINI_MAX_OUTPUT_TOKENS',
                        config_path=('llm', 'gemini', 'max_output_tokens'),
                        default=512,
                    ),
                    256,
                )


if __name__ == '__main__':
    unittest.main()