"""
scraper.py — Motor de scraping de docs_to_book
Soporta modo estático (requests) y modo JS (Playwright).
"""

import re
import json
import time
import logging
import requests
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from markdownify import markdownify as md

log = logging.getLogger("scraper")

# ══════════════════════════════════════════════════════════════
#  PDF
# ══════════════════════════════════════════════════════════════

PDF_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono&display=swap');

* { box-sizing: border-box; }

body {
    font-family: 'Inter', 'Segoe UI', sans-serif;
    font-size: 13px;
    line-height: 1.7;
    color: #1a1a2e;
    max-width: 860px;
    margin: 0 auto;
    padding: 20px 40px;
}

h1 { font-size: 2em;   color: #0f3460; border-bottom: 3px solid #0f3460; padding-bottom: 8px; margin-top: 48px; }
h2 { font-size: 1.5em; color: #16213e; border-bottom: 1px solid #cdd6e0; padding-bottom: 4px; margin-top: 36px; }
h3 { font-size: 1.2em; color: #1a1a2e; margin-top: 28px; }
h4, h5, h6 { color: #444; margin-top: 20px; }

a { color: #0f3460; }

code {
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 0.85em;
    background: #f0f4f8;
    border: 1px solid #d0dce8;
    border-radius: 4px;
    padding: 1px 5px;
}

pre {
    background: #1e1e2e;
    color: #cdd6f4;
    border-radius: 8px;
    padding: 16px 20px;
    overflow-x: auto;
    margin: 16px 0;
    line-height: 1.5;
}

pre code {
    background: none;
    border: none;
    padding: 0;
    color: inherit;
    font-size: 0.9em;
}

blockquote {
    border-left: 4px solid #0f3460;
    background: #f0f4f8;
    margin: 16px 0;
    padding: 10px 16px;
    color: #555;
    border-radius: 0 6px 6px 0;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
    font-size: 0.92em;
}
th {
    background: #0f3460;
    color: white;
    padding: 10px 14px;
    text-align: left;
}
td {
    padding: 8px 14px;
    border-bottom: 1px solid #dde3ea;
}
tr:nth-child(even) td { background: #f7f9fb; }

img {
    max-width: 100%;
    border-radius: 6px;
    margin: 12px 0;
}

hr {
    border: none;
    border-top: 2px solid #e0e8f0;
    margin: 40px 0;
}

@page {
    margin: 2.5cm 2cm;
    @bottom-center {
        content: counter(page) " / " counter(pages);
        font-size: 10px;
        color: #999;
    }
}
"""


def md_to_pdf(md_path: Path, pdf_path: Path, emit=None) -> Path:
    """
    Convierte un archivo Markdown a PDF usando WeasyPrint.
    Las imágenes referenciadas relativamente se resuelven desde el directorio del MD.
    """
    try:
        import markdown as md_lib
        from weasyprint import HTML, CSS
    except ImportError:
        raise RuntimeError(
            "WeasyPrint no está instalado. Ejecuta: pip install weasyprint markdown"
        )

    if emit:
        emit(0, 1, "📄 Convirtiendo Markdown → HTML...")

    md_text = md_path.read_text(encoding="utf-8")

    # MD → HTML (con extensiones para tablas, código y listas de tareas)
    html_body = md_lib.markdown(
        md_text,
        extensions=["tables", "fenced_code", "codehilite", "toc", "nl2br"],
    )

    # HTML completo con CSS embebido
    html_full = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>{md_path.stem}</title>
</head>
<body>
{html_body}
</body>
</html>"""

    if emit:
        emit(0, 1, "🖨️  Generando PDF...")

    # base_url apunta al directorio del MD para resolver imágenes relativas
    HTML(string=html_full, base_url=str(md_path.parent)).write_pdf(
        target=str(pdf_path),
        stylesheets=[CSS(string=PDF_CSS)],
    )

    size_kb = pdf_path.stat().st_size // 1024
    if emit:
        emit(1, 1, f"✅ PDF generado: {pdf_path.name} ({size_kb} KB)")

    return pdf_path


# ── Configuración ──────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
DELAY     = 0.6
MAX_PAGES = 200

# ══════════════════════════════════════════════════════════════
#  DETECCIÓN DE PLATAFORMA
# ══════════════════════════════════════════════════════════════

def detect_platform(soup: BeautifulSoup, url: str) -> str:
    html   = str(soup).lower()
    domain = urlparse(url).netloc

    if "readthedocs" in domain:
        return "readthedocs"
    if soup.find(attrs={"data-gitbook-asset": True}) or "gitbook" in domain:
        return "gitbook"
    if soup.find("meta", attrs={"name": "generator", "content": re.compile("mkdocs", re.I)}):
        return "mkdocs"
    if "docusaurus" in html:
        return "docusaurus"
    if soup.find(class_=re.compile(r"sphinx", re.I)) or "/_static/doctools.js" in html:
        return "sphinx"
    return "generic"

# ══════════════════════════════════════════════════════════════
#  SELECTORES POR PLATAFORMA
# ══════════════════════════════════════════════════════════════

PLATFORM_TOC = {
    "readthedocs": [".wy-menu-vertical", ".md-nav--primary", "nav[role='navigation']"],
    "gitbook":     ["aside", "[data-testid='page.desktopTableOfContents']", "[class*='TableOfContents']", "[class*='sidebar']"],
    "mkdocs":      [".md-nav--primary", ".md-sidebar--primary nav", ".bs-sidenav"],
    "docusaurus":  [".theme-doc-sidebar-container nav", "nav[aria-label='Docs sidebar']"],
    "sphinx":      [".sphinxsidebarwrapper", "div.sphinxsidebar"],
    "generic":     ["nav", "[class*='sidebar']", "[class*='toc']", "[class*='menu']", "[class*='navigation']"],
}

PLATFORM_CONTENT = {
    "readthedocs": [".wy-nav-content", ".rst-content", "article", "main"],
    "gitbook":     ["[class*='page-inner']", ".markdown-section", "main article", "main"],
    "mkdocs":      [".md-content article", ".md-content", "article", "main"],
    "docusaurus":  ["article", ".markdown", "main"],
    "sphinx":      [".document", "div[role='main']", "article"],
    "generic":     ["article", "main", "[class*='content']", "[role='main']"],
}

REMOVE_TAGS = ["script", "style", "nav", "footer", "header", "aside"]
REMOVE_SEL  = [".headerlink", "[class*='edit-this-page']",
               "[class*='feedback']", "[class*='pagination']"]

# ══════════════════════════════════════════════════════════════
#  FETCH — estático o JS
# ══════════════════════════════════════════════════════════════

def fetch_static(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        log.warning(f"fetch_static error {url}: {e}")
        return None


def fetch_js(url: str, pw_page) -> BeautifulSoup | None:
    """Usa una página de Playwright ya abierta para renderizar JS."""
    try:
        pw_page.goto(url, wait_until="networkidle", timeout=30000)
        html = pw_page.content()
        return BeautifulSoup(html, "html.parser")
    except Exception as e:
        log.warning(f"fetch_js error {url}: {e}")
        return None


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_-]+", "-", text).strip("-")[:60]

def same_domain(url: str, base: str) -> bool:
    return urlparse(url).netloc == urlparse(base).netloc

def normalize_url(url: str) -> str:
    """
    Clave de deduplicación: esquema+dominio+path sin trailing slash ni fragmentos.
    'https://docs.x.com/install/' == 'https://docs.x.com/install'
    """
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path.rstrip('/')}"

def find_toc_links(soup: BeautifulSoup, base_url: str, platform: str) -> list[dict]:
    """
    Extrae links del índice lateral una sola vez desde la home.
    Deduplica por URL normalizada (ignora trailing slash y fragmentos).
    """
    selectors = PLATFORM_TOC.get(platform, []) + PLATFORM_TOC["generic"]
    base_norm = normalize_url(base_url)

    for sel in selectors:
        nav = soup.select_one(sel)
        if not nav:
            continue

        links, seen = [], set()
        for a in nav.find_all("a", href=True):
            href  = urljoin(base_url, a["href"]).split("#")[0]
            norm  = normalize_url(href)
            title = a.get_text(strip=True) or "Sin título"

            if (
                norm not in seen
                and norm != base_norm          # Fix A: excluir la home
                and same_domain(href, base_url)
                and href
                and title
            ):
                seen.add(norm)
                links.append({"href": norm, "title": title})  # guardar URL normalizada

        if len(links) > 2:
            log.info(f"[{platform.upper()}] TOC encontrado: '{sel}' → {len(links)} páginas")
            return links

    # Fallback: links internos de la página
    log.warning("Sin nav clara — usando links internos de la home")
    seen, links = set(), []
    for a in soup.find_all("a", href=True):
        href  = urljoin(base_url, a["href"]).split("#")[0]
        norm  = normalize_url(href)
        title = a.get_text(strip=True)
        if (
            norm not in seen
            and norm != base_norm
            and same_domain(href, base_url)
            and len(title) > 2
        ):
            seen.add(norm)
            links.append({"href": norm, "title": title})
    return links[:MAX_PAGES]

# ══════════════════════════════════════════════════════════════
#  IMÁGENES
# ══════════════════════════════════════════════════════════════

def download_image(img_url: str, images_dir: Path) -> str | None:
    try:
        r = requests.get(img_url, headers=HEADERS, timeout=20, stream=True)
        r.raise_for_status()
        filename = Path(urlparse(img_url).path).name or "image"
        if "." not in filename[-6:]:
            ext = r.headers.get("content-type", "image/png").split("/")[-1].split(";")[0]
            filename = f"{filename}.{ext}"
        dest, counter = images_dir / filename, 1
        while dest.exists():
            dest = images_dir / f"{dest.stem}_{counter}{dest.suffix}"
            counter += 1
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return f"../images/{dest.name}"
    except Exception as e:
        log.warning(f"Imagen no descargada ({img_url[:60]}): {e}")
        return None

# ══════════════════════════════════════════════════════════════
#  EXTRACCIÓN Y CONVERSIÓN
# ══════════════════════════════════════════════════════════════

def extract_content(soup: BeautifulSoup, base_url: str,
                    images_dir: Path, platform: str) -> str:
    selectors = PLATFORM_CONTENT.get(platform, PLATFORM_CONTENT["generic"])
    content = None
    for sel in selectors:
        content = soup.select_one(sel)
        if content:
            break
    if not content:
        content = soup.find("body") or soup

    for tag in REMOVE_TAGS:
        for el in content.find_all(tag):
            el.decompose()
    for sel in REMOVE_SEL:
        for el in content.select(sel):
            el.decompose()

    downloaded = 0
    for img in content.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original") or ""
        if not src or src.startswith("data:"):
            continue
        local = download_image(urljoin(base_url, src), images_dir)
        if local:
            img["src"] = local
            downloaded += 1
    if downloaded:
        log.info(f"{downloaded} imagen(es) descargada(s)")

    text = md(str(content), heading_style="ATX", strip=["script", "style"])
    text = re.sub(r"\[¶\]\([^)]*\)", "", text)
    text = re.sub(r"\[\]\([^)]*\)", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

# ══════════════════════════════════════════════════════════════
#  PROCESO PRINCIPAL
# ══════════════════════════════════════════════════════════════

def process_docs(
    start_url: str,
    output_dir: str = "output",
    use_js: bool = False,
    export_pdf: bool = False,
    progress_cb=None,   # callback(current, total, message)
) -> dict:
    """
    Convierte documentación a Markdown.
    progress_cb(current, total, msg) se llama en cada paso para SSE / logging.
    Retorna dict con estadísticas.
    """
    out        = Path(output_dir)
    pages_dir  = out / "pages"
    images_dir = out / "images"
    for d in [out, pages_dir, images_dir]:
        d.mkdir(parents=True, exist_ok=True)

    def emit(current, total, msg):
        log.info(msg)
        if progress_cb:
            progress_cb(current, total, msg)

    emit(0, 1, f"🚀 Iniciando: {start_url}")

    # ── Playwright setup ───────────────────────────────────────
    pw_ctx = None
    pw_page = None
    if use_js:
        try:
            from playwright.sync_api import sync_playwright
            _pw = sync_playwright().start()
            pw_ctx = _pw.chromium.launch(headless=True)
            pw_page = pw_ctx.new_page()
            emit(0, 1, "🌐 Playwright (modo JS) activo")
        except ImportError:
            emit(0, 1, "⚠️  Playwright no instalado — usando modo estático")
            use_js = False

    fetch = (lambda url: fetch_js(url, pw_page)) if use_js else fetch_static

    # ── Estado persistente (resume si se interrumpe) ───────────
    state_path = out / "state.json"

    def load_state() -> dict:
        if state_path.exists():
            try:
                return json.loads(state_path.read_text())
            except Exception:
                pass
        return {"visited": [], "toc_entries": []}

    def save_state(visited_norms: set, entries: list):
        state_path.write_text(json.dumps({
            "visited":     list(visited_norms),
            "toc_entries": entries,
        }, ensure_ascii=False, indent=2))

    state       = load_state()
    # Fix B: visited usa URLs normalizadas, no exactas
    visited     = set(state["visited"])
    toc_entries = state["toc_entries"]

    if visited:
        emit(0, 1, f"♻️  Retomando — {len(visited)} página(s) ya procesadas")

    # ── Página principal ───────────────────────────────────────
    home = fetch(start_url)
    if not home:
        if pw_ctx:
            pw_ctx.close()
        raise RuntimeError("No se pudo acceder a la URL.")

    platform = detect_platform(home, start_url)
    emit(0, 1, f"🔍 Plataforma detectada: {platform.upper()}")

    # TOC se extrae UNA sola vez desde la home (Fix A)
    links = find_toc_links(home, start_url, platform)
    total = min(len(links), MAX_PAGES)
    emit(0, total, f"📋 {total} páginas en el índice")

    # ── Procesar páginas ───────────────────────────────────────
    for i, item in enumerate(links[:MAX_PAGES], 1):
        url   = item["href"]
        title = item["title"]
        norm  = normalize_url(url)   # Fix B: comparar normalizado

        if norm in visited:
            emit(i, total, f"[{i}/{total}] ⏭️  Ya procesada: {title[:55]}")
            continue

        emit(i, total, f"[{i}/{total}] {title[:65]}")

        soup = fetch(url)
        if not soup:
            continue

        content = extract_content(soup, url, images_dir, platform)
        if len(content) < 80:
            emit(i, total, "  ⚠️  Contenido muy corto, saltando")
            visited.add(norm)        # marcar para no reintentar
            save_state(visited, toc_entries)
            continue

        filename = f"{i:03d}-{slugify(title)}.md"
        (pages_dir / filename).write_text(
            f"# {title}\n\n> 🔗 {url}\n\n{content}\n", encoding="utf-8"
        )

        visited.add(norm)
        toc_entries.append({"title": title, "file": f"pages/{filename}", "url": url})
        save_state(visited, toc_entries)  # Fix C: guardar tras cada página

        emit(i, total, f"  ✅ {filename} ({len(content):,} chars)")

        if not use_js:
            time.sleep(DELAY)

    # ── Índice ─────────────────────────────────────────────────
    toc_lines = [
        f"# 📚 Índice\n",
        f"> Fuente: {start_url}  \n> Plataforma: **{platform.upper()}**\n",
    ]
    for idx, e in enumerate(toc_entries, 1):
        toc_lines.append(f"{idx}. [{e['title']}]({e['file']})")
    (out / "index.md").write_text("\n".join(toc_lines), encoding="utf-8")

    # ── Libro completo ─────────────────────────────────────────
    emit(total, total, "📖 Compilando book.md...")
    book = [f"# 📚 Documentación Completa\n\n> Fuente: {start_url}\n\n---\n\n"]
    for e in toc_entries:
        p = pages_dir / Path(e["file"]).name
        if p.exists():
            book.append(p.read_text(encoding="utf-8"))
            book.append("\n\n---\n\n")
    (out / "book.md").write_text("".join(book), encoding="utf-8")

    # ── Cleanup Playwright ─────────────────────────────────────
    if pw_ctx:
        pw_ctx.close()

    # state.json ya no es necesario — conversión completada
    if state_path.exists():
        state_path.unlink()

    imgs = len(list(images_dir.iterdir()))
    kb   = (out / "book.md").stat().st_size // 1024
    stats = {
        "platform": platform,
        "pages": len(toc_entries),
        "images": imgs,
        "book_kb": kb,
        "pdf_kb": None,
        "output_dir": str(out.resolve()),
    }

    # ── Exportar PDF (opcional) ────────────────────────────────
    if export_pdf:
        try:
            pdf_path = out / "book.pdf"
            md_to_pdf(
                md_path=out / "book.md",
                pdf_path=pdf_path,
                emit=emit,
            )
            stats["pdf_kb"] = pdf_path.stat().st_size // 1024
        except Exception as e:
            emit(total, total, f"⚠️  PDF falló: {e}")

    emit(total, total, f"✅ Completado: {len(toc_entries)} páginas, {imgs} imágenes, {kb} KB MD"
         + (f", {stats['pdf_kb']} KB PDF" if stats["pdf_kb"] else ""))
    return stats
