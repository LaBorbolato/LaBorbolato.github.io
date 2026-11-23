#!/usr/bin/env python3
"""
Baixa os papers das suas bibliotecas do ADS e gera data/papers.json,
que é lido pelas páginas do site (assets/js/papers.js).

No GitHub: roda sozinho pelo workflow .github/workflows/update-papers.yml
Localmente: ADS_TOKEN=seu_token python scripts/update_papers.py
"""
import html
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

import requests

# ---------------------------------------------------------------------------
# Uma biblioteca do ADS por categoria do site.
# O ID está na URL da biblioteca: https://ui.adsabs.harvard.edu/user/libraries/<ID>
# A chave da esquerda é a mesma usada em data-papers="..." nas páginas HTML.
# Categorias com o ID ainda não preenchido são ignoradas.
# ---------------------------------------------------------------------------
LIBRARIES = {
    "reviews": "0fxGRbUyQy6hZBCLA3Yk1w",
    "formation_structure": "4FzGi46BTMSh7wWg9hOoaw",
    "chemical": "yQ2Ul0lsSAeFh9Qr5wEe-A",
    "firststars": "KmAzCGjFRpm8881DWEmcCA",
}

API = "https://api.adsabs.harvard.edu/v1"
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "papers.json"
FIELDS = "bibcode,title,author,year,pubdate,doi,identifier"
ALLOWED_TAGS = re.compile(r"&lt;(/?)(sub|sup|i|b|em)&gt;", re.IGNORECASE)


def ads_get(session, path, **params):
    r = session.get(f"{API}/{path}", params=params, timeout=60)
    if r.status_code == 401:
        sys.exit("O ADS recusou o token (401). Confira o secret ADS_TOKEN.")
    if r.status_code in (403, 404):
        sys.exit(f"O ADS não encontrou '{path}' ({r.status_code}). Confira o ID da biblioteca.")
    r.raise_for_status()
    return r.json()


def library_bibcodes(session, library_id):
    """Todos os bibcodes de uma biblioteca (a API devolve em páginas)."""
    bibcodes, start, rows = [], 0, 100
    while True:
        data = ads_get(session, f"biblib/libraries/{library_id}", start=start, rows=rows)
        batch = data.get("documents", [])
        bibcodes += batch
        total = data.get("metadata", {}).get("num_documents", len(bibcodes))
        start += rows
        if not batch or start >= total:
            return bibcodes


def fetch_metadata(session, bibcodes):
    """Título, autores, ano etc. de cada bibcode, em blocos de 50."""
    docs = []
    for i in range(0, len(bibcodes), 50):
        chunk = bibcodes[i:i + 50]
        # identifier: também encontra bibcodes antigos (ex.: o do arXiv antes da publicação)
        query = "identifier:(" + " OR ".join(f'"{b}"' for b in chunk) + ")"
        data = ads_get(session, "search/query", q=query, fl=FIELDS, rows=len(chunk))
        docs += data["response"]["docs"]
    return docs


def clean_title(raw):
    """Escapa o título, mas mantém <sub>, <sup>, <i> e <b> que o ADS às vezes usa."""
    text = html.escape(html.unescape(" ".join(raw.split())), quote=False)
    return ALLOWED_TAGS.sub(lambda m: f"<{m.group(1)}{m.group(2).lower()}>", text)


def short_authors(authors):
    names = [a.split(",")[0].strip() for a in authors] or ["Anonymous"]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} & {names[1]}"
    return f"{names[0]} et al."


def build_paper(doc):
    bibcode = doc["bibcode"]
    identifiers = doc.get("identifier", [])
    arxiv = next((i[6:] for i in identifiers if i.lower().startswith("arxiv:")), None)
    # DOIs 10.48550 são do próprio arXiv; o link principal vai para a revista quando houver
    journal_doi = next((d for d in doc.get("doi", []) if not d.startswith("10.48550/")), None)
    ads = f"https://ui.adsabs.harvard.edu/abs/{quote(bibcode, safe='')}/abstract"
    if journal_doi:
        url = f"https://doi.org/{journal_doi}"
    elif arxiv:
        url = f"https://arxiv.org/abs/{arxiv}"
    else:
        url = ads
    return {
        "title": clean_title((doc.get("title") or ["(untitled)"])[0]),
        "authors": short_authors(doc.get("author", [])),
        "year": str(doc.get("year", "")),
        "pubdate": doc.get("pubdate", "").replace("-00", "-01"),
        "url": url,
        "ads": ads,
        "arxiv": arxiv,
        "categories": [],
        "ids": sorted({bibcode, *identifiers}),
    }


def main():
    token = os.environ.get("ADS_TOKEN")
    if not token:
        sys.exit("Defina a variável ADS_TOKEN com o seu token da API do ADS.")

    libraries = {cat: lib for cat, lib in LIBRARIES.items() if lib and lib != "COLE_AQUI_O_ID"}
    if not libraries:
        sys.exit("Preencha pelo menos um ID de biblioteca em LIBRARIES no topo do script.")

    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token}"

    papers = {}
    for category, library_id in libraries.items():
        bibcodes = library_bibcodes(session, library_id)
        docs = fetch_metadata(session, bibcodes)
        print(f"{category}: {len(bibcodes)} na biblioteca, {len(docs)} encontrados no ADS")
        for doc in docs:
            paper = papers.setdefault(doc["bibcode"], build_paper(doc))
            if category not in paper["categories"]:
                paper["categories"].append(category)

    # Guarda a data em que cada paper apareceu pela primeira vez (seção "Recently added").
    old = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {"papers": []}
    seen = {i: p["added"] for p in old["papers"] for i in p.get("ids", []) if p.get("added")}
    first_sync = not seen  # na primeira vez, usa a data de publicação para não marcar tudo como novo
    today = date.today().isoformat()
    for paper in papers.values():
        known = next((seen[i] for i in paper["ids"] if i in seen), None)
        paper["added"] = known or (paper["pubdate"] if first_sync else today)

    new_list = sorted(papers.values(), key=lambda p: (p["pubdate"], p["title"]), reverse=True)
    if new_list == old["papers"]:
        print("Nada mudou; data/papers.json não foi alterado.")
        return

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated": today, "papers": new_list}
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"data/papers.json atualizado: {len(new_list)} papers.")


if __name__ == "__main__":
    main()
