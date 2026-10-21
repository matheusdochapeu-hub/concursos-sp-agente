"""
Agente de busca de concursos - PCI Concursos (Sudeste -> somente SP)

Busca diariamente:
  1. Concursos com cargos de Fisioterapeuta / Fisioterapia
  2. Cargos que exigem APENAS nível médio com salário acima de R$ 5.000,00

Gera:
  - docs/index.html      (página de resultados, publicável no GitHub Pages)
  - data/resultados.json (resultados estruturados)
  - data/cache.json      (cache por notícia, evita reprocessar / gastar IA)

IA (opcional): se a variável de ambiente GEMINI_API_KEY estiver definida, o
Gemini é usado para extrair a lista de cargos (escolaridade + salário) de cada
notícia. Sem a chave, o agente usa heurísticas e marca os casos de nível médio
como "possíveis — verificar edital".
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Literal, Optional

import requests
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------- #
# Configuração
# --------------------------------------------------------------------------- #
LISTING_URL = "https://www.pciconcursos.com.br/concursos/sudeste/"
UF_ALVO = "SP"
SALARIO_MINIMO_MEDIO = 5000.00
FISIO_REGEX = re.compile(r"fisioterap", re.I)

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
CACHE_FILE = DATA_DIR / "cache.json"
RESULTS_FILE = DATA_DIR / "resultados.json"
HTML_FILE = DOCS_DIR / "index.html"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
MAX_AI_CALLS = int(os.getenv("MAX_AI_CALLS", "200"))
AI_DELAY_S = float(os.getenv("AI_DELAY_S", "4"))  # respeita limites do free tier
HTTP_DELAY_S = float(os.getenv("HTTP_DELAY_S", "0.6"))  # educação com o site

BRT = timezone(timedelta(hours=-3))  # Brasil não tem horário de verão desde 2019
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

session = requests.Session()
session.headers.update(HEADERS)


def log(msg: str) -> None:
    print(f"[{datetime.now(BRT):%H:%M:%S}] {msg}", flush=True)


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def fetch(url: str, retries: int = 3) -> str:
    for tentativa in range(1, retries + 1):
        try:
            r = session.get(url, timeout=90)
            r.raise_for_status()
            r.encoding = r.encoding or "utf-8"
            if r.encoding.lower() in ("iso-8859-1", "latin-1"):
                r.encoding = "utf-8"
            return r.text
        except requests.RequestException as e:
            log(f"  erro HTTP ({tentativa}/{retries}) em {url}: {e}")
            time.sleep(2 * tentativa)
    raise RuntimeError(f"Falha ao baixar {url}")


def parse_brl(valor: str) -> Optional[float]:
    """'8.595,15' -> 8595.15"""
    try:
        return float(valor.replace(".", "").replace(",", "."))
    except (ValueError, AttributeError):
        return None


def salarios_no_texto(texto: str) -> List[float]:
    vals = [parse_brl(v) for v in re.findall(r"R\$\s*([\d.]+,\d{2})", texto)]
    return [v for v in vals if v]


def brl(v: Optional[float]) -> str:
    if v is None:
        return "—"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# --------------------------------------------------------------------------- #
# 1) Listagem
# --------------------------------------------------------------------------- #
def parse_listing(page_html: str) -> List[dict]:
    """Cada concurso é um bloco <div class="na|da|ea" ... data-url="...">.
    O HTML do site tem tags mal fechadas, então fatiamos por bloco antes de
    usar o parser."""
    blocos = re.split(r'(?=<div class="\w+"[^>]*\bdata-url=)', page_html)[1:]
    concursos = []
    for bloco in blocos:
        soup = BeautifulSoup(bloco, "html.parser")
        da = soup.select_one("div[data-url]")
        uf_el = soup.select_one("div.cc")
        link = soup.select_one("div.ca a")
        if not (da and uf_el and link):
            continue
        uf = uf_el.get_text(strip=True)
        cd = soup.select_one("div.cd")
        ce = soup.select_one("div.ce")
        resumo = cd.get_text(" | ", strip=True) if cd else ""
        partes = [p.strip() for p in resumo.split("|")]
        vagas_sal = partes[0] if partes else ""
        cargos_resumo = partes[1] if len(partes) > 1 else ""
        niveis = partes[2] if len(partes) > 2 else ""
        sal = salarios_no_texto(vagas_sal)
        concursos.append(
            {
                "url": da.get("data-url") or link.get("href"),
                "orgao": link.get_text(strip=True),
                "titulo": link.get("title") or link.get_text(strip=True),
                "uf": uf,
                "vagas_salario": vagas_sal,
                "cargos_resumo": cargos_resumo,
                "niveis": niveis,
                "salario_max_listagem": max(sal) if sal else None,
                "inscricao_ate": ce.get_text(" ", strip=True) if ce else "",
            }
        )
    return concursos


# --------------------------------------------------------------------------- #
# 2) Notícia (detalhe)
# --------------------------------------------------------------------------- #
CORTE_RODAPE = re.compile(
    r"(Eleve seus estudos|Otimize sua prepara|Apostilas Digitais|Tenha a not[ií]cia completa|"
    r"Al[eé]m da leitura, voc[eê] pode)",
    re.I,
)


def extrair_texto_noticia(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    art = soup.select_one("#noticia") or soup.select_one("article") or soup.body
    for tag in art.select("script, style, noscript, iframe"):
        tag.decompose()
    linhas = [l.strip() for l in art.get_text("\n").splitlines()]
    texto = "\n".join(l for l in linhas if l)
    m = CORTE_RODAPE.search(texto)
    if m:
        texto = texto[: m.start()]
    return texto.strip()


def linhas_fisio(texto: str) -> List[str]:
    achados = []
    for linha in texto.splitlines():
        if FISIO_REGEX.search(linha):
            l = linha.strip()
            if len(l) > 220:  # frase longa: recorta em volta do termo
                i = FISIO_REGEX.search(l).start()
                l = "…" + l[max(0, i - 90): i + 120] + "…"
            if l not in achados:
                achados.append(l)
    return achados


# --------------------------------------------------------------------------- #
# 3) IA (Gemini) - extração estruturada de cargos
# --------------------------------------------------------------------------- #
_client = None
_ai_calls = 0

try:
    from pydantic import BaseModel, Field

    class Cargo(BaseModel):
        nome: str = Field(description="Nome do cargo exatamente como na notícia.")
        escolaridade: Literal["fundamental", "medio", "tecnico", "superior", "desconhecida"] = Field(
            description=(
                "Escolaridade exigida. 'medio' = exige APENAS ensino médio completo; "
                "'tecnico' = exige curso técnico/ensino médio técnico; "
                "'desconhecida' se a notícia não deixar claro."
            )
        )
        vagas: Optional[str] = Field(default=None, description="Ex.: '3 vagas + CR', 'CR'.")
        salario: Optional[float] = Field(
            default=None,
            description=(
                "Salário/vencimento base ESPECÍFICO deste cargo em reais (número). "
                "Use null se a notícia só informa uma faixa geral do concurso."
            ),
        )

    class AnaliseConcurso(BaseModel):
        cargos: List[Cargo] = Field(description="Todos os cargos citados na notícia.")
        salario_min: Optional[float] = Field(default=None, description="Menor remuneração citada.")
        salario_max: Optional[float] = Field(default=None, description="Maior remuneração citada.")

    PYDANTIC_OK = True
except ImportError:  # pragma: no cover
    PYDANTIC_OK = False

SYSTEM_INSTRUCTION = (
    "Você é um extrator de dados de editais de concursos públicos brasileiros. "
    "Leia a notícia e liste TODOS os cargos com sua escolaridade e, quando a notícia "
    "informar explicitamente, o salário daquele cargo. Use a seção/título em que o cargo "
    "aparece (ex.: 'Ensino médio', 'Nível superior') para inferir a escolaridade. "
    "Cargos como 'Técnico em ...' que exigem curso técnico são 'tecnico'. "
    "Nunca invente salários: se não houver valor por cargo, use null."
)


def get_client():
    global _client
    if _client is None:
        from google import genai  # import tardio: só exige o pacote se houver chave

        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def analisar_com_ia(texto: str) -> Optional[dict]:
    global _ai_calls
    if not (GEMINI_API_KEY and PYDANTIC_OK) or _ai_calls >= MAX_AI_CALLS:
        return None
    for tentativa in range(1, 4):
        try:
            _ai_calls += 1
            interaction = get_client().interactions.create(
                model=GEMINI_MODEL,
                system_instruction=SYSTEM_INSTRUCTION,
                input=texto[:12000],
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": AnaliseConcurso.model_json_schema(),
                },
                store=False,
            )
            analise = AnaliseConcurso.model_validate_json(interaction.output_text)
            time.sleep(AI_DELAY_S)
            return analise.model_dump()
        except Exception as e:  # noqa: BLE001 - qualquer falha de IA cai no fallback
            espera = 15 * tentativa
            log(f"  IA falhou ({tentativa}/3): {str(e)[:160]} — aguardando {espera}s")
            time.sleep(espera)
    return None


# --------------------------------------------------------------------------- #
# 4) Classificação
# --------------------------------------------------------------------------- #
def tem_nivel_medio(c: dict, texto: str) -> bool:
    if re.search(r"m[ée]dio", c.get("niveis", ""), re.I):
        return True
    return bool(re.search(r"n[íi]vel m[ée]dio|ensino m[ée]dio", texto, re.I))


def classificar(c: dict, info: dict) -> None:
    """Preenche c['fisio'], c['medio_confirmado'], c['medio_possivel']."""
    c["fisio_linhas"] = info.get("fisio_linhas", [])
    c["fisio"] = bool(c["fisio_linhas"]) or bool(FISIO_REGEX.search(c.get("cargos_resumo", "")))

    sal_max = max(
        [v for v in (c.get("salario_max_listagem"), info.get("salario_max_texto")) if v] or [0]
    ) or None
    c["salario_max"] = sal_max
    c["medio_confirmado"] = []
    c["medio_sem_salario"] = []
    c["medio_possivel"] = False
    c["analise_ia"] = bool(info.get("ia"))

    if sal_max is not None and sal_max <= SALARIO_MINIMO_MEDIO:
        return  # nenhum cargo pode passar de R$ 5.000

    ia = info.get("ia")
    if ia:
        for cargo in ia.get("cargos", []):
            if cargo.get("escolaridade") != "medio":
                continue
            s = cargo.get("salario")
            if s and s > SALARIO_MINIMO_MEDIO:
                c["medio_confirmado"].append(cargo)
            elif not s:
                c["medio_sem_salario"].append(cargo)
        c["medio_possivel"] = not c["medio_confirmado"] and bool(c["medio_sem_salario"])
    elif info.get("tem_medio"):
        c["medio_possivel"] = True


# --------------------------------------------------------------------------- #
# 5) Pipeline
# --------------------------------------------------------------------------- #
def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return default


def precisa_ia(c: dict) -> bool:
    sal = c.get("salario_max_listagem")
    return bool(re.search(r"m[ée]dio", c.get("niveis", ""), re.I)) and (sal is None or sal > SALARIO_MINIMO_MEDIO)


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)
    cache: dict = load_json(CACHE_FILE, {})
    hoje = datetime.now(BRT).strftime("%Y-%m-%d")

    log(f"Baixando listagem: {LISTING_URL}")
    todos = parse_listing(fetch(LISTING_URL))
    concursos = [c for c in todos if c["uf"] == UF_ALVO]
    log(f"{len(todos)} concursos no Sudeste, {len(concursos)} em {UF_ALVO}.")
    log("IA: " + (f"ativada ({GEMINI_MODEL})" if GEMINI_API_KEY else "desativada (sem GEMINI_API_KEY)"))

    for i, c in enumerate(concursos, 1):
        url = c["url"]
        info = cache.get(url)
        quer_ia = bool(GEMINI_API_KEY) and precisa_ia(c)
        if info is None or (quer_ia and not info.get("ia")):
            log(f"[{i}/{len(concursos)}] {c['orgao']}")
            try:
                texto = extrair_texto_noticia(fetch(url))
            except RuntimeError as e:
                log(f"  ignorado: {e}")
                continue
            time.sleep(HTTP_DELAY_S)
            sal_txt = salarios_no_texto(texto)
            info = {
                **(info or {}),
                "first_seen": (info or {}).get("first_seen", hoje),
                "hash": hashlib.sha1(texto.encode()).hexdigest()[:12],
                "fisio_linhas": linhas_fisio(texto),
                "salario_max_texto": max(sal_txt) if sal_txt else None,
                "tem_medio": tem_nivel_medio(c, texto),
            }
            if quer_ia:
                ia = analisar_com_ia(texto)
                if ia:
                    info["ia"] = ia
                    info["ia_model"] = GEMINI_MODEL
            cache[url] = info
        c["first_seen"] = info.get("first_seen", hoje)
        c["novo"] = c["first_seen"] == hoje
        classificar(c, info)

    # mantém só o que ainda está na listagem
    ativos = {c["url"] for c in concursos}
    cache = {u: v for u, v in cache.items() if u in ativos}
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    fisio = [c for c in concursos if c.get("fisio")]
    medio_ok = [c for c in concursos if c.get("medio_confirmado")]
    medio_pos = [c for c in concursos if c.get("medio_possivel")]
    gerado_em = datetime.now(BRT).strftime("%d/%m/%Y %H:%M")

    RESULTS_FILE.write_text(
        json.dumps(
            {
                "gerado_em": gerado_em,
                "fonte": LISTING_URL,
                "total_sp": len(concursos),
                "ia_ativa": bool(GEMINI_API_KEY),
                "fisioterapia": fisio,
                "nivel_medio_acima_5000": medio_ok,
                "nivel_medio_possiveis": medio_pos,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    HTML_FILE.write_text(render_html(fisio, medio_ok, medio_pos, len(concursos), gerado_em), encoding="utf-8")
    log(f"Fisioterapia: {len(fisio)} | Médio > R$5k: {len(medio_ok)} | Possíveis: {len(medio_pos)}")
    log(f"Página gerada: {HTML_FILE}")
    return 0


# --------------------------------------------------------------------------- #
# 6) HTML
# --------------------------------------------------------------------------- #
def e(s) -> str:
    return html.escape(str(s or ""))


def card(c: dict, modo: str) -> str:
    chips = ""
    if modo == "fisio":
        chips = "".join(f'<li>{e(l)}</li>' for l in c.get("fisio_linhas", [])[:8])
        if not chips:
            chips = f"<li>{e(c.get('cargos_resumo'))}</li>"
    elif modo == "medio":
        chips = "".join(
            f'<li><b>{e(x["nome"])}</b> — {brl(x.get("salario"))}'
            f'{" · " + e(x["vagas"]) if x.get("vagas") else ""}</li>'
            for x in c["medio_confirmado"]
        )
    else:
        if c.get("medio_sem_salario"):
            chips = "".join(
                f'<li><b>{e(x["nome"])}</b>{" · " + e(x["vagas"]) if x.get("vagas") else ""}</li>'
                for x in c["medio_sem_salario"][:12]
            )
        else:
            chips = f"<li>Níveis: {e(c.get('niveis'))}</li>"
    novo = '<span class="badge novo">NOVO</span>' if c.get("novo") else ""
    busca = e(" ".join([c["orgao"], c["titulo"], " ".join(c.get("fisio_linhas", []))]).lower())
    return f"""
    <article class="card" data-busca="{busca}">
      <header>
        <h3><a href="{e(c['url'])}" target="_blank" rel="noopener">{e(c['orgao'])}</a> {novo}</h3>
        <p class="titulo">{e(c['titulo'])}</p>
      </header>
      <ul class="cargos">{chips}</ul>
      <footer>
        <span>📋 {e(c['vagas_salario'])}</span>
        <span>🎓 {e(c['niveis'] or '—')}</span>
        <span class="prazo">⏰ Inscrições até <b>{e(c['inscricao_ate'] or '—')}</b></span>
      </footer>
    </article>"""


def secao(id_: str, titulo: str, desc: str, itens: List[dict], modo: str) -> str:
    corpo = "".join(card(c, modo) for c in itens) or '<p class="vazio">Nenhum concurso encontrado hoje.</p>'
    return f"""
  <section id="{id_}" class="tab-panel">
    <h2>{titulo} <small>({len(itens)})</small></h2>
    <p class="desc">{desc}</p>
    <div class="grid">{corpo}</div>
  </section>"""


def render_html(fisio, medio_ok, medio_pos, total, gerado_em) -> str:
    aviso_ia = (
        ""
        if GEMINI_API_KEY
        else '<div class="alerta">⚠️ IA desativada: a aba "Nível médio &gt; R$ 5.000" depende da '
        "extração por IA (Gemini). Sem ela, os concursos de nível médio aparecem em "
        '"Possíveis (verificar edital)".</div>'
    )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Concursos SP — Fisioterapia &amp; Nível Médio</title>
<style>
  :root {{ --bg:#0f172a; --card:#1e293b; --muted:#94a3b8; --txt:#e2e8f0; --acc:#22d3ee; --ok:#4ade80; --warn:#fbbf24; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif; background:var(--bg); color:var(--txt); }}
  .top {{ padding:28px 20px 12px; max-width:1200px; margin:auto; }}
  h1 {{ margin:0 0 6px; font-size:1.6rem; }}
  .meta {{ color:var(--muted); font-size:.9rem; }}
  .stats {{ display:flex; gap:12px; flex-wrap:wrap; margin:16px 0; }}
  .stat {{ background:var(--card); padding:10px 16px; border-radius:10px; }}
  .stat b {{ font-size:1.4rem; display:block; }}
  nav {{ display:flex; gap:8px; flex-wrap:wrap; max-width:1200px; margin:auto; padding:0 20px; }}
  nav button {{ background:var(--card); color:var(--txt); border:1px solid #334155; padding:10px 16px; border-radius:999px; cursor:pointer; font-size:.95rem; }}
  nav button.ativo {{ background:var(--acc); color:#0f172a; border-color:var(--acc); font-weight:600; }}
  .filtro {{ max-width:1200px; margin:14px auto 0; padding:0 20px; }}
  .filtro input {{ width:100%; padding:10px 14px; border-radius:10px; border:1px solid #334155; background:#0b1222; color:var(--txt); font-size:1rem; }}
  main {{ max-width:1200px; margin:auto; padding:10px 20px 40px; }}
  .tab-panel {{ display:none; }} .tab-panel.ativo {{ display:block; }}
  h2 small {{ color:var(--muted); font-weight:400; }}
  .desc {{ color:var(--muted); margin-top:-6px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(340px,1fr)); gap:14px; }}
  .card {{ background:var(--card); border-radius:14px; padding:16px; display:flex; flex-direction:column; gap:10px; border:1px solid #334155; }}
  .card h3 {{ margin:0; font-size:1.08rem; }} .card h3 a {{ color:var(--acc); text-decoration:none; }}
  .card h3 a:hover {{ text-decoration:underline; }}
  .titulo {{ margin:4px 0 0; color:var(--muted); font-size:.88rem; }}
  .cargos {{ margin:0; padding-left:18px; font-size:.92rem; line-height:1.45; }}
  .card footer {{ display:flex; flex-direction:column; gap:3px; font-size:.85rem; color:var(--muted); margin-top:auto; }}
  .prazo b {{ color:var(--warn); }}
  .badge.novo {{ background:var(--ok); color:#052e16; font-size:.7rem; padding:2px 7px; border-radius:6px; vertical-align:middle; font-weight:700; }}
  .alerta {{ background:#422006; border:1px solid var(--warn); color:#fde68a; padding:10px 14px; border-radius:10px; margin:10px 0; font-size:.9rem; }}
  .vazio {{ color:var(--muted); }}
  a.fonte {{ color:var(--acc); }}
</style>
</head>
<body>
  <div class="top">
    <h1>🔎 Concursos em São Paulo</h1>
    <div class="meta">Atualizado em <b>{gerado_em}</b> (horário de Brasília) · Fonte:
      <a class="fonte" href="{LISTING_URL}" target="_blank" rel="noopener">PCI Concursos — Sudeste</a></div>
    <div class="stats">
      <div class="stat"><b>{total}</b>concursos abertos em SP</div>
      <div class="stat"><b>{len(fisio)}</b>com Fisioterapia</div>
      <div class="stat"><b>{len(medio_ok)}</b>nível médio &gt; R$ 5 mil</div>
      <div class="stat"><b>{len(medio_pos)}</b>possíveis (verificar)</div>
    </div>
    {aviso_ia}
  </div>
  <nav>
    <button data-tab="fisio" class="ativo">🩺 Fisioterapia ({len(fisio)})</button>
    <button data-tab="medio">💰 Nível médio &gt; R$ 5.000 ({len(medio_ok)})</button>
    <button data-tab="possiveis">🔍 Possíveis — verificar edital ({len(medio_pos)})</button>
  </nav>
  <div class="filtro"><input id="q" type="search" placeholder="Filtrar por cidade, órgão ou cargo..."></div>
  <main>
    {secao("fisio", "Fisioterapeuta / Fisioterapia", "Concursos de SP cuja notícia cita cargos de fisioterapia.", fisio, "fisio")}
    {secao("medio", "Nível médio com salário acima de R$ 5.000", "Cargos que exigem apenas ensino médio e cujo salário informado é maior que R$ 5.000,00 (extraído por IA — confirme no edital).", medio_ok, "medio")}
    {secao("possiveis", "Possíveis — nível médio, salário por cargo não informado", "Concursos com cargos de nível médio e teto salarial acima de R$ 5.000, mas a notícia não detalha o salário de cada cargo. Confira o edital.", medio_pos, "possivel")}
  </main>
<script>
  const btns = document.querySelectorAll('nav button');
  function abrir(tab) {{
    btns.forEach(b => b.classList.toggle('ativo', b.dataset.tab === tab));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('ativo', p.id === tab));
    history.replaceState(null, '', '#' + tab);
  }}
  btns.forEach(b => b.addEventListener('click', () => abrir(b.dataset.tab)));
  abrir(['fisio','medio','possiveis'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'fisio');
  document.getElementById('q').addEventListener('input', ev => {{
    const q = ev.target.value.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
    document.querySelectorAll('.card').forEach(c => {{
      const t = c.dataset.busca.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
      c.style.display = t.includes(q) ? '' : 'none';
    }});
  }});
</script>
</body>
</html>"""


if __name__ == "__main__":
    sys.exit(main())
