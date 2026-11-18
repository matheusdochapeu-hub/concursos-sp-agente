"""Checa os assets de PWA/loja que precisam existir e estar coerentes.

Roda em CI e localmente sem rede: valida manifest, ícones, service worker e a
política de privacidade (exigida pela Google Play quando há coleta de dados).
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"


class TestAssetsPwa(unittest.TestCase):
    def test_manifest_completo(self):
        manifesto = json.loads((DOCS / "manifest.webmanifest").read_text(encoding="utf-8"))

        for campo in ("name", "short_name", "start_url", "scope", "display", "icons", "theme_color"):
            self.assertIn(campo, manifesto, f"manifest sem campo {campo}")
        self.assertIn(manifesto["display"], {"standalone", "minimal-ui", "fullscreen"})
        self.assertFalse(manifesto.get("prefer_related_applications", False))

        tamanhos = {i.get("sizes") for i in manifesto["icons"]}
        self.assertIn("192x192", tamanhos)
        self.assertIn("512x512", tamanhos)
        self.assertTrue(
            any(i.get("purpose") == "maskable" for i in manifesto["icons"]),
            "falta ícone maskable (a Play recorta o ícone em círculo)",
        )
        # Todo ícone do manifest precisa existir em docs/
        for icone in manifesto["icons"]:
            caminho = DOCS / icone["src"].lstrip("./")
            self.assertTrue(caminho.exists(), f"ícone ausente: {caminho.name}")

    def test_icones_existem_no_tamanho_certo(self):
        try:
            from PIL import Image
        except ImportError:  # Pillow é opcional para rodar a suíte
            self.skipTest("Pillow indisponível")

        for nome, lado in (
            ("icon-192.png", 192),
            ("icon-512.png", 512),
            ("icon-512-maskable.png", 512),
            ("apple-touch-icon.png", 180),
        ):
            caminho = DOCS / nome
            self.assertTrue(caminho.exists(), f"faltando {nome}")
            with Image.open(caminho) as img:
                self.assertEqual(img.size, (lado, lado), f"{nome} fora do tamanho")

    def test_service_worker_precacheia_o_essencial(self):
        sw = (DOCS / "sw.js").read_text(encoding="utf-8")
        self.assertRegex(sw, r'CACHE_NAME\s*=\s*"[^"]+"')
        for asset in ("./index.html", "./privacidade.html", "./manifest.webmanifest", "./icon-512-maskable.png"):
            self.assertIn(asset, sw, f"{asset} fora do precache")
        # Só intercepta a própria origem (OAuth do Google e planilha passam direto).
        self.assertIn("reqUrl.origin !== self.location.origin", sw)

    def test_privacidade_publicada_e_linkada(self):
        pagina = DOCS / "privacidade.html"
        self.assertTrue(pagina.exists())
        texto = pagina.read_text(encoding="utf-8")
        for termo in ("LGPD", "dados", "Google", "PCI Concursos"):
            self.assertIn(termo, texto)
        self.assertIn("privacidade.html", (DOCS / "index.html").read_text(encoding="utf-8"))

    def test_assets_da_play_store(self):
        self.assertTrue((REPO / "play-store" / "README.md").exists())
        self.assertTrue((REPO / "play-store" / "assetlinks.json.example").exists())
        for nome in ("icon-play-512.png", "feature-graphic-1024x500.png"):
            self.assertTrue((REPO / "play-store" / "assets" / nome).exists(), f"faltando {nome}")

    def test_html_nao_expoe_webhook(self):
        html = (DOCS / "index.html").read_text(encoding="utf-8")
        # Nenhuma URL de Apps Script embutida por padrão (só via secret no build).
        self.assertIsNone(re.search(r"script\.google\.com/macros/s/[A-Za-z0-9_-]{20,}", html))


if __name__ == "__main__":
    unittest.main()
