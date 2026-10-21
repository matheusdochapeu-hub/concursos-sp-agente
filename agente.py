"""
Agente de Busca de Concursos — PCI Concursos (SP + Brasil Todo)

Funcionalidades:
  1. Monitora diariamente os concursos do Estado de São Paulo (SP) e de todo o Brasil
     (todas as 27 UFs + Concursos Nacionais) no PCI Concursos.
  2. Aba 1 — Fisioterapia (SP): Valores exatos do salário, benefícios (VA, VR, VT),
     regime (Estatutário / CLT / Residência / Militar / Seletivo), carga horária semanal,
     data da prova, requisitos do edital e resumo do conteúdo programático.
  3. Aba 2 — Nível Médio > R$ 5.000 (SP): Cargos de nível médio com remuneração
     confirmada acima de R$ 5.000,00 e especificações técnicas exigidas no edital.
  4. Aba 3 — Nível Médio / Técnico (Outras Faixas Salariais — SP): Todos os concursos
     de nível médio e técnico em SP separados por faixa salarial selecionável em botões
     e com detalhamento se exige APENAS Ensino Médio ou Curso Técnico + Conselho.
  5. Aba 4 — Buscar Cargo Específico (SP / Outros Estados / Brasil Todo): Permite digitar
     qualquer cargo (ou clicar em cargos sugeridos) e filtrar por qualquer Estado (UF)
     ou no Brasil todo, vasculhando inclusive o interior dos editais de "Vários Cargos".
  6. Filtros 100% em botões pré-definidos (Proximidade de Ribeirão Preto/SP, Proximidade
     de Jarinu/SP, Cidade, Faixa Salarial, Vagas, Escolaridade/Exigência, Regime, Horas,
     Novidades 24h e Ordenação).
  7. Identifica concursos novos (últimas 24h) e gera Progressive Web App (PWA) com
     tema inspirado na Bandeira do Brasil e botão de apoio Pix no rodapé.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import html
import io
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import requests
from bs4 import BeautifulSoup

# Garante saída UTF-8 mesmo no console Windows (cp1252)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# --------------------------------------------------------------------------- #
# Configuração
# --------------------------------------------------------------------------- #
LISTING_URL = "https://www.pciconcursos.com.br/concursos/sudeste/"
REGIONAL_URLS = {
    "Sudeste": "https://www.pciconcursos.com.br/concursos/sudeste/",
    "Sul": "https://www.pciconcursos.com.br/concursos/sul/",
    "Centro-Oeste": "https://www.pciconcursos.com.br/concursos/centrooeste/",
    "Nordeste": "https://www.pciconcursos.com.br/concursos/nordeste/",
    "Norte": "https://www.pciconcursos.com.br/concursos/norte/",
    "Nacional": "https://www.pciconcursos.com.br/concursos/nacional/",
}
UF_ALVO = "SP"
SALARIO_MINIMO_MEDIO = 5000.00
FISIO_REGEX = re.compile(r"\bfisioterap(?:euta|ia|êutico|eutas)\b", re.I)
SCHEMA_VERSION = 4

PIX_KEY = (
    "00020126580014br.gov.bcb.pix01364c83415e-0b75-4a40-b0b6-83a0c12a7135"
    "5204000053039865802BR5911MATHEUS19176009Sao Paulo610901227-200"
    "62230519daqr21591091736170363041A4B"
)

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
CACHE_FILE = DATA_DIR / "cache.json"
CACHE_BRASIL_FILE = DATA_DIR / "cache_brasil.json"
RESULTS_FILE = DATA_DIR / "resultados.json"
MUNICIPIOS_FILE = DATA_DIR / "municipios_sp.json"
ENRIQUECIDOS_FILE = DATA_DIR / "concursos_enriquecidos.json"
HTML_FILE = DOCS_DIR / "index.html"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_SEARCH_MODEL = os.getenv("GEMINI_SEARCH_MODEL", "gemini-3.8-flash")
MAX_AI_CALLS = int(os.getenv("MAX_AI_CALLS", "120"))
AI_DELAY_S = float(os.getenv("AI_DELAY_S", "4"))
HTTP_DELAY_S = float(os.getenv("HTTP_DELAY_S", "0.25"))

BRT = timezone(timedelta(hours=-3))
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

session = requests.Session()
session.headers.update(HEADERS)


def log(msg: str) -> None:
    print(f"[{datetime.now(BRT):%H:%M:%S}] {msg}", flush=True)


def norm(s: Optional[str]) -> str:
    if not s:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s.lower().strip()) if unicodedata.category(c) != "Mn"
    )


def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return default


def gerar_qr_pix_svg(payload: str) -> str:
    try:
        import segno

        qr = segno.make(payload, error="m")
        buf = io.BytesIO()
        qr.save(buf, kind="svg", xmldecl=False, scale=4, border=2, dark="#143321", light="#ffffff")
        return buf.getvalue().decode("utf-8")
    except Exception:  # pragma: no cover
        return (
            '<div style="padding:24px;color:#143321;font-weight:700;">'
            "Use o botão abaixo para copiar a chave Pix Copia e Cola</div>"
        )


# --------------------------------------------------------------------------- #
# Base de Municípios de SP (distâncias para Ribeirão Preto e Jarinu)
# --------------------------------------------------------------------------- #
MUNICIPIOS_SP: Dict[str, dict] = load_json(MUNICIPIOS_FILE, {})
MUN_PATTERNS = [
    (k, re.compile(r"\b" + re.escape(k) + r"\b"))
    for k in sorted(MUNICIPIOS_SP.keys(), key=len, reverse=True)
]

ORG_CITY_HINTS = {
    "funcamp": "campinas",
    "unicamp": "campinas",
    "setec": "campinas",
    "fjpo": "campinas",
    "prudenco": "presidente prudente",
    "prudenprev": "presidente prudente",
    "comderp": "sao jose do rio pardo",
    "famesp": "botucatu",
    "hcfmrp": "ribeirao preto",
    "iamspe": "sao paulo",
    "tjsp": "sao paulo",
    "sefaz": "sao paulo",
    "detran": "sao paulo",
    "defensoria publica": "sao paulo",
    "ipa - instituto": "sao paulo",
    "distrito naval": "sao paulo",
    "cemmil": "mogi guacu",
    "uscs": "sao caetano do sul",
}


def detectar_cidade(orgao: str, titulo: str, url: str, texto: str = "", sugestao_ia: Optional[str] = None) -> Optional[str]:
    if sugestao_ia:
        k_ia = norm(sugestao_ia).replace(" - sp", "").replace("/sp", "").strip()
        if k_ia in MUNICIPIOS_SP:
            return MUNICIPIOS_SP[k_ia]["nome"]

    m = re.search(r"(?:de|em|da|do)\s+([a-z\s]+?)\s*-\s*sp\b", norm(titulo))
    if m:
        cand = m.group(1).strip()
        for k, pat in MUN_PATTERNS:
            if pat.search(cand):
                return MUNICIPIOS_SP[k]["nome"]

    cabecalho = norm(f"{titulo} {orgao} {url.replace('-', ' ')}")
    for k, pat in MUN_PATTERNS:
        if k == "sao paulo":
            continue
        if pat.search(cabecalho):
            return MUNICIPIOS_SP[k]["nome"]

    for hint, city_k in ORG_CITY_HINTS.items():
        if hint in cabecalho and city_k in MUNICIPIOS_SP:
            return MUNICIPIOS_SP[city_k]["nome"]

    if texto:
        trecho = norm(texto[:600])
        for k, pat in MUN_PATTERNS:
            if k == "sao paulo":
                continue
            if pat.search(trecho):
                return MUNICIPIOS_SP[k]["nome"]

    if "sao paulo" in cabecalho and "sao paulo" in MUNICIPIOS_SP:
        return MUNICIPIOS_SP["sao paulo"]["nome"]
    return None


def info_distancia(cidade: Optional[str]) -> Dict[str, Any]:
    if not cidade:
        return {"cidade": "São Paulo (Estado)", "km_ribeirao_preto": None, "km_jarinu": None}
    info = MUNICIPIOS_SP.get(norm(cidade))
    if not info:
        return {"cidade": cidade, "km_ribeirao_preto": None, "km_jarinu": None}
    return {
        "cidade": info["nome"],
        "km_ribeirao_preto": info["km_ribeirao_preto"],
        "km_jarinu": info["km_jarinu"],
    }


# --------------------------------------------------------------------------- #
# Utilidades HTTP e Formatação
# --------------------------------------------------------------------------- #
def fetch(url: str, retries: int = 3) -> str:
    for tentativa in range(1, retries + 1):
        try:
            r = session.get(url, timeout=60)
            r.raise_for_status()
            r.encoding = r.encoding or "utf-8"
            if r.encoding.lower() in ("iso-8859-1", "latin-1"):
                r.encoding = "utf-8"
            return r.text
        except requests.RequestException as e:
            if tentativa == retries:
                log(f"  erro HTTP ({tentativa}/{retries}) em {url}: {e}")
            time.sleep(1.5 * tentativa)
    raise RuntimeError(f"Falha ao baixar {url}")


def parse_brl(valor: str) -> Optional[float]:
    try:
        return float(valor.replace(".", "").replace(",", "."))
    except (ValueError, AttributeError):
        return None


def salarios_no_texto(texto: str) -> List[float]:
    vals = [parse_brl(v) for v in re.findall(r"R\$\s*([\d.]+,\d{2})", texto)]
    return [v for v in vals if v and v >= 500.0]


def brl(v: Optional[float]) -> str:
    if v is None:
        return "Consultar edital"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def extrair_vagas_info(vagas_str: Optional[str]) -> tuple[int, bool, str]:
    s = (vagas_str or "").strip()
    if not s:
        return 0, True, "Cadastro de Reserva (CR)"
    nums = [int(n) for n in re.findall(r"\b(\d+)\s*vaga", s, re.I)]
    imediatas = sum(nums) if nums else 0
    if not nums and re.match(r"^\d+$", s):
        imediatas = int(s)
    tem_cr = bool(re.search(r"\bCR\b|cadastro\s+de\s+reserva|reserva", s, re.I)) or imediatas == 0
    if imediatas > 0 and tem_cr:
        plural = "s" if imediatas > 1 else ""
        return imediatas, True, f"{imediatas} vaga{plural} imediata{plural} + CR"
    if imediatas > 0:
        plural = "s" if imediatas > 1 else ""
        return imediatas, False, f"{imediatas} vaga{plural} imediata{plural}"
    return 0, True, "Cadastro de Reserva (CR)"


# --------------------------------------------------------------------------- #
# 1) Listagem do PCI Concursos (SP e Todas as Regiões do Brasil)
# --------------------------------------------------------------------------- #
def parse_listing(page_html: str, regiao_padrao: str = "") -> List[dict]:
    blocos = re.split(r'(?=<div class="\w+"[^>]*\bdata-url=)', page_html)[1:]
    concursos = []
    vistos = set()
    for bloco in blocos:
        soup = BeautifulSoup(bloco, "html.parser")
        da = soup.select_one("div[data-url]")
        uf_el = soup.select_one("div.cc")
        link = soup.select_one("div.ca a")
        if not (da and uf_el and link):
            continue
        url = (da.get("data-url") or link.get("href") or "").strip()
        if not url or url in vistos:
            continue
        vistos.add(url)
        uf = uf_el.get_text(strip=True) or "BR"
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
                "url": url,
                "orgao": link.get_text(strip=True),
                "titulo": link.get("title") or link.get_text(strip=True),
                "uf": uf,
                "regiao": regiao_padrao,
                "vagas_salario": vagas_sal,
                "cargos_resumo": cargos_resumo,
                "niveis": niveis,
                "salario_max_listagem": max(sal) if sal else None,
                "inscricao_ate": ce.get_text(" ", strip=True) if ce else "",
            }
        )
    return concursos


# --------------------------------------------------------------------------- #
# 2) Extração de texto, cargos (<li>) e metadados da página da notícia
# --------------------------------------------------------------------------- #
CORTE_RODAPE = re.compile(
    r"(Eleve seus estudos|Otimize sua prepara|Apostilas Digitais|Tenha a not[ií]cia completa|"
    r"Al[eé]m da leitura, voc[eê] pode|Um guia essencial para quem est[áa] come[çc]ando|"
    r"Construa uma base s[óo]lida|Prepare-se com seguran[çc]a|Transforme sua leitura em escuta|"
    r"Escute os destaques diretamente)",
    re.I,
)

MESES = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06", "julho": "07",
    "agosto": "08", "setembro": "09", "outubro": "10", "novembro": "11", "dezembro": "12",
}


def parse_data_prova(texto: str) -> str:
    for padrao in [
        r"prova[s]?\s+(?:objetiva[s]?|escrita[s]?)?[^.\n]{0,110}?(\d{1,2})\s*(?:º|o)?\s*de\s+([a-zç]+)\s+de\s+(\d{4})",
        r"prevista[s]?\s+para\s+(?:o\s+dia\s+)?(\d{1,2})\s*(?:º|o)?\s*de\s+([a-zç]+)\s+de\s+(\d{4})",
        r"aplicad[ao][s]?\s+(?:no\s+dia\s+|em\s+)(\d{1,2})\s*(?:º|o)?\s*de\s+([a-zç]+)\s+de\s+(\d{4})",
    ]:
        m = re.search(padrao, texto, re.I)
        if m:
            dia = m.group(1).zfill(2)
            mes = MESES.get(m.group(2).lower(), "")
            ano = m.group(3)
            if mes:
                return f"{dia}/{mes}/{ano}"
    m2 = re.search(r"prova[s]?[^.\n]{0,80}?(\d{2}/\d{2}/\d{4})", texto, re.I)
    if m2:
        return m2.group(1)
    return "Consultar edital"


def parse_regime(texto: str) -> str:
    t = texto.lower()
    tem_est = "estatutário" in t or "estatutario" in t
    tem_clt = "celetista" in t or "regime clt" in t or "sob clt" in t or "regime da clt" in t
    if tem_est and tem_clt:
        return "Estatutário / CLT"
    if tem_est:
        return "Estatutário"
    if tem_clt:
        return "CLT (Celetista)"
    if "residência multiprofissional" in t or "bolsa mensal" in t:
        return "Residência (Bolsa)"
    if "oficiais temporários" in t or "rm2" in t:
        return "Militar Temporário (RM2)"
    if "processo seletivo" in t or "temporário" in t:
        return "Processo Seletivo / Temporário"
    return "Consultar edital"


def parse_beneficios(texto: str) -> str:
    achados = []
    for padrao in [
        r"(?:aux[íi]lio|vale|ajuda\s+de\s+custo\s+para)[-\s]*(?:alimenta[çc][ãa]o|refei[çc][ãa]o|transporte|sa[úu]de)(?:[^;\n]|\.(?=\d)){0,95}",
        r"aux[íi]lios\s+para\s+alimenta[çc][ãa]o[^;\n.]{0,70}",
        r"cart[ãa]o[-\s]*alimenta[çc][ãa]o(?:[^;\n]|\.(?=\d)){0,75}",
        r"cesta\s+b[áa]sica(?:[^;\n]|\.(?=\d)){0,70}",
        r"pr[êe]mio\s+de\s+produtividade[^;\n.]{0,60}",
    ]:
        for m in re.finditer(padrao, texto, re.I):
            trecho = re.split(r"(?<!\d)\.(?!\d)", m.group(0))[0].strip(" ,;-")
            if trecho and trecho not in achados:
                achados.append(trecho[0].upper() + trecho[1:])
    return " · ".join(achados) if achados else "Consultar edital"


def parse_jornada(texto: str) -> str:
    for padrao in [
        r"(?:jornada|carga\s+hor[áa]ria)[^.\n]{0,60}?(\d+\s*(?:a|e|ou\s+at[ée])\s*\d+\s*horas(?:\s*semanais|\s*mensais)?)",
        r"(?:jornada|carga\s+hor[áa]ria)[^.\n]{0,60}?(\d+\s*horas\s*semanais)",
        r"\b(\d+\s*(?:a|e)\s*\d+\s*horas\s*semanais)\b",
        r"\b(\d+\s*horas\s*semanais)\b",
    ]:
        m = re.search(padrao, texto, re.I)
        if m:
            s = re.sub(r"\s+", " ", m.group(1).strip())
            return s if "semanais" in s or "mensais" in s else s + " semanais"
    return "Consultar edital"


def parse_faixa_salarial(texto: str, vagas_salario_listagem: str) -> str:
    m = re.search(
        r"(?:remunera[çc][õo]es|sal[áa]rios|vencimentos|ganhos)[^.\n]{0,50}?(R\$\s*[\d.,]+\s*(?:a|at[ée]|e)\s*R\$\s*[\d.,]+)",
        texto,
        re.I,
    )
    if m:
        return re.sub(r"\s+", " ", m.group(1))
    sals = salarios_no_texto(vagas_salario_listagem)
    if sals:
        return f"Até {brl(max(sals))}"
    return "Consultar edital"


def extrair_pagina_noticia(page_html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(page_html, "html.parser")

    arquivos_edital = []
    link_provas = None
    for a in soup.select("#links a"):
        txt = a.get_text(" ", strip=True)
        href = (a.get("href") or "").strip()
        if "edital-pdf-link" in (a.get("class") or []) or "edital" in txt.lower() or "errata" in txt.lower() or "aviso" in txt.lower():
            if txt and txt not in arquivos_edital:
                arquivos_edital.append(txt)
        elif "provas" in href.lower() or "provas" in txt.lower():
            if href.startswith("http"):
                link_provas = href

    art = soup.select_one("#noticia") or soup.select_one("article") or soup.body
    link_banca = None
    nome_banca = None
    cargos_li: List[str] = []
    if art:
        for a in art.select("a[href]"):
            href = (a.get("href") or "").strip()
            if href.startswith("http") and "pciconcursos.com.br" not in href.lower():
                link_banca = href
                txt_a = a.get_text(" ", strip=True)
                if txt_a and not txt_a.startswith("www.") and len(txt_a) < 80:
                    nome_banca = txt_a
                break

        for li in art.select("li"):
            t_li = li.get_text(" ", strip=True).rstrip(";.")
            if 3 <= len(t_li) <= 240 and not CORTE_RODAPE.search(t_li):
                if t_li not in cargos_li:
                    cargos_li.append(t_li)

        for tag in art.select("script, style, noscript, iframe, aside, .compartilhar, .relacionadas"):
            tag.decompose()
        linhas = [l.strip() for l in art.get_text("\n").splitlines()]
        texto = "\n".join(l for l in linhas if l)
    else:
        texto = ""

    m = CORTE_RODAPE.search(texto)
    if m:
        texto = texto[: m.start()]
    texto = texto.strip()

    return {
        "texto": texto,
        "cargos_li": cargos_li[:120],
        "arquivos_edital": arquivos_edital,
        "link_provas": link_provas,
        "link_banca": link_banca,
        "nome_banca": nome_banca,
        "data_prova": parse_data_prova(texto),
        "regime": parse_regime(texto),
        "beneficios": parse_beneficios(texto),
        "jornada": parse_jornada(texto),
    }


def extrair_linhas_fisio(texto: str) -> List[str]:
    achados = []
    for linha in texto.splitlines():
        if FISIO_REGEX.search(linha):
            l = linha.strip()
            if len(l) > 180:
                continue
            if l not in achados:
                achados.append(l)
    if not achados:
        for linha in texto.splitlines():
            if FISIO_REGEX.search(linha):
                l = linha.strip()
                i = FISIO_REGEX.search(l).start()
                recorte = ("…" if i > 80 else "") + l[max(0, i - 80) : i + 120] + ("…" if i + 120 < len(l) else "")
                achados.append(recorte)
                break
    return achados


# --------------------------------------------------------------------------- #
# 3) IA (Gemini) — Extração Estruturada Completa para Novos Concursos
# --------------------------------------------------------------------------- #
_client = None
_ai_calls = 0

try:
    from pydantic import BaseModel, Field

    class CargoExtraido(BaseModel):
        nome: str = Field(description="Nome exato do cargo.")
        escolaridade: Literal["fundamental", "medio", "tecnico", "superior", "desconhecida"] = Field(
            description=(
                "'medio' = exige APENAS ensino médio completo (sem curso técnico); "
                "'tecnico' = exige curso técnico; 'superior' = exige graduação."
            )
        )
        vagas: Optional[str] = Field(default=None, description="Ex.: '1 vaga + CR', '4 vagas', 'CR'.")
        salario: Optional[float] = Field(
            default=None,
            description="Salário/vencimento base específico deste cargo em R$ (número). Use null se não informado.",
        )
        carga_horaria: Optional[str] = Field(
            default=None, description="Carga horária semanal específica do cargo, ex.: '30h semanais'."
        )
        regime: Optional[str] = Field(
            default=None, description="Regime do cargo: 'Estatutário', 'CLT (Celetista)', 'Residência (Bolsa)', etc."
        )
        requisitos: Optional[str] = Field(
            default=None,
            description="Requisitos técnicos ou de escolaridade para assumir o cargo (ex.: apenas Ensino Médio, CNH B, Curso Técnico + Conselho).",
        )

    class AnaliseConcurso(BaseModel):
        cidade: Optional[str] = Field(default=None, description="Município de SP onde ocorrem as vagas.")
        banca: Optional[str] = Field(default=None, description="Nome da banca organizadora.")
        data_prova: Optional[str] = Field(default=None, description="Data da prova objetiva (DD/MM/AAAA).")
        regime_geral: Optional[str] = Field(
            default=None, description="Regime de contratação ('Estatutário', 'CLT (Celetista)', 'Temporário', etc.)."
        )
        beneficios: Optional[str] = Field(
            default=None,
            description="Benefícios citados (VA, VR, VT, auxílio-saúde, prêmio produtividade) com valores em R$.",
        )
        jornada_geral: Optional[str] = Field(default=None, description="Jornada semanal informada.")
        resumo_conteudo_fisio: Optional[List[str]] = Field(
            default=None,
            description="Se houver cargo de Fisioterapeuta/Fisioterapia, lista de 4 a 6 tópicos do conteúdo programático.",
        )
        cargos: List[CargoExtraido] = Field(description="Cargos citados na notícia.")

    PYDANTIC_OK = True
except ImportError:  # pragma: no cover
    PYDANTIC_OK = False

SYSTEM_INSTRUCTION = (
    "Você é um especialista em editais de concursos públicos brasileiros em São Paulo. "
    "Extraia cidade, banca, data da prova objetiva (DD/MM/AAAA), regime jurídico, benefícios "
    "(VA, VR, VT com valores quando houver), jornada semanal e a lista de cargos com escolaridade, "
    "salário específico e requisitos técnicos para assumir o cargo."
)


def get_client():
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def analisar_com_ia(texto: str, usar_busca: bool = False) -> Optional[dict]:
    global _ai_calls
    if not (GEMINI_API_KEY and PYDANTIC_OK) or _ai_calls >= MAX_AI_CALLS:
        return None

    tentativas_cfg = []
    if usar_busca:
        tentativas_cfg.append((GEMINI_SEARCH_MODEL, [{"type": "google_search"}]))
    tentativas_cfg.append((GEMINI_MODEL, None))

    for modelo, tools in tentativas_cfg:
        for tentativa in range(1, 3):
            try:
                _ai_calls += 1
                kwargs: Dict[str, Any] = {
                    "model": modelo,
                    "system_instruction": SYSTEM_INSTRUCTION,
                    "input": texto[:12000],
                    "response_format": {
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": AnaliseConcurso.model_json_schema(),
                    },
                    "store": False,
                }
                if tools:
                    kwargs["tools"] = tools
                interaction = get_client().interactions.create(**kwargs)
                analise = AnaliseConcurso.model_validate_json(interaction.output_text)
                time.sleep(AI_DELAY_S)
                return analise.model_dump()
            except Exception as e:  # noqa: BLE001
                log(f"  IA ({modelo}, tentativa {tentativa}) aviso: {str(e)[:140]}")
                if tools:
                    break
                time.sleep(8 * tentativa)
    return None


# --------------------------------------------------------------------------- #
# 4) Conteúdo Programático e Especificações Técnicas Padrão
# --------------------------------------------------------------------------- #
def conteudo_padrao_fisio(banca: str, regime: str) -> List[str]:
    b = f" ({banca})" if banca and banca != "Consultar edital" else ""
    return [
        f"Língua Portuguesa{b}: Interpretação de textos, ortografia oficial, morfologia, sintaxe, concordância, regência, crase e pontuação",
        "Políticas Públicas de Saúde e Legislação do SUS: Constituição Federal (arts. 196 a 200), Leis Orgânicas da Saúde (8.080/90 e 8.142/90), PNAB e Redes de Atenção à Saúde",
        "Fundamentos de Fisioterapia: Anatomia, fisiologia humana e do exercício, neurofisiologia, biomecânica, cinesiologia, semiologia e avaliação cinético-funcional",
        "Recursos Terapêuticos: Cinesioterapia, eletrotermofototerapia, mecanoterapia, terapia manual, hidroterapia, órteses e próteses",
        "Fisioterapia Clínica e Preventiva: Traumato-ortopédica, reumatológica, neurofuncional (adulto e infantil), cardiorrespiratória, uroginecológica, geriátrica e Saúde da Família",
        "Ética e Legislação Profissional: Código de Ética e Deontologia da Fisioterapia e resoluções do COFFITO/CREFITO",
    ]


def conteudo_padrao_medio(cargo_nome: str, banca: str) -> List[str]:
    b = f" ({banca})" if banca and banca != "Consultar edital" else ""
    return [
        f"Língua Portuguesa{b}: Compreensão e interpretação de textos, gramática normativa, concordância, regência, pontuação e redação oficial",
        "Matemática e Raciocínio Lógico: Operações fundamentais, porcentagem, razão e proporção, regra de três, equações, geometria básica e lógica proposicional",
        "Noções de Informática: Sistema operacional Windows, editores de texto (Word), planilhas (Excel), internet, correio eletrônico e segurança da informação",
        f"Conhecimentos Específicos ({cargo_nome}): Rotinas administrativas/operacionais, atendimento ao público, noções de Administração Pública e legislação específica do órgão",
    ]


def inferir_requisitos_cargo(cargo_nome: str, niveis: str) -> tuple[str, str]:
    """Retorna (escolaridade_tipo, descricao_requisitos) para cargos extraídos automaticamente."""
    cn = norm(cargo_nome)
    nv = norm(niveis)
    eh_tec = bool(
        re.search(
            r"\b(tecnico|auxiliar\s+de\s+enfermagem|desenhista|topografo|radiologia|contabilidade|seguranca\s+do\s+trabalho|edificacoes|informatica|audiovisual)\b",
            cn,
        )
    ) and "escrevente tecnico" not in cn and "tecnico de administracao" not in cn

    if "guarda" in cn:
        return (
            "medio",
            "Exige Ensino Médio completo + CNH (geralmente 'A/B' ou 'B') + idade/altura previstas no edital + aprovação em Teste de Aptidão Física (TAF) e avaliação psicológica.",
        )
    if "motorista" in cn:
        return (
            "medio",
            "Exige Ensino Médio completo + Carteira Nacional de Habilitação (CNH) categoria 'D' ou 'E' válida + curso especializado quando aplicável e prova prática de direção.",
        )
    if "comunitario de saude" in cn or "endemias" in cn:
        return (
            "medio",
            "Exige APENAS Ensino Médio completo (sem curso técnico) + residir na área/microárea de atuação desde a data da publicação do edital (para ACS) + conclusão do curso introdutório.",
        )
    if eh_tec or ("tecnico" in nv and "medio" not in nv):
        return (
            "medio_tecnico",
            f"Exige Ensino Médio completo + Curso Técnico/Profissionalizante específico na área ({cargo_nome}) e registro ativo no respectivo Conselho de Classe (COREN, CFT, CRTR, CRC ou MTE) quando aplicável.",
        )
    return (
        "medio",
        f"Exige APENAS Ensino Médio completo reconhecido pelo MEC para assumir o cargo ({cargo_nome}), sem necessidade de curso técnico profissionalizante.",
    )


# --------------------------------------------------------------------------- #
# 5) Classificação e Montagem dos Concursos Enriquecidos (SP)
# --------------------------------------------------------------------------- #
CARGOS_MEDIO_CONHECIDOS = re.compile(
    r"\b(agente\s+administrativo|assistente\s+administrativo|auxiliar\s+administrativo|"
    r"escritur[áa]rio|oficial\s+legislativo|oficial\s+de\s+finan[çc]as|inspetor\s+de\s+alunos|"
    r"agente\s+comunit[áa]rio\s+de\s+sa[úu]de|agente\s+de\s+combate\s+[àa]s\s+endemias|"
    r"agente\s+de\s+controle\s+de\s+endemias|agente\s+de\s+fiscaliza[çc][ãa]o|fiscal|"
    r"monitor\s+de\s+transporte|monitor\s+de\s+creche|monitor\s+escolar|recepcionista|almoxarife|"
    r"assistente\s+de\s+suporte\s+acad[êe]mico|guarda\s+civil|guarda\s+municipal|telefonista|"
    r"apoio\s+administrativo|profissional\s+de\s+apoio|auxiliar\s+de\s+desenvolvimento|"
    r"auxiliar\s+de\s+servi[çc]os\s+educacionais|motorista)\b",
    re.I,
)


def eh_novo_24h(info: dict, agora: datetime) -> bool:
    if info.get("is_baseline", False):
        return False
    ts_str = info.get("first_seen_ts")
    if not ts_str:
        return False
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=BRT)
        segundos = (agora - dt).total_seconds()
        return 0 <= segundos <= 86400
    except ValueError:
        return False


def montar_concurso_sp(c: dict, info: dict, enriquecidos: Dict[str, dict], agora: datetime) -> None:
    url = c["url"]
    enriq = enriquecidos.get(url, {})
    ia = info.get("ia") or {}
    det = info.get("detalhes") or {}

    cidade_ia = enriq.get("cidade") or ia.get("cidade")
    cidade = detectar_cidade(c["orgao"], c["titulo"], url, det.get("texto", ""), cidade_ia)
    dist = info_distancia(cidade)
    c["cidade"] = dist["cidade"]
    c["km_ribeirao_preto"] = dist["km_ribeirao_preto"]
    c["km_jarinu"] = dist["km_jarinu"]

    c["banca"] = (
        enriq.get("banca")
        or ia.get("banca")
        or det.get("nome_banca")
        or "Consultar edital"
    )
    c["site_banca"] = enriq.get("site_banca") or det.get("link_banca") or ""
    c["link_edital"] = f"{url}#links"
    c["arquivos_edital"] = det.get("arquivos_edital") or ["EDITAL COMPLETO E ANEXOS"]
    c["link_provas"] = det.get("link_provas") or ""
    c["data_prova"] = (
        enriq.get("data_prova")
        or ia.get("data_prova")
        or det.get("data_prova")
        or "Consultar edital"
    )
    c["regime_geral"] = (
        enriq.get("regime")
        or ia.get("regime_geral")
        or det.get("regime")
        or "Consultar edital"
    )
    c["beneficios_gerais"] = (
        enriq.get("beneficios")
        or ia.get("beneficios")
        or det.get("beneficios")
        or "Consultar edital"
    )
    c["jornada_geral"] = (
        ia.get("jornada_geral")
        or det.get("jornada")
        or "Consultar edital"
    )
    c["faixa_salarial"] = parse_faixa_salarial(det.get("texto", ""), c.get("vagas_salario", ""))

    # Lista completa de cargos deste concurso para a Aba 4 (Busca por Cargo Específico)
    cargos_todos = []
    for cl in det.get("cargos_li") or []:
        if cl not in cargos_todos:
            cargos_todos.append(cl)
    for cg in ia.get("cargos") or []:
        nm = cg.get("nome")
        if nm and nm not in cargos_todos:
            cargos_todos.append(nm)
    if not cargos_todos and c.get("cargos_resumo") and "Vários" not in c["cargos_resumo"]:
        cargos_todos = [x.strip() for x in c["cargos_resumo"].split(",") if x.strip()]
    c["cargos_lista"] = cargos_todos

    c["first_seen_ts"] = info.get("first_seen_ts", "2026-10-20T07:00:00-03:00")
    c["is_baseline"] = bool(info.get("is_baseline", False))
    c["novo"] = eh_novo_24h(info, agora)

    # ---------------- 1) FISIOTERAPIA ---------------- #
    fisio_linhas = info.get("fisio_linhas", [])
    c["fisio_linhas"] = fisio_linhas
    c["fisio"] = bool(enriq.get("fisio")) or bool(fisio_linhas) or bool(FISIO_REGEX.search(c.get("cargos_resumo", "")))

    if c["fisio"]:
        f_enriq = enriq.get("fisio") or {}
        cargo_ia_fisio = next(
            (x for x in (ia.get("cargos") or []) if FISIO_REGEX.search(x.get("nome", ""))),
            {},
        )
        linha_bruta = fisio_linhas[0] if fisio_linhas else "Fisioterapeuta"
        m_vagas = re.search(r"\(([^)]+)\)", linha_bruta)
        vagas_raw = f_enriq.get("vagas") or cargo_ia_fisio.get("vagas") or (m_vagas.group(1) if m_vagas else "CR")
        vagas_im, tem_cr, vagas_txt = extrair_vagas_info(vagas_raw)
        if "vagas_imediatas" in f_enriq:
            vagas_im = f_enriq["vagas_imediatas"]
            tem_cr = f_enriq.get("tem_cr", tem_cr)
            vagas_txt = f_enriq.get("vagas", vagas_txt)

        sal_fisio = f_enriq.get("salario") if "salario" in f_enriq else cargo_ia_fisio.get("salario")
        sal_det = f_enriq.get("salario_detalhe")
        if not sal_det:
            sal_det = f"{brl(sal_fisio)} (vencimento base)" if sal_fisio else f"Faixa do edital: {c['faixa_salarial']}"

        c["fisio_detalhes"] = {
            "cargo": f_enriq.get("cargo") or cargo_ia_fisio.get("nome") or re.sub(r"\s*\([^)]*\)", "", linha_bruta).strip(),
            "vagas": vagas_txt,
            "vagas_imediatas": vagas_im,
            "tem_cr": tem_cr,
            "salario": sal_fisio,
            "salario_exibicao": brl(sal_fisio) if sal_fisio else c["faixa_salarial"],
            "salario_detalhe": sal_det,
            "carga_horaria": f_enriq.get("carga_horaria") or cargo_ia_fisio.get("carga_horaria") or c["jornada_geral"],
            "regime": f_enriq.get("regime") or cargo_ia_fisio.get("regime") or c["regime_geral"],
            "escolaridade_tipo": "superior",
            "requisitos": (
                f_enriq.get("requisitos")
                or cargo_ia_fisio.get("requisitos")
                or "Ensino Superior completo em Fisioterapia + Registro regular ativo no CREFITO-3."
            ),
            "beneficios": f_enriq.get("beneficios") or c["beneficios_gerais"],
            "resumo_conteudo": (
                f_enriq.get("resumo_conteudo")
                or ia.get("resumo_conteudo_fisio")
                or conteudo_padrao_fisio(c["banca"], c["regime_geral"])
            ),
        }

    # ---------------- 2) NÍVEL MÉDIO > R$ 5.000 & 3) OUTRAS FAIXAS ---------------- #
    c["medio_confirmado"] = []
    c["medio_outros"] = []

    if enriq.get("medio"):
        for item in enriq["medio"]:
            c["medio_confirmado"].append(item)
            c["medio_outros"].append(item)
        return

    if enriq.get("medio_outros"):
        for item in enriq["medio_outros"]:
            c["medio_outros"].append(item)
        return

    if enriq.get("medio_excluido"):
        return

    # Extração automática para os demais concursos de Nível Médio / Técnico em SP
    niveis_str = c.get("niveis", "")
    tem_med_listagem = bool(re.search(r"m[ée]dio|t[ée]cnico", niveis_str, re.I))
    if not tem_med_listagem and not info.get("tem_medio"):
        return

    sal_max = max([v for v in (c.get("salario_max_listagem"), info.get("salario_max_texto")) if v] or [0]) or None
    c["salario_max"] = sal_max

    # Filtra cargos de nível médio/técnico nos <li> ou resumo da listagem
    cargos_med = []
    if c.get("cargos_resumo") and "Vários" not in c["cargos_resumo"]:
        # Quando a listagem já traz os cargos explícitos
        for p in [x.strip() for x in c["cargos_resumo"].split(",") if x.strip()]:
            if not re.search(
                r"\b(m[ée]dico|professor|docente|peb|diretor|psic[óo]logo|engenheiro|arquiteto|advogado|procurador|contador|enfermeiro|dentista|farmac[êe]utico|nutricionista|fisioterapeuta|terapeuta|assistente\s+social)\b",
                p,
                re.I,
            ):
                cargos_med.append(p)
    if not cargos_med:
        for cl in cargos_todos:
            if re.search(r"\b(docente|professor|peb)\b", cl, re.I):
                continue
            if CARGOS_MEDIO_CONHECIDOS.search(cl) or re.search(r"\bt[ée]cnico\b", cl, re.I):
                cargos_med.append(cl)

    if not cargos_med and tem_med_listagem and "Superior" not in niveis_str:
        resumo_c = c.get("cargos_resumo") or ""
        if resumo_c and "Vários" not in resumo_c and not re.search(r"\b(docente|professor|peb)\b", resumo_c, re.I):
            cargos_med = [resumo_c]

    if not cargos_med:
        return

    nomes_limpos = [re.sub(r"\s*\([^)]*\)", "", x).strip() for x in cargos_med[:4]]
    nome_exib = " / ".join(nomes_limpos)
    if len(cargos_med) > 4:
        nome_exib += f" (+{len(cargos_med) - 4} cargos)"

    v_im, t_cr, v_txt = extrair_vagas_info(c.get("vagas_salario"))
    esc_tipo, req_txt = inferir_requisitos_cargo(nome_exib, niveis_str)

    # Se o edital também tem Nível Superior, o salário máximo da listagem é do cargo superior;
    # nesses casos estimamos ou indicamos a faixa salarial de nível médio
    tem_superior = "Superior" in niveis_str
    sal_cargo = sal_max if (sal_max and not tem_superior) else (min(sal_max, 3200.0) if sal_max else None)
    sal_det = (
        f"{brl(sal_max)} (vencimento informado no edital)"
        if (sal_max and not tem_superior)
        else f"Faixa do edital: {c['faixa_salarial']} (consultar tabela de Nível Médio/Técnico no Anexo I)"
    )

    item_auto = {
        "nome": nome_exib,
        "vagas": v_txt,
        "vagas_imediatas": v_im,
        "tem_cr": t_cr,
        "salario": sal_cargo,
        "salario_detalhe": sal_det,
        "carga_horaria": c["jornada_geral"],
        "regime": c["regime_geral"],
        "escolaridade_tipo": esc_tipo,
        "requisitos": req_txt,
        "beneficios": c["beneficios_gerais"],
        "resumo_conteudo": conteudo_padrao_medio(nomes_limpos[0], c["banca"]),
    }
    if sal_cargo and sal_cargo > SALARIO_MINIMO_MEDIO and not tem_superior:
        c["medio_confirmado"].append(item_auto)
    c["medio_outros"].append(item_auto)


# --------------------------------------------------------------------------- #
# 6) Coleta Nacional (Brasil Todo + Todos os Estados)
# --------------------------------------------------------------------------- #
def coletar_concursos_brasil(cache_sp: Dict[str, dict], enriquecidos: Dict[str, dict]) -> List[dict]:
    cache_br: Dict[str, dict] = load_json(CACHE_BRASIL_FILE, {})
    vistos_url: Dict[str, dict] = {}

    for regiao, r_url in REGIONAL_URLS.items():
        log(f"Baixando listagem regional ({regiao}): {r_url}")
        try:
            itens = parse_listing(fetch(r_url), regiao_padrao=regiao)
            for it in itens:
                u = it["url"]
                if u not in vistos_url:
                    vistos_url[u] = it
        except Exception as e:  # noqa: BLE001
            log(f"  aviso ao baixar região {regiao}: {e}")

    lista_br = list(vistos_url.values())
    log(f"Total de concursos ativos no Brasil: {len(lista_br)}")

    # Identifica páginas "Vários Cargos" que ainda não estão no cache_sp nem no cache_br
    urls_para_baixar = []
    for it in lista_br:
        u = it["url"]
        if u in cache_sp and (cache_sp[u].get("detalhes") or {}).get("cargos_li") is not None:
            continue
        if u in cache_br:
            continue
        if "Vários" in it.get("cargos_resumo", "") or it["uf"] == "SP":
            urls_para_baixar.append(u)

    if urls_para_baixar:
        log(f"Extraindo lista de cargos de {len(urls_para_baixar)} editais 'Vários Cargos' (em paralelo)...")

        def _worker(u: str) -> tuple[str, Optional[dict]]:
            try:
                det = extrair_pagina_noticia(fetch(u))
                return u, {
                    "cargos_li": det["cargos_li"],
                    "data_prova": det["data_prova"],
                    "regime": det["regime"],
                    "beneficios": det["beneficios"],
                    "jornada": det["jornada"],
                    "nome_banca": det["nome_banca"],
                    "link_banca": det["link_banca"],
                    "arquivos_edital": det["arquivos_edital"],
                }
            except Exception:  # noqa: BLE001
                return u, None

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            for idx, (u, res) in enumerate(ex.map(_worker, urls_para_baixar), 1):
                if res is not None:
                    cache_br[u] = res
                if idx % 50 == 0 or idx == len(urls_para_baixar):
                    log(f"  progresso Brasil: {idx}/{len(urls_para_baixar)} páginas processadas")

        ativos_br = {it["url"] for it in lista_br}
        cache_br = {u: v for u, v in cache_br.items() if u in ativos_br}
        CACHE_BRASIL_FILE.write_text(json.dumps(cache_br, ensure_ascii=False, indent=1), encoding="utf-8")

    # Monta catálogo compacto de todos os concursos do Brasil para a Aba 4
    catalogo_br = []
    for it in lista_br:
        u = it["url"]
        enriq = enriquecidos.get(u, {})
        sp_info = cache_sp.get(u, {})
        sp_det = sp_info.get("detalhes") or {}
        sp_ia = sp_info.get("ia") or {}
        br_det = cache_br.get(u, {})

        cargos_lista: List[str] = []
        for fonte_lista in (
            br_det.get("cargos_li") or [],
            sp_det.get("cargos_li") or [],
            [x.get("nome", "") for x in (sp_ia.get("cargos") or []) if x.get("nome")],
        ):
            for cg in fonte_lista:
                if cg and cg not in cargos_lista:
                    cargos_lista.append(cg)

        if enriq.get("fisio"):
            fc = enriq["fisio"].get("cargo")
            if fc and fc not in cargos_lista:
                cargos_lista.insert(0, fc)
        for m_item in (enriq.get("medio") or []) + (enriq.get("medio_outros") or []):
            mc = m_item.get("nome")
            if mc and mc not in cargos_lista:
                cargos_lista.insert(0, mc)

        if not cargos_lista and it.get("cargos_resumo") and "Vários" not in it["cargos_resumo"]:
            cargos_lista = [x.strip() for x in it["cargos_resumo"].split(",") if x.strip()]

        cidade_sp = None
        km_rp = None
        km_ja = None
        if it["uf"] == "SP":
            cidade_sp = detectar_cidade(it["orgao"], it["titulo"], u, "", enriq.get("cidade") or sp_ia.get("cidade"))
            d_info = info_distancia(cidade_sp)
            cidade_sp = d_info["cidade"]
            km_rp = d_info["km_ribeirao_preto"]
            km_ja = d_info["km_jarinu"]

        catalogo_br.append(
            {
                "url": u,
                "orgao": it["orgao"],
                "titulo": it["titulo"],
                "uf": it["uf"] or "BR",
                "regiao": it["regiao"],
                "cidade": cidade_sp or it["uf"] or "Nacional",
                "km_rp": km_rp,
                "km_ja": km_ja,
                "vagas_salario": it["vagas_salario"],
                "salario_max": it["salario_max_listagem"],
                "cargos_resumo": it["cargos_resumo"],
                "niveis": it["niveis"],
                "inscricao_ate": it["inscricao_ate"] or "Consultar edital",
                "data_prova": (
                    enriq.get("data_prova")
                    or sp_ia.get("data_prova")
                    or sp_det.get("data_prova")
                    or br_det.get("data_prova")
                    or "Consultar edital"
                ),
                "banca": (
                    enriq.get("banca")
                    or sp_ia.get("banca")
                    or sp_det.get("nome_banca")
                    or br_det.get("nome_banca")
                    or "Consultar edital"
                ),
                "site_banca": enriq.get("site_banca") or sp_det.get("link_banca") or br_det.get("link_banca") or "",
                "regime": (
                    enriq.get("regime")
                    or sp_ia.get("regime_geral")
                    or sp_det.get("regime")
                    or br_det.get("regime")
                    or "Consultar edital"
                ),
                "beneficios": (
                    enriq.get("beneficios")
                    or sp_ia.get("beneficios")
                    or sp_det.get("beneficios")
                    or br_det.get("beneficios")
                    or "Consultar edital"
                ),
                "jornada": (
                    sp_ia.get("jornada_geral")
                    or sp_det.get("jornada")
                    or br_det.get("jornada")
                    or "Consultar edital"
                ),
                "cargos": cargos_lista[:80],
            }
        )

    return catalogo_br


# --------------------------------------------------------------------------- #
# 7) Pipeline Principal
# --------------------------------------------------------------------------- #
def tem_nivel_medio(c: dict, texto: str) -> bool:
    if re.search(r"m[ée]dio|t[ée]cnico", c.get("niveis", ""), re.I):
        return True
    return bool(re.search(r"n[íi]vel m[ée]dio|ensino m[ée]dio|curso t[ée]cnico", texto, re.I))


def candidato_relevante(c: dict, info: Optional[dict]) -> bool:
    if info and info.get("fisio_linhas"):
        return True
    if FISIO_REGEX.search(c.get("cargos_resumo", "")) or FISIO_REGEX.search(c.get("titulo", "")):
        return True
    sal = max([v for v in (c.get("salario_max_listagem"), (info or {}).get("salario_max_texto")) if v] or [0])
    tem_med = bool(re.search(r"m[ée]dio|t[ée]cnico", c.get("niveis", ""), re.I)) or bool((info or {}).get("tem_medio"))
    return tem_med and (sal == 0 or sal > SALARIO_MINIMO_MEDIO)


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)
    cache: Dict[str, dict] = load_json(CACHE_FILE, {})
    enriquecidos: Dict[str, dict] = load_json(ENRIQUECIDOS_FILE, {})
    agora = datetime.now(BRT)
    hoje = agora.strftime("%Y-%m-%d")

    for u, item in cache.items():
        if "first_seen_ts" not in item:
            item["first_seen_ts"] = "2026-10-20T07:00:00-03:00"
            item["is_baseline"] = True

    log(f"Baixando listagem principal (Sudeste): {LISTING_URL}")
    todos = parse_listing(fetch(LISTING_URL), regiao_padrao="Sudeste")
    concursos = [c for c in todos if c["uf"] == UF_ALVO]
    log(f"{len(todos)} concursos no Sudeste, {len(concursos)} em {UF_ALVO}.")

    for i, c in enumerate(concursos, 1):
        url = c["url"]
        info = cache.get(url)
        eh_url_nova = info is None
        precisa_detalhes = eh_url_nova or not (info or {}).get("detalhes")
        quer_ia = (
            bool(GEMINI_API_KEY)
            and url not in enriquecidos
            and candidato_relevante(c, info)
            and not (info or {}).get("ia")
        )

        if precisa_detalhes or quer_ia:
            log(f"[{i}/{len(concursos)}] Analisando detalhes SP: {c['orgao']}")
            try:
                det = extrair_pagina_noticia(fetch(url))
            except RuntimeError as e:
                log(f"  ignorado: {e}")
                continue
            time.sleep(HTTP_DELAY_S)
            texto = det["texto"]
            sal_txt = salarios_no_texto(texto)
            fisio_l = extrair_linhas_fisio(texto)
            info = {
                **(info or {}),
                "first_seen": (info or {}).get("first_seen", hoje),
                "first_seen_ts": (info or {}).get("first_seen_ts", agora.isoformat()),
                "is_baseline": (info or {}).get("is_baseline", False),
                "schema_version": SCHEMA_VERSION,
                "hash": hashlib.sha1(texto.encode()).hexdigest()[:12],
                "fisio_linhas": fisio_l,
                "salario_max_texto": max(sal_txt) if sal_txt else None,
                "tem_medio": tem_nivel_medio(c, texto),
                "detalhes": {k: v for k, v in det.items() if k != "texto"},
            }
            if bool(GEMINI_API_KEY) and url not in enriquecidos and candidato_relevante(c, info) and not info.get("ia"):
                ia_res = analisar_com_ia(texto, usar_busca=bool(fisio_l))
                if ia_res:
                    info["ia"] = ia_res
                    info["ia_model"] = GEMINI_MODEL
            cache[url] = info

    # Coleta Brasil todo (e aproveita para preencher cargos_li de SP que estavam faltando)
    catalogo_brasil = coletar_concursos_brasil(cache, enriquecidos)
    cache_br_map = load_json(CACHE_BRASIL_FILE, {})

    for c in concursos:
        url = c["url"]
        info = cache.get(url)
        if info is None:
            continue
        if url in cache_br_map and not (info.get("detalhes") or {}).get("cargos_li"):
            info.setdefault("detalhes", {})["cargos_li"] = cache_br_map[url].get("cargos_li", [])
        montar_concurso_sp(c, info, enriquecidos, agora)

    ativos = {c["url"] for c in concursos}
    cache = {u: v for u, v in cache.items() if u in ativos}
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    fisio = [c for c in concursos if c.get("fisio")]
    medio_ok = [c for c in concursos if c.get("medio_confirmado")]
    medio_todos = [c for c in concursos if c.get("medio_outros")]
    # Ordena medio_todos por salário decrescente por padrão
    medio_todos.sort(
        key=lambda x: max([it.get("salario") or 0 for it in x.get("medio_outros", [])] or [0]),
        reverse=True,
    )

    urls_vistas = set()
    novos_24h = 0
    for c in fisio + medio_ok + medio_todos:
        if c["url"] not in urls_vistas:
            urls_vistas.add(c["url"])
            if c.get("novo"):
                novos_24h += 1

    gerado_em = agora.strftime("%d/%m/%Y %H:%M")

    RESULTS_FILE.write_text(
        json.dumps(
            {
                "gerado_em": gerado_em,
                "gerado_em_iso": agora.isoformat(),
                "fonte": LISTING_URL,
                "total_sp": len(concursos),
                "total_brasil": len(catalogo_brasil),
                "ia_ativa": bool(GEMINI_API_KEY) or bool(enriquecidos),
                "novos_ultimas_24h": novos_24h,
                "fisioterapia": fisio,
                "nivel_medio_acima_5000": medio_ok,
                "nivel_medio_todas_faixas": medio_todos,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    HTML_FILE.write_text(
        render_html(
            fisio=fisio,
            medio_ok=medio_ok,
            medio_todos=medio_todos,
            catalogo_brasil=catalogo_brasil,
            total_sp=len(concursos),
            gerado_em=gerado_em,
        ),
        encoding="utf-8",
    )
    log(
        f"Concluído! Fisioterapia: {len(fisio)} | Nível Médio > R$5k: {len(medio_ok)} | "
        f"Nível Médio/Técnico (Todas as Faixas): {len(medio_todos)} | Brasil: {len(catalogo_brasil)}"
    )
    log(f"Página PWA gerada: {HTML_FILE}")
    return 0


# --------------------------------------------------------------------------- #
# 8) Renderização HTML + UX Bandeira do Brasil + Botões de Filtro + Pix
# --------------------------------------------------------------------------- #
def e(s: Any) -> str:
    return html.escape(str(s if s is not None else ""))


def data_iso_sort(data_br: str) -> str:
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", data_br or "")
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return "9999-12-31"


def horas_num(carga: str) -> int:
    nums = [int(n) for n in re.findall(r"\b(\d+)\s*h", (carga or "").lower())]
    if not nums:
        nums = [int(n) for n in re.findall(r"\b(\d+)\s*hora", (carga or "").lower())]
    return min(nums) if nums else 999


def regime_categoria(regime: str) -> str:
    r = (regime or "").lower()
    if "estatut" in r and "clt" not in r:
        return "estatutario"
    if "clt" in r or "celetista" in r:
        return "clt"
    if "estatut" in r:
        return "estatutario"
    return "outros"


def faixa_salarial_slug(sal: Optional[float]) -> str:
    if sal is None or sal <= 0:
        return "consultar"
    if sal <= 2500:
        return "ate2500"
    if sal <= 3500:
        return "2500a3500"
    if sal <= 5000:
        return "3500a5000"
    return "acima5000"


def badge_escolaridade_html(esc_tipo: str) -> str:
    if esc_tipo == "superior":
        return '<span class="esc-badge esc-sup">🎓 Ensino Superior + CREFITO</span>'
    if esc_tipo == "medio_tecnico":
        return '<span class="esc-badge esc-tec">🛠️ Nível Médio / Curso Técnico</span>'
    return '<span class="esc-badge esc-med">📗 Exige Apenas Ensino Médio</span>'


def render_card(c: dict, modo: str) -> str:
    if modo == "fisio":
        fd = c.get("fisio_detalhes") or {}
        cargo_titulo = fd.get("cargo") or "Fisioterapeuta"
        vagas_txt = fd.get("vagas") or "CR"
        vagas_im = fd.get("vagas_imediatas", 0)
        tem_cr = fd.get("tem_cr", True)
        sal_val = fd.get("salario")
        sal_exib = fd.get("salario_exibicao") or c.get("faixa_salarial") or "Consultar edital"
        sal_det = fd.get("salario_detalhe") or ""
        carga = fd.get("carga_horaria") or c.get("jornada_geral") or "Consultar edital"
        regime = fd.get("regime") or c.get("regime_geral") or "Consultar edital"
        beneficios = fd.get("beneficios") or c.get("beneficios_gerais") or "Consultar edital"
        esc_tipo = fd.get("escolaridade_tipo") or "superior"
        requisitos = fd.get("requisitos") or "Ensino Superior completo em Fisioterapia + Registro no CREFITO-3."
        topicos = fd.get("resumo_conteudo") or []
        icone_cargo = "🩺"
    else:
        chave = "medio_confirmado" if modo == "medio5k" else "medio_outros"
        itens = c.get(chave) or [{}]
        prim = itens[0]
        cargo_titulo = " / ".join(x.get("nome", "") for x in itens if x.get("nome"))
        vagas_txt = prim.get("vagas") or "CR"
        vagas_im = sum(x.get("vagas_imediatas", 0) for x in itens)
        tem_cr = any(x.get("tem_cr", True) for x in itens)
        sals = [x.get("salario") for x in itens if x.get("salario")]
        sal_val = max(sals) if sals else c.get("salario_max")
        sal_exib = brl(sal_val) if sal_val else c.get("faixa_salarial")
        sal_det = prim.get("salario_detalhe") or ""
        carga = prim.get("carga_horaria") or c.get("jornada_geral") or "Consultar edital"
        regime = prim.get("regime") or c.get("regime_geral") or "Consultar edital"
        beneficios = prim.get("beneficios") or c.get("beneficios_gerais") or "Consultar edital"
        esc_tipo = prim.get("escolaridade_tipo") or "medio"
        requisitos = (
            prim.get("requisitos")
            or "Exige Ensino Médio completo conforme especificações do Anexo I do edital."
        )
        topicos = prim.get("resumo_conteudo") or []
        icone_cargo = "💼"

    cidade = c.get("cidade") or "São Paulo"
    km_rp = c.get("km_ribeirao_preto")
    km_ja = c.get("km_jarinu")
    km_rp_attr = km_rp if km_rp is not None else 9999
    km_ja_attr = km_ja if km_ja is not None else 9999
    sal_attr = sal_val if sal_val is not None else 0
    faixa_attr = faixa_salarial_slug(sal_val)
    horas_attr = horas_num(carga)
    reg_cat = regime_categoria(regime)
    prova_sort = data_iso_sort(c.get("data_prova", ""))
    insc_sort = data_iso_sort(c.get("inscricao_ate", ""))

    badge_novo = (
        '<span class="badge-novo" title="Apareceu nas últimas 24h e não estava no período anterior">'
        "✨ CONCURSO NOVO · 24h</span>"
        if c.get("novo")
        else ""
    )

    chips_dist = f'<span class="chip-loc">📍 {e(cidade)}/SP</span>'
    if km_rp is not None:
        chips_dist += f'<span class="chip-dist" title="Distância rodoviária/linear aproximada até Ribeirão Preto/SP">🧭 {km_rp} km de Rib. Preto</span>'
    if km_ja is not None:
        chips_dist += f'<span class="chip-dist" title="Distância aproximada até Jarinu/SP">🧭 {km_ja} km de Jarinu</span>'

    arqs_str = " • ".join(c.get("arquivos_edital") or ["Edital Completo"])
    botoes = (
        f'<a class="btn-link primario" href="{e(c.get("link_edital"))}" target="_blank" rel="noopener" '
        f'title="{e(arqs_str)}">📄 Edital &amp; Anexos</a>'
    )
    if c.get("site_banca"):
        botoes += (
            f'<a class="btn-link" href="{e(c["site_banca"])}" target="_blank" rel="noopener">'
            f'🌐 Banca ({e(c.get("banca"))})</a>'
        )
    if c.get("link_provas"):
        botoes += (
            f'<a class="btn-link" href="{e(c["link_provas"])}" target="_blank" rel="noopener">'
            f"📝 Provas Anteriores</a>"
        )

    lista_topicos = "".join(f"<li>{e(t)}</li>" for t in topicos)
    label_prog = (
        "📚 Ver Resumo do Conteúdo Programático (Fisioterapeuta)"
        if modo == "fisio"
        else "📚 Ver Resumo do Conteúdo Programático do Edital"
    )

    return f"""
    <article class="card"
      data-cidade="{e(cidade)}"
      data-km-rp="{km_rp_attr}"
      data-km-jarinu="{km_ja_attr}"
      data-salario="{sal_attr}"
      data-faixa="{faixa_attr}"
      data-escolaridade="{esc_tipo}"
      data-vagas="{vagas_im}"
      data-tem-cr="{1 if tem_cr else 0}"
      data-regime="{reg_cat}"
      data-horas="{horas_attr}"
      data-prova="{prova_sort}"
      data-inscricao="{insc_sort}"
      data-novo="{1 if c.get('novo') else 0}"
      data-first-seen-ts="{e(c.get('first_seen_ts'))}"
      data-is-baseline="{1 if c.get('is_baseline') else 0}">
      <header class="card-head">
        <div class="head-top">
          <h3><a href="{e(c['url'])}" target="_blank" rel="noopener">{e(c['orgao'])}</a></h3>
          {badge_novo}
        </div>
        <div class="loc-row">
          {chips_dist}
          {badge_escolaridade_html(esc_tipo)}
        </div>
        <p class="titulo">{e(c['titulo'])}</p>
      </header>

      <div class="cargo-banner">
        <div class="cargo-nome">{icone_cargo} <strong>{e(cargo_titulo)}</strong></div>
        <span class="badge-vagas">{e(vagas_txt)}</span>
      </div>

      <div class="req-box">
        <div class="req-title">🎓 Requisitos &amp; Especificações Técnicas para Assumir o Cargo</div>
        <p class="req-text">{e(requisitos)}</p>
      </div>

      <div class="info-grid">
        <div class="info-box destaque-sal">
          <span class="lbl">💰 Remuneração do Cargo</span>
          <strong class="val">{e(sal_exib)}</strong>
          <small class="sub">{e(sal_det)}</small>
        </div>
        <div class="info-box">
          <span class="lbl">🎁 Benefícios (VA / VR / VT)</span>
          <strong class="val-sm">{e(beneficios)}</strong>
        </div>
        <div class="info-box">
          <span class="lbl">🏛️ Regime de Contratação</span>
          <strong class="val-sm">{e(regime)}</strong>
        </div>
        <div class="info-box">
          <span class="lbl">⏱️ Jornada Semanal</span>
          <strong class="val-sm">{e(carga)}</strong>
        </div>
        <div class="info-box destaque-prova">
          <span class="lbl">📅 Data da Prova</span>
          <strong class="val-sm">{e(c.get('data_prova') or 'Consultar edital')}</strong>
          <small class="sub">Banca: {e(c.get('banca') or '—')}</small>
        </div>
        <div class="info-box destaque-prazo">
          <span class="lbl">⏰ Inscrições até</span>
          <strong class="val-sm">{e(c.get('inscricao_ate') or 'Consultar edital')}</strong>
          <small class="sub">{e(c.get('vagas_salario'))}</small>
        </div>
      </div>

      <div class="links-row">{botoes}</div>

      <details class="prog-box">
        <summary>{label_prog}</summary>
        <div class="prog-body">
          <p class="prog-arq">📑 <b>Documentos e Anexos:</b> {e(arqs_str)}</p>
          <ul>{lista_topicos}</ul>
          <a class="prog-cta" href="{e(c.get('link_edital'))}" target="_blank" rel="noopener">
            👉 Abrir Edital Completo e Anexo de Salários / Conteúdo Programático
          </a>
        </div>
      </details>
    </article>"""


def render_secao(
    id_: str,
    icone: str,
    titulo: str,
    desc: str,
    itens: List[dict],
    modo: str,
    ativo: bool = False,
    barra_extra: str = "",
) -> str:
    corpo = "".join(render_card(c, modo) for c in itens)
    cls = "tab-panel ativo" if ativo else "tab-panel"
    return f"""
  <section id="{id_}" class="{cls}" data-total="{len(itens)}">
    <div class="sec-head">
      <div class="sec-title-row">
        <h2>{icone} {titulo}</h2>
        <div class="count-box-lg" title="Concursos vigentes nesta categoria">
          <b class="sec-count">{len(itens)}</b>
          <span>vigentes</span>
        </div>
      </div>
      <p class="desc">{desc}</p>
      {barra_extra}
    </div>
    <div class="grid">{corpo}</div>
    <p class="vazio" style="display:{'none' if itens else 'block'};">
      Nenhum concurso encontrado com os botões de filtro selecionados. Clique em "Limpar Filtros" acima para ver todos.
    </p>
  </section>"""


def render_html(
    fisio: List[dict],
    medio_ok: List[dict],
    medio_todos: List[dict],
    catalogo_brasil: List[dict],
    total_sp: int,
    gerado_em: str,
) -> str:
    # Cidades únicas presentes nos cards de SP para criar os botões pré-definidos de cidade
    cidades_set = sorted({c.get("cidade") for c in (fisio + medio_ok + medio_todos) if c.get("cidade")})
    botoes_cidades = (
        '<button type="button" class="pill-btn ativo" data-filter="cidade" data-val="">Todas as Cidades</button>'
        + "".join(
            f'<button type="button" class="pill-btn" data-filter="cidade" data-val="{e(cid)}">{e(cid)}</button>'
            for cid in cidades_set
        )
    )

    urls_unicas = {}
    for c in fisio + medio_ok + medio_todos:
        urls_unicas[c["url"]] = c
    novos_count = sum(1 for c in urls_unicas.values() if c.get("novo"))

    # Barra rápida de faixas salariais exclusiva do topo da Aba 3 (Nível Médio / Técnico — Todas as Faixas)
    barra_faixas_aba3 = """
    <div class="faixa-highlight-bar">
      <span class="faixa-bar-lbl">💵 Escolha a Faixa de Remuneração (Nível Médio / Técnico):</span>
      <div class="pill-row">
        <button type="button" class="pill-btn pill-gold ativo" data-filter="faixa" data-val="">Todas as Faixas</button>
        <button type="button" class="pill-btn pill-gold" data-filter="faixa" data-val="ate2500">Até R$ 2.500</button>
        <button type="button" class="pill-btn pill-gold" data-filter="faixa" data-val="2500a3500">R$ 2.500 a R$ 3.500</button>
        <button type="button" class="pill-btn pill-gold" data-filter="faixa" data-val="3500a5000">R$ 3.500 a R$ 5.000</button>
        <button type="button" class="pill-btn pill-gold" data-filter="faixa" data-val="acima5000">Acima de R$ 5.000</button>
      </div>
    </div>
    """

    # UFs presentes no catálogo nacional
    ufs_contagem: Dict[str, int] = {}
    for item in catalogo_brasil:
        uf = item.get("uf") or "BR"
        ufs_contagem[uf] = ufs_contagem.get(uf, 0) + 1

    ordem_ufs = [
        "SP", "MG", "RJ", "ES", "PR", "SC", "RS", "DF", "GO", "MS", "MT",
        "BA", "PE", "CE", "RN", "PB", "AL", "SE", "MA", "PI", "PA", "AM", "RO", "TO", "AC", "AP", "RR", "BR",
    ]
    botoes_ufs = (
        f'<button type="button" class="pill-btn uf-btn ativo" data-uf="TODOS">'
        f'🇧🇷 Brasil Todo <span class="mini-cnt">{len(catalogo_brasil)}</span></button>'
    )
    for uf in ordem_ufs:
        if uf in ufs_contagem:
            rotulo = "🌎 Nacional (BR)" if uf == "BR" else uf
            botoes_ufs += (
                f'<button type="button" class="pill-btn uf-btn" data-uf="{uf}">'
                f'{rotulo} <span class="mini-cnt">{ufs_contagem[uf]}</span></button>'
            )

    cargos_sugeridos = [
        "Fisioterapeuta",
        "Enfermeiro",
        "Técnico de Enfermagem",
        "Agente Administrativo",
        "Escriturário",
        "Guarda Municipal",
        "Psicólogo",
        "Nutricionista",
        "Farmacêutico",
        "Dentista",
        "Assistente Social",
        "Engenheiro Civil",
        "Contador",
        "Fiscal",
        "Professor",
        "Motorista",
        "Técnico em Informática",
        "Técnico em Segurança do Trabalho",
    ]
    botoes_cargos_rapidos = (
        '<button type="button" class="pill-btn cargo-quick ativo" data-cargo="">Mostrar Todos os Cargos</button>'
        + "".join(
            f'<button type="button" class="pill-btn cargo-quick" data-cargo="{e(cg)}">{e(cg)}</button>'
            for cg in cargos_sugeridos
        )
    )

    qr_svg = gerar_qr_pix_svg(PIX_KEY)
    catalogo_json = json.dumps(catalogo_brasil, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#006b2d">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Concursos Brasil &amp; SP">
<meta name="description" content="Painel diário de Concursos Públicos — Fisioterapia, Nível Médio/Técnico e Busca por Cargo em SP e em todo o Brasil.">
<link rel="manifest" href="./manifest.webmanifest">
<link rel="icon" type="image/png" sizes="192x192" href="./icon-192.png">
<link rel="apple-touch-icon" href="./icon-192.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&amp;family=Plus+Jakarta+Sans:wght@400;500;600;700;800&amp;display=swap" rel="stylesheet">
<title>Concursos SP &amp; Brasil — Fisioterapia, Nível Médio e Busca por Cargo</title>
<style>
  :root {{
    /* Paleta Inspirada na Bandeira do Brasil */
    --br-green-dark: #005c24;
    --br-green: #009739;
    --br-green-soft: #e8f5ee;
    --br-green-border: #b7e1c7;
    --br-yellow: #FEDD00;
    --br-yellow-soft: #fffbeb;
    --br-yellow-border: #fde047;
    --br-yellow-text: #854d0e;
    --br-blue-dark: #001b52;
    --br-blue: #002776;
    --br-blue-soft: #eef4ff;
    --br-blue-border: #c7d9fe;
    --bg: #f3f7f4;
    --surface: #ffffff;
    --surface-alt: #f8fbf9;
    --border: #d8e4dc;
    --txt: #0f291e;
    --muted: #4b6358;
    --radius-lg: 18px;
    --radius-md: 12px;
    --shadow-sm: 0 2px 10px rgba(0, 45, 18, 0.05);
    --shadow-md: 0 8px 26px rgba(0, 45, 18, 0.08);
  }}

  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--txt);
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }}
  .container {{ max-width: 1320px; margin: 0 auto; padding: 0 20px; }}

  /* Cabeçalho Institucional (Verde, Amarelo e Azul) */
  header.app-bar {{
    background: linear-gradient(135deg, var(--br-blue-dark) 0%, var(--br-blue) 42%, var(--br-green-dark) 100%);
    color: #ffffff;
    padding: 26px 0 22px;
    border-bottom: 5px solid var(--br-yellow);
    box-shadow: 0 6px 24px rgba(0, 39, 118, 0.18);
  }}
  .bar-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 18px;
    flex-wrap: wrap;
  }}
  .brand-badge {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(254, 221, 0, 0.16);
    border: 1px solid rgba(254, 221, 0, 0.5);
    color: var(--br-yellow);
    font-size: 0.78rem;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 999px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 8px;
  }}
  h1 {{
    margin: 0 0 6px;
    font-family: 'Fraunces', Georgia, serif;
    font-size: 1.75rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: #ffffff;
  }}
  .meta {{ color: rgba(255, 255, 255, 0.86); font-size: 0.9rem; }}
  .meta a {{ color: var(--br-yellow); font-weight: 600; text-decoration: none; }}
  .meta a:hover {{ text-decoration: underline; }}

  .btn-pwa {{
    background: var(--br-yellow);
    color: var(--br-blue-dark);
    border: 2px solid #ffffff;
    padding: 11px 20px;
    border-radius: 999px;
    font-weight: 800;
    font-size: 0.92rem;
    font-family: inherit;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.22);
    transition: transform 0.15s, box-shadow 0.15s;
  }}
  .btn-pwa:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0, 0, 0, 0.28); }}

  /* Navegação Principal com Caixinhas Separadas para Contadores */
  .tabs-wrap {{
    margin: 22px 0 18px;
  }}
  nav.tabs {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(275px, 1fr));
    gap: 12px;
  }}
  .tab-item {{
    display: flex;
    align-items: stretch;
    gap: 8px;
  }}
  .tab-btn {{
    flex: 1;
    background: var(--surface);
    color: var(--txt);
    border: 2px solid var(--border);
    padding: 13px 16px;
    border-radius: 14px;
    cursor: pointer;
    font-family: inherit;
    font-size: 0.95rem;
    font-weight: 700;
    text-align: left;
    display: flex;
    align-items: center;
    gap: 10px;
    box-shadow: var(--shadow-sm);
    transition: all 0.16s ease;
  }}
  .tab-btn:hover {{
    border-color: var(--br-green);
    background: var(--br-green-soft);
  }}
  .tab-item.ativo .tab-btn {{
    background: var(--br-green);
    color: #ffffff;
    border-color: var(--br-green-dark);
    box-shadow: 0 6px 18px rgba(0, 151, 57, 0.25);
  }}
  /* Caixinha separada ao lado do nome da aba */
  .tab-count-box {{
    min-width: 78px;
    background: var(--br-blue-soft);
    border: 2px solid var(--br-blue-border);
    color: var(--br-blue);
    border-radius: 14px;
    padding: 6px 10px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    box-shadow: var(--shadow-sm);
    transition: all 0.16s ease;
  }}
  .tab-count-box b {{
    font-size: 1.2rem;
    line-height: 1.1;
    font-weight: 800;
  }}
  .tab-count-box small {{
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 700;
    opacity: 0.85;
  }}
  .tab-item.ativo .tab-count-box {{
    background: var(--br-yellow);
    border-color: #eab308;
    color: var(--br-blue-dark);
    box-shadow: 0 6px 18px rgba(254, 221, 0, 0.35);
  }}

  /* Painel de Filtros em Botões Pré-definidos */
  .filtros-panel {{
    background: var(--surface);
    border: 2px solid var(--border);
    border-top: 5px solid var(--br-green);
    border-radius: var(--radius-lg);
    padding: 18px 20px;
    margin-bottom: 22px;
    box-shadow: var(--shadow-sm);
  }}
  .filtros-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    padding-bottom: 12px;
    margin-bottom: 14px;
    border-bottom: 1px solid var(--border);
  }}
  .filtros-head-title {{
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 1.02rem;
    font-weight: 800;
    color: var(--br-blue);
  }}
  .filtros-actions {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }}
  .btn-limpar {{
    background: var(--surface-alt);
    color: var(--br-blue);
    border: 1.5px solid var(--br-blue-border);
    padding: 8px 14px;
    border-radius: 999px;
    cursor: pointer;
    font-family: inherit;
    font-weight: 700;
    font-size: 0.83rem;
    transition: all 0.15s;
  }}
  .btn-limpar:hover {{
    background: var(--br-blue);
    color: #ffffff;
  }}

  .filter-groups {{
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .f-group {{
    display: grid;
    grid-template-columns: 230px 1fr;
    align-items: flex-start;
    gap: 12px;
    padding: 8px 12px;
    background: var(--surface-alt);
    border-radius: 12px;
    border: 1px solid #e5efe8;
  }}
  @media (max-width: 760px) {{
    .f-group {{ grid-template-columns: 1fr; gap: 8px; }}
  }}
  .f-label {{
    font-size: 0.8rem;
    font-weight: 800;
    color: var(--br-green-dark);
    text-transform: uppercase;
    letter-spacing: 0.03em;
    padding-top: 5px;
  }}
  .pill-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
  }}
  .pill-btn {{
    background: #ffffff;
    color: var(--txt);
    border: 1.5px solid var(--border);
    padding: 6px 13px;
    border-radius: 999px;
    font-family: inherit;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.14s ease;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }}
  .pill-btn:hover {{
    border-color: var(--br-green);
    background: var(--br-green-soft);
    color: var(--br-green-dark);
  }}
  .pill-btn.ativo {{
    background: var(--br-blue);
    color: #ffffff;
    border-color: var(--br-blue-dark);
    font-weight: 700;
    box-shadow: 0 2px 8px rgba(0, 39, 118, 0.22);
  }}
  .pill-btn.pill-gold.ativo {{
    background: var(--br-green);
    color: #ffffff;
    border-color: var(--br-green-dark);
  }}
  .mini-cnt {{
    background: rgba(0, 39, 118, 0.1);
    color: inherit;
    padding: 1px 7px;
    border-radius: 999px;
    font-size: 0.73rem;
    font-weight: 800;
  }}
  .pill-btn.ativo .mini-cnt {{
    background: var(--br-yellow);
    color: var(--br-blue-dark);
  }}

  /* Barra de Destaque de Faixa Salarial na Aba 3 */
  .faixa-highlight-bar {{
    background: var(--br-yellow-soft);
    border: 2px solid var(--br-yellow-border);
    border-radius: 14px;
    padding: 14px 16px;
    margin-bottom: 18px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .faixa-bar-lbl {{
    font-size: 0.88rem;
    font-weight: 800;
    color: var(--br-blue-dark);
  }}

  /* Cabeçalho de Seção com Caixinha Separada */
  main {{ padding-bottom: 40px; }}
  .tab-panel {{ display: none; }}
  .tab-panel.ativo {{ display: block; }}
  .sec-head {{ margin-bottom: 18px; }}
  .sec-title-row {{
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 6px;
  }}
  .sec-title-row h2 {{
    margin: 0;
    font-family: 'Fraunces', Georgia, serif;
    font-size: 1.45rem;
    color: var(--br-blue-dark);
  }}
  .count-box-lg {{
    display: inline-flex;
    align-items: baseline;
    gap: 6px;
    background: var(--br-green);
    color: #ffffff;
    border: 2px solid var(--br-yellow);
    padding: 5px 14px;
    border-radius: 12px;
    box-shadow: 0 3px 10px rgba(0, 151, 57, 0.2);
  }}
  .count-box-lg b {{ font-size: 1.15rem; font-weight: 800; }}
  .count-box-lg span {{ font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; color: var(--br-yellow); }}
  .desc {{ color: var(--muted); margin: 0 0 14px; font-size: 0.94rem; }}

  /* Grid e Cards Alinhados */
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
    gap: 20px;
    align-items: stretch;
  }}
  @media (max-width: 500px) {{
    .grid {{ grid-template-columns: 1fr; }}
  }}

  .card {{
    background: var(--surface);
    border-radius: var(--radius-lg);
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    border: 1.5px solid var(--border);
    border-top: 5px solid var(--br-green);
    box-shadow: var(--shadow-sm);
    transition: transform 0.16s ease, box-shadow 0.16s ease;
  }}
  .card:hover {{
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
    border-color: var(--br-green-border);
  }}

  .head-top {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 10px;
  }}
  .card h3 {{
    margin: 0;
    font-size: 1.15rem;
    line-height: 1.32;
    font-weight: 800;
  }}
  .card h3 a {{
    color: var(--br-blue);
    text-decoration: none;
  }}
  .card h3 a:hover {{
    color: var(--br-green);
    text-decoration: underline;
  }}

  .badge-novo {{
    background: var(--br-yellow);
    color: var(--br-blue-dark);
    border: 1.5px solid #eab308;
    font-size: 0.73rem;
    padding: 4px 10px;
    border-radius: 999px;
    font-weight: 800;
    white-space: nowrap;
  }}

  .loc-row {{
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 8px;
    align-items: center;
  }}
  .chip-loc {{
    background: var(--br-green-soft);
    color: var(--br-green-dark);
    border: 1px solid var(--br-green-border);
    font-size: 0.77rem;
    padding: 3px 10px;
    border-radius: 999px;
    font-weight: 700;
  }}
  .chip-dist {{
    background: var(--surface-alt);
    color: var(--muted);
    border: 1px solid var(--border);
    font-size: 0.75rem;
    padding: 3px 9px;
    border-radius: 999px;
    font-weight: 600;
  }}
  .esc-badge {{
    font-size: 0.74rem;
    padding: 3px 10px;
    border-radius: 999px;
    font-weight: 800;
  }}
  .esc-med {{
    background: #dcfce7;
    color: #14532d;
    border: 1px solid #86efac;
  }}
  .esc-tec {{
    background: #fef9c3;
    color: #713f12;
    border: 1px solid #fde047;
  }}
  .esc-sup {{
    background: var(--br-blue-soft);
    color: var(--br-blue);
    border: 1px solid var(--br-blue-border);
  }}

  .titulo {{
    margin: 6px 0 0;
    color: var(--muted);
    font-size: 0.85rem;
  }}

  .cargo-banner {{
    background: linear-gradient(90deg, var(--br-blue-dark), var(--br-blue));
    color: #ffffff;
    border-radius: var(--radius-md);
    padding: 11px 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }}
  .cargo-nome {{ font-size: 0.94rem; line-height: 1.35; }}
  .badge-vagas {{
    background: var(--br-yellow);
    color: var(--br-blue-dark);
    font-size: 0.76rem;
    padding: 4px 10px;
    border-radius: 999px;
    font-weight: 800;
    white-space: nowrap;
  }}

  /* Box de Especificações Técnicas & Requisitos para Assumir o Cargo */
  .req-box {{
    background: var(--br-yellow-soft);
    border: 1.5px solid var(--br-yellow-border);
    border-left: 5px solid #eab308;
    border-radius: 11px;
    padding: 10px 13px;
  }}
  .req-title {{
    font-size: 0.76rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--br-yellow-text);
    margin-bottom: 3px;
  }}
  .req-text {{
    margin: 0;
    font-size: 0.84rem;
    color: #422006;
    font-weight: 500;
  }}

  /* Grid de Informações Alinhado */
  .info-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 9px;
  }}
  @media (max-width: 440px) {{
    .info-grid {{ grid-template-columns: 1fr; }}
  }}
  .info-box {{
    background: var(--surface-alt);
    border: 1px solid var(--border);
    border-radius: 11px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }}
  .info-box .lbl {{
    font-size: 0.72rem;
    color: var(--muted);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.02em;
  }}
  .info-box .val {{
    font-size: 1.15rem;
    font-weight: 800;
    color: var(--br-green-dark);
  }}
  .info-box .val-sm {{
    font-size: 0.88rem;
    font-weight: 700;
    color: var(--txt);
  }}
  .info-box .sub {{
    font-size: 0.75rem;
    color: var(--muted);
    line-height: 1.35;
  }}
  .destaque-sal {{
    background: var(--br-green-soft);
    border-color: var(--br-green-border);
  }}
  .destaque-prova .val-sm {{ color: var(--br-blue); }}
  .destaque-prazo .val-sm {{ color: #b45309; }}

  /* Botões de Link e Conteúdo Programático */
  .links-row {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }}
  .btn-link {{
    background: var(--surface-alt);
    color: var(--br-blue);
    border: 1.5px solid var(--br-blue-border);
    padding: 7px 13px;
    border-radius: 9px;
    font-size: 0.81rem;
    text-decoration: none;
    font-weight: 700;
    transition: all 0.15s;
  }}
  .btn-link:hover {{
    background: var(--br-blue);
    color: #ffffff;
  }}
  .btn-link.primario {{
    background: var(--br-green);
    color: #ffffff;
    border-color: var(--br-green-dark);
  }}
  .btn-link.primario:hover {{
    background: var(--br-green-dark);
  }}

  details.prog-box {{
    background: var(--surface-alt);
    border: 1.5px solid var(--border);
    border-radius: 11px;
    padding: 9px 13px;
    margin-top: auto;
  }}
  details.prog-box summary {{
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 800;
    color: var(--br-blue);
  }}
  .prog-body {{
    margin-top: 9px;
    font-size: 0.84rem;
    color: var(--txt);
  }}
  .prog-arq {{ margin: 0 0 7px; font-size: 0.8rem; color: var(--muted); }}
  .prog-body ul {{
    margin: 0 0 10px;
    padding-left: 18px;
    display: flex;
    flex-direction: column;
    gap: 5px;
  }}
  .prog-cta {{
    display: inline-block;
    color: var(--br-green-dark);
    font-weight: 800;
    text-decoration: none;
    font-size: 0.83rem;
  }}
  .prog-cta:hover {{ text-decoration: underline; }}

  /* Aba 4: Busca por Cargo Específico e Estados do Brasil */
  .busca-cargo-panel {{
    background: var(--surface);
    border: 2px solid var(--br-blue-border);
    border-top: 5px solid var(--br-blue);
    border-radius: var(--radius-lg);
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: var(--shadow-sm);
    display: flex;
    flex-direction: column;
    gap: 16px;
  }}
  .cargo-input-row {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }}
  .cargo-input-wrap {{
    flex: 1;
    min-width: 260px;
    position: relative;
  }}
  .cargo-input-wrap input {{
    width: 100%;
    padding: 13px 16px;
    border-radius: 12px;
    border: 2px solid var(--br-blue-border);
    background: var(--surface-alt);
    color: var(--txt);
    font-family: inherit;
    font-size: 0.98rem;
    font-weight: 600;
  }}
  .cargo-input-wrap input:focus {{
    outline: none;
    border-color: var(--br-green);
    background: #ffffff;
    box-shadow: 0 0 0 4px rgba(0, 151, 57, 0.12);
  }}
  .cargos-match-list {{
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-top: 4px;
  }}
  .cargo-tag {{
    background: var(--br-green-soft);
    color: var(--br-green-dark);
    border: 1px solid var(--br-green-border);
    padding: 2px 9px;
    border-radius: 999px;
    font-size: 0.76rem;
    font-weight: 700;
  }}

  .vazio {{
    background: var(--surface);
    border: 1.5px dashed var(--border);
    border-radius: var(--radius-lg);
    color: var(--muted);
    text-align: center;
    padding: 36px 16px;
    font-size: 1rem;
    font-weight: 600;
  }}

  /* Rodapé e Botão "☕ Me pague um café" igual ao anexo */
  footer.app-footer {{
    margin-top: 44px;
    padding: 32px 0 48px;
    border-top: 2px solid var(--border);
    background: linear-gradient(180deg, var(--surface) 0%, var(--br-green-soft) 100%);
    text-align: center;
  }}
  .footer-coffee-wrap {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
  }}
  .btn-coffee {{
    background: #286e34;
    color: #ffffff;
    border: none;
    padding: 13px 28px;
    border-radius: 12px;
    font-family: inherit;
    font-size: 1rem;
    font-weight: 700;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 9px;
    box-shadow: 0 4px 14px rgba(40, 110, 52, 0.3);
    transition: transform 0.15s, background 0.15s;
  }}
  .btn-coffee:hover {{
    background: #1f5829;
    transform: translateY(-2px);
  }}
  .footer-note {{
    color: var(--muted);
    font-size: 0.85rem;
    margin: 4px 0 0;
  }}

  /* Modais (Pix e PWA) */
  .modal-bg {{
    position: fixed;
    inset: 0;
    background: rgba(10, 25, 18, 0.62);
    backdrop-filter: blur(3px);
    display: none;
    align-items: center;
    justify-content: center;
    padding: 18px;
    z-index: 1000;
  }}
  .modal-bg.aberto {{ display: flex; }}

  /* Modal Pix idêntico ao anexo do usuário */
  .pix-modal {{
    background: #ffffff;
    border-radius: 20px;
    max-width: 440px;
    width: 100%;
    padding: 24px 26px 26px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
    text-align: center;
    color: #2c3e35;
  }}
  .pix-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
  }}
  .pix-head h3 {{
    margin: 0;
    font-family: 'Fraunces', Georgia, serif;
    font-size: 1.35rem;
    color: #286e34;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .pix-close {{
    background: transparent;
    border: none;
    font-size: 1.25rem;
    color: #889990;
    cursor: pointer;
    padding: 4px 8px;
    line-height: 1;
  }}
  .pix-close:hover {{ color: #2c3e35; }}
  .pix-desc {{
    margin: 0 0 18px;
    font-size: 0.93rem;
    line-height: 1.55;
    color: #6b726e;
  }}
  .pix-qr-box {{
    display: inline-flex;
    padding: 12px;
    background: #ffffff;
    border: 2px solid #dfe7e2;
    border-radius: 16px;
    margin-bottom: 12px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.04);
  }}
  .pix-qr-box svg {{
    display: block;
    width: 210px;
    height: 210px;
  }}
  .pix-receiver {{
    margin: 0 0 16px;
    font-size: 0.84rem;
    color: #7c8782;
    font-weight: 500;
  }}
  .btn-copy-pix {{
    width: 100%;
    background: #286e34;
    color: #ffffff;
    border: none;
    padding: 13px 18px;
    border-radius: 10px;
    font-family: inherit;
    font-size: 0.96rem;
    font-weight: 700;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: background 0.15s;
  }}
  .btn-copy-pix:hover {{ background: #1f5829; }}
</style>
</head>
<body>
  <header class="app-bar">
    <div class="container">
      <div class="bar-row">
        <div>
          <div class="brand-badge">🇧🇷 Monitoramento Diário de Editais · SP &amp; Brasil</div>
          <h1>Concursos Públicos — Fisioterapia &amp; Nível Médio/Técnico</h1>
          <div class="meta">
            Atualizado em <b>{gerado_em}</b> (Brasília) · <b>{total_sp}</b> editais em SP e <b>{len(catalogo_brasil)}</b> no Brasil · Fonte:
            <a href="{LISTING_URL}" target="_blank" rel="noopener">PCI Concursos</a>
          </div>
        </div>
        <button id="btnInstall" class="btn-pwa" type="button">📲 Baixar Aplicativo (PWA)</button>
      </div>
    </div>
  </header>

  <div class="container">
    <!-- Abas com Caixinha Separada para o Número de Concursos Vigentes -->
    <div class="tabs-wrap">
      <nav class="tabs" aria-label="Categorias de Concursos">
        <div class="tab-item ativo" data-tab="fisio">
          <button type="button" class="tab-btn">🩺 Fisioterapia (SP)</button>
          <div class="tab-count-box" title="Concursos vigentes para Fisioterapia em SP">
            <b class="cnt" data-cnt-for="fisio">{len(fisio)}</b>
            <small>vigentes</small>
          </div>
        </div>

        <div class="tab-item" data-tab="medio5k">
          <button type="button" class="tab-btn">💰 Nível Médio &gt; R$ 5.000</button>
          <div class="tab-count-box" title="Concursos vigentes de Nível Médio acima de R$ 5.000 em SP">
            <b class="cnt" data-cnt-for="medio5k">{len(medio_ok)}</b>
            <small>vigentes</small>
          </div>
        </div>

        <div class="tab-item" data-tab="medio_todos">
          <button type="button" class="tab-btn">📊 Nível Médio / Técnico (Faixas)</button>
          <div class="tab-count-box" title="Concursos vigentes de Nível Médio e Técnico em SP em todas as faixas salariais">
            <b class="cnt" data-cnt-for="medio_todos">{len(medio_todos)}</b>
            <small>vigentes</small>
          </div>
        </div>

        <div class="tab-item" data-tab="busca_cargo">
          <button type="button" class="tab-btn">🔎 Buscar Outro Cargo (Brasil)</button>
          <div class="tab-count-box" title="Concursos vigentes em todos os estados do Brasil">
            <b class="cnt" data-cnt-for="busca_cargo">{len(catalogo_brasil)}</b>
            <small>vigentes</small>
          </div>
        </div>
      </nav>
    </div>

    <!-- Painel de Filtros em Botões Pré-definidos (Para as Abas de SP) -->
    <section id="painelFiltrosSp" class="filtros-panel" aria-label="Filtros em botões pré-definidos">
      <div class="filtros-head">
        <div class="filtros-head-title">
          🎛️ Filtros Rápidos (Clique nos botões para filtrar)
        </div>
        <div class="filtros-actions">
          <button type="button" id="btnLimpar" class="btn-limpar">🔄 Limpar Todos os Filtros</button>
        </div>
      </div>

      <div class="filter-groups">
        <div class="f-group">
          <div class="f-label">📍 Perto de Ribeirão Preto</div>
          <div class="pill-row">
            <button type="button" class="pill-btn ativo" data-filter="kmRp" data-val="">Qualquer distância</button>
            <button type="button" class="pill-btn" data-filter="kmRp" data-val="50">Até 50 km</button>
            <button type="button" class="pill-btn" data-filter="kmRp" data-val="100">Até 100 km</button>
            <button type="button" class="pill-btn" data-filter="kmRp" data-val="150">Até 150 km</button>
            <button type="button" class="pill-btn" data-filter="kmRp" data-val="250">Até 250 km</button>
            <button type="button" class="pill-btn" data-filter="kmRp" data-val="350">Até 350 km</button>
          </div>
        </div>

        <div class="f-group">
          <div class="f-label">📍 Perto de Jarinu/SP</div>
          <div class="pill-row">
            <button type="button" class="pill-btn ativo" data-filter="kmJa" data-val="">Qualquer distância</button>
            <button type="button" class="pill-btn" data-filter="kmJa" data-val="50">Até 50 km</button>
            <button type="button" class="pill-btn" data-filter="kmJa" data-val="100">Até 100 km</button>
            <button type="button" class="pill-btn" data-filter="kmJa" data-val="150">Até 150 km</button>
            <button type="button" class="pill-btn" data-filter="kmJa" data-val="250">Até 250 km</button>
            <button type="button" class="pill-btn" data-filter="kmJa" data-val="350">Até 350 km</button>
          </div>
        </div>

        <div class="f-group">
          <div class="f-label">💵 Faixa de Remuneração</div>
          <div class="pill-row">
            <button type="button" class="pill-btn ativo" data-filter="faixa" data-val="">Qualquer valor</button>
            <button type="button" class="pill-btn" data-filter="faixa" data-val="ate2500">Até R$ 2.500</button>
            <button type="button" class="pill-btn" data-filter="faixa" data-val="2500a3500">R$ 2.500 a R$ 3.500</button>
            <button type="button" class="pill-btn" data-filter="faixa" data-val="3500a5000">R$ 3.500 a R$ 5.000</button>
            <button type="button" class="pill-btn" data-filter="faixa" data-val="acima5000">Acima de R$ 5.000</button>
          </div>
        </div>

        <div class="f-group">
          <div class="f-label">🎓 Exigência do Edital</div>
          <div class="pill-row">
            <button type="button" class="pill-btn ativo" data-filter="escolaridade" data-val="">Todas</button>
            <button type="button" class="pill-btn" data-filter="escolaridade" data-val="medio">📗 Apenas Ensino Médio</button>
            <button type="button" class="pill-btn" data-filter="escolaridade" data-val="medio_tecnico">🛠️ Médio / Curso Técnico</button>
            <button type="button" class="pill-btn" data-filter="escolaridade" data-val="superior">🎓 Ensino Superior</button>
          </div>
        </div>

        <div class="f-group">
          <div class="f-label">👥 Número de Vagas</div>
          <div class="pill-row">
            <button type="button" class="pill-btn ativo" data-filter="vagas" data-val="todas">Todas (Vagas + CR)</button>
            <button type="button" class="pill-btn" data-filter="vagas" data-val="1">Com Vagas Imediatas (≥ 1)</button>
            <button type="button" class="pill-btn" data-filter="vagas" data-val="3">≥ 3 Vagas Imediatas</button>
            <button type="button" class="pill-btn" data-filter="vagas" data-val="5">≥ 5 Vagas Imediatas</button>
            <button type="button" class="pill-btn" data-filter="vagas" data-val="cr">Somente Cadastro de Reserva (CR)</button>
          </div>
        </div>

        <div class="f-group">
          <div class="f-label">🏛️ Regime &amp; Jornada</div>
          <div class="pill-row">
            <button type="button" class="pill-btn ativo" data-filter="regime" data-val="">Todos os Regimes</button>
            <button type="button" class="pill-btn" data-filter="regime" data-val="estatutario">Estatutário (Efetivo)</button>
            <button type="button" class="pill-btn" data-filter="regime" data-val="clt">CLT (Celetista)</button>
            <button type="button" class="pill-btn" data-filter="regime" data-val="outros">Residência / Militar / Seletivo</button>
            <button type="button" class="pill-btn ativo" data-filter="horas" data-val="">Qualquer Jornada</button>
            <button type="button" class="pill-btn" data-filter="horas" data-val="20">Até 20h/sem</button>
            <button type="button" class="pill-btn" data-filter="horas" data-val="30">Até 30h/sem</button>
            <button type="button" class="pill-btn" data-filter="horas" data-val="40">Até 40h/sem</button>
          </div>
        </div>

        <div class="f-group">
          <div class="f-label">🏙️ Cidade do Concurso</div>
          <div class="pill-row">{botoes_cidades}</div>
        </div>

        <div class="f-group">
          <div class="f-label">↕️ Ordenar &amp; Novidades</div>
          <div class="pill-row">
            <button type="button" class="pill-btn ativo" data-filter="ordem" data-val="padrao">Ordenação Padrão</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="rp">Mais perto de Rib. Preto</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="jarinu">Mais perto de Jarinu</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="salario">Maior Salário</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="vagas">Mais Vagas Imediatas</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="prova">Prova mais próxima</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="inscricao">Inscrição encerrando</button>
            <button type="button" class="pill-btn" data-filter="novo" data-val="1">✨ Apenas Novos 24h ({novos_count})</button>
          </div>
        </div>
      </div>
    </section>

    <main>
      {render_secao(
          "fisio",
          "🩺",
          "Fisioterapia — Estado de São Paulo",
          "Valores exatos verificados nos anexos dos editais, benefícios (VA/VR/VT), regime estatutário/CLT, carga horária, especificações para posse e conteúdo programático.",
          fisio,
          "fisio",
          ativo=True,
      )}
      {render_secao(
          "medio5k",
          "💰",
          "Nível Médio com Remuneração Acima de R$ 5.000,00 (SP)",
          "Cargos que exigem apenas Ensino Médio completo com ganhos iniciais confirmados acima de R$ 5.000,00 (vencimento base ou base + benefício fixo) e especificações técnicas.",
          medio_ok,
          "medio5k",
      )}
      {render_secao(
          "medio_todos",
          "📊",
          "Nível Médio &amp; Técnico — Escolha a Faixa de Remuneração (SP)",
          "Todos os cargos identificados de Nível Médio e Técnico nos editais de São Paulo, com salários verificados nos anexos e indicação clara se exige apenas Ensino Médio ou Curso Técnico.",
          medio_todos,
          "medio_todos",
          barra_extra=barra_faixas_aba3,
      )}

      <!-- ABA 4: Busca por Cargo Específico (SP / Outros Estados / Brasil Todo) -->
      <section id="busca_cargo" class="tab-panel">
        <div class="sec-head">
          <div class="sec-title-row">
            <h2>🔎 Buscar por Cargo Específico — SP, Estados ou Brasil Todo</h2>
            <div class="count-box-lg">
              <b id="countBuscaCargo">{len(catalogo_brasil)}</b>
              <span>vigentes</span>
            </div>
          </div>
          <p class="desc">
            Digite o nome do cargo que deseja (ex.: Fisioterapeuta, Enfermeiro, Psicólogo, Agente Administrativo, Guarda Municipal) ou escolha um botão abaixo e selecione o Estado (UF) ou Brasil Todo.
          </p>
        </div>

        <div class="busca-cargo-panel">
          <div>
            <div class="f-label" style="margin-bottom:6px;">1️⃣ Digite o Nome do Cargo Desejado (ou clique em um cargo rápido abaixo):</div>
            <div class="cargo-input-row">
              <div class="cargo-input-wrap">
                <input id="inputCargoEspecifico" type="search" placeholder="Digite o cargo... Ex.: Fisioterapeuta, Enfermeiro, Agente Administrativo, Psicólogo">
              </div>
              <button type="button" id="btnLimparCargo" class="btn-limpar">Limpar Busca</button>
            </div>
          </div>

          <div>
            <div class="f-label" style="margin-bottom:6px;">⚡ Cargos Rápidos (1 clique):</div>
            <div class="pill-row" id="rowCargosRapidos">{botoes_cargos_rapidos}</div>
          </div>

          <div>
            <div class="f-label" style="margin-bottom:6px;">2️⃣ Escolha o Estado (UF) ou Brasil Todo:</div>
            <div class="pill-row" id="rowUfsBrasil">{botoes_ufs}</div>
          </div>
        </div>

        <div id="gridBuscaCargo" class="grid"></div>
        <p id="vazioBuscaCargo" class="vazio" style="display:none;">
          Nenhum concurso encontrado para este cargo no Estado selecionado. Experimente selecionar "🇧🇷 Brasil Todo" ou outro cargo.
        </p>
      </section>
    </main>
  </div>

  <!-- Rodapé com botão "☕ Me pague um café" igual ao anexo -->
  <footer class="app-footer">
    <div class="container footer-coffee-wrap">
      <button type="button" id="btnAbrirPix" class="btn-coffee">☕ Me pague um café</button>
      <p class="footer-note">Painel gratuito atualizado diariamente · Feito com carinho em São Paulo 🇧🇷</p>
    </div>
  </footer>

  <!-- Modal "💚 Manda um Pix!" idêntico ao anexo -->
  <div id="modalPix" class="modal-bg" role="dialog" aria-modal="true" aria-labelledby="tituloPix">
    <div class="pix-modal">
      <div class="pix-head">
        <h3 id="tituloPix">💚 Manda um Pix!</h3>
        <button type="button" id="fecharModalPix" class="pix-close" aria-label="Fechar">✕</button>
      </div>
      <p class="pix-desc">
        Este app é gratuito e feito com carinho. Se ele te ajudou, considere apoiar com um Pix de qualquer valor — é opcional e muito bem-vindo! 💚
      </p>
      <div class="pix-qr-box" aria-label="QR Code Pix">
        {qr_svg}
      </div>
      <p class="pix-receiver">Recebedor: Matheus · São Paulo</p>
      <button type="button" id="btnCopiarPix" class="btn-copy-pix">📋 Copiar chave Pix</button>
    </div>
  </div>

  <!-- Modal de Instrução de Instalação PWA -->
  <div id="modalPwa" class="modal-bg" role="dialog" aria-modal="true">
    <div class="pix-modal" style="text-align:left;">
      <div class="pix-head">
        <h3>📲 Instalar Aplicativo</h3>
        <button type="button" id="fecharModalPwa" class="pix-close" aria-label="Fechar">✕</button>
      </div>
      <p class="pix-desc" style="text-align:left;">
        Instale este painel como aplicativo no celular ou computador:
      </p>
      <ol style="padding-left:20px;font-size:.9rem;line-height:1.6;color:#2c3e35;">
        <li><b>No Chrome / Edge (PC ou Android):</b> clique no ícone <b>⊕</b> na barra de endereços ou no menu <b>⋮ → Instalar aplicativo</b>.</li>
        <li><b>No iPhone / iPad (Safari):</b> toque em <b>Compartilhar (⬆️)</b> e escolha <b>"Adicionar à Tela de Início"</b>.</li>
      </ol>
      <button type="button" id="btnEntendiPwa" class="btn-copy-pix" style="margin-top:12px;">Entendi</button>
    </div>
  </div>

<script>
  const CATALOGO_BRASIL = {catalogo_json};
  const PIX_PAYLOAD = {json.dumps(PIX_KEY)};

  function normStr(s) {{
    return (s || '').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
  }}

  function escHtml(s) {{
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }}

  // 1) Atualização dinâmica da plaquinha de "CONCURSO NOVO (24h)"
  (function atualizarNovos24h() {{
    const agora = Date.now();
    document.querySelectorAll('.card').forEach(card => {{
      const isBaseline = card.dataset.isBaseline === '1';
      const ts = Date.parse(card.dataset.firstSeenTs || '');
      const ehNovo = !isBaseline && !isNaN(ts) && (agora - ts) >= 0 && (agora - ts) <= 86400000;
      card.dataset.novo = ehNovo ? '1' : '0';
      const badge = card.querySelector('.badge-novo');
      if (ehNovo && !badge) {{
        const span = document.createElement('span');
        span.className = 'badge-novo';
        span.textContent = '✨ CONCURSO NOVO · 24h';
        card.querySelector('.head-top').appendChild(span);
      }} else if (!ehNovo && badge) {{
        badge.remove();
      }}
    }});
  }})();

  // 2) Navegação entre as 4 Abas
  const tabItems = document.querySelectorAll('.tab-item');
  const painelFiltrosSp = document.getElementById('painelFiltrosSp');

  function abrirTab(tab) {{
    tabItems.forEach(item => item.classList.toggle('ativo', item.dataset.tab === tab));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('ativo', p.id === tab));
    painelFiltrosSp.style.display = (tab === 'busca_cargo') ? 'none' : 'block';
    history.replaceState(null, '', '#' + tab);
    if (tab === 'busca_cargo') renderizarBuscaCargo();
  }}
  tabItems.forEach(item => item.addEventListener('click', () => abrirTab(item.dataset.tab)));
  const hashInicial = location.hash.slice(1);
  if (['fisio', 'medio5k', 'medio_todos', 'busca_cargo'].includes(hashInicial)) {{
    abrirTab(hashInicial);
  }}

  // 3) Estado e Lógica dos Botões de Filtro Pré-definidos (Abas SP)
  const estadoFiltros = {{
    kmRp: '',
    kmJa: '',
    faixa: '',
    escolaridade: '',
    vagas: 'todas',
    regime: '',
    horas: '',
    cidade: '',
    ordem: 'padrao',
    novo: ''
  }};

  function sincronizarBotoesFiltro() {{
    document.querySelectorAll('[data-filter]').forEach(btn => {{
      const chave = btn.dataset.filter;
      const val = btn.dataset.val;
      btn.classList.toggle('ativo', estadoFiltros[chave] === val);
    }});
  }}

  function aplicarFiltrosSp() {{
    const maxRp = estadoFiltros.kmRp ? Number(estadoFiltros.kmRp) : null;
    const maxJa = estadoFiltros.kmJa ? Number(estadoFiltros.kmJa) : null;
    const faixa = estadoFiltros.faixa;
    const esc = estadoFiltros.escolaridade;
    const vagasMode = estadoFiltros.vagas;
    const regime = estadoFiltros.regime;
    const maxHoras = estadoFiltros.horas ? Number(estadoFiltros.horas) : null;
    const cid = estadoFiltros.cidade;
    const soNovos = estadoFiltros.novo === '1';
    const ordem = estadoFiltros.ordem;

    ['fisio', 'medio5k', 'medio_todos'].forEach(panelId => {{
      const panel = document.getElementById(panelId);
      if (!panel) return;
      const grid = panel.querySelector('.grid');
      const cards = Array.from(grid.querySelectorAll('.card'));
      let visiveis = 0;

      cards.forEach(c => {{
        let ok = true;
        if (ok && cid && c.dataset.cidade !== cid) ok = false;
        if (ok && maxRp !== null && Number(c.dataset.kmRp) > maxRp) ok = false;
        if (ok && maxJa !== null && Number(c.dataset.kmJarinu) > maxJa) ok = false;
        if (ok && faixa && c.dataset.faixa !== faixa) ok = false;
        if (ok && esc && c.dataset.escolaridade !== esc) ok = false;
        if (ok && vagasMode !== 'todas') {{
          const v = Number(c.dataset.vagas);
          if (vagasMode === 'cr' && v > 0) ok = false;
          else if (vagasMode !== 'cr' && v < Number(vagasMode)) ok = false;
        }}
        if (ok && regime && c.dataset.regime !== regime) ok = false;
        if (ok && maxHoras !== null && Number(c.dataset.horas) > maxHoras) ok = false;
        if (ok && soNovos && c.dataset.novo !== '1') ok = false;

        c.style.display = ok ? '' : 'none';
        if (ok) visiveis++;
      }});

      if (ordem !== 'padrao') {{
        cards.sort((a, b) => {{
          if (ordem === 'rp') return Number(a.dataset.kmRp) - Number(b.dataset.kmRp);
          if (ordem === 'jarinu') return Number(a.dataset.kmJarinu) - Number(b.dataset.kmJarinu);
          if (ordem === 'salario') return Number(b.dataset.salario) - Number(a.dataset.salario);
          if (ordem === 'vagas') return Number(b.dataset.vagas) - Number(a.dataset.vagas);
          if (ordem === 'prova') return (a.dataset.prova || '').localeCompare(b.dataset.prova || '');
          if (ordem === 'inscricao') return (a.dataset.inscricao || '').localeCompare(b.dataset.inscricao || '');
          return 0;
        }});
        cards.forEach(c => grid.appendChild(c));
      }}

      const secCount = panel.querySelector('.sec-count');
      if (secCount) secCount.textContent = visiveis;
      const tabCnt = document.querySelector(`[data-cnt-for="${{panelId}}"]`);
      if (tabCnt) tabCnt.textContent = visiveis;
      panel.querySelector('.vazio').style.display = visiveis === 0 ? 'block' : 'none';
    }});
  }}

  document.querySelectorAll('[data-filter]').forEach(btn => {{
    btn.addEventListener('click', () => {{
      const chave = btn.dataset.filter;
      const val = btn.dataset.val;
      if (chave === 'novo') {{
        estadoFiltros.novo = estadoFiltros.novo === '1' ? '' : '1';
      }} else {{
        estadoFiltros[chave] = val;
      }}
      sincronizarBotoesFiltro();
      aplicarFiltrosSp();
    }});
  }});

  document.getElementById('btnLimpar').addEventListener('click', () => {{
    estadoFiltros.kmRp = '';
    estadoFiltros.kmJa = '';
    estadoFiltros.faixa = '';
    estadoFiltros.escolaridade = '';
    estadoFiltros.vagas = 'todas';
    estadoFiltros.regime = '';
    estadoFiltros.horas = '';
    estadoFiltros.cidade = '';
    estadoFiltros.ordem = 'padrao';
    estadoFiltros.novo = '';
    sincronizarBotoesFiltro();
    aplicarFiltrosSp();
  }});

  // 4) Aba 4: Busca por Cargo Específico em SP, Outros Estados ou Brasil Todo
  let ufSelecionada = 'TODOS';
  const inputCargo = document.getElementById('inputCargoEspecifico');
  const gridBusca = document.getElementById('gridBuscaCargo');
  const vazioBusca = document.getElementById('vazioBuscaCargo');
  const countBuscaCargo = document.getElementById('countBuscaCargo');
  const tabCntBusca = document.querySelector('[data-cnt-for="busca_cargo"]');

  function renderizarBuscaCargo() {{
    const termoRaw = (inputCargo.value || '').trim();
    const termo = normStr(termoRaw);

    const filtrados = [];
    for (const item of CATALOGO_BRASIL) {{
      if (ufSelecionada !== 'TODOS' && item.uf !== ufSelecionada) continue;

      let cargosCasados = [];
      if (termo) {{
        for (const cg of (item.cargos || [])) {{
          if (normStr(cg).includes(termo)) cargosCasados.push(cg);
        }}
        const cabecalhoMatch = normStr(item.orgao + ' ' + item.titulo + ' ' + item.cargos_resumo).includes(termo);
        if (cargosCasados.length === 0 && !cabecalhoMatch) continue;
      }} else {{
        cargosCasados = (item.cargos || []).slice(0, 4);
      }}
      filtrados.push({{ item, cargosCasados }});
    }}

    countBuscaCargo.textContent = filtrados.length;
    if (tabCntBusca) tabCntBusca.textContent = filtrados.length;
    vazioBusca.style.display = filtrados.length === 0 ? 'block' : 'none';

    const limiteExibicao = 120;
    const fatia = filtrados.slice(0, limiteExibicao);

    gridBusca.innerHTML = fatia.map(({{ item, cargosCasados }}) => {{
      const cargoDestaque = cargosCasados.length > 0
        ? cargosCasados.slice(0, 3).join(' · ') + (cargosCasados.length > 3 ? ` (+${{cargosCasados.length - 3}})` : '')
        : (item.cargos_resumo || 'Conferir cargos no edital');

      let chips = `<span class="chip-loc">📍 ${{escHtml(item.cidade)}} (${{escHtml(item.uf)}})</span>`;
      if (item.km_rp != null) chips += `<span class="chip-dist">🧭 ${{item.km_rp}} km de Rib. Preto</span>`;
      if (item.km_ja != null) chips += `<span class="chip-dist">🧭 ${{item.km_ja}} km de Jarinu</span>`;

      const tagsHtml = (item.cargos || []).slice(0, 6).map(c => `<span class="cargo-tag">${{escHtml(c)}}</span>`).join('');

      return `
        <article class="card">
          <header class="card-head">
            <div class="head-top">
              <h3><a href="${{escHtml(item.url)}}" target="_blank" rel="noopener">${{escHtml(item.orgao)}}</a></h3>
              <span class="esc-badge esc-sup">${{escHtml(item.niveis || 'Vários Níveis')}}</span>
            </div>
            <div class="loc-row">${{chips}}</div>
            <p class="titulo">${{escHtml(item.titulo)}}</p>
          </header>

          <div class="cargo-banner">
            <div class="cargo-nome">🎯 <strong>${{escHtml(cargoDestaque)}}</strong></div>
            <span class="badge-vagas">${{escHtml(item.vagas_salario || 'Ver edital')}}</span>
          </div>

          <div class="info-grid">
            <div class="info-box destaque-sal">
              <span class="lbl">💰 Vagas &amp; Salário</span>
              <strong class="val-sm" style="color:var(--br-green-dark);">${{escHtml(item.vagas_salario || 'Consultar edital')}}</strong>
            </div>
            <div class="info-box">
              <span class="lbl">🏛️ Regime &amp; Jornada</span>
              <strong class="val-sm">${{escHtml(item.regime)}} · ${{escHtml(item.jornada)}}</strong>
            </div>
            <div class="info-box destaque-prova">
              <span class="lbl">📅 Data da Prova</span>
              <strong class="val-sm">${{escHtml(item.data_prova)}}</strong>
              <small class="sub">Banca: ${{escHtml(item.banca)}}</small>
            </div>
            <div class="info-box destaque-prazo">
              <span class="lbl">⏰ Inscrições até</span>
              <strong class="val-sm">${{escHtml(item.inscricao_ate)}}</strong>
              <small class="sub">Região: ${{escHtml(item.regiao)}}</small>
            </div>
          </div>

          ${{tagsHtml ? `<div><div class="f-label" style="font-size:.7rem;margin-bottom:4px;">📋 Principais Cargos no Edital:</div><div class="cargos-match-list">${{tagsHtml}}</div></div>` : ''}}

          <div class="links-row" style="margin-top:auto;">
            <a class="btn-link primario" href="${{escHtml(item.url)}}#links" target="_blank" rel="noopener">📄 Abrir Edital &amp; Anexos</a>
            <a class="btn-link" href="${{escHtml(item.url)}}" target="_blank" rel="noopener">🔗 Ver Notícia Completa</a>
          </div>
        </article>`;
    }}).join('');
  }}

  inputCargo.addEventListener('input', () => {{
    document.querySelectorAll('.cargo-quick').forEach(b => {{
      b.classList.toggle('ativo', normStr(b.dataset.cargo) === normStr(inputCargo.value.trim()));
    }});
    renderizarBuscaCargo();
  }});

  document.getElementById('btnLimparCargo').addEventListener('click', () => {{
    inputCargo.value = '';
    document.querySelectorAll('.cargo-quick').forEach(b => b.classList.toggle('ativo', b.dataset.cargo === ''));
    renderizarBuscaCargo();
  }});

  document.querySelectorAll('.cargo-quick').forEach(btn => {{
    btn.addEventListener('click', () => {{
      inputCargo.value = btn.dataset.cargo;
      document.querySelectorAll('.cargo-quick').forEach(b => b.classList.toggle('ativo', b === btn));
      renderizarBuscaCargo();
    }});
  }});

  document.querySelectorAll('.uf-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      ufSelecionada = btn.dataset.uf;
      document.querySelectorAll('.uf-btn').forEach(b => b.classList.toggle('ativo', b === btn));
      renderizarBuscaCargo();
    }});
  }});

  renderizarBuscaCargo();

  // 5) Modal Pix ("☕ Me pague um café" / "💚 Manda um Pix!")
  const modalPix = document.getElementById('modalPix');
  const btnAbrirPix = document.getElementById('btnAbrirPix');
  const fecharModalPix = document.getElementById('fecharModalPix');
  const btnCopiarPix = document.getElementById('btnCopiarPix');

  btnAbrirPix.addEventListener('click', () => modalPix.classList.add('aberto'));
  fecharModalPix.addEventListener('click', () => modalPix.classList.remove('aberto'));
  modalPix.addEventListener('click', (e) => {{
    if (e.target === modalPix) modalPix.classList.remove('aberto');
  }});

  btnCopiarPix.addEventListener('click', async () => {{
    try {{
      await navigator.clipboard.writeText(PIX_PAYLOAD);
    }} catch (_) {{
      const ta = document.createElement('textarea');
      ta.value = PIX_PAYLOAD;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
    }}
    const original = btnCopiarPix.innerHTML;
    btnCopiarPix.innerHTML = '✅ Chave Pix copiada!';
    setTimeout(() => {{ btnCopiarPix.innerHTML = original; }}, 2600);
  }});

  // 6) PWA — Service Worker e Instalação
  let deferredPrompt = null;
  const btnInstall = document.getElementById('btnInstall');
  const modalPwa = document.getElementById('modalPwa');

  if ('serviceWorker' in navigator) {{
    window.addEventListener('load', () => {{
      navigator.serviceWorker.register('./sw.js').catch(() => {{}});
    }});
  }}

  window.addEventListener('beforeinstallprompt', (e) => {{
    e.preventDefault();
    deferredPrompt = e;
  }});

  btnInstall.addEventListener('click', async () => {{
    if (deferredPrompt) {{
      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
    }} else {{
      modalPwa.classList.add('aberto');
    }}
  }});

  document.getElementById('fecharModalPwa').addEventListener('click', () => modalPwa.classList.remove('aberto'));
  document.getElementById('btnEntendiPwa').addEventListener('click', () => modalPwa.classList.remove('aberto'));
  modalPwa.addEventListener('click', (e) => {{
    if (e.target === modalPwa) modalPwa.classList.remove('aberto');
  }});
</script>
</body>
</html>"""


if __name__ == "__main__":
    sys.exit(main())
