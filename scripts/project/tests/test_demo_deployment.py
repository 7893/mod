"""Executable deployment boundaries, without production processes or credentials."""
import importlib.util
import os
from pathlib import Path
import signal
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts/project'))
from render_deploy_config import render, absolute_path


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts/project' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DemoDeploymentTests(unittest.TestCase):
    def test_render_relocated_clone_and_background_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = str(Path(directory) / 'relocated')
            result = render(root, 'demo_user', root + '/private.env', sys.executable)
            main = result['mod.service']
            self.assertIn('WorkingDirectory=' + root, main)
            self.assertIn('Environment=MOD_DEMO_MODE=true', main)
            self.assertNotIn('__PROJECT_ROOT__', main)
            self.assertIn('ExecCondition=', result['mod-ml-retrain.service'])
            # A legacy EnvironmentFile can override Environment= in systemd;
            # the launch command and rendered condition must remain authoritative.
            start = next(line.split('=', 1)[1] for line in main.splitlines() if line.startswith('ExecStart='))
            command = shlex.split(start)[:-1]
            with patch.dict(os.environ, {'MOD_DEMO_MODE': 'false'}, clear=True):
                probe = subprocess.run(command + ['-c', 'import os; print(os.environ["MOD_DEMO_MODE"])'], capture_output=True, text=True)
                condition = next(line.split('=', 1)[1] for line in result['mod-ml-retrain.service'].splitlines() if line.startswith('ExecCondition='))
                blocked = subprocess.run(shlex.split(condition), capture_output=True)
            self.assertEqual(probe.returncode, 0)
            self.assertEqual(probe.stdout.strip(), 'true')
            self.assertEqual(blocked.returncode, 1)
            self.assertIn('Environment=MOD_DEMO_MODE=false', render(root, 'demo_user', root + '/private.env', sys.executable, demo=False)['mod.service'])

    def test_render_rejects_injected_paths(self):
        for path in ['/srv/demo;touch', '/srv/../other', '/', '/srv/demo\nExecStart=bad']:
            with self.assertRaises(ValueError):
                absolute_path(path)

    def test_render_nginx_has_explicit_assets_and_preserves_security(self):
        fields = {'PUBLIC_DOMAIN': 'example.test', 'FRONTEND_ROOT': '/srv/demo/web',
                  'SSL_CERT_PATH': '/srv/demo/cert', 'SSL_KEY_PATH': '/srv/demo/key',
                  'NGINX_SNIPPETS': '/srv/demo/snippets', 'ACME_ROOT': '/srv/demo/acme'}
        nginx = render('/srv/demo', 'demo_user', '/srv/demo/private.env', sys.executable, nginx=fields)['mod.conf']
        self.assertIn('root /srv/demo/web;', nginx)
        self.assertIn('noindex, nofollow', nginx)
        self.assertNotIn('__', nginx)

    def test_publish_without_apply_has_no_external_effect(self):
        with patch.dict(os.environ, {}, clear=True):
            result = subprocess.run(['bash', str(ROOT / 'scripts/project/publish.sh')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('No deployment performed', result.stdout)

    def test_supervisor_demo_launches_only_api_and_preserves_explicit_environment(self):
        supervisor = load_script('run_unified')
        handlers = {}
        child = MagicMock()
        child.poll.return_value = None
        def stop(_):
            handlers[signal.SIGTERM](signal.SIGTERM, None)
        environment = {'MOD_DEMO_MODE': 'true', 'MOD_DEMO_DATABASE_URL': 'mysql+pymysql://127.0.0.1/demo',
                       'MOD_CF_AI_ENABLED': 'true', 'MOD_SIMULATION_ENGINE_ENABLED': 'true'}
        with patch.dict(os.environ, environment, clear=True), patch.object(supervisor, 'load_env_file', return_value={'MOD_DEMO_MODE': 'false'}), patch.object(supervisor.signal, 'signal', side_effect=lambda sig, fn: handlers.update({sig: fn})), patch.object(supervisor.time, 'sleep', side_effect=stop), patch.object(supervisor.subprocess, 'Popen', return_value=child) as popen:
            self.assertEqual(supervisor.main(), 0)
        self.assertEqual(popen.call_count, 1)
        env = popen.call_args.kwargs['env']
        self.assertEqual(env['MOD_DEMO_MODE'], 'true')
        self.assertEqual(env['MOD_CF_AI_ENABLED'], 'false')
        self.assertEqual(env['MOD_SIMULATION_ENGINE_ENABLED'], 'false')

    def test_supervisor_missing_demo_target_never_starts(self):
        supervisor = load_script('run_unified')
        with patch.dict(os.environ, {'MOD_DEMO_MODE': 'true'}, clear=True), patch.object(supervisor, 'load_env_file', return_value={}), patch.object(supervisor.subprocess, 'Popen') as popen:
            self.assertEqual(supervisor.main(), 2)
        popen.assert_not_called()
