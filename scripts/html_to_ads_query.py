#!/usr/bin/env python3
"""
Ajuda a migrar as listas antigas para o ADS (use uma vez só).

Lê uma página HTML antiga e imprime uma busca para colar no ADS.
No ADS: cole a busca, confira se o número de resultados bate,
selecione todos e use "Add to library".

Uso: python scripts/html_to_ads_query.py MWStructure_papers.html
"""
import html
import re
import sys
from html.parser import HTMLParser


class LinkParser(HTMLParser):
    """Coleta (href, texto) de cada link dentro de <li>."""

    def __init__(self):
        super().__init__()
        self.links, self._href, self._text, self._in_li = [], None, [], False

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self._in_li = True
        elif tag == "a" and self._in_li:
            self._href, self._text = dict(attrs).get("href", ""), []

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, "".join(self._text).strip()))
            self._href = None
        elif tag == "li":
            self._in_li = False

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)


def to_query(url, text):
    if m := re.search(r"adsabs\.harvard\.edu/abs/([^/?#]+)", url):
        return f'identifier:"{html.unescape(m.group(1))}"'
    if m := re.search(r"arxiv\.org/(?:abs|pdf)/([^?#]+?)(?:v\d+)?(?:\.pdf)?$", url):
        return f'identifier:"arXiv:{m.group(1)}"'
    if m := re.search(r"(?:iopscience\.iop\.org/article|doi\.org)/(10\.[^?#]+?)/?(?:/meta|/pdf)?$", url):
        return f'doi:"{m.group(1)}"'
    if m := re.search(r"aanda\.org/articles/aa/\w+/\d{4}/\d{2}/aa(\d+)-(\d{2})", url):
        return f'doi:"10.1051/0004-6361/20{m.group(2)}{m.group(1)}"'
    if m := re.search(r"academic\.oup\.com/mnras/article/(\d+)/\d+/(\d+)/", url):
        return f'(bibstem:"MNRAS" volume:"{m.group(1)}" page:"{m.group(2)}")'
    # Sem identificador no link: busca pelo título (sem o "(Autor et al. ano)" do final)
    title = re.sub(r"\s*\([^()]*\d{4}\)\s*$", "", text).replace('"', "")
    print(f"  aviso: sem identificador, buscando pelo título -> {title}", file=sys.stderr)
    return f'title:"{title}"'


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for path in sys.argv[1:]:
        parser = LinkParser()
        with open(path, encoding="utf-8") as f:
            parser.feed(f.read())
        papers = [(u, t) for u, t in parser.links if u.startswith("http")]
        print(f"\n# {path}: {len(papers)} papers", file=sys.stderr)
        print(" OR ".join(to_query(u, t) for u, t in papers))


if __name__ == "__main__":
    main()
