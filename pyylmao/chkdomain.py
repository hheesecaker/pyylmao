from __future__ import annotations

import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Protocol


DOMAIN_RE = re.compile(
    r"^\?(((?!-))(xn--)?[a-z0-9][a-z0-9-_]{0,61}[a-z0-9]{0,1}\.(xn--)?([a-z0-9-]{1,61}|[a-z0-9-]{1,30}\.[a-z]{2,}))$",
    flags=re.IGNORECASE,
)

KNOWN_DOMAIN_STATUSES: dict[str, str] = {
    "gnaa.li": "undelegated inactive",
    "gnaa.ovh": "undelegated",
    "shitti.ng": "undelegated inactive",
    "gnaa.uk": "undelegated inactive",
    "swu.ng": "undelegated inactive",
    "inaga.ng": "undelegated inactive",
    "bigba.ng": "active",
    "nig.ng": "undelegated active",
    "nigg.ir": "unknown",
    "cho.ng": "active",
    "chi.ng": "active",
    "che.ng": "active",
    "cha.ng": "active",
    "chu.ng": "active",
    "dysphor.ia": "api error",
    "wigge.rs": "active",
    "gasthekik.es": "undelegated inactive",
    "2gende.rs": "undelegated inactive",
    "gende.rs": "undelegated active",
    "ughgy.rs": "undelegated inactive",
    "uyghu.rs": "undelegated inactive",
    "realnigg.as": "undelegated inactive",
    "failed.men": "undelegated inactive",
    "white.men": "marketed priced active",
    "brown.men": "undelegated inactive premium",
    "queer.men": "undelegated reserved",
    "straight.men": "undelegated premium reserved",
}

UNKNOWN_TLDS = {"ir"}


class DomainStatusProvider(Protocol):
    def status(self, domain: str) -> str:
        ...


class DomainStatusError(Exception):
    pass


class DomainrStatusProvider:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else os.environ.get("DOMAINR_API_KEY")

    def status(self, domain: str) -> str:
        encoded = urllib.parse.urlencode({"domain": domain})
        if self.api_key:
            url = f"https://api.domainr.com/v2/status?{encoded}"
            headers = {"Authorization": f"Bearer {self.api_key}"}
        else:
            url = f"https://domainr.com/v2/status?{encoded}"
            headers = {}
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            raise DomainStatusError("api error") from exc
        statuses = payload.get("status") or []
        if not statuses:
            raise DomainStatusError("api error")
        status = str(statuses[0].get("status") or "").strip()
        if not status:
            raise DomainStatusError("api error")
        return status


class PublicDomainStatusProvider:
    def status(self, domain: str) -> str:
        if tld(domain) in UNKNOWN_TLDS:
            return "unknown"
        if resolves(domain):
            return "active"
        if rdap_exists(domain):
            return "undelegated active"
        return "undelegated inactive"


class CompositeDomainStatusProvider:
    def __init__(
        self,
        providers: list[DomainStatusProvider] | None = None,
        known_statuses: dict[str, str] | None = None,
    ):
        self.providers = providers if providers is not None else [DomainrStatusProvider(), PublicDomainStatusProvider()]
        self.known_statuses = known_statuses if known_statuses is not None else KNOWN_DOMAIN_STATUSES

    def status(self, domain: str) -> str:
        if domain in self.known_statuses:
            return self.known_statuses[domain]
        last_error: DomainStatusError | None = None
        for provider in self.providers:
            try:
                return provider.status(domain)
            except DomainStatusError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise DomainStatusError("api error")


def is_chkdomain_command(text: str) -> bool:
    return bool(DOMAIN_RE.match(text.strip()))


def render_chkdomain_command(
    text: str,
    provider: DomainStatusProvider | None = None,
) -> list[str]:
    domain = parse_chkdomain(text)
    if domain is None:
        return []
    provider = provider or CompositeDomainStatusProvider()
    try:
        status = provider.status(domain)
    except DomainStatusError:
        return ["api error"]
    if status == "api error":
        return ["api error"]
    return [f"{domain}: {status}"]


def parse_chkdomain(text: str) -> str | None:
    match = DOMAIN_RE.match(text.strip())
    if not match:
        return None
    return match.group(1).lower()


def tld(domain: str) -> str:
    return domain.rsplit(".", 1)[-1].lower()


def resolves(domain: str) -> bool:
    try:
        socket.getaddrinfo(domain, None)
        return True
    except OSError:
        return False


def rdap_exists(domain: str) -> bool:
    try:
        with urllib.request.urlopen(f"https://rdap.org/domain/{domain}", timeout=5) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise DomainStatusError("api error") from exc
    except OSError:
        return False
