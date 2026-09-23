#!/usr/bin/env python3
"""Block sensitive infrastructure identifiers from the public repository.

Owner: project governance tooling (KI-103).
Input: tracked UTF-8 files plus an optional private asset inventory.
Output: redacted diagnostics containing only path, line and finding category.
Read/write: read-only; no repository, service, database or network writes.
Risk: private inventory values are matched in memory and are never printed.
Validation: python3 -m unittest scripts.project.tests.test_public_sanitization
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[2]

# SHA-256 fingerprints prevent the scanner itself from republishing known hostnames.
# They are identifiers, not a secrecy boundary; maintainers must also supply the
# private inventory for release audits and whenever production assets change.
KNOWN_SENSITIVE_DOMAIN_FINGERPRINTS = frozenset(
    {
        "0c8200cf1930ab3dff4cc16bfc61e52eada24d3bac56b971362236f111569d53",
        "251ea8b4d09dd32ed29922d0984c4599e3c74a5d2f28ae5ab10e53982c5ab395",
    }
)

IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
IPV6_TOKEN_RE = re.compile(r"(?<![\w:])\[?[0-9A-Fa-f:]{3,}\]?(?![\w:])")
DOMAIN_RE = re.compile(
    r"(?<![\w@-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z]{2,63}(?![\w.-])",
    re.IGNORECASE,
)
OCI_RE = re.compile(r"\bocid1\.[a-z0-9_.-]+", re.IGNORECASE)
RESOURCE_PATTERNS = (
    ("cloud-instance-name", re.compile(r"\binstance-\d{8}-\d+\b", re.IGNORECASE)),
    ("cloud-database-name", re.compile(r"\bmysqldbsystem\d{10,}\b", re.IGNORECASE)),
    ("cloud-backup-name", re.compile(r"\bmysqlbackup\d{10,}\b", re.IGNORECASE)),
)
PRIVATE_DOMAIN_SUFFIXES = (".corp", ".internal", ".lan", ".private")
ALLOWED_IPV4_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in ("0.0.0.0/32", "127.0.0.0/8", "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
)
ALLOWED_IPV6_NETWORKS = tuple(
    ipaddress.ip_network(value) for value in ("::/128", "::1/128", "2001:db8::/32")
)


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    line: int
    category: str

    def diagnostic(self) -> str:
        return f"{self.path}:{self.line}: {self.category}"


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.casefold().encode("utf-8")).hexdigest()


def _domain_is_sensitive(hostname: str) -> bool:
    labels = hostname.casefold().strip(".").split(".")
    return any(
        _fingerprint(".".join(labels[index:])) in KNOWN_SENSITIVE_DOMAIN_FINGERPRINTS
        for index in range(max(0, len(labels) - 3), len(labels) - 1)
    )


def _allowed_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    networks = ALLOWED_IPV4_NETWORKS if address.version == 4 else ALLOWED_IPV6_NETWORKS
    return any(address in network for network in networks)


def load_private_assets(path: Path | None = None) -> tuple[str, ...]:
    """Load exact sensitive values without logging their contents."""
    candidates: list[str] = []
    configured_path = path or (
        Path(os.environ["MOD_SENSITIVE_ASSET_FILE"])
        if os.environ.get("MOD_SENSITIVE_ASSET_FILE")
        else None
    )
    if configured_path:
        candidates.extend(configured_path.read_text(encoding="utf-8").splitlines())
    candidates.extend(os.environ.get("MOD_SENSITIVE_ASSETS", "").splitlines())
    return tuple(
        value.strip().casefold()
        for value in candidates
        if value.strip() and not value.lstrip().startswith("#")
    )


def scan_text(path: str, text: str, private_assets: Sequence[str] = ()) -> list[Finding]:
    findings: set[Finding] = set()
    normalized_assets = tuple(asset.casefold() for asset in private_assets if asset)

    for line_number, line in enumerate(text.splitlines(), start=1):
        folded = line.casefold()
        if any(asset in folded for asset in normalized_assets):
            findings.add(Finding(path, line_number, "private-asset-inventory-match"))

        for match in IPV4_RE.finditer(line):
            try:
                address = ipaddress.ip_address(match.group(0))
            except ValueError:
                continue
            if not _allowed_ip(address):
                category = "private-ipv4" if address.is_private else "public-or-routable-ipv4"
                findings.add(Finding(path, line_number, category))

        for match in IPV6_TOKEN_RE.finditer(line):
            candidate = match.group(0).strip("[]")
            if candidate.count(":") < 2:
                continue
            try:
                address = ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if address.version == 6 and not _allowed_ip(address):
                findings.add(Finding(path, line_number, "non-example-ipv6"))

        for match in DOMAIN_RE.finditer(line):
            hostname = match.group(0).casefold().strip(".")
            if hostname.endswith(PRIVATE_DOMAIN_SUFFIXES):
                findings.add(Finding(path, line_number, "private-dns-name"))
            elif _domain_is_sensitive(hostname):
                findings.add(Finding(path, line_number, "known-production-domain"))

        if OCI_RE.search(line) and "..." not in line:
            findings.add(Finding(path, line_number, "cloud-resource-identifier"))
        for category, pattern in RESOURCE_PATTERNS:
            if pattern.search(line):
                findings.add(Finding(path, line_number, category))

    return sorted(findings)


def redact_sensitive_text(text: str, private_assets: Sequence[str] = ()) -> str:
    """Deterministically replace sensitive identifiers without retaining raw values."""
    redacted = text
    for asset in sorted((value for value in private_assets if value), key=len, reverse=True):
        redacted = re.sub(re.escape(asset), "<sensitive-asset>", redacted, flags=re.IGNORECASE)

    def replace_ipv4(match: re.Match[str]) -> str:
        try:
            address = ipaddress.ip_address(match.group(0))
        except ValueError:
            return match.group(0)
        if _allowed_ip(address):
            return match.group(0)
        return "<internal-ip>" if address.is_private else "<public-ip>"

    def replace_ipv6(match: re.Match[str]) -> str:
        candidate = match.group(0).strip("[]")
        if candidate.count(":") < 2:
            return match.group(0)
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            return match.group(0)
        return match.group(0) if _allowed_ip(address) else "<ipv6-address>"

    def replace_domain(match: re.Match[str]) -> str:
        hostname = match.group(0)
        folded = hostname.casefold().strip(".")
        if folded.endswith(PRIVATE_DOMAIN_SUFFIXES) or _domain_is_sensitive(folded):
            return "<production-domain>"
        return hostname

    redacted = IPV4_RE.sub(replace_ipv4, redacted)
    redacted = IPV6_TOKEN_RE.sub(replace_ipv6, redacted)
    redacted = DOMAIN_RE.sub(replace_domain, redacted)
    redacted = OCI_RE.sub("<cloud-resource-id>", redacted)
    for category, pattern in RESOURCE_PATTERNS:
        redacted = pattern.sub(f"<{category}>", redacted)
    return redacted


def tracked_paths(explicit_paths: Iterable[str] = ()) -> list[Path]:
    requested = [Path(value) for value in explicit_paths]
    if requested:
        return [path if path.is_absolute() else ROOT / path for path in requested]
    result = subprocess.run(
        ["git", "ls-files", "--cached", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return [ROOT / value.decode("utf-8") for value in result.stdout.split(b"\0") if value]


def scan_files(paths: Iterable[Path], private_assets: Sequence[str]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        try:
            display_path = path.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            display_path = path.name
        findings.extend(scan_text(display_path, text, private_assets))
    return sorted(set(findings))


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan tracked files for sensitive infrastructure identifiers.")
    parser.add_argument("paths", nargs="*", help="Optional files; default scans every Git-tracked file.")
    parser.add_argument("--private-assets", type=Path, help="Untracked newline-delimited sensitive asset inventory.")
    args = parser.parse_args()

    private_assets = load_private_assets(args.private_assets)
    findings = scan_files(tracked_paths(args.paths), private_assets)
    if findings:
        for finding in findings:
            print(f"  PUBLIC SANITIZATION  {finding.diagnostic()}", file=sys.stderr)
        print(
            f"[public-sanitization] {len(findings)} finding(s); raw matched values were intentionally suppressed.",
            file=sys.stderr,
        )
        return 1
    print("[public-sanitization] OK: tracked text files contain no blocked infrastructure identifiers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
