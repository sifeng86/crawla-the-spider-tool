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
                    runtime_config.get_setting('CRAWLA_MAIL_HOST'),
                    'smtp.dotenv.example',
                )

    def test_get_setting_returns_default_when_env_is_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                runtime_config.get_setting('CRAWLA_MAIL_HOST', default='smtp.default.example'),
                'smtp.default.example',
            )

    def test_get_setting_prefers_env_over_default(self):
        with patch.dict(os.environ, {'CRAWLA_MAIL_HOST': 'smtp.env.example'}, clear=True):
            self.assertEqual(
                runtime_config.get_setting('CRAWLA_MAIL_HOST', default='smtp.default.example'),
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

    def test_get_secret_setting_returns_default_when_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                runtime_config.get_secret_setting('CRAWLA_MONGO_URI', default='mongodb://fallback'),
                'mongodb://fallback',
            )

    def test_get_int_setting_reads_env_value(self):
        with patch.dict(os.environ, {'CRAWLA_GEMINI_MAX_OUTPUT_TOKENS': '256'}, clear=True):
            self.assertEqual(
                runtime_config.get_int_setting('CRAWLA_GEMINI_MAX_OUTPUT_TOKENS', default=512),
                256,
            )

    def test_get_int_setting_falls_back_to_default_for_invalid_env(self):
        with patch.dict(os.environ, {'CRAWLA_GEMINI_MAX_OUTPUT_TOKENS': 'not-a-number'}, clear=True):
            self.assertEqual(
                runtime_config.get_int_setting('CRAWLA_GEMINI_MAX_OUTPUT_TOKENS', default=512),
                512,
            )


if __name__ == '__main__':
    unittest.main()