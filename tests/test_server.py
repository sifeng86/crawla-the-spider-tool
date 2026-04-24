import importlib
import os
import sys
import types
import unittest
from pathlib import Path
from subprocess import CalledProcessError
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
LOGIN_DIR = ROOT / 'login'
for path in (ROOT, LOGIN_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def load_server_module(env_vars):
    sys.modules.pop('server', None)
    fake_db = types.SimpleNamespace(
        contents=MagicMock(),
        urls=MagicMock(),
        preview_contents=MagicMock(),
    )
    with patch('lib.mongo.mongoHelper.mongo_conn', return_value=fake_db):
        module = importlib.import_module('server')
        module = importlib.reload(module)
    return module, fake_db


class ServerModuleTests(unittest.TestCase):
    def test_local_login_sets_profile_and_redirects(self):
        with patch.dict(os.environ, {'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'}, clear=False):
            module, _ = load_server_module({'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'})
            client = module.app.test_client()

            response = client.get('/login')

            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.location.endswith('/contents'))
            with client.session_transaction() as session:
                self.assertEqual(session[module.constants.PROFILE_KEY]['user_id'], 'local_admin')

    def test_local_logout_returns_home_without_auth0(self):
        with patch.dict(os.environ, {'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'}, clear=False):
            module, _ = load_server_module({'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'})
            client = module.app.test_client()

            with client.session_transaction() as session:
                session[module.constants.PROFILE_KEY] = module.get_local_profile()

            response = client.get('/logout')

            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.location.endswith('/'))

    def test_production_login_requires_auth0_configuration(self):
        env_vars = {
            'APP_ENV': 'production',
            'SECRET_KEY': 'test-secret',
            'AUTH0_CLIENT_ID': '',
            'AUTH0_CLIENT_SECRET': '',
            'AUTH0_DOMAIN': '',
            'AUTH0_CALLBACK_URL': '',
            'AUTH0_LOGOUT_REDIRECT_URL': '',
            'AUTH0_AUDIENCE': '',
        }
        with patch.dict(os.environ, env_vars, clear=False):
            module, _ = load_server_module(env_vars)
            client = module.app.test_client()

            response = client.get('/login')

            self.assertEqual(response.status_code, 503)
            self.assertIn('Auth0 is not configured', response.get_data(as_text=True))

    def test_temphtml_reports_subprocess_failure(self):
        with patch.dict(os.environ, {'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'}, clear=False):
            module, _ = load_server_module({'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'})
            client = module.app.test_client()

            with patch.object(module.subprocess, 'run', side_effect=CalledProcessError(1, ['python'])):
                response = client.post('/temphtml', json={'preview_id': 'pid', 'url': 'https://example.com'})

            self.assertEqual(response.status_code, 500)
            self.assertIn('Failed to cache preview content', response.get_data(as_text=True))

    def test_delete_task_cleans_related_data(self):
        with patch.dict(os.environ, {'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'}, clear=False):
            module, fake_db = load_server_module({'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'})
            client = module.app.test_client()

            fake_db.urls.delete_one.return_value = types.SimpleNamespace(deleted_count=1)

            with client.session_transaction() as session:
                session[module.constants.PROFILE_KEY] = module.get_local_profile()

            with patch.object(module.os, 'remove') as remove_file:
                response = client.get('/del_contents/task-123')

            self.assertEqual(response.status_code, 302)
            fake_db.urls.delete_one.assert_called_once_with({'task_id': 'task-123', 'user_id': 'local_admin'})
            fake_db.contents.delete_many.assert_called_once_with({'task_id': 'task-123'})
            fake_db.preview_contents.delete_many.assert_called_once_with({'preview_id': 'task-123'})
            remove_file.assert_called_once_with('/work/login/downloads/task-123.csv')


if __name__ == '__main__':
    unittest.main()