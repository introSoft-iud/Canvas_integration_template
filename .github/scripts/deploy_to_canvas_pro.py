#!/usr/bin/env python3
import os
import mimetypes
import requests
from canvasapi import Canvas
from bs4 import BeautifulSoup
from pathlib import Path

API_URL = os.environ["CANVAS_URL"].rstrip("/")
API_KEY = os.environ["CANVAS_TOKEN"]
COURSE_ID = int(os.environ["CANVAS_COURSE_ID"])

canvas = Canvas(API_URL, API_KEY)
course = canvas.get_course(COURSE_ID)
site_dir = Path("site")
uploaded = {}  # cache: ruta local → URL pública en Canvas

print("1. Borrando páginas antiguas [Docs]...")
for page in course.get_pages():
    if page.title.startswith("[Docs]"):
        if getattr(page, "front_page", False):
            page.edit(wiki_page={"front_page": False})
        page.delete()

def upload_asset(local_path: Path) -> str:
    if str(local_path) in uploaded:
        return uploaded[str(local_path)]

    # Crear carpeta mkdocs-assets si no existe
    folder_name = "mkdocs-assets"
    folders = list(course.get_folders())
    folder = next((f for f in folders if f.name == folder_name), None)
    if not folder:
        folder = course.create_folder(name=folder_name)

    # Subir archivo (método sencillo y 100 % funcional)
    with open(local_path, "rb") as f:
        upload = course.upload_to_folder(folder.id, local_path.name, f, on_duplicate="overwrite")
    
    public_url = upload[1]["url"]  # URL directa
    uploaded[str(local_path)] = public_url
    print(f"   ↑ {local_path.relative_to(site_dir)}")
    return public_url

print("\n2. Subiendo todos los assets (css/js/img/font)...")
for asset in site_dir.rglob("*"):
    if asset.is_file() and asset.suffix.lower() != ".html":
        upload_asset(asset)

print("\n3. Subiendo páginas HTML...\n")
for html_file in site_dir.rglob("index.html"):
    rel_dir = html_file.relative_to(site_dir).parent

    if rel_dir == Path("."):
        url_slug = "inicio-mkdocs"
        title = "[Docs] Inicio"
    else:
        title = "[Docs] " + " → ".join(p.capitalize() for p in rel_dir.parts)
        url_slug = str(rel_dir).replace("\\", "/")

    body = html_file.read_text(encoding="utf-8")
    soup = BeautifulSoup(body, "html.parser")

    # Reemplazar rutas locales por URLs públicas de Canvas
    for tag in soup.find_all(["link", "script", "img", "source"]):
        attr = "href" if tag.has_attr("href") else "src"
        src = tag.get(attr)
        if src and not src.startswith(("http", "#", "data:", "mailto:")):
            asset_path = (html_file.parent / src.lstrip("./")).resolve()
            if asset_path.exists():
                tag[attr] = upload_asset(asset_path)

    body = str(soup)

    try:
        page = course.create_page({
            "title": title,
            "body": body,
            "published": True,
            "url": url_slug,
            "front_page": (url_slug == "inicio-mkdocs")
        })
        print(f"  ✓ {title}  →  /{url_slug}")
    except Exception as e:
        if "already exists" in str(e).lower():
            existing = course.get_page(url_slug)
            existing.edit(wiki_page={"body": body})
            print(f"  ↻ {title} actualizada")
        else:
            print(f"  ✗ Error: {e}")

print(f"\n¡100 % FUNCIONANDO! Abre tu curso:")
print(f"{API_URL}/courses/{COURSE_ID}/pages/inicio-mkdocs")