"""
cli.py — Interfaz de línea de comandos para docs_to_book
Uso: python cli.py <URL> [-o carpeta] [--js] [--max-pages N]
"""

import argparse
import sys
from scraper import process_docs


def main():
    parser = argparse.ArgumentParser(
        prog="docs-to-book",
        description="📚 Convierte documentación técnica a un libro en Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python cli.py https://docs.python-requests.org/en/latest/
  python cli.py https://docs.mkdocs.org/ --js -o mkdocs_book
  python cli.py https://docs.docker.com/ --js --max-pages 50 -o docker_book
        """,
    )

    parser.add_argument("url",
        help="URL de la documentación")

    parser.add_argument("-o", "--output",
        default="output",
        help="Carpeta de salida (default: output)")

    parser.add_argument("--js",
        action="store_true",
        default=False,
        help="Usar Playwright para renderizar JS (necesario para GitBook, MkDocs moderno, Docusaurus)")

    parser.add_argument("--pdf",
        action="store_true",
        default=False,
        help="Exportar también a PDF (book.pdf) además del Markdown")

    parser.add_argument("--max-pages",
        type=int,
        default=200,
        metavar="N",
        help="Máximo de páginas a procesar (default: 200)")

    args = parser.parse_args()

    # Validar URL básica
    if not args.url.startswith(("http://", "https://")):
        print("❌ La URL debe comenzar con http:// o https://")
        sys.exit(1)

    if args.js:
        try:
            import playwright
        except ImportError:
            print("❌ Playwright no está instalado. Ejecuta:")
            print("   pip install playwright")
            print("   playwright install chromium")
            sys.exit(1)

    # Progress callback para CLI
    def progress_cb(current, total, msg):
        print(msg)

    print(f"\n{'='*55}")
    print(f"  📚 DOCS TO BOOK")
    print(f"{'='*55}")
    print(f"  URL    : {args.url}")
    print(f"  Output : {args.output}")
    print(f"  Modo   : {'🌐 JS (Playwright)' if args.js else '⚡ Estático (requests)'}")
    print(f"  Export : {'📄 MD + PDF' if args.pdf else '📝 Solo Markdown'}")
    print(f"  Límite : {args.max_pages} páginas")
    print(f"{'='*55}\n")

    try:
        stats = process_docs(
            start_url=args.url,
            output_dir=args.output,
            use_js=args.js,
            export_pdf=args.pdf,
            progress_cb=progress_cb,
        )

        print(f"""
╔══════════════════════════════════════════════╗
║  ✅  ¡Conversión completada!                 ║
╠══════════════════════════════════════════════╣
║  🔍  Plataforma : {stats['platform'].upper():<26} ║
║  📝  book.md   : {stats['book_kb']:>5} KB                      ║
║  📄  book.pdf  : {str(stats['pdf_kb'])+'KB' if stats.get('pdf_kb') else 'no generado':<28} ║
║  🖼️   Imágenes : {stats['images']:>5}                          ║
║  📄  Páginas   : {stats['pages']:>5}                          ║
║  📁  Carpeta   : {stats['output_dir'][:26]:<26} ║
╚══════════════════════════════════════════════╝
""")
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrumpido por el usuario.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
