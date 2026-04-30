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
        selector_memory=MagicMock(),
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

    def test_contents_renders_when_legacy_task_is_missing_task_id(self):
        with patch.dict(os.environ, {'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'}, clear=False):
            module, fake_db = load_server_module({'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'})
            client = module.app.test_client()
            fake_db.urls.find.return_value.sort.return_value = [
                {
                    'task_name': 'Legacy task',
                    'url': 'https://example.com',
                    'schedule_enabled': True,
                }
            ]

            response = client.get('/contents')

            self.assertEqual(response.status_code, 200)
            body = response.get_data(as_text=True)
            self.assertIn('Legacy task', body)
            self.assertIn('Missing task id', body)
            self.assertIn('Legacy record requires migration before actions are available.', body)

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

            with client.session_transaction() as session:
                session[module.constants.PROFILE_KEY] = module.get_local_profile()
                session['form_token'] = 'pid'

            with patch.object(module.subprocess, 'run', side_effect=CalledProcessError(1, ['python'])):
                response = client.post('/temphtml', json={'preview_id': 'pid', 'url': 'https://example.com'})

            self.assertEqual(response.status_code, 500)
            self.assertIn('Failed to cache preview content', response.get_data(as_text=True))

    def test_preview_rejects_mismatched_steps_and_args(self):
        with patch.dict(os.environ, {'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'}, clear=False):
            module, _ = load_server_module({'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'})
            client = module.app.test_client()

            with client.session_transaction() as session:
                session[module.constants.PROFILE_KEY] = module.get_local_profile()
                session['form_token'] = 'pid'

            response = client.post(
                '/preview',
                json={
                    'preview_id': 'pid',
                    'steps': ['select_one'],
                    'args': ['.title', '-'],
                    'c_method': 'py_requests',
                    'url': 'https://example.com',
                },
            )

            self.assertEqual(response.status_code, 400)
            self.assertIn('Steps_and_Arguments_are_not_match.', response.get_data(as_text=True))

    def test_temphtml_rejects_invalid_preview_token(self):
        with patch.dict(os.environ, {'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'}, clear=False):
            module, _ = load_server_module({'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'})
            client = module.app.test_client()

            with client.session_transaction() as session:
                session[module.constants.PROFILE_KEY] = module.get_local_profile()
                session['form_token'] = 'pid'

            response = client.post('/temphtml', json={'preview_id': 'someone-else', 'url': 'https://example.com'})

            self.assertEqual(response.status_code, 400)
            self.assertIn('Invalid preview token', response.get_data(as_text=True))

    def test_security_headers_applied_in_local_mode(self):
        with patch.dict(os.environ, {'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'}, clear=False):
            module, _ = load_server_module({'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'})
            client = module.app.test_client()

            response = client.get('/')

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers.get('X-Frame-Options'), 'SAMEORIGIN')
            self.assertEqual(response.headers.get('X-Content-Type-Options'), 'nosniff')
            self.assertEqual(response.headers.get('Referrer-Policy'), 'strict-origin-when-cross-origin')
            self.assertIn('default-src', response.headers.get('Content-Security-Policy', ''))
            self.assertIsNone(response.headers.get('Strict-Transport-Security'))

    def test_security_headers_include_hsts_in_production(self):
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

            response = client.get('/')

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers.get('Strict-Transport-Security'), 'max-age=31536000; includeSubDomains')

    def test_preview_rate_limit_returns_429(self):
        with patch.dict(os.environ, {'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'}, clear=False):
            module, _ = load_server_module({'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'})
            client = module.app.test_client()
            module.request_rate_limiter.reset()
            module.app.config['RATE_LIMITS'] = {
                'preview': {'limit': 1, 'window_seconds': 60},
            }

            with client.session_transaction() as session:
                session[module.constants.PROFILE_KEY] = module.get_local_profile()
                session['form_token'] = 'pid'

            payload = {
                'preview_id': 'pid',
                'steps': ['select_one'],
                'args': ['h1'],
                'c_method': 'py_requests',
                'url': 'https://example.com',
            }

            with patch.object(module, 'enqueue_preview', return_value='queued'):
                first_response = client.post('/preview', json=payload)
                second_response = client.post('/preview', json=payload)

            self.assertEqual(first_response.status_code, 200)
            self.assertEqual(second_response.status_code, 429)
            self.assertEqual(second_response.get_json()['message'], 'Too many requests. Please retry later.')
            self.assertGreaterEqual(int(second_response.headers.get('Retry-After', '0')), 1)

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
            fake_db.preview_contents.delete_many.assert_called_once_with({'preview_id': 'task-123', 'user_id': 'local_admin'})
            remove_file.assert_called_once_with(str(module.get_downloads_dir() / 'task-123.csv'))

    def test_studio_route_renders_workspace_shell(self):
        env_vars = {
            'APP_ENV': 'local',
            'SECRET_KEY': 'test-secret',
            'CRAWLA_STUDIO_ENABLED': 'true',
        }
        with patch.dict(os.environ, env_vars, clear=False):
            module, _ = load_server_module(env_vars)
            client = module.app.test_client()

            response = client.get('/studio')

            self.assertEqual(response.status_code, 200)
            body = response.get_data(as_text=True)
            self.assertIn('Crawla AI Studio', body)
            self.assertIn('Studio workspace is live', body)
            self.assertIn('Flow blueprint', body)

    def test_studio_route_respects_feature_flag(self):
        env_vars = {
            'APP_ENV': 'local',
            'SECRET_KEY': 'test-secret',
            'CRAWLA_STUDIO_ENABLED': 'false',
        }
        with patch.dict(os.environ, env_vars, clear=False):
            module, _ = load_server_module(env_vars)
            client = module.app.test_client()

            response = client.get('/studio')

            self.assertEqual(response.status_code, 404)
            self.assertIn('Studio is disabled', response.get_data(as_text=True))

    def test_studio_task_persists_and_queues_normalized_payload(self):
        env_vars = {
            'APP_ENV': 'local',
            'SECRET_KEY': 'test-secret',
            'CRAWLA_STUDIO_ENABLED': 'true',
        }
        with patch.dict(os.environ, env_vars, clear=False):
            module, fake_db = load_server_module(env_vars)
            client = module.app.test_client()

            with patch.object(module, 'enqueue_task', return_value='queued') as enqueue_task:
                response = client.post(
                    '/studio/api/task',
                    json={
                        'draft_id': 'studio-1',
                        'task_name': 'Docs watch',
                        'url': 'https://docs.github.com/en',
                        'noti_email': 'ops@example.com',
                        'c_method': 'py_playwright',
                        'nodes': [
                            {
                                'id': 'node-1',
                                'title': 'Collect cards',
                                'step': 'find_elements_by_css',
                                'args': 'article',
                                'intent': 'Collect visible cards',
                            },
                            {
                                'id': 'node-2',
                                'title': 'Read title',
                                'step': 'ext_str_get_text',
                                'args': '-',
                                'intent': 'Read text',
                            },
                        ],
                    },
                )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload['status'], 'queued')
            self.assertTrue(payload['task_id'].startswith('studio-task-'))
            fake_db.urls.insert_one.assert_called_once()
            inserted = fake_db.urls.insert_one.call_args[0][0]
            self.assertEqual(inserted['task_name'], 'Docs watch')
            self.assertEqual(inserted['c_method'], 'py_playwright')
            self.assertEqual(inserted['schedule_enabled'], True)
            self.assertEqual(inserted['steps'], ['find_elements_by_css', 'ext_str_get_text'])
            self.assertEqual(inserted['args'], ['article', '-'])
            self.assertEqual(inserted['user_id'], 'local_admin')
            enqueue_task.assert_called_once_with(inserted['task_id'])

    def test_run_contents_queues_existing_task(self):
        with patch.dict(os.environ, {'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'}, clear=False):
            module, fake_db = load_server_module({'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'})
            client = module.app.test_client()

            fake_db.urls.find_one.return_value = {'task_id': 'task-123'}

            with client.session_transaction() as session:
                session[module.constants.PROFILE_KEY] = module.get_local_profile()
                session['form_token'] = 'form-token-1'

            with patch.object(module, 'enqueue_task', return_value='queued') as enqueue_task:
                response = client.post('/run_contents/task-123', data={'token': 'form-token-1'})

            self.assertEqual(response.status_code, 302)
            self.assertIn('msg=queued', response.location)
            fake_db.urls.find_one.assert_called_once_with(
                {'task_id': 'task-123', 'user_id': 'local_admin'},
                {'task_id': 1},
            )
            enqueue_task.assert_called_once_with('task-123')

    def test_schedule_contents_toggles_task_batch_eligibility(self):
        with patch.dict(os.environ, {'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'}, clear=False):
            module, fake_db = load_server_module({'APP_ENV': 'local', 'SECRET_KEY': 'test-secret'})
            client = module.app.test_client()

            fake_db.urls.update_one.return_value = types.SimpleNamespace(matched_count=1)

            with client.session_transaction() as session:
                session[module.constants.PROFILE_KEY] = module.get_local_profile()
                session['form_token'] = 'form-token-1'

            response = client.post(
                '/schedule_contents/task-123',
                data={'token': 'form-token-1', 'schedule_enabled': '0'},
            )

            self.assertEqual(response.status_code, 302)
            self.assertIn('msg=schedule_paused', response.location)
            fake_db.urls.update_one.assert_called_once_with(
                {'task_id': 'task-123', 'user_id': 'local_admin'},
                {'$set': {'schedule_enabled': False}},
            )

    def test_studio_task_validates_payload(self):
        env_vars = {
            'APP_ENV': 'local',
            'SECRET_KEY': 'test-secret',
            'CRAWLA_STUDIO_ENABLED': 'true',
        }
        with patch.dict(os.environ, env_vars, clear=False):
            module, fake_db = load_server_module(env_vars)
            client = module.app.test_client()

            response = client.post(
                '/studio/api/task',
                json={
                    'task_name': 'Broken',
                    'url': 'docs.github.com/en',
                    'noti_email': 'ops@example.com',
                    'c_method': 'py_playwright',
                    'nodes': [],
                },
            )

            self.assertEqual(response.status_code, 400)
            self.assertIn('Target URL must start with http:// or https://', response.get_data(as_text=True))
            fake_db.urls.insert_one.assert_not_called()

    def test_studio_task_rejects_missing_selector_argument(self):
        env_vars = {
            'APP_ENV': 'local',
            'SECRET_KEY': 'test-secret',
            'CRAWLA_STUDIO_ENABLED': 'true',
        }
        with patch.dict(os.environ, env_vars, clear=False):
            module, fake_db = load_server_module(env_vars)
            client = module.app.test_client()

            response = client.post(
                '/studio/api/task',
                json={
                    'task_name': 'Broken selector flow',
                    'url': 'https://docs.github.com/en',
                    'noti_email': 'ops@example.com',
                    'c_method': 'py_playwright',
                    'nodes': [
                        {
                            'id': 'node-1',
                            'title': 'Need selector',
                            'step': 'find_element_by_css',
                            'args': '-',
                            'intent': 'This should fail validation',
                        }
                    ],
                },
            )

            self.assertEqual(response.status_code, 400)
            self.assertIn('requires an argument', response.get_data(as_text=True))
            fake_db.urls.insert_one.assert_not_called()

    def test_studio_inspector_returns_sanitized_snapshot(self):
        env_vars = {
            'APP_ENV': 'local',
            'SECRET_KEY': 'test-secret',
            'CRAWLA_STUDIO_ENABLED': 'true',
        }
        with patch.dict(os.environ, env_vars, clear=False):
            module, fake_db = load_server_module(env_vars)
            client = module.app.test_client()

            with client.session_transaction() as session:
                session[module.constants.PROFILE_KEY] = module.get_local_profile()
                session['studio_token'] = 'studio-preview-1'

            cursor = MagicMock()
            cursor.limit.return_value = [
                {
                    'contents': '<html><body><script>alert(1)</script><h1 id="headline" onclick="evil()">Docs</h1></body></html>'
                }
            ]
            fake_db.preview_contents.find.return_value = cursor

            response = client.post(
                '/studio/api/inspector',
                json={
                    'preview_id': 'studio-preview-1',
                    'url': 'https://docs.github.com/en',
                    'c_method': 'py_playwright',
                },
            )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload['source_mode'], 'http_snapshot')
            self.assertIn('crawla-studio-inspector', payload['html'])
            self.assertNotIn('alert(1)', payload['html'])
            self.assertNotIn('onclick=', payload['html'])
            fake_db.preview_contents.find.assert_called_once_with(
                {'preview_id': 'studio-preview-1', 'user_id': 'local_admin'}
            )

    def test_production_requires_secret_key(self):
        env_vars = {
            'APP_ENV': 'production',
            'SECRET_KEY': '',
            'AUTH0_CLIENT_ID': '',
            'AUTH0_CLIENT_SECRET': '',
            'AUTH0_DOMAIN': '',
            'AUTH0_CALLBACK_URL': '',
            'AUTH0_LOGOUT_REDIRECT_URL': '',
            'AUTH0_AUDIENCE': '',
        }
        with patch.dict(os.environ, env_vars, clear=False):
            with self.assertRaises(RuntimeError):
                load_server_module(env_vars)

    def test_studio_selector_memory_returns_summary(self):
        env_vars = {
            'APP_ENV': 'local',
            'SECRET_KEY': 'test-secret',
            'CRAWLA_STUDIO_ENABLED': 'true',
        }
        with patch.dict(os.environ, env_vars, clear=False):
            module, _ = load_server_module(env_vars)
            client = module.app.test_client()

            with patch.object(
                module,
                'get_selector_memory_summary',
                return_value={
                    'domain': 'docs.github.com',
                    'items': [
                        {
                            'step_name': 'select_one',
                            'source_param': '.broken-title',
                            'resolved_param': 'h3',
                            'strategy': 'memory',
                            'success_count': 2,
                            'last_seen_at': '2026-04-30T00:00:00+00:00',
                        }
                    ],
                },
            ) as get_selector_memory_summary:
                response = client.post(
                    '/studio/api/selector-memory',
                    json={
                        'url': 'https://docs.github.com/en',
                        'c_method': 'py_requests',
                    },
                )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload['domain'], 'docs.github.com')
            self.assertEqual(payload['items'][0]['resolved_param'], 'h3')
            get_selector_memory_summary.assert_called_once_with(
                'https://docs.github.com/en',
                'py_requests',
                database=module.db,
            )

    def test_studio_copilot_returns_suggestion(self):
        env_vars = {
            'APP_ENV': 'local',
            'SECRET_KEY': 'test-secret',
            'CRAWLA_STUDIO_ENABLED': 'true',
        }
        with patch.dict(os.environ, env_vars, clear=False):
            module, _ = load_server_module(env_vars)
            client = module.app.test_client()

            with patch.object(
                module,
                'suggest_studio_copilot_plan',
                return_value={
                    'goal': 'Collect article titles and links',
                    'source': 'template',
                    'headline': 'Copilot drafted a docs flow for Requests / BS4',
                    'task_name': 'Article Titles And Links Flow',
                    'rationale': 'Copilot built a selector-first flow for the requested docs goal.',
                    'memory_hits': 2,
                    'nodes': [
                        {
                            'id': 'copilot-root',
                            'title': 'Anchor the main content surface',
                            'step': 'select_one',
                            'args': 'main, article',
                            'intent': 'Lock onto the docs surface.',
                        }
                    ],
                },
            ) as suggest_studio_copilot_plan:
                response = client.post(
                    '/studio/api/copilot',
                    json={
                        'goal': 'Collect article titles and links',
                        'url': 'https://docs.github.com/en',
                        'c_method': 'py_requests',
                        'nodes': [],
                    },
                )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload['task_name'], 'Article Titles And Links Flow')
            self.assertEqual(payload['memory_hits'], 2)
            self.assertEqual(payload['nodes'][0]['step'], 'select_one')
            suggest_studio_copilot_plan.assert_called_once_with(
                'Collect article titles and links',
                'https://docs.github.com/en',
                'py_requests',
                current_nodes=[],
                database=module.db,
            )


if __name__ == '__main__':
    unittest.main()