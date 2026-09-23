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


if __name__ == "__main__":
    unittest.main()
