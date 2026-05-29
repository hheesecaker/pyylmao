from __future__ import annotations

import unittest

from pyylmao.crt import (
    CertificateIssuance,
    CrtError,
    is_crt_command,
    parse_crt_domain,
    parse_issuance,
    render_crt_command,
)


class FakeProvider:
    def __init__(self, rows: list[CertificateIssuance] | None = None, error: Exception | None = None):
        self.rows = rows or []
        self.error = error

    def issuances_for(self, domain: str) -> list[CertificateIssuance]:
        if self.error is not None:
            raise self.error
        return self.rows


def fake_rows() -> list[CertificateIssuance]:
    return [
        CertificateIssuance(
            issuer="N/A",
            dns_names=("*.gnaa.africa", "gnaa.africa"),
            not_before="2026-01-22",
            not_after="2026-04-22",
        ),
        CertificateIssuance(
            issuer="N/A",
            dns_names=("predbase.gnaa.africa",),
            not_before="2026-02-19",
            not_after="2026-05-20",
        ),
    ]


class CrtTests(unittest.TestCase):
    def test_detects_logged_command_pattern(self) -> None:
        self.assertTrue(is_crt_command("!crt gnaa.africa"))
        self.assertTrue(is_crt_command("?crt gnaa.africa"))
        self.assertEqual(parse_crt_domain("!crt gnaa.africa"), "gnaa.africa")
        self.assertFalse(is_crt_command("!crt"))
        self.assertFalse(is_crt_command("!crtx gnaa.africa"))

    def test_parses_certspotter_issuance(self) -> None:
        row = parse_issuance(
            {
                "dns_names": ["*.gnaa.africa", "gnaa.africa"],
                "not_before": "2026-03-24T00:00:00Z",
                "not_after": "2026-06-22T00:37:36Z",
            }
        )
        self.assertEqual(row.issuer, "N/A")
        self.assertEqual(row.dns_names, ("*.gnaa.africa", "gnaa.africa"))
        self.assertEqual(row.not_before, "2026-03-24")
        self.assertEqual(row.not_after, "2026-06-22")

    def test_renders_summary_and_compact_table(self) -> None:
        lines = render_crt_command("!crt gnaa.africa", "tinky", FakeProvider(fake_rows()))
        self.assertEqual(lines[0], "tinky: Certificates for gnaa.africa (2 total, showing 2):")
        self.assertEqual(lines[1], "")
        self.assertTrue(lines[2].startswith("▂"))
        self.assertIn("Issuer", lines[3])
        self.assertIn("DNS Names", lines[3])
        self.assertIn("*.gnaa.africa, gnaa.africa", "\n".join(lines))
        self.assertIn("predbase.gnaa.africa", "\n".join(lines))
        self.assertTrue(lines[-3].startswith("🮂"))

    def test_limits_rendered_rows(self) -> None:
        rows = fake_rows() * 6
        lines = render_crt_command("!crt gnaa.africa", "tinky", FakeProvider(rows), limit=10)
        self.assertEqual(lines[0], "tinky: Certificates for gnaa.africa (12 total, showing 10):")
        rendered_rows = [line for line in lines if "N/A" in line]
        self.assertEqual(len(rendered_rows), 10)

    def test_no_results_and_fetch_errors(self) -> None:
        self.assertEqual(
            render_crt_command("!crt example.test", "alice", FakeProvider([])),
            ["alice: No certificates found for example.test"],
        )
        self.assertEqual(
            render_crt_command("!crt example.test", "alice", FakeProvider(error=CrtError("offline"))),
            ["crt: offline"],
        )
