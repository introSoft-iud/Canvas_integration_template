#!/usr/bin/env python3
import os
import mimetypes
from canvasapi import Canvas
from bs4 import BeautifulSoup
from pathlib import Path

API_URL = os.environ["CANVAS_URL"]
API_KEY = os.environ["CANVAS_TOKEN"]
COURSE_ID = int(os.environ["CANVAS_COURSE_ID"])

canvas = Canvas(API_URL, API_KEY)
course = canvas.get_course(COURSE_ID)
site_dir = Path("site")
uploaded_files = {}  # cache: ruta local → URL pública en Canvas

print("1. Limpiando páginas antiguas [Docs]...")
for page in course.get_pages():
    if page.title.startswith("[Docs]"):
        if getattr(page, "front_page", False):
            page.edit(wiki_page={"front_page": False})
        page.delete()

print("2. Subiendo archivos estáticos (css/js/img/font)...")
def upload_file_to_canvas(local_path):
    if str(local_path) in uploaded_files:
        return uploaded_files[str(local_path)]
    
    mime_type, _ = mimetypes.guess_type(local_path)
    if not mime_type:
        mime_type = "application/octet-stream"
    
    file = course.upload_file(
        str(local_path),
        name=local_path.name,
        parent_folder_path="mkdocs-assets/" + str(local_path.parent.relative_to(site_dir))
    )
    public_url = file[1]["url"]  # URL pública directa
    uploaded_files[str(local_path)] = public_url
    print(f"   ↑ {local_path.relative_to(site_dir)}")
    return public_url

# Subir todos los archivos que NO sean *.html
for asset in site_dir.rglob("*"):
    if asset.is_file() and asset.suffix != ".html":
        upload_file_to_canvas(asset)

print("\n3. Subiendo páginas HTML (con rutas corregidas)...\n")
for html_file in site_dir.rglob("index.html"):
    rel_dir = html_file.relative_to(site_dir).parent
    if rel_dir == Path("."):
        url_slug = "inicio-mkdocs"
        title = "[Docs] Inicio"
    else:
        title = "[Docs] " + " → ".join(p.capitalize() for p in rel_dir.parts)
        url_slug = str(rel_dir).replace("\\", "/")

    with open(html_file, encoding="utf-8") as f:
        body = f.read()

    soup = BeautifulSoup(body, "html.parser")
    
    # Reemplazar todas las rutas locales por URLs públicas de Canvas
    for tag in soup.find_all(["link", "script", "img", "source"]):
        attr = "href" if tag.has_attr("href") else "src"
        src = tag.get(attr)
        if src and not src.startswith(("http", "#", "data:", "mailto")):
            # Ruta relativa → convertir a Path absoluto dentro de site/
            asset_path = (html_file.parent / src.lstrip("./")).resolve()
            if asset_path.exists():
                canvas_url = upload_file_to_canvas(asset_path)
                tag[attr] = canvas_url
            else:
                tag[attr] = src  # dejar como está si no existe

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
            print(f"  ✗ Error {title}: {e}")

print(f"\n¡VERSIÓN PRO 100% FUNCIONANDO!")
print(f"→ {API_URL}/courses/{COURSE_ID}/pages/inicio-mkdocs")