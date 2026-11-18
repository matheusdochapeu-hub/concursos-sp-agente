"""
Valida a sintaxe de TODO JavaScript embutido no HTML gerado.

O site é um único HTML montado por f-strings: um `{{` esquecido quebra o JS sem
quebrar o Python, e o erro só aparece no navegador. Este script extrai cada bloco
<script> inline do arquivo e roda `node --check` nele.

Uso:
    python tools/check_inline_js.py                    # valida docs/index.html
    python tools/check_inline_js.py caminho/arquivo.html
    python tools/check_inline_js.py --node "C:/.../node.exe"

Requisito: Node.js no PATH (ou --node). Sai com código 1 se algum bloco falhar.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.S | re.I)
SRC_RE = re.compile(r"\bsrc\s*=", re.I)


def achar_node(explicito: str | None = None) -> str | None:
    if explicito:
        return explicito
    candidatos = [shutil.which("node"), shutil.which("node.exe")]
    # runtime empacotado do DSH, se existir
    candidatos.append(str(Path.home() / ".dsh/dsh-runtimes/dsh-primary-runtime/dependencies/node/bin/node.exe"))
    for c in candidatos:
        if c and Path(c).exists():
            return c
    return None


def extrair_blocos(html: str) -> list[tuple[int, str]]:
    blocos = []
    for m in SCRIPT_RE.finditer(html):
        attrs, corpo = m.group(1), m.group(2)
        if SRC_RE.search(attrs):
            continue  # script externo
        if not corpo.strip():
            continue
        linha = html.count("\n", 0, m.start(2)) + 1
        blocos.append((linha, corpo))
    return blocos


def main() -> int:
    ap = argparse.ArgumentParser(description="Checa a sintaxe do JS inline do HTML gerado.")
    ap.add_argument("arquivo", nargs="?", default=str(REPO / "docs" / "index.html"))
    ap.add_argument("--node", default=None, help="caminho do node.exe")
    args = ap.parse_args()

    caminho = Path(args.arquivo)
    if not caminho.exists():
        print(f"ERRO: {caminho} não existe. Rode o agente ou tools/render_from_json.py antes.")
        return 1

    node = achar_node(args.node)
    if not node:
        print("AVISO: Node.js não encontrado — pulando checagem de sintaxe JS.")
        return 0

    html = caminho.read_text(encoding="utf-8")
    blocos = extrair_blocos(html)
    if not blocos:
        print("Nenhum <script> inline encontrado.")
        return 0

    falhas = 0
    for linha, corpo in blocos:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write(corpo)
            temp = fh.name
        try:
            proc = subprocess.run([node, "--check", temp], capture_output=True, text=True, encoding="utf-8", errors="replace")
        finally:
            try:
                os.unlink(temp)
            except OSError:
                pass
        if proc.returncode != 0:
            falhas += 1
            print(f"✗ Bloco <script> iniciado na linha {linha} do HTML — JS inválido:")
            for ln in (proc.stderr or "").strip().splitlines()[:8]:
                print("   " + ln)
        else:
            print(f"✓ Bloco <script> (linha {linha}, {len(corpo):,} chars) OK")

    if falhas:
        print(f"\n{falhas} bloco(s) com erro de sintaxe.")
        return 1
    print(f"\n{len(blocos)} bloco(s) de JS inline válidos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
