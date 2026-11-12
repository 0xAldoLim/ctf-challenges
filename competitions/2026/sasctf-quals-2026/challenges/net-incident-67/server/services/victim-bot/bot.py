import logging
import os
import time

import dns.resolver
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [victim-bot] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("victim-bot")

DNS_SERVER = "10.0.1.53"
DOMAIN = "cryptowallet.ctf"
TX_ENDPOINT = "/api/v1/transaction"
INTERVAL = 30

FLAG = os.environ.get("FLAG")
if not FLAG:
    raise RuntimeError("FLAG environment variable is required")

PAYLOAD = {
    "wallet": "0xd3CdA913deB6f67967B99D67aCDFa1712C293601",
    "amount": "1.337",
    "memo": FLAG,
}


def resolve_domain() -> str | None:
    try:
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = [DNS_SERVER]
        resolver.lifetime = 5
        answers = resolver.resolve(DOMAIN, "A")
        ip = str(answers[0])
        log.info("Resolved %s -> %s", DOMAIN, ip)
        return ip
    except Exception:
        log.exception("DNS resolution failed for %s via %s", DOMAIN, DNS_SERVER)
        return None


def submit_transaction(ip: str) -> None:
    url = f"https://{ip}{TX_ENDPOINT}"
    headers = {"Host": DOMAIN, "Content-Type": "application/json"}

    log.info("Submitting transaction to %s (Host: %s)", url, DOMAIN)
    try:
        resp = requests.post(
            url,
            json=PAYLOAD,
            headers=headers,
            verify=False,
            timeout=10,
        )
        log.info("Response %d: %s", resp.status_code, resp.text[:256])
    except requests.RequestException:
        log.exception("Transaction request failed to %s", url)


def main() -> None:
    log.info("Victim bot starting — target: %s, DNS: %s", DOMAIN, DNS_SERVER)
    log.info("Transaction interval: %ds", INTERVAL)

    while True:
        ip = resolve_domain()
        if ip:
            submit_transaction(ip)
        else:
            log.warning("Skipping transaction — DNS resolution failed")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
