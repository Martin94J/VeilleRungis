"""Récupère des infos sur Rungis et les écrit dans data.json."""
import json
import datetime
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RungisInfoBot/1.0)"}

# --- Sources à scraper : ajoute ou modifie des lignes ici ---------------
# (nom affiché, adresse de la page, sélecteur CSS des liens à récupérer)
PAGES = [
    ("Site de la ville", "https://www.ville-rungis.fr", "h2 a, h3 a"),
]

FLUX_ACTUS = "https://news.google.com/rss/search?q=Rungis&hl=fr&gl=FR&ceid=FR:fr"
# -------------------------------------------------------------------------


def actualites():
    """Actualités via le flux RSS de Google Actualités."""
    try:
        flux = feedparser.parse(FLUX_ACTUS)
        return [
            {"titre": e.title, "lien": e.link, "date": e.get("published", "")}
            for e in flux.entries[:15]
        ]
    except Exception as erreur:
        print("Erreur actualités :", erreur)
        return []


def scraper_page(nom, url, selecteur):
    """Récupère les liens d'une page web."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soupe = BeautifulSoup(r.text, "html.parser")
        vus, resultats = set(), []
        for a in soupe.select(selecteur):
            titre = a.get_text(strip=True)
            lien = urljoin(r.url, a.get("href", ""))
            if titre and lien not in vus:
                vus.add(lien)
                resultats.append({"titre": titre, "lien": lien})
        return {"nom": nom, "url": url, "liens": resultats[:10]}
    except Exception as erreur:
        print(f"Erreur sur {url} :", erreur)
        return {"nom": nom, "url": url, "liens": []}


data = {
    "maj": datetime.datetime.now().strftime("%d/%m/%Y à %H:%M UTC"),
    "actus": actualites(),
    "pages": [scraper_page(*p) for p in PAGES],
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("data.json mis à jour.")
