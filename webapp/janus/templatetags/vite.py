import json
import os
from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag
def vite_asset(path):
    """
    Template tag to include Vite assets.
    In DEBUG mode (unless VITE_DEV_MODE=False), it points to the Vite dev server.
    In production, it reads the manifest.json and returns the path to the built asset.
    """
    # Use dev server if VITE_DEV_MODE is explicitly True (independent of DEBUG)
    use_dev_server = getattr(settings, 'VITE_DEV_MODE', False)

    if use_dev_server:
        # Vite dev server URL
        base_url = "http://127.0.0.1:3000/static/dist/"
        
        client_script = f'<script type="module" src="{base_url}@vite/client"></script>'
        
        if path.endswith('.js'):
            asset_script = f'<script type="module" src="{base_url}src/{path}"></script>'
            return mark_safe(f"{client_script}\n{asset_script}")
        elif path.endswith('.css'):
            return mark_safe(f'<link rel="stylesheet" href="{base_url}src/{path}">')
        return mark_safe(client_script)

    # Production path
    manifest_path = os.path.join(settings.BASE_DIR, 'static', 'static', 'dist', '.vite', 'manifest.json')
    
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return mark_safe(f"<!-- Vite manifest not found at {manifest_path} -->")

    # In Vite manifest, the key is the source path relative to the root
    asset_key = f"src/{path}"
    asset_data = manifest.get(asset_key)
    
    if not asset_key in manifest:
        # try without src prefix
        asset_key = path
        asset_data = manifest.get(asset_key)

    if not asset_data:
        return mark_safe(f"<!-- Asset {path} not found in manifest -->")

    file_path = asset_data.get('file')
    css_files = asset_data.get('css', [])
    
    html = ""
    if file_path:
        html += f'<script type="module" src="{settings.STATIC_URL}dist/{file_path}"></script>'
    
    for css_file in css_files:
        html += f'<link rel="stylesheet" href="{settings.STATIC_URL}dist/{css_file}">'
        
    return mark_safe(html)
