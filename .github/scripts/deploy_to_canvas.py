#!/usr/bin/env python3
import os
from canvasapi import Canvas
from bs4 import BeautifulSoup
from pathlib import Path

# Configuración
API_URL = os.environ["CANVAS_URL"]
API_KEY = os.environ["CANVAS_TOKEN"]
COURSE_ID = int(os.environ["CANVAS_COURSE_ID"])

canvas = Canvas(API_URL, API_KEY)
course = canvas.get_course(COURSE_ID)

site_dir = Path("site")
pages_created = 0

print("Eliminando páginas antiguas del sitio MkDocs (excepto la Front Page)...")
for page in course.get_pages():
    if page.title.startswith("[MkDocs]"):
        # Si es la página de inicio del curso, la desmarcamos primero
        if getattr(page, "front_page", False):
            print(f"  Desmarcando Front Page: {page.title}")
            page.edit(wiki_page={"front_page": False})
        print(f"  Eliminada: {page.title}")
        page.delete()

print("\nSubiendo las nuevas páginas...")
for html_file in site_dir.rglob("*.html"):
    rel_path = html_file.relative_to(site_dir)
    url_slug = str(rel_path.parent / html_file.stem).replace("\\", "/")
    if url_slug == "index":
        url_slug = "inicio-mkdocs"

    title = "[Docs] " + " → ".join(part.capitalize() for part in rel_path.parts[:-1] if part != "index")
    if not title.strip("[Docs] "):
        title = "[Docs] Inicio"

    with open(html_file, encoding="utf-8") as f:
        body = f.read()

    # Pequeña limpieza de rutas relativas (suficiente para Material + MathJax)
    soup = BeautifulSoup(body, "html.parser")
    for tag in soup.find_all(["link", "script", "img"]):
        attr = "href" if tag.has_attr("href") else "src"
        if tag.get(attr) and not tag[attr].startswith(("http", "https", "#", "data:")):
            tag[attr] = tag[attr].lstrip("./")

    body = str(soup)

    # Crear o actualizar página
    try:
        page = course.create_page({
            "title": title,
            "body": body,
            "published": True,
            "url": url_slug,
            "front_page": (url_slug == "inicio-mkdocs")
        })
        print(f"  ✓ {title}")
        pages_created += 1
    except Exception as e:
        # Si ya existe, la actualizamos
        if "already exists" in str(e):
            existing = course.get_page(url_slug)
            existing.edit(wiki_page={"body": body, "published": True})
            print(f"  ↻ Actualizada: {title}")
        else:
            print(f"  ✗ Error {title}: {e}")

print(f"\n¡Terminado! {pages_created} páginas en tu curso Canvas")
print(f"URL directa → {API_URL}/courses/{COURSE_ID}/pages/inicio-mkdocs")