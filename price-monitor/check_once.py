#!/usr/bin/env python3
"""
Eenmalige check voor GitHub Actions (draait elke ~5 minuten via een schema).

Stuurt een pushmelding via ntfy (https://ntfy.sh) zodra het product weer op voorraad is
of de prijs op/onder de doelprijs komt. Tik op de melding om de winkelpagina te openen.

Instellingen komen uit omgevingsvariabelen:
    PRODUCT_URL   de productpagina
    NTFY_TOPIC    je (geheime, moeilijk te raden) ntfy-topicnaam
    DOELPRIJS     optioneel, standaard 899.99
    STATE_FILE    optioneel, waar de vorige status bewaard wordt
    TEST_MELDING  "true" om altijd een testmelding te sturen
"""

import json
import os
import sys
from pathlib import Path

import requests

import price_monitor as pm

STATE_FILE = Path(os.environ.get("STATE_FILE", "state/state.json"))


def stuur_melding(topic: str, titel: str, bericht: str, url: str) -> None:
    # JSON-publicatie zodat tekens als € en emoji goed doorkomen.
    response = requests.post(
        "https://ntfy.sh/",
        json={
            "topic": topic,
            "title": titel,
            "message": bericht,
            "click": url,
            "priority": 5,
            "tags": ["rotating_light", "shopping_cart"],
            "actions": [{"action": "view", "label": "Naar de winkel", "url": url}],
        },
        timeout=pm.TIMEOUT,
    )
    response.raise_for_status()
    pm.log("Pushmelding verstuurd.")


def lees_status() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def schrijf_status(status: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(status, indent=2))


def main() -> None:
    url = os.environ.get("PRODUCT_URL", "").strip()
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    doelprijs = float(os.environ.get("DOELPRIJS") or pm.DOELPRIJS)
    if not url.startswith("http") or not topic:
        sys.exit("Stel PRODUCT_URL en NTFY_TOPIC in (Settings → Secrets and variables → Actions).")

    if os.environ.get("TEST_MELDING", "").lower() == "true":
        stuur_melding(topic, "Testmelding prijsmonitor", "Het werkt! Tik hier om de pagina te openen.", url)

    uitverkocht, prijs = pm.check_pagina(requests.Session(), url)
    prijs_txt = f"€ {prijs:.2f}" if prijs is not None else "onbekend"
    pm.log(f"Status: {'uitverkocht' if uitverkocht else 'BESCHIKBAAR'} | Prijs: {prijs_txt}")

    redenen = []
    if not uitverkocht:
        redenen.append(f"'{pm.UITVERKOCHT_TEKST}' staat niet meer op de pagina")
    if prijs is not None and prijs <= doelprijs:
        redenen.append(f"prijs is {prijs_txt}")

    vorige = lees_status()
    alarm = bool(redenen)
    # Alleen melden bij de overgang naar "alarm", niet elke 5 minuten opnieuw.
    if alarm and not vorige.get("alarm"):
        bericht = " en ".join(redenen)
        stuur_melding(topic, "🚨 Nu kopen!", bericht[0].upper() + bericht[1:] + ". Tik om af te rekenen.", url)

    schrijf_status({"alarm": alarm, "uitverkocht": uitverkocht, "prijs": prijs})


if __name__ == "__main__":
    main()
