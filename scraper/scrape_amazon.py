#!/usr/bin/env python3
"""
Scraper offerte Amazon.it
--------------------------
Cerca prodotti in sconto su Amazon.it per una lista di parole chiave/categorie
e genera un file offerte.json con lo schema atteso dall'app.

ATTENZIONE:
- Amazon proibisce lo scraping nei suoi Termini di Servizio. Questo script è
  pensato per uso personale, con frequenza contenuta (max 1 run/ora).
- Amazon blocca aggressivamente richieste automatiche, soprattutto da IP di
  datacenter (es. GitHub Actions). Se noti molti fallimenti consecutivi,
  valuta di eseguire lo script da un tuo PC/Raspberry Pi con IP residenziale
  invece che da GitHub Actions.
- Se in futuro ottieni un account Amazon Associates, l'API ufficiale
  (Product Advertising API) è enormemente più affidabile: vale la pena
  migrare appena puoi.
"""

import json
import random
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

# ----------------------------------------------------------------------------
# CONFIGURAZIONE
# ----------------------------------------------------------------------------

# Parole chiave/categorie da cercare. Modificale come preferisci.
SEARCH_QUERIES = [
    "offerte elettronica",
    "offerte informatica",
    "offerte casa",
    "offerte smartphone",
]

BASE_URL = "https://www.amazon.it/s"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "offerte.json"
MAX_PRODUCTS_PER_QUERY = 15
MIN_DISCOUNT_PERCENT = 15  # scarta prodotti con sconto sotto questa soglia
REQUEST_DELAY_RANGE = (3, 7)  # secondi di pausa tra una richiesta e l'altra
REQUEST_TIMEOUT = 15

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


@dataclass
class Deal:
    asin: str
    title: str
    url: str
    image: str
    price: float
    old_price: float
    discount_percent: int
    currency: str
    category: str
    updated_at: str


def get_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def parse_price(text: str) -> float | None:
    if not text:
        return None
    # es. "19,99" -> 19.99
    cleaned = re.sub(r"[^\d,\.]", "", text).replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def scrape_query(query: str, category_label: str) -> list[Deal]:
    deals: list[Deal] = []
    url = f"{BASE_URL}?k={quote_plus(query)}&s=price-asc-rank"

    try:
        resp = requests.get(url, headers=get_headers(), timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        print(f"[ERRORE] richiesta fallita per '{query}': {exc}", file=sys.stderr)
        return deals

    if resp.status_code != 200:
        print(
            f"[ERRORE] status {resp.status_code} per '{query}' "
            f"(possibile blocco anti-bot)",
            file=sys.stderr,
        )
        return deals

    soup = BeautifulSoup(resp.text, "html.parser")
    results = soup.select("div[data-component-type='s-search-result']")

    for item in results[:MAX_PRODUCTS_PER_QUERY]:
        asin = item.get("data-asin")
        if not asin:
            continue

        title_el = item.select_one("h2 span")
        title = title_el.get_text(strip=True) if title_el else None

        img_el = item.select_one("img.s-image")
        image = img_el.get("src") if img_el else None

        price_el = item.select_one("span.a-price > span.a-offscreen")
        price = parse_price(price_el.get_text(strip=True)) if price_el else None

        old_price_el = item.select_one(
            "span.a-price.a-text-price > span.a-offscreen"
        )
        old_price = (
            parse_price(old_price_el.get_text(strip=True)) if old_price_el else None
        )

        if not (title and price and old_price and old_price > price):
            continue

        discount = round((1 - price / old_price) * 100)
        if discount < MIN_DISCOUNT_PERCENT:
            continue

        deals.append(
            Deal(
                asin=asin,
                title=title,
                url=f"https://www.amazon.it/dp/{asin}",
                image=image or "",
                price=price,
                old_price=old_price,
                discount_percent=discount,
                currency="EUR",
                category=category_label,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
        )

    return deals


def main() -> None:
    all_deals: list[Deal] = []
    seen_asins: set[str] = set()

    for query in SEARCH_QUERIES:
        print(f"Cerco: {query}")
        results = scrape_query(query, category_label=query)
        for deal in results:
            if deal.asin not in seen_asins:
                all_deals.append(deal)
                seen_asins.add(deal.asin)
        time.sleep(random.uniform(*REQUEST_DELAY_RANGE))

    all_deals.sort(key=lambda d: d.discount_percent, reverse=True)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump([asdict(d) for d in all_deals], f, ensure_ascii=False, indent=2)

    print(f"Salvate {len(all_deals)} offerte in {OUTPUT_FILE}")

    if not all_deals:
        print(
            "[AVVISO] Nessuna offerta trovata: probabile blocco anti-bot di "
            "Amazon su questo IP. Vedi il README per alternative.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
