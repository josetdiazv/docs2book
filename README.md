# 📚 Docs to Book

Convierte documentación técnica en línea a un libro estructurado en Markdown,
con imágenes descargadas y listo para exportar a PDF.

Soporta **ReadTheDocs · Sphinx · GitBook · MkDocs · Docusaurus** y cualquier
sitio con navegación lateral.

---

## ⚡ Inicio rápido

```bash
# 1. Clonar e instalar
git clone https://github.com/tu-usuario/bookfromdocs
cd bookfromdocs
pip install -r requirements.txt

# 2. (Solo si usas --js) Instalar el browser de Playwright
playwright install chromium

# 3. Convertir una documentación
python cli.py https://docs.python-requests.org/en/latest/

# 4. O levanta la API
uvicorn api:app --reload --port 8000
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
| `--js` | Usa Playwright para sitios que renderizan con JavaScript | desactivado |
| `--max-pages N` | Límite de páginas a procesar | `200` |

### Ejemplos

```bash
# Documentación estática (Sphinx / RTD clásico)
python cli.py https://docs.python-requests.org/en/latest/ -o requests_book

# Sitio con JavaScript (MkDocs moderno, GitBook, Docusaurus)
python cli.py https://docs.mkdocs.org/ --js -o mkdocs_book

# Limitar páginas
python cli.py https://docs.docker.com/ --js --max-pages 50 -o docker_book
```

### Output generado

```
output/
├── index.md          ← índice navegable con links a cada página
├── book.md           ← todo el contenido en un solo archivo
├── images/           ← imágenes descargadas (referenciadas relativamente)
└── pages/
    ├── 001-intro.md
    ├── 002-quickstart.md
    └── ...
```

---

## 🌐 API (FastAPI + Uvicorn)

```bash
uvicorn api:app --reload --port 8000
# Documentación interactiva: http://localhost:8000/docs
```

### Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/` | Info y lista de endpoints |
| `POST` | `/convert` | Inicia una conversión |
| `GET` | `/jobs` | Lista todos los jobs |
| `GET` | `/jobs/{id}` | Estado completo de un job |
| `GET` | `/jobs/{id}/stream` | Progreso en tiempo real (SSE) |
| `GET` | `/jobs/{id}/download` | Descarga el libro como ZIP |

### Ejemplo: convertir via API

```bash
# Iniciar conversión
curl -X POST http://localhost:8000/convert \
  -H "Content-Type: application/json" \
  -d '{"url": "https://docs.python-requests.org/en/latest/", "use_js": false}'

# Respuesta
{
  "job_id": "abc-123",
  "status": "pending",
  "stream_url": "/jobs/abc-123/stream",
  "download_url": "/jobs/abc-123/download"
}

# Ver progreso (SSE)
curl -N http://localhost:8000/jobs/abc-123/stream

# Descargar ZIP cuando termine
curl -OJ http://localhost:8000/jobs/abc-123/download
```

### Ejemplo JavaScript (EventSource)

```javascript
const res = await fetch('/convert', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ url: 'https://docs.python-requests.org/', use_js: false })
});
const { job_id, stream_url } = await res.json();

// Escuchar progreso en tiempo real
const es = new EventSource(stream_url);
es.onmessage = (e) => console.log(e.data);
es.addEventListener('done', () => {
  es.close();
  window.location = `/jobs/${job_id}/download`;
});
```

---

## 🔍 Plataformas soportadas

| Plataforma | Modo recomendado | Detección |
|------------|-----------------|-----------|
| Sphinx / RTD clásico | `estático` | dominio `readthedocs.io` o clase `sphinx` |
| ReadTheDocs (Material) | `estático` | selector `.wy-menu-vertical` |
| GitBook | `--js` | dominio `gitbook.io/com` |
| MkDocs (Material) | `--js` | meta generator `mkdocs` |
| Docusaurus | `--js` | string `docusaurus` en HTML |
| Genérico | `estático` | fallback a `nav`, `sidebar`, `toc` |

---

## 🏗️ Estructura del proyecto

```
bookfromdocs/
├── scraper.py        ← motor principal (detección, scraping, conversión)
├── cli.py            ← interfaz de línea de comandos
├── api.py            ← servidor FastAPI con jobs y SSE
├── requirements.txt
├── README.md
└── output/           ← carpeta de salida (generada automáticamente)
```

---

## 🗺️ Roadmap

- [ ] Exportación directa a PDF (via `pandoc` o `weasyprint`)
- [ ] Soporte para autenticación (docs privados)
- [ ] UI web con progreso en tiempo real
- [ ] Persistencia de jobs en Redis
- [ ] Docker Compose listo para producción

---

## 📄 Licencia

MIT

> Proyecto: [doc2book.diaz.com.ve](https://bookfromdocs.com)
