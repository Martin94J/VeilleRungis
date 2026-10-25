"""Récupère des infos sur Rungis et les écrit dans data.json."""
import json
import os
import datetime
from urllib.parse import urljoin, quote

import feedparser
import requests
from bs4 import BeautifulSoup

try:
    from googlenewsdecoder import gnewsdecoder  # retrouve le vrai lien de l'article
except ImportError:
    gnewsdecoder = None

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RungisInfoBot/1.0)"}

# ======================= À PERSONNALISER ==================================
# Thèmes de veille : ("nom du bouton", "recherche 1", "recherche 2", ...)
# Le premier texte est le nom affiché sur la page, les suivants sont les
# recherches lancées pour ce thème. Tu peux en mettre autant que tu veux.
#
# - La casse (majuscules/minuscules) n'a aucune importance pour la recherche.
# - Le nom du bouton s'affiche exactement comme tu l'écris.
# - Plusieurs mots : les deux doivent apparaître dans l'article.
# - Expression exacte : entoure-la de guillemets, à l'intérieur des apostrophes.
#       '"Rungis Wissous"'
# - L'un OU l'autre : utilise OR en majuscules.
#       "Wissous OR Chevilly-Larue"
THEMES = [
    ("Ville", "ville de Rungis", "Mairie de Rungis", "Rungis Wissous",
     "Bruno Marcillaud", "Maire de Rungis", "Parking Rungis Wissous"),
    ("Acteurs", "Semmaris", "Sogaris Rungis", "Orly Rungis", "Entreprise Rungis", "Marché de Rungis"),
]

# Ancienneté maximale des articles (ex. 7d = 7 jours, 30d = 30 jours)
PERIODE = "30d"
ARTICLES_PAR_RECHERCHE = 6

# Nombre maximum de nouveaux articles dont on cherche l'image à chaque passage
MAX_NOUVEAUX_IMAGES = 40

# Pages web à scraper : (nom affiché, adresse, sélecteur CSS des liens)
PAGES = [
    ("Site de la ville", "https://www.ville-rungis.fr", "h2 a, h3 a"),
]
# ==========================================================================


def charger_ancien():
    """Relit data.json pour ne pas refaire les recherches d'images déjà faites."""
    try:
        with open("data.json", encoding="utf-8") as f:
            ancien = json.load(f)
        return {
            a["id"]: {"lien": a["lien"], "image": a.get("image", "")}
            for a in ancien.get("actus", [])
            if a.get("id") and a["lien"] != a["id"]
        }
    except Exception:
        return {}


def lien_reel(url_google):
    """Transforme le lien Google Actualités en vrai lien vers l'article."""
    if not gnewsdecoder:
        return ""
    try:
        res = gnewsdecoder(url_google, interval=1)
        if res.get("status"):
            return res["decoded_url"]
    except Exception as erreur:
        print("Lien non décodé :", erreur)
    return ""


def trouver_image(url):
    """Lit la page de l'article et récupère son image principale (og:image)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10, stream=True)
        r.raise_for_status()
        contenu = r.raw.read(300_000, decode_content=True)
        r.close()
        soupe = BeautifulSoup(contenu, "html.parser")
        for attrs in (
            {"property": "og:image"},
            {"property": "og:image:url"},
            {"name": "twitter:image"},
        ):
            meta = soupe.find("meta", attrs=attrs)
            if meta and meta.get("content"):
                image = urljoin(r.url, meta["content"].strip())
                if image.startswith("http://"):
                    image = "https://" + image[len("http://"):]
                return image
    except Exception as erreur:
        print("Image introuvable :", erreur)
    return ""


def nettoyer_titre(titre, source):
    """Google Actualités ajoute ' - Nom du média' à la fin du titre."""
    suffixe = " - " + source
    if source and titre.endswith(suffixe):
        return titre[: -len(suffixe)]
    return titre


def actualites():
    """Actualités par thème via le flux RSS de Google Actualités."""
    articles, vus = [], set()
    for theme, *recherches in THEMES:
        for recherche in recherches:
            url = (
                "https://news.google.com/rss/search?q="
                + quote(f"{recherche} when:{PERIODE}")
                + "&hl=fr&gl=FR&ceid=FR:fr"
            )
            try:
                flux = feedparser.parse(url)
                for e in flux.entries[:ARTICLES_PAR_RECHERCHE]:
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
                            "id": e.link,
                            "titre": titre,
                            "lien": e.link,
                            "image": "",
                            "source": source,
                            "date": date_iso,
                            "theme": theme,
                        }
                    )
            except Exception as erreur:
                print(f"Erreur recherche « {recherche} » :", erreur)
    articles.sort(key=lambda a: a["date"], reverse=True)

    # Images : on réutilise celles déjà trouvées, on cherche seulement les nouvelles
    ancien = charger_ancien()
    nouveaux = 0
    for a in articles:
        if a["id"] in ancien:
            a["lien"] = ancien[a["id"]]["lien"]
            a["image"] = ancien[a["id"]]["image"]
        elif nouveaux < MAX_NOUVEAUX_IMAGES:
            nouveaux += 1
            reel = lien_reel(a["id"])
            if reel:
                a["lien"] = reel
                a["image"] = trouver_image(reel)
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
    "themes": list(dict.fromkeys(t[0] for t in THEMES)),
    "actus": actualites(),
    "pages": [scraper_page(*p) for p in PAGES],
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

avec_image = sum(1 for a in data["actus"] if a["image"])
print(f"data.json mis à jour : {len(data['actus'])} articles, {avec_image} avec image.")
