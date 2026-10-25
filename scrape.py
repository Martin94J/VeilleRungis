"""Récupère des infos sur Rungis et les écrit dans data.json."""
import json
import datetime
from urllib.parse import urljoin, quote

import feedparser
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RungisInfoBot/1.0)"}

# ======================= À PERSONNALISER ==================================
# Thèmes de veille : (nom affiché sur la page, mots recherchés)
# Ajoute, retire ou modifie des lignes. Garde la virgule en fin de ligne.
THEMES = [
    ("Ville", "ville de Rungis"),
    ("Marché", "Marché de Rungis"),
    ("Travaux", "Rungis travaux"),
    ("Événements", "Rungis événement"),
]

# Ancienneté maximale des articles (ex. 7d = 7 jours, 30d = 30 jours)
PERIODE = "30d"
ARTICLES_PAR_THEME = 10

# Pages web à scraper : (nom affiché, adresse, sélecteur CSS des liens)
PAGES = [
    ("Site de la ville", "https://www.ville-rungis.fr", "h2 a, h3 a"),
]
# ==========================================================================


def nettoyer_titre(titre, source):
    """Google Actualités ajoute ' - Nom du média' à la fin du titre."""
    suffixe = " - " + source
    if source and titre.endswith(suffixe):
        return titre[: -len(suffixe)]
    return titre


def actualites():
    """Actualités par thème via le flux RSS de Google Actualités."""
    articles, vus = [], set()
    for theme, recherche in THEMES:
        url = (
            "https://news.google.com/rss/search?q="
            + quote(f"{recherche} when:{PERIODE}")
            + "&hl=fr&gl=FR&ceid=FR:fr"
        )
        try:
            flux = feedparser.parse(url)
            for e in flux.entries[:ARTICLES_PAR_THEME]:
                source = (e.get("source") or {}).get("title", "")
                titre = nettoyer_titre(e.title, source)
                if e.link in vus or titre in vus:
                    continue
                vus.update([e.link, titre])
                date_iso = ""
                if e.get("published_parsed"):
                    p = e.published_parsed
                    date_iso = datetime.datetime(
                        *p[:6], tzinfo=datetime.timezone.utc
                    ).isoformat()
                articles.append(
                    {
                        "titre": titre,
                        "lien": e.link,
                        "source": source,
                        "date": date_iso,
                        "theme": theme,
                    }
                )
        except Exception as erreur:
            print(f"Erreur thème {theme} :", erreur)
    articles.sort(key=lambda a: a["date"], reverse=True)
    return articles


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
        return {"nom": nom, "url": url, "liens": resultats[:8]}
    except Exception as erreur:
        print(f"Erreur sur {url} :", erreur)
        return {"nom": nom, "url": url, "liens": []}


data = {
    "maj": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "themes": [t[0] for t in THEMES],
    "actus": actualites(),
    "pages": [scraper_page(*p) for p in PAGES],
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"data.json mis à jour : {len(data['actus'])} articles.")
