#!/usr/bin/env python3
import os
import mimetypes
from canvasapi import Canvas
from bs4 import BeautifulSoup
from pathlib import Path

API_URL = os.environ["CANVAS_URL"].rstrip("/")
API_KEY = os.environ["CANVAS_TOKEN"]
COURSE_ID = int(os.environ["CANVAS_COURSE_ID"])

canvas = Canvas(API_URL, API_KEY)
course = canvas.get_course(COURSE_ID)
site_dir = Path("site")

# Carpeta raíz para assets en Canvas
ASSETS_FOLDER = "mkdocs-assets"
uploaded = {}  # local_path → URL pública

print("1. Limpiando páginas antiguas [Docs]...")
for page in course.get_pages():
    if page.title.startswith("[Docs]"):
        if getattr(page, "front_page", False):
            page.edit(wiki_page={"front_page": False})
        page.delete()

def create_folder_if_needed(folder_path):
    """Crea carpetas en Canvas si no existen"""
    parts = [p for p in folder_path.split("/") if p]
    current_path = ""
    for part in parts:
        current_path += f"{part}/"
        # Buscar carpeta existente
        folders = course.get_folders()
        folder = next((f for f in folders if f.full_name == current_path.strip("/")), None)
        if not folder:
            # Crear carpeta
            new_folder = course.create_folder(folder={"name": part, "parent_folder_path": current_path.rstrip(part + "/")})
            print(f"   📁 Creada carpeta: {part}")
        folders = course.get_folders()  # Refrescar lista

def upload_asset(local_path: Path) -> str:
    if str(local_path) in uploaded:
        return uploaded[str(local_path)]

    relative_folder = str(local_path.relative_to(site_dir).parent).replace("\\", "/")
    canvas_folder = f"{ASSETS_FOLDER}/{relative_folder}" if relative_folder != "." else ASSETS_FOLDER

    # Crear carpetas si es necesario
    create_folder_if_needed(canvas_folder)

    # Paso 1: Obtener URL de upload (iniciar el upload)
    upload_url, upload_params = course.create_file_upload(
        filename=local_path.name,
        parent_folder_path=canvas_folder,
        content_type=mimetypes.guess_type(local_path)[0] or "application/octet-stream",
        on_duplicate="overwrite"
    )

    # Paso 2: Completar el upload con requests
    import requests
    with open(local_path, "rb") as f:
        response = requests.post(upload_url, files=upload_params, headers={"Authorization": f"Bearer {API_KEY}"})
    
    if response.status_code != 200:
        print(f"✗ Falló subida de {local_path.name}: {response.text}")
        return str(local_path)

    # Obtener la URL pública del archivo subido
    file_id = response.json().get("id")
    if file_id:
        canvas_file = course.get_file(file_id)
        public_url = canvas_file.public_url if hasattr(canvas_file, "public_url") else f"{API_URL}/courses/{COURSE_ID}/files/{file_id}/download"
        uploaded[str(local_path)] = public_url
        print(f"   ↑ {local_path.relative_to(site_dir)} → {public_url}")
        return public_url
    else:
        print(f"✗ No se obtuvo ID del archivo: {local_path.name}")
        return str(local_path)

print("\n2. Subiendo assets (css/js/img/font)...")
for asset in site_dir.rglob("*"):
    if asset.is_file() and asset.suffix.lower() != ".html":
        upload_asset(asset)

print("\n3. Subiendo páginas HTML con rutas corregidas...\n")
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

    # Reemplazar rutas locales por URLs de Canvas
    for tag in soup.find_all(["link", "script", "img", "source"]):
        attr = "href" if tag.has_attr("href") else "src"
        src = tag.get(attr)
        if src and not src.startswith(("http", "#", "data:", "mailto:")):
            asset_path = html_file.parent / src.lstrip("./")
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
            existing = next((p for p in course.get_pages() if p.url == url_slug), None)
            if existing:
                existing.edit(wiki_page={"body": body})
                print(f"  ↻ {title} actualizada")
        else:
            print(f"  ✗ {title}: {e}")

print(f"\n¡PRO FINAL FUNCIONANDO! Revisa en Canvas:")
print(f"→ {API_URL}/courses/{COURSE_ID}/pages/inicio-mkdocs")
print(f"→ Archivos: {API_URL}/courses/{COURSE_ID}/files?folder=mkdocs-assets")