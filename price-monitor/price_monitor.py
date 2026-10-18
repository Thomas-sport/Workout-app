#!/usr/bin/env python3
"""
Prijs- en voorraadmonitor voor een webwinkel.

Controleert ongeveer elke 30 seconden (met willekeurige vertraging) een productpagina.
Zodra de tekst 'Tijdelijk uitverkocht' verdwijnt/verandert, of de prijs op of onder
de doelprijs komt, wordt de pagina automatisch in je standaardbrowser geopend zodat
je direct handmatig kunt afrekenen.

Gebruik:
    pip install requests beautifulsoup4
    python price_monitor.py "https://www.voorbeeldwinkel.nl/product/123"
"""

import random
import re
import sys
import time
import webbrowser
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# ----------------------------------------------------------------------------
# Instellingen
# ----------------------------------------------------------------------------
PRODUCT_URL = "[Vul hier de winkel-URL in]"   # of geef de URL mee als argument
UITVERKOCHT_TEKST = "Tijdelijk uitverkocht"
DOELPRIJS = 899.99

BASIS_INTERVAL = 30          # seconden tussen checks
JITTER = (-5, 10)            # willekeurige afwijking in seconden (min, max)
TIMEOUT = 15                 # request-timeout in seconden

# Optioneel: CSS-selector van het prijs-element (bijv. ".price" of "span.sales-price").
# Laat leeg (None) om automatisch naar een €-bedrag in de pagina te zoeken.
PRIJS_SELECTOR = None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
}

# Matcht o.a. "€ 899,99", "€899,-", "€ 1.099,00" en "899,99 €"
PRIJS_REGEX = re.compile(r"€\s*(\d{1,3}(?:\.\d{3})*(?:,(?:\d{2}|-))?)|(\d{1,3}(?:\.\d{3})*,\d{2})\s*€")


def log(bericht: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {bericht}", flush=True)


def parse_prijs(tekst: str) -> float | None:
    """Zet een Nederlandse prijsnotatie ('1.099,99' / '899,-') om naar float."""
    tekst = tekst.replace("€", "").replace(",-", ",00").strip()
    tekst = tekst.replace(".", "").replace(",", ".")
    try:
        return float(tekst)
    except ValueError:
        return None


def zoek_prijs(soup: BeautifulSoup) -> float | None:
    if PRIJS_SELECTOR:
        element = soup.select_one(PRIJS_SELECTOR)
        if element:
            match = PRIJS_REGEX.search(element.get_text(" ", strip=True))
            if match:
                return parse_prijs(match.group(1) or match.group(2))
            return parse_prijs(element.get_text(strip=True))
        return None

    # Fallback: eerste €-bedrag dat in de zichtbare tekst voorkomt.
    match = PRIJS_REGEX.search(soup.get_text(" ", strip=True))
    if match:
        return parse_prijs(match.group(1) or match.group(2))
    return None


def check_pagina(sessie: requests.Session, url: str) -> tuple[bool, float | None]:
    """Geeft (is_uitverkocht, prijs) terug."""
    response = sessie.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    uitverkocht = UITVERKOCHT_TEKST.lower() in soup.get_text(" ", strip=True).lower()
    return uitverkocht, zoek_prijs(soup)


def open_browser(url: str, reden: str) -> None:
    log(f"🚨 ALARM: {reden} — browser wordt geopend!")
    print("\a", end="", flush=True)  # systeempiepje
    webbrowser.open(url, new=2)


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else PRODUCT_URL
    if not url.startswith("http"):
        sys.exit("Geef een geldige URL op (in PRODUCT_URL of als argument).")

    log(f"Monitoring gestart voor: {url}")
    log(f"Doelprijs: € {DOELPRIJS:.2f} | Stop met Ctrl+C")

    sessie = requests.Session()
    vorige_status = None

    while True:
        try:
            uitverkocht, prijs = check_pagina(sessie, url)
            prijs_txt = f"€ {prijs:.2f}" if prijs is not None else "onbekend"
            log(f"Status: {'uitverkocht' if uitverkocht else 'BESCHIKBAAR'} | Prijs: {prijs_txt}")

            reden = None
            if vorige_status is True and not uitverkocht:
                reden = f"'{UITVERKOCHT_TEKST}' is verdwenen (weer op voorraad?)"
            elif vorige_status is None and not uitverkocht:
                reden = f"'{UITVERKOCHT_TEKST}' staat niet (meer) op de pagina"
            elif prijs is not None and prijs <= DOELPRIJS:
                reden = f"prijs is gezakt naar {prijs_txt}"

            if reden:
                open_browser(url, reden)
                break  # stop na alarm; haal deze regel weg om door te blijven monitoren

            vorige_status = uitverkocht

        except requests.RequestException as fout:
            log(f"Fout bij ophalen pagina: {fout}")

        wachttijd = max(5, BASIS_INTERVAL + random.uniform(*JITTER))
        log(f"Volgende check over {wachttijd:.1f} s")
        time.sleep(wachttijd)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Monitoring gestopt.")
