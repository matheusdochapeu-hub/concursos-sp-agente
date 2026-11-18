"""
Reconstrói o site (docs/index.html) a partir dos JSON já coletados, SEM raspar
o PCI Concursos e SEM chamar IA.

Serve para:
  - revisar/pré-visualizar mudanças de layout e JS sem esperar a coleta diária;
  - validar o template (`render_site.render_html`) em CI, offline;
  - recuperar a página quando a coleta falha (desde que os JSON existam).

Uso:
    python tools/render_from_json.py            # regrava docs/index.html
    python tools/render_from_json.py --check    # só valida, não grava

Entradas: data/resultados.json, data/municipios_sp.json e
docs/data/catalogo_brasil.json (saída da última coleta).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agente import gerar_links_provas_banca_cargo, PIX_KEY, LISTING_URL  # noqa: E402
from render_site import render_html  # noqa: E402

DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def montar_catalogo_provas(fisio, medio_todos, superior_sp) -> list[dict]:
    """Mesma regra do agente: um par (cargo, banca) por concurso, sem duplicar."""
    vistos: set[tuple[str, str]] = set()
    catalogo: list[dict] = []

    def adicionar(cargo_nome: str, banca_raw: str, escolaridade: str, orgao: str, data_prova: str) -> None:
        lp = gerar_links_provas_banca_cargo(cargo_nome, banca_raw)
        chave = (lp["cargo_busca"], lp["banca_busca"])
        if chave in vistos:
            return
        vistos.add(chave)
        catalogo.append({
            "cargo": lp["cargo_busca"],
            "banca": lp["banca_busca"],
            "banca_original": banca_raw,
            "escolaridade": escolaridade,
            "url_combo": lp["url_combo"],
            "url_cargo": lp["url_cargo"],
            "url_banca": lp["url_banca"],
            "exemplo_orgao": orgao,
            "data_prova": data_prova or "Consultar edital",
        })

    for c in fisio:
        cargo = (c.get("fisio_detalhes") or {}).get("cargo") or "Fisioterapeuta"
        adicionar(cargo, c.get("banca") or "Consultar edital",
                  "Ensino Superior (Fisioterapia)", c.get("orgao", ""), c.get("data_prova", ""))
    for c in medio_todos:
        banca = c.get("banca") or "Consultar edital"
        for item in c.get("medio_outros") or []:
            adicionar(item.get("nome") or "Agente Administrativo", banca,
                      "Nível Médio / Técnico", c.get("orgao", ""), c.get("data_prova", ""))
    for c in superior_sp:
        banca = c.get("banca") or "Consultar edital"
        for item in c.get("superior_itens") or []:
            adicionar(item.get("nome") or "Analista", banca,
                      "Ensino Superior", c.get("orgao", ""), c.get("data_prova", ""))

    return catalogo


def render() -> str:
    resultados = _load(DATA_DIR / "resultados.json", {})
    if not resultados:
        raise SystemExit("data/resultados.json ausente ou vazio: rode `python agente.py` primeiro.")

    fisio = resultados.get("fisioterapia") or []
    medio_todos = resultados.get("nivel_medio_todas_faixas") or []
    superior_sp = resultados.get("nivel_superior_sp") or []

    catalogo_brasil = _load(DOCS_DIR / "data" / "catalogo_brasil.json", [])
    municipios_sp = _load(DATA_DIR / "municipios_sp.json", {})

    # `total_sp` no agente = todos os concursos SP vigentes (mesmo os que não
    # entraram em nenhuma aba). O JSON só guarda os que entraram, então usamos
    # a contagem informada na última coleta, com fallback para os URLs únicos.
    total_sp = int(resultados.get("total_sp") or 0)
    if total_sp <= 0:
        total_sp = len({c.get("url") for c in fisio + medio_todos + superior_sp if c.get("url")})

    return render_html(
        fisio=fisio,
        medio_ok=[],
        medio_todos=medio_todos,
        catalogo_brasil=catalogo_brasil,
        catalogo_provas_banca_cargo=montar_catalogo_provas(fisio, medio_todos, superior_sp),
        total_sp=total_sp,
        gerado_em=resultados.get("gerado_em") or "",
        listing_url=resultados.get("fonte") or LISTING_URL,
        pix_key=PIX_KEY,
        superior_sp=superior_sp,
        municipios_sp=municipios_sp,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Regenera docs/index.html a partir dos JSON locais.")
    ap.add_argument("--check", action="store_true", help="valida o template sem gravar o arquivo")
    ap.add_argument("--out", default=str(DOCS_DIR / "index.html"), help="arquivo de saída")
    args = ap.parse_args()

    html_out = render()
    destino = Path(args.out)
    if args.check:
        print(f"OK: template renderizado ({len(html_out):,} caracteres) — nada foi gravado.")
        return 0
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html_out, encoding="utf-8")
    print(f"OK: {destino} ({len(html_out):,} caracteres)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
