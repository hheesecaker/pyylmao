from __future__ import annotations

import unittest

from pyylmao.chkdomain import (
    CompositeDomainStatusProvider,
    DomainStatusError,
    is_chkdomain_command,
    parse_chkdomain,
    render_chkdomain_command,
)


class FakeProvider:
    def __init__(self, status: str | Exception):
        self.status_or_error = status
        self.seen: list[str] = []

    def status(self, domain: str) -> str:
        self.seen.append(domain)
        if isinstance(self.status_or_error, Exception):
            raise self.status_or_error
        return self.status_or_error


class ChkDomainTests(unittest.TestCase):
    def test_command_detection_matches_logged_trigger(self) -> None:
        self.assertTrue(is_chkdomain_command("?gnaa.li"))
        self.assertTrue(is_chkdomain_command("?2gende.rs"))
        self.assertTrue(is_chkdomain_command("  ?GNAa.OVH  "))
        self.assertFalse(is_chkdomain_command("?ughgyrs"))
        self.assertFalse(is_chkdomain_command("??gnaa.li"))
        self.assertFalse(is_chkdomain_command("gnaa.li"))
        self.assertEqual(parse_chkdomain("?GNAa.OVH"), "gnaa.ovh")

    def test_known_logged_statuses(self) -> None:
        self.assertEqual(render_chkdomain_command("?gnaa.li"), ["gnaa.li: undelegated inactive"])
        self.assertEqual(render_chkdomain_command("?gnaa.ovh"), ["gnaa.ovh: undelegated"])
        self.assertEqual(render_chkdomain_command("?bigba.ng"), ["bigba.ng: active"])
        self.assertEqual(render_chkdomain_command("?nig.ng"), ["nig.ng: undelegated active"])
        self.assertEqual(render_chkdomain_command("?nigg.ir"), ["nigg.ir: unknown"])
        self.assertEqual(render_chkdomain_command("?white.men"), ["white.men: marketed priced active"])
        self.assertEqual(render_chkdomain_command("?brown.men"), ["brown.men: undelegated inactive premium"])
        self.assertEqual(render_chkdomain_command("?queer.men"), ["queer.men: undelegated reserved"])
        self.assertEqual(render_chkdomain_command("?straight.men"), ["straight.men: undelegated premium reserved"])
        self.assertEqual(render_chkdomain_command("?dysphor.ia"), ["api error"])

    def test_injected_provider_is_used_for_unknown_domains(self) -> None:
        provider = FakeProvider("active")
        self.assertEqual(
            render_chkdomain_command("?example.test", provider=provider),
            ["example.test: active"],
        )
        self.assertEqual(provider.seen, ["example.test"])

    def test_provider_error_renders_api_error(self) -> None:
        provider = FakeProvider(DomainStatusError("api error"))
        self.assertEqual(render_chkdomain_command("?example.test", provider=provider), ["api error"])

    def test_composite_provider_falls_back_after_errors(self) -> None:
        first = FakeProvider(DomainStatusError("api error"))
        second = FakeProvider("undelegated inactive")
        provider = CompositeDomainStatusProvider(
            providers=[first, second],
            known_statuses={},
        )
        self.assertEqual(provider.status("example.test"), "undelegated inactive")
        self.assertEqual(first.seen, ["example.test"])
        self.assertEqual(second.seen, ["example.test"])


if __name__ == "__main__":
    unittest.main()
