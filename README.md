# 📚 Docs to Book

Convierte documentación técnica en línea a un libro estructurado en Markdown y PDF,
con imágenes descargadas localmente y soporte de resume si el proceso se interrumpe.

Soporta **ReadTheDocs · Sphinx · GitBook · MkDocs · Docusaurus** y cualquier sitio con navegación lateral.

---

## ⚡ Inicio rápido

```bash
# 1. Clonar e instalar (crea .venv automáticamente)
git clone https://github.com/tu-usuario/bookfromdocs
cd bookfromdocs
make install

# 2. Solo si usas --js (sitios que renderizan con JavaScript)
make install-js

# 3. Convertir una documentación
make convert URL=https://docs.python-requests.org/en/latest/

# 4. O levanta la API
make dev
```

---

## 🖥️ CLI

```
python cli.py <URL> [opciones]
```

| Flag | Descripción | Default |
|------|-------------|---------|
| `URL` | URL de la documentación | requerido |
| `-o, --output` | Carpeta de salida | `output/` |
| `--js` | Playwright para sitios que renderizan con JavaScript | desactivado |
| `--pdf` | Exportar también a `book.pdf` además del Markdown | desactivado |
| `--max-pages N` | Límite de páginas a procesar | `200` |

### Ejemplos

```bash
# Documentación estática → solo Markdown
python cli.py https://docs.python-requests.org/en/latest/ -o requests_book

# Documentación estática → Markdown + PDF
python cli.py https://docs.python-requests.org/en/latest/ --pdf -o requests_book

# Sitio con JavaScript (MkDocs, GitBook, Docusaurus) → Markdown + PDF
python cli.py https://docs.mkdocs.org/ --js --pdf -o mkdocs_book

# Limitar páginas
python cli.py https://docs.docker.com/ --js --max-pages 50 -o docker_book
```

### Output generado

```
output/
├── index.md          ← índice navegable con links a cada página
├── book.md           ← todo el contenido en un solo archivo
├── book.pdf          ← libro PDF (solo con --pdf)
├── images/           ← imágenes descargadas (rutas relativas)
└── pages/
    ├── 001-quickstart.md
    ├── 002-advanced-usage.md
    └── ...
```

> **Resume automático**: si el proceso se interrumpe, al volver a ejecutar el mismo comando
> retoma desde donde quedó — saltando páginas ya procesadas.

---

## 🛠️ Makefile

| Comando | Descripción |
|---------|-------------|
| `make install` | Crea `.venv/` + instala dependencias |
| `make install-js` | Ídem + instala Playwright Chromium |
| `make dev` | API en modo desarrollo con hot-reload |
| `make start` | API en modo producción |
| `make convert URL=...` | CLI — solo Markdown, estático |
| `make convert-js URL=...` | CLI — solo Markdown, con JS |
| `make convert-pdf URL=...` | CLI — Markdown + PDF, estático |
| `make convert-js-pdf URL=...` | CLI — Markdown + PDF, con JS |
| `make test` | Verifica que los módulos importan OK |
| `make lint` | Linter con `ruff` |
| `make clean` | Borra `output/` |
| `make clean-all` | Borra `output/` + `.venv/` + caché |

Variables sobreescribibles: `PORT`, `URL`, `OUTPUT`, `WORKERS`.

```bash
make dev PORT=3000
make convert-pdf URL=https://docs.docker.com/ OUTPUT=docker_book
make start WORKERS=4
```

---

## 🌐 API (FastAPI + Uvicorn)

```bash
make dev
# Swagger interactivo: http://localhost:8000/docs
```

### Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/` | Info y lista de endpoints |
| `POST` | `/convert` | Inicia una conversión (retorna `job_id`) |
| `GET` | `/jobs` | Lista todos los jobs |
| `GET` | `/jobs/{id}` | Estado completo de un job |
| `GET` | `/jobs/{id}/stream` | Progreso en tiempo real (SSE) |
| `GET` | `/jobs/{id}/download` | Descarga el libro como ZIP |

### Body de `/convert`

```json
{
  "url": "https://docs.python-requests.org/en/latest/",
  "use_js": false,
  "export_pdf": false
}
```

### Ejemplo curl

```bash
# Iniciar conversión con PDF
curl -X POST http://localhost:8000/convert \
  -H "Content-Type: application/json" \
  -d '{"url": "https://docs.python-requests.org/en/latest/", "export_pdf": true}'

# Ver progreso (SSE)
curl -N http://localhost:8000/jobs/<job_id>/stream

# Descargar ZIP cuando termine
curl -OJ http://localhost:8000/jobs/<job_id>/download
```

### Ejemplo JavaScript (EventSource)

```javascript
const { job_id, stream_url } = await fetch('/convert', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ url: 'https://...', use_js: false, export_pdf: true })
}).then(r => r.json());

const es = new EventSource(stream_url);
es.onmessage = (e) => console.log(e.data);
es.addEventListener('done', () => {
  es.close();
  window.location = `/jobs/${job_id}/download`;
});
```

---

## 🔍 Plataformas soportadas

| Plataforma | Modo recomendado | Cómo se detecta |
|------------|-----------------|-----------------|
| Sphinx / RTD clásico | estático | clase `sphinx` o `/_static/doctools.js` |
| ReadTheDocs | estático | dominio `readthedocs.io` |
| GitBook | `--js` | dominio `gitbook.io/com` |
| MkDocs Material | `--js` | meta generator `mkdocs` |
| Docusaurus | `--js` | string `docusaurus` en HTML |
| Genérico | estático | fallback: `nav`, `sidebar`, `toc`, `menu` |

---

## 🏗️ Estructura del proyecto

```
bookfromdocs/
├── scraper.py        ← motor: detección, scraping, imágenes, PDF, resume
├── cli.py            ← interfaz de línea de comandos
├── api.py            ← servidor FastAPI con jobs, SSE y descarga ZIP
├── requirements.txt
├── Makefile
├── README.md
└── output/           ← carpeta de salida (generada automáticamente)
```

---

## 🗺️ Roadmap

- [x] Exportación a PDF (WeasyPrint)
- [x] Soporte Playwright para sitios JS
- [x] Resume automático si el proceso se interrumpe
- [x] Deduplicación robusta de URLs (trailing slash, fragmentos)
- [ ] Soporte para autenticación (docs privados)
- [ ] UI web con progreso en tiempo real
- [ ] Persistencia de jobs en Redis
- [ ] Docker Compose listo para producción

---

## 📄 Licencia

MIT — úsalo, modifícalo, véndelo.

> Proyecto: [doc2book.diaz.com.ve](https://bookfromdocs.com)