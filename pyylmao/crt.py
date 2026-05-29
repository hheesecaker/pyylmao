from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


CERTSPOTTER_URL = "https://api.certspotter.com/v1/issuances"


@dataclass(frozen=True)
class CertificateIssuance:
    issuer: str
    dns_names: tuple[str, ...]
    not_before: str
    not_after: str


class CrtProvider(Protocol):
    def issuances_for(self, domain: str) -> list[CertificateIssuance]:
        ...


class CertSpotterProvider:
    def __init__(self, base_url: str = CERTSPOTTER_URL):
        self.base_url = base_url

    def issuances_for(self, domain: str) -> list[CertificateIssuance]:
        query = urlencode(
            {
                "domain": domain,
                "include_subdomains": "true",
                "expand": "dns_names",
            }
        )
        request = Request(f"{self.base_url}?{query}", headers={"User-Agent": "pyylmao/0.1"})
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list):
            raise CrtError("CertSpotter returned an unexpected response")
        return [parse_issuance(item) for item in payload if isinstance(item, dict)]


class CrtError(RuntimeError):
    pass


DEFAULT_PROVIDER = CertSpotterProvider()


def is_crt_command(text: str) -> bool:
    return parse_crt_domain(text) is not None


def parse_crt_domain(text: str) -> str | None:
    match = re.match(r"^[!?]crt\s+(\S+)$", text.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1)


def render_crt_command(
    text: str,
    nick: str | None = None,
    provider: CrtProvider | None = None,
    limit: int = 10,
) -> list[str]:
    domain = parse_crt_domain(text)
    if domain is None:
        return ["Usage: !crt <hostname>"]
    try:
        issuances = (provider or DEFAULT_PROVIDER).issuances_for(domain)
    except (CrtError, HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return [f"crt: {exc}"]

    shown = issuances[: max(limit, 0)]
    prefix = f"{nick}: " if nick else ""
    if not issuances:
        return [f"{prefix}No certificates found for {domain}"]
    return [
        f"{prefix}Certificates for {domain} ({len(issuances)} total, showing {len(shown)}):",
        *render_certificate_table(shown),
    ]


def parse_issuance(item: dict[str, object]) -> CertificateIssuance:
    dns_names = item.get("dns_names")
    issuer = item.get("issuer")
    issuer_name = "N/A"
    if isinstance(issuer, dict):
        raw = issuer.get("name") or issuer.get("common_name") or issuer.get("friendly_name")
        if isinstance(raw, str) and raw.strip():
            issuer_name = raw.strip()
    elif isinstance(item.get("issuer_name"), str):
        issuer_name = str(item["issuer_name"]).strip() or "N/A"
    return CertificateIssuance(
        issuer=issuer_name,
        dns_names=tuple(str(name) for name in dns_names) if isinstance(dns_names, list) else (),
        not_before=format_cert_date(item.get("not_before")),
        not_after=format_cert_date(item.get("not_after")),
    )


def format_cert_date(value: object) -> str:
    text = str(value or "")
    return text[:10] if len(text) >= 10 else text


def render_certificate_table(rows: Iterable[CertificateIssuance]) -> list[str]:
    table_rows = [
        [
            row.issuer or "N/A",
            ", ".join(row.dns_names) if row.dns_names else "N/A",
            row.not_before,
            row.not_after,
        ]
        for row in rows
    ]
    if not table_rows:
        return []
    headers = ["Issuer", "DNS Names", "From", "Until"]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in table_rows))
        for index in range(len(headers))
    ]
    total_width = sum(widths) + 3 * (len(widths) - 1) + 2

    def render_row(row: list[str]) -> str:
        values = [row[index].ljust(widths[index]) for index in range(len(widths))]
        return " " + " | ".join(values) + " "

    return [
        "",
        "▂" * total_width,
        render_row(headers),
        *[render_row(row) for row in table_rows],
        "🮂" * total_width,
        "",
        "",
    ]
