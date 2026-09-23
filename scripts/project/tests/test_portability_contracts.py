from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class PortabilityContractTests(unittest.TestCase):
    def test_china_map_geometry_is_deployment_owned(self) -> None:
        package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
        lockfile = (ROOT / "frontend/pnpm-lock.yaml").read_text(encoding="utf-8")
        component = (ROOT / "frontend/src/components/ChinaMap.vue").read_text(encoding="utf-8")
        source = (ROOT / "frontend/src/charts/chinaMapSource.ts").read_text(encoding="utf-8")
        vite_config = (ROOT / "frontend/vite.config.ts").read_text(encoding="utf-8")
        env_example = (ROOT / "frontend/.env.example").read_text(encoding="utf-8")
        deploy_workflow = (ROOT / ".github/workflows/quality.yml").read_text(
            encoding="utf-8"
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

        self.assertNotIn("china-geojson", package["dependencies"])
        self.assertNotIn("china-geojson@", lockfile)
        self.assertNotIn("china-geojson", component)
        self.assertNotIn("china-geojson", vite_config)
        self.assertIn("fetchChinaMapGeoJson", component)
        self.assertIn("FeatureCollection", source)
        self.assertRegex(env_example, r"(?m)^VITE_CHINA_MAP_GEOJSON_URL=$")
        self.assertIn("Validate deployment configuration", deploy_workflow)
        self.assertIn(
            "VITE_CHINA_MAP_GEOJSON_URL is required for a configured production deployment",
            deploy_workflow,
        )
        self.assertIn("frontend/shared/china.geojson", deploy_workflow)
        self.assertIn("VITE_CHINA_MAP_GEOJSON_URL", readme)
        self.assertGreaterEqual(readme.count("THIRD_PARTY_NOTICES.md"), 3)
        self.assertIn("Apache ECharts", notices)
        self.assertIn("VITE_CHINA_MAP_GEOJSON_URL", notices)

    def test_public_tools_do_not_embed_workspace_root(self) -> None:
        fixed_root = "/".join(("", "home", "ubuntu", "mod"))
        for relative in (
            ".pi/extensions/mod-harness.ts",
            "scripts/project/pre_flight.sh",
            "scripts/project/safe_db_query.py",
        ):
            self.assertNotIn(fixed_root, (ROOT / relative).read_text(encoding="utf-8"))

    def test_preflight_reports_unavailable_harness_as_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            result = subprocess.run(
                ["bash", "scripts/project/pre_flight.sh"],
                cwd=ROOT,
                env={"HOME": home, "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("make check", result.stdout)

    def test_publish_origin_secret_requires_explicit_host(self) -> None:
        env = os.environ.copy()
        env["CLOUDFRONT_ORIGIN_SECRET"] = "test-only-placeholder"  # pragma: allowlist secret
        env.pop("MOD_ORIGIN_HOST", None)
        env.pop("MOD_PUBLIC_HOST", None)
        result = subprocess.run(
            ["bash", "scripts/project/publish.sh", "--local"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("requires MOD_ORIGIN_HOST", result.stdout)

    def test_production_requirements_are_portable_runtime_only(self) -> None:
        requirements = (ROOT / "backend/requirements.prod.txt").read_text(encoding="utf-8")
        self.assertNotIn("file://", requirements)
        for development_package in ("pytest", "ruff", "pluggy", "iniconfig"):
            self.assertNotRegex(requirements, rf"(?m)^{development_package}(?:==|>=|$)")


if __name__ == "__main__":
    unittest.main()
