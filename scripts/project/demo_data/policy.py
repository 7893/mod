"""Keep simulator-generated business records; redact real environment values only."""
from datetime import date, datetime
from decimal import Decimal
import re
import json


def private_values(environment):
    return [v for k, v in environment.items() if v and len(v) >= 8 and any(
        token in k.upper() for token in
        ('PASSWORD', 'TOKEN', 'SECRET', 'ACCOUNT_ID', 'OCID', 'DB_HOST', 'API_KEY'))]


class ArchiveAudit:
    """Inspect decoded archive lines without logging any matching value."""
    def __init__(self, private_assets=()):
        escaped = [re.escape(json.dumps(v, ensure_ascii=False)[1:-1])
                   for v in private_assets if len(v) >= 8]
        self.assets = re.compile('|'.join(escaped)) if escaped else None
        self.candidate = re.compile(
            r'(?:\d{1,3}\.){3}\d{1,3}|(?:[0-9A-Fa-f]{0,4}:){3,}[0-9A-Fa-f:]+'
            r'|oraclecloud\.|ocid1\.|cloudflared|github_pat_|gh[pousr]_|AKIA|PRIVATE KEY')
        self.host_path = re.compile(r'/(?:home|root|srv|opt|tmp|etc|var|usr|mnt|Users)/')
        self.tokens = re.compile(
            r'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})'
            r'|-----BEGIN [^-]*PRIVATE KEY-----|://[^/\s\"]+@'
            r'|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')

    def check(self, line):
        text = line.decode('utf-8')
        if self.assets and self.assets.search(text):
            raise ValueError('Archive contains a known private asset')
        if self.host_path.search(text) or self.tokens.search(text):
            raise ValueError('Archive contains a host path or credential')
        if self.candidate.search(text):
            from check_public_sanitization import scan_text
            if scan_text('archive', text):
                raise ValueError('Archive contains real infrastructure information')

# Parent-first load order. Includes every table, logs, model results and future simulated snapshots.
TABLES = ('rollout_batch', 'org_unit', 'sys_user', 'construction_task', 'training',
          'data_readiness', 'dual_run_result', 'business_document', 'business_document_line',
          'accounting_voucher', 'accounting_voucher_line', 'document_voucher_link',
          'integration_result', 'rollout_status_snapshot', 'issue_metric_snapshot',
          'risk_metric_snapshot', 'governance_issue', 'issue_timeline', 'daily_stats',
          'monthly_stats', 'province_stats', 'metric_snapshot', 'daily_briefing',
          'ml_feat_doc_delta', 'ml_feat_risk', 'ml_score_doc_delta', 'ml_score_risk',
          'ml_model_metadata', 'ml_risk_explanation', 'ml_eval_doc_delta_test',
          'ml_eval_doc_delta_train', 'ml_eval_risk_test', 'ml_eval_risk_train',
          'ml_feat_doc_delta_test', 'ml_feat_doc_delta_train', 'ml_feat_risk_test',
          'ml_feat_risk_train', 'ml_risk_explanation_previous', 'ml_training_log',
          'sim_ai_quota_ledger', 'sim_event_outbox', 'sim_event_outbox_state', 'test_doc')


class Sanitizer:
    def __init__(self, private_assets=()):
        self.assets = sorted(set(v for v in private_assets if len(v) >= 8), key=len, reverse=True)
        self.asset_pattern = re.compile('|'.join(re.escape(v) for v in self.assets)) if self.assets else None
        self.replacements = 0

    def value(self, value):
        if isinstance(value, datetime):
            return value.isoformat(sep=' ')
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        if not isinstance(value, str):
            return value
        if value.startswith(('{', '[')):
            try:
                parsed = json.loads(value)
                def walk(item):
                    if isinstance(item, dict):
                        return {self.value(k): walk(v) for k, v in item.items()}
                    if isinstance(item, list):
                        return [walk(v) for v in item]
                    return self.value(item)
                return json.dumps(walk(parsed), ensure_ascii=False, separators=(',', ':'))
            except json.JSONDecodeError:
                pass
        asset_hit = self.asset_pattern and self.asset_pattern.search(value)
        token_hint = 'github_pat_' in value or 'AKIA' in value or re.search(r'gh[pousr]_', value)
        if not asset_hit and not token_hint and not any(c in value for c in '/.@') and value.count(':') < 3 and 'PRIVATE KEY' not in value:
            return value
        from check_public_sanitization import redact_sensitive_text
        result = value
        if self.asset_pattern:
            result = self.asset_pattern.sub('[s]', result)
        result = redact_sensitive_text(result)
        result = re.sub(r'<(?:internal-ip|public-ip|ipv6-address)>', '[ip]', result)
        result = re.sub(r'<(?:production-domain|cloud-resource-id|sensitive-asset)>', '[s]', result)
        result = re.sub(r'(?<![\w])/(?:home|root|srv|opt|tmp|etc|var|usr|mnt|Users)(?:/[^\s\"\'<>;,)}\]]*)?',
                        '[p]', result)
        result = re.sub(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[email]', result)
        result = re.sub(r'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})',
                        '[s]', result)
        result = re.sub(r'(?<=://)[^/\s]+@', '[s]@', result)
        result = re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----',
                        '[s]', result, flags=re.S)
        if result != value:
            self.replacements += 1
        return result
