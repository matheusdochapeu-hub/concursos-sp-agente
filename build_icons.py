"""
Gera os ícones do PWA e os assets exigidos pela Google Play a partir da arte-mestre.

Antes: caminhos absolutos de outra máquina (não rodava aqui nem no CI).
Agora: caminhos relativos ao repositório, com args opcionais.

Uso:
    python build_icons.py
    python build_icons.py --src data/concursos_dog_logo_master.jpg

Saídas em docs/:
    icon-192.png, icon-512.png          (PWA, "any")
    icon-512-maskable.png               (PWA/Play, area segura de 80%)
    apple-touch-icon.png, favicon.ico
Saídas em play-store/assets/:
    icon-play-512.png                   (ícone de loja 512x512)
    feature-graphic-1024x500.png        (gráfico de destaque obrigatório)
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
PLAY_ASSETS = ROOT / "play-store" / "assets"
DEFAULT_SRC = ROOT / "data" / "concursos_dog_logo_master.jpg"

# Fundo do ícone mascarado: canto superior esquerdo da própria arte (verde escuro).
FALLBACK_BG = (9, 56, 42)


def _cor_de_fundo(img: Image.Image) -> tuple[int, int, int]:
    px = img.convert("RGB").resize((8, 8)).load()
    try:
        r, g, b = px[1, 1]
        return (r, g, b)
    except Exception:
        return FALLBACK_BG


def _mascara_redonda(lado: int, raio: int, centro: tuple[int, int], suavidade: int = 26) -> Image.Image:
    """Máscara circular com borda suave, para o mascote fundir no fundo."""
    mask = Image.new("L", (lado, lado), 0)
    draw = ImageDraw.Draw(mask)
    x, y = centro
    draw.ellipse([x - raio, y - raio, x + raio, y + raio], fill=255)
    return mask.filter(ImageFilter.GaussianBlur(suavidade))


def _mascara_radial(lado: int) -> Image.Image:
    """Branco no centro, preto nas bordas — usado para fundir o fundo desfocado."""
    mask = Image.new("L", (lado, lado), 0)
    px = mask.load()
    centro = lado / 2.0
    raio = centro * 0.92
    for y in range(lado):
        for x in range(lado):
            d = ((x - centro) ** 2 + (y - centro) ** 2) ** 0.5
            v = 1.0 - max(0.0, min(1.0, d / raio))
            px[x, y] = int(255 * (v ** 0.7))
    return mask.filter(ImageFilter.GaussianBlur(18))


def _maskable(img: Image.Image, lado: int = 512, ocupacao: float = 0.72) -> Image.Image:
    """Fundo desfocado da própria arte + mascote em círculo dentro da área segura."""
    fundo = _cor_de_fundo(img)
    base = img.convert("RGB").resize((lado, lado), Image.Resampling.LANCZOS)
    base = base.filter(ImageFilter.GaussianBlur(34))
    tela = Image.composite(base, Image.new("RGB", (lado, lado), fundo), _mascara_radial(lado))

    interno = int(lado * ocupacao)
    reduzida = img.convert("RGB").resize((interno, interno), Image.Resampling.LANCZOS)
    pos = ((lado - interno) // 2, (lado - interno) // 2)
    mask = _mascara_redonda(interno, interno // 2 - 6, (interno // 2, interno // 2))
    tela.paste(reduzida, pos, mask)
    return tela


def _feature_graphic(img: Image.Image, largura: int = 1024, altura: int = 500) -> Image.Image:
    """Gráfico 1024x500 da Play: degradê da marca + mascote à direita, fundido na borda."""
    fundo = _cor_de_fundo(img)
    tela = Image.new("RGB", (largura, altura), fundo)
    draw = ImageDraw.Draw(tela)
    # degradê vertical suave
    for y in range(altura):
        f = y / max(altura - 1, 1)
        draw.line(
            [(0, y), (largura, y)],
            fill=(
                int(fundo[0] * (1 - 0.35 * f)),
                int(fundo[1] * (1 - 0.25 * f) + 30 * f),
                int(fundo[2] * (1 - 0.2 * f)),
            ),
        )

    mascote = img.convert("RGB").resize((altura, altura), Image.Resampling.LANCZOS)
    # máscara que apaga só a borda esquerda (o resto encosta no topo/rodapé/direita)
    mask = Image.new("L", (altura, altura), 255)
    fade = 150
    px = mask.load()
    for x in range(fade):
        valor = int(255 * (x / fade) ** 1.5)
        for y in range(altura):
            px[x, y] = valor
    tela.paste(mascote, (largura - altura, 0), mask)

    # faixa amarela da identidade (mesma do app)
    draw.rectangle([(0, altura - 26), (largura, altura)], fill=(254, 221, 0))
    return tela


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera ícones do PWA e assets da Play Store.")
    ap.add_argument("--src", default=str(DEFAULT_SRC), help="arte-mestre (jpg/png)")
    args = ap.parse_args()

    src = Path(args.src)
    if not src.exists():
        raise SystemExit(f"Arte-mestre não encontrada: {src}")
    if not src.is_absolute():
        src = (Path.cwd() / src).resolve() if (Path.cwd() / src).exists() else (ROOT / src)

    DOCS.mkdir(exist_ok=True)
    PLAY_ASSETS.mkdir(parents=True, exist_ok=True)

    img = Image.open(src).convert("RGBA")
    print(f"Arte-mestre: {src} ({img.width}x{img.height})")

    img.resize((512, 512), Image.Resampling.LANCZOS).save(DOCS / "icon-512.png", format="PNG", optimize=True)
    print("docs/icon-512.png")
    img.resize((192, 192), Image.Resampling.LANCZOS).save(DOCS / "icon-192.png", format="PNG", optimize=True)
    print("docs/icon-192.png")
    _maskable(img, 512).save(DOCS / "icon-512-maskable.png", format="PNG", optimize=True)
    print("docs/icon-512-maskable.png")
    img.resize((180, 180), Image.Resampling.LANCZOS).save(DOCS / "apple-touch-icon.png", format="PNG", optimize=True)
    print("docs/apple-touch-icon.png")
    img.save(DOCS / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print("docs/favicon.ico")

    img.resize((512, 512), Image.Resampling.LANCZOS).save(PLAY_ASSETS / "icon-play-512.png", format="PNG", optimize=True)
    print("play-store/assets/icon-play-512.png")
    _feature_graphic(img).save(PLAY_ASSETS / "feature-graphic-1024x500.png", format="PNG", optimize=True)
    print("play-store/assets/feature-graphic-1024x500.png")

    print("OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
