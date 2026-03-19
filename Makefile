.PHONY: venv install install-js dev start test convert convert-js convert-pdf convert-js-pdf lint clean clean-all help

# ── Variables ──────────────────────────────────────────────────
PORT     ?= 8000
URL      ?= https://docs.python-requests.org/en/latest/
OUTPUT   ?= output
WORKERS  ?= 1
VENV     := .venv
PYTHON   := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip
UVICORN  := $(VENV)/bin/uvicorn
PW       := $(VENV)/bin/playwright

# ══════════════════════════════════════════════════════════════
#  SETUP
# ══════════════════════════════════════════════════════════════

## Crea el entorno virtual
venv:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	@echo "✅ Entorno virtual creado en $(VENV)/"
	@echo "   Actívalo con: source $(VENV)/bin/activate"

## Crea venv + instala dependencias base (incluye PDF)
install: venv
	$(PIP) install -r requirements.txt
	@echo "✅ Dependencias instaladas"
	@echo ""
	@echo "  Para levantar el servidor : make dev"
	@echo "  Para convertir (MD)       : make convert URL=https://..."
	@echo "  Para convertir (MD+PDF)   : make convert-pdf URL=https://..."

## Crea venv + instala todo + browser Playwright (modo --js)
install-js: install
	$(PW) install chromium
	@echo "✅ Playwright + Chromium listos"

# ══════════════════════════════════════════════════════════════
#  SERVIDOR
# ══════════════════════════════════════════════════════════════

## Levanta el servidor en modo desarrollo (hot-reload)
dev:
	$(UVICORN) api:app --reload --port $(PORT)

## Levanta el servidor en modo producción
start:
	$(UVICORN) api:app --host 0.0.0.0 --port $(PORT) --workers $(WORKERS)

# ══════════════════════════════════════════════════════════════
#  CLI — Conversión
# ══════════════════════════════════════════════════════════════

## Solo Markdown — estático:           make convert URL=https://...
convert:
	$(PYTHON) cli.py $(URL) -o $(OUTPUT)

## Solo Markdown — con JS:             make convert-js URL=https://...
convert-js:
	$(PYTHON) cli.py $(URL) --js -o $(OUTPUT)

## Markdown + PDF — estático:          make convert-pdf URL=https://...
convert-pdf:
	$(PYTHON) cli.py $(URL) --pdf -o $(OUTPUT)

## Markdown + PDF — con JS:            make convert-js-pdf URL=https://...
convert-js-pdf:
	$(PYTHON) cli.py $(URL) --js --pdf -o $(OUTPUT)

# ══════════════════════════════════════════════════════════════
#  CALIDAD
# ══════════════════════════════════════════════════════════════

## Verifica que los módulos importan sin errores
test:
	@$(PYTHON) -c "import scraper; print('✅ scraper.py OK')"
	@$(PYTHON) -c "import api;     print('✅ api.py    OK')"
	@$(PYTHON) -c "import cli;     print('✅ cli.py    OK')"

## Corre el linter (requiere: pip install ruff)
lint:
	$(VENV)/bin/ruff check scraper.py api.py cli.py

# ══════════════════════════════════════════════════════════════
#  LIMPIEZA
# ══════════════════════════════════════════════════════════════

## Borra carpeta output/ y ZIPs/PDFs generados
clean:
	rm -rf output/
	@echo "🧹 output/ eliminado"

## Borra output/ + caché Python + entorno virtual
clean-all: clean
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf $(VENV)
	@echo "🧹 Todo limpio (incluyendo .venv/)"

# ══════════════════════════════════════════════════════════════
#  AYUDA
# ══════════════════════════════════════════════════════════════

## Muestra esta ayuda
help:
	@echo ""
	@echo "  📚 DOCS TO BOOK — Comandos disponibles"
	@echo "  ══════════════════════════════════════"
	@grep -E '^##' Makefile | sed 's/## /  /'
	@echo ""
	@echo "  Variables:"
	@echo "    PORT=$(PORT)      — puerto del servidor"
	@echo "    URL=$(URL)"
	@echo "    OUTPUT=$(OUTPUT)        — carpeta de salida"
	@echo "    WORKERS=$(WORKERS)         — workers en producción"
	@echo ""
	@echo "  Flujo inicial:"
	@echo "    make install        — instala todo (sin Playwright)"
	@echo "    make install-js     — instala todo + Playwright"
	@echo "    make dev            — API en localhost:$(PORT)"
	@echo ""
	@echo "  Combinaciones de flags:"
	@echo "    convert             — MD, estático"
	@echo "    convert-js          — MD, con JS"
	@echo "    convert-pdf         — MD + PDF, estático"
	@echo "    convert-js-pdf      — MD + PDF, con JS"
	@echo ""

.DEFAULT_GOAL := help
