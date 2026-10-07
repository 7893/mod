from __future__ import annotations

import unittest

from scripts.project.check_public_sanitization import redact_sensitive_text, scan_text


class PublicSanitizationTests(unittest.TestCase):
    def test_allows_localhost_and_documentation_addresses(self) -> None:
        text = "127.0.0.1 0.0.0.0 192.0.2.10 2001:db8::10 https://example.com"
        self.assertEqual(scan_text("docs/example.md", text), [])

    def test_reports_real_addresses_without_echoing_value(self) -> None:
        raw_value = ".".join(("10", "23", "45", "67"))
        findings = scan_text("config.env", f"HOST={raw_value}")
        self.assertEqual([finding.category for finding in findings], ["private-ipv4"])
        self.assertNotIn(raw_value, findings[0].diagnostic())

    def test_private_inventory_matches_without_echoing_value(self) -> None:
        raw_value = "service.production.invalid"
        findings = scan_text("deploy/app.conf", raw_value, (raw_value,))
        self.assertTrue(any(item.category == "private-asset-inventory-match" for item in findings))
        self.assertTrue(all(raw_value not in item.diagnostic() for item in findings))

    def test_redaction_is_deterministic(self) -> None:
        raw_address = ".".join(("10", "23", "45", "67"))
        text = f"DB_HOST={raw_address}\nURL=https://service.production.invalid/api"
        redacted = redact_sensitive_text(text, ("service.production.invalid",))
        self.assertNotIn(raw_address, redacted)
        self.assertNotIn("service.production.invalid", redacted)
        self.assertIn("<internal-ip>", redacted)
        self.assertIn("<sensitive-asset>", redacted)

    def test_host_paths_preserve_portable_role_and_suffix(self) -> None:
        prefix = "/".join(("", "home", "demo-user"))
        text = f"{prefix}/mod/backend {prefix}/mod-runtime/current {prefix}/.cache"
        self.assertTrue(scan_text("docs/example.md", text))
        redacted = redact_sensitive_text(text)
        self.assertEqual(redacted, "${MOD_PROJECT_ROOT}/backend ${MOD_DEPLOY_ROOT}/current ${HOME}/.cache")
        self.assertEqual(scan_text("docs/example.md", redacted), [])
        self.assertEqual(redact_sensitive_text(redacted), redacted)

    def test_only_explicit_synthetic_test_paths_are_allowed(self) -> None:
        prefix = "/".join(("", "home", "operator"))
        self.assertEqual(scan_text("scripts/project/tests/test_fixture.py", prefix + "/mod"), [])
        self.assertTrue(scan_text("docs/example.md", prefix + "/mod"))

    def test_personal_email_is_redacted_and_example_identity_is_allowed(self) -> None:
        identity = "fixture-user" + "@" + "mail.invalid"
        findings = scan_text("docs/example.md", identity)
        self.assertEqual([f.category for f in findings], ["non-example-email"])
        self.assertNotIn(identity, findings[0].diagnostic())
        redacted = redact_sensitive_text(identity + " archive@example.invalid")
        self.assertEqual(redacted, "<redacted-email> archive@example.invalid")
        self.assertEqual(scan_text("docs/example.md", redacted), [])


if __name__ == "__main__":
    unittest.main()
