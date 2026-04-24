import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_module():
    sys.modules.pop('celery_task1', None)
    fake_app = MagicMock()
    fake_app.task.side_effect = lambda *args, **kwargs: (lambda func: func)
    with patch('login.lib.celery.celeryHelper.redis_conn', return_value=fake_app):
        module = importlib.import_module('celery_task1')
        return importlib.reload(module)


class CeleryTaskTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_preview_timeout_defaults_to_50_seconds(self):
        args = 'pid_&_["select_one"]_&_["h3"]_&_py_requests_&_https://example.com'

        self.assertEqual(self.module.get_preview_timeout(args), 50)

    def test_preview_timeout_extends_for_llm(self):
        args = 'pid_&_["ask_llm"]_&_["What is the title?"]_&_py_llm_&_https://example.com'

        self.assertEqual(self.module.get_preview_timeout(args), 570)

    def test_preview_async_options_stay_small_for_non_llm(self):
        args = 'pid_&_["select_one"]_&_["h3"]_&_py_requests_&_https://example.com'

        self.assertEqual(
            self.module.get_preview_async_options(args),
            {'expires': 120},
        )

    def test_preview_async_options_extend_for_llm(self):
        args = 'pid_&_["ask_llm"]_&_["What is the title?"]_&_py_llm_&_https://example.com'

        self.assertEqual(
            self.module.get_preview_async_options(args),
            {
                'expires': 600,
                'soft_time_limit': 540,
                'time_limit': 600,
            },
        )

    def test_task_async_options_extend_for_llm(self):
        with patch.object(self.module, 'get_task_method', return_value='py_llm'):
            self.assertEqual(
                self.module.get_task_async_options('task-123'),
                {
                    'soft_time_limit': 540,
                    'time_limit': 600,
                },
            )


if __name__ == '__main__':
    unittest.main()