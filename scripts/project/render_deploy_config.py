#!/usr/bin/env python3
"""Render portable deployment templates. Owner: project.

Inputs: explicit target paths/user; output: new local directory, mode 0600.
Never installs services, invokes sudo, contacts hosts, or copies credentials.
Review generated files before separately authorized installation.
"""
import argparse
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def absolute_path(value):
    if value == '/' or not value.startswith('/') or not re.fullmatch(r'/[A-Za-z0-9_./-]+', value):
        raise ValueError('Target paths must be absolute and contain no whitespace or shell syntax')
    if '..' in Path(value).parts:
        raise ValueError('Parent traversal is forbidden')
    return value.rstrip('/')


def render(project_root, user, env_file, python, demo=True, nginx=None):
    project_root = absolute_path(project_root)
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*', user):
        raise ValueError('Invalid service user')
    python = absolute_path(python)
    values = {'PROJECT_ROOT': project_root, 'RUN_USER': user,
              'ENV_FILE': absolute_path(env_file), 'PYTHON': python,
              'VENV_BIN': str(Path(python).parent), 'DEMO_MODE': str(demo).lower()}
    result = {}
    paths = sorted((ROOT / 'deploy').glob('*.service')) + sorted((ROOT / 'deploy').glob('*.timer'))
    if nginx:
        if not re.fullmatch(r'[A-Za-z0-9.-]+', nginx['PUBLIC_DOMAIN']):
            raise ValueError('Invalid public host')
        values.update({k: absolute_path(v) if k != 'PUBLIC_DOMAIN' else v for k, v in nginx.items()})
        paths.append(ROOT / 'deploy/nginx/mod.conf.example')
    for path in paths:
        data = path.read_text()
        for key, value in values.items():
            data = data.replace(f'__{key}__', value)
        if re.search(r'__[A-Z_]+__', data):
            raise ValueError('Template still has unresolved parameters')
        result[path.name.removesuffix('.example')] = data
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--user', required=True)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--python', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--enable-background-jobs', action='store_true', help='Render non-demo services; never enables timers')
    for key in ('public-domain', 'frontend-root', 'ssl-cert-path', 'ssl-key-path', 'nginx-snippets', 'acme-root'):
        parser.add_argument('--' + key)
    args = parser.parse_args()
    keys = ('public_domain', 'frontend_root', 'ssl_cert_path', 'ssl_key_path', 'nginx_snippets', 'acme_root')
    nginx = {key.upper(): getattr(args, key) for key in keys}
    if any(nginx.values()) and not all(nginx.values()):
        parser.error('All six Nginx parameters must be supplied together')
    rendered = render(args.root, args.user, args.env_file, args.python,
                      not args.enable_background_jobs, nginx if all(nginx.values()) else None)
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    for name, data in rendered.items():
        with (args.output / name).open('x', opener=lambda p, flags: os.open(p, flags, 0o600)) as handle:
            handle.write(data)
    print(f'Rendered {len(rendered)} configuration files; nothing installed or started.')


if __name__ == '__main__':
    main()
