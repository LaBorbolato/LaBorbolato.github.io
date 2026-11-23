/*
  Monta as listas de papers a partir de data/papers.json.

  Nas páginas HTML:
    <div data-papers="structure"></div>               lista da categoria, agrupada por ano
    <div data-papers="recent" data-limit="10"></div>  últimos papers adicionados (todas as categorias)
    <input type="text" data-papers-search>            campo de busca (opcional)
    <span data-papers-updated></span>                 data da última atualização (opcional)
*/
(function () {
  "use strict";

  var DATA_URL = "data/papers.json";
  var CATEGORIES = {
    reviews: { label: "Reviews", page: "Reviews_papers.html" },
    formation_structure: { label: "Milky Way Structure and Formation", page: "MWStructure_papers.html" },
    chemical: { label: "Chemical Evolution, Stellar Abundances and Stellar Ages", page: "ChemicalEvolution_papers.html" },
    firststars: { label: "First Stars", page: "FirstStars_papers.html" }
  };

  // Estilos mínimos para os links ADS/arXiv e o campo de busca (pode mover para main.css)
  var style = document.createElement("style");
  style.textContent =
    ".paper-meta { font-size: 0.8em; white-space: nowrap; }" +
    ".paper-meta a { margin-left: 0.5em; }" +
    "[data-papers-search] { margin-bottom: 2em; }";
  document.head.appendChild(style);

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function link(href, text) {
    return '<a href="' + esc(href) + '" target="_blank" rel="noopener">' + text + "</a>";
  }

  // Um <li> no mesmo formato que você já usava: "Título (Autor et al. Ano)"
  function item(p, showCategories) {
    var meta = p.ads && p.ads !== p.url ? [link(p.ads, "ADS")] : [];
    if (p.arxiv) meta.push(link("https://arxiv.org/abs/" + p.arxiv, "arXiv"));
    if (showCategories) {
      p.categories.forEach(function (c) {
        if (CATEGORIES[c]) meta.push('<a href="' + CATEGORIES[c].page + '">' + esc(CATEGORIES[c].label) + "</a>");
      });
    }
    // p.title já vem sanitizado pelo update_papers.py (pode ter <sub>/<sup>)
    return "<li>" + link(p.url, p.title + " (" + esc(p.authors) + " " + esc(p.year) + ")") +
      ' <span class="paper-meta">' + meta.join("") + "</span></li>";
  }

  function renderCategory(el, papers, query) {
    var category = el.getAttribute("data-papers");
    var q = query.trim().toLowerCase();
    var list = papers.filter(function (p) {
      return p.categories.indexOf(category) !== -1 && (!q || p._search.indexOf(q) !== -1);
    });
    if (!list.length) {
      el.innerHTML = "<p>" + (q ? "No papers match “" + esc(query.trim()) + "”." : "No papers in this category yet.") + "</p>";
      return;
    }
    var years = [];
    list.forEach(function (p) { if (years.indexOf(p.year) === -1) years.push(p.year); });
    years.sort(function (a, b) { return b - a; });
    el.innerHTML = years.map(function (y) {
      var items = list.filter(function (p) { return p.year === y; }).map(function (p) { return item(p, false); });
      return '<h4><span style="color: #ff961f">' + esc(y) + "</span></h4><ul>" + items.join("") + "</ul>";
    }).join("");
  }

  function renderRecent(el, papers) {
    var limit = parseInt(el.getAttribute("data-limit") || "10", 10);
    var list = papers.slice().sort(function (a, b) {
      return (b.added || "").localeCompare(a.added || "") || (b.pubdate || "").localeCompare(a.pubdate || "");
    }).slice(0, limit);
    el.innerHTML = list.length
      ? "<ul>" + list.map(function (p) { return item(p, true); }).join("") + "</ul>"
      : "<p>No papers yet.</p>";
  }

  function plainText(htmlString) {
    var div = document.createElement("div");
    div.innerHTML = htmlString;
    return div.textContent;
  }

  function start(data) {
    var papers = data.papers.map(function (p) {
      p._search = (plainText(p.title) + " " + p.authors + " " + p.year).toLowerCase();
      return p;
    });
    var categoryEls = document.querySelectorAll("[data-papers]:not([data-papers='recent'])");
    var search = document.querySelector("[data-papers-search]");

    function renderAll() {
      var q = search ? search.value : "";
      categoryEls.forEach(function (el) { renderCategory(el, papers, q); });
    }
    renderAll();
    if (search) search.addEventListener("input", renderAll);

    document.querySelectorAll("[data-papers='recent']").forEach(function (el) { renderRecent(el, papers); });
    document.querySelectorAll("[data-papers-updated]").forEach(function (el) {
      el.textContent = data.updated ? "Last updated on " + data.updated + "." : "";
    });
  }

  fetch(DATA_URL, { cache: "no-cache" })
    .then(function (r) {
      if (!r.ok) throw new Error(r.status + " " + r.statusText);
      return r.json();
    })
    .then(start)
    .catch(function (err) {
      // Abrindo o HTML direto do computador (file://) o navegador bloqueia o fetch.
      // Para testar localmente: rode "python -m http.server" na pasta do site.
      console.error("papers.js: não consegui carregar " + DATA_URL, err);
      document.querySelectorAll("[data-papers]").forEach(function (el) {
        el.innerHTML = "<p>The paper list could not be loaded. Please reload the page.</p>";
      });
    });
})();
