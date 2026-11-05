import os
from PIL import Image

src_path = r"C:\Users\matheus.ribeiro\.gemini\antigravity\brain\54d49c73-1d05-406f-a5f1-eabb999ca832\concursos_dog_mascot_grad_icon_1793906870478.jpg"
repo_dir = r"c:\Users\matheus.ribeiro\Desktop\Matheus\5. IA\concursos-sp-agente"
docs_dir = os.path.join(repo_dir, "docs")

assert os.path.exists(src_path), f"Source image not found: {src_path}"

img = Image.open(src_path).convert("RGBA")
print(f"Original image size: {img.size}")

# 1. Generate docs/icon-512.png
img_512 = img.resize((512, 512), Image.Resampling.LANCZOS)
img_512.save(os.path.join(docs_dir, "icon-512.png"), format="PNG", optimize=True)
print("Saved docs/icon-512.png")

# 2. Generate docs/icon-192.png
img_192 = img.resize((192, 192), Image.Resampling.LANCZOS)
img_192.save(os.path.join(docs_dir, "icon-192.png"), format="PNG", optimize=True)
print("Saved docs/icon-192.png")

# 3. Generate docs/apple-touch-icon.png (180x180)
img_180 = img.resize((180, 180), Image.Resampling.LANCZOS)
img_180.save(os.path.join(docs_dir, "apple-touch-icon.png"), format="PNG", optimize=True)
print("Saved docs/apple-touch-icon.png")

# 4. Generate multi-resolution docs/favicon.ico (16, 32, 48, 64)
fav_sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
img.save(os.path.join(docs_dir, "favicon.ico"), format="ICO", sizes=fav_sizes)
print("Saved docs/favicon.ico")

# 5. Also copy master into data or scripts for persistence
os.makedirs(os.path.join(repo_dir, "data"), exist_ok=True)
master_dest = os.path.join(repo_dir, "data", "concursos_dog_logo_master.jpg")
img.convert("RGB").save(master_dest, quality=95)
print(f"Saved master copy to {master_dest}")

print("All icon assets generated successfully!")
