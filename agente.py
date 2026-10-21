"""
Agente de Busca de Concursos — PCI Concursos (Sudeste -> exclusivamente SP)

Funcionalidades:
  1. Filtra exclusivamente concursos do Estado de São Paulo (UF = SP).
  2. Busca vagas de Fisioterapeuta / Fisioterapia com salário exato, benefícios
     (VA, VR, VT), regime (Estatutário / CLT / Residência / Militar / Seletivo),
     carga horária semanal, data da prova, banca, links para edital/conteúdo
     programático e resumo do conteúdo programático voltado para Fisioterapeuta.
  3. Busca cargos que exigem APENAS Nível Médio com remuneração acima de R$ 5.000,00,
     apresentando os mesmos detalhes completos na tela inicial.
  4. Calcula a distância em km de cada concurso até Ribeirão Preto/SP e até Jarinu/SP
     usando as coordenadas oficiais dos 645 municípios de SP.
  5. Identifica concursos que apareceram nas últimas 24 horas (e que não estavam
     no período anterior) com a plaquinha "CONCURSO NOVO".
  6. Gera um Progressive Web App (PWA) completo e instalável em `docs/`.
"""
from __future__ import annotations

import hashlib
import html
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
UF_ALVO = "SP"
SALARIO_MINIMO_MEDIO = 5000.00
FISIO_REGEX = re.compile(r"\bfisioterap(?:euta|ia|êutico|eutas)\b", re.I)
SCHEMA_VERSION = 3

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
CACHE_FILE = DATA_DIR / "cache.json"
RESULTS_FILE = DATA_DIR / "resultados.json"
MUNICIPIOS_FILE = DATA_DIR / "municipios_sp.json"
ENRIQUECIDOS_FILE = DATA_DIR / "concursos_enriquecidos.json"
HTML_FILE = DOCS_DIR / "index.html"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_SEARCH_MODEL = os.getenv("GEMINI_SEARCH_MODEL", "gemini-3.8-flash")
MAX_AI_CALLS = int(os.getenv("MAX_AI_CALLS", "120"))
AI_DELAY_S = float(os.getenv("AI_DELAY_S", "4"))
HTTP_DELAY_S = float(os.getenv("HTTP_DELAY_S", "0.5"))

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

    # 1) Padrão explícito "<Cidade> - SP" no título
    m = re.search(r"(?:de|em|da|do)\s+([a-z\s]+?)\s*-\s*sp\b", norm(titulo))
    if m:
        cand = m.group(1).strip()
        for k, pat in MUN_PATTERNS:
            if pat.search(cand):
                return MUNICIPIOS_SP[k]["nome"]

    # 2) Busca no título + órgão + slug da URL (evitando casar "São Paulo" antes de outra cidade do interior)
    cabecalho = norm(f"{titulo} {orgao} {url.replace('-', ' ')}")
    for k, pat in MUN_PATTERNS:
        if k == "sao paulo":
            continue
        if pat.search(cabecalho):
            return MUNICIPIOS_SP[k]["nome"]

    # 3) Dicas de órgãos conhecidos
    for hint, city_k in ORG_CITY_HINTS.items():
        if hint in cabecalho and city_k in MUNICIPIOS_SP:
            return MUNICIPIOS_SP[city_k]["nome"]

    # 4) Busca no primeiro parágrafo do texto da notícia
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
    """Retorna (vagas_imediatas, tem_cr, texto_formatado)."""
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
# 1) Listagem do PCI Concursos
# --------------------------------------------------------------------------- #
def parse_listing(page_html: str) -> List[dict]:
    """Cada concurso é um bloco <div class="na|da|ea" ... data-url="...">.
    Fatiamos por bloco para evitar problemas com tags mal fechadas no site."""
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
                "url": url,
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
# 2) Extração de texto e metadados da página da notícia
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
        return "Estatutário / CLT (conforme edital)"
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
    return " · ".join(achados) if achados else "Consultar edital (não detalhado no resumo)"


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

    # Links de editais e provas na barra lateral <#links>
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
    if art:
        for a in art.select("a[href]"):
            href = (a.get("href") or "").strip()
            if href.startswith("http") and "pciconcursos.com.br" not in href.lower():
                link_banca = href
                txt_a = a.get_text(" ", strip=True)
                if txt_a and not txt_a.startswith("www.") and len(txt_a) < 80:
                    nome_banca = txt_a
                break

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
                continue  # ignora parágrafos longos introdutórios quando há linha de cargo
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
# 3) IA (Gemini) — Extração Estruturada Completa
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
            description=(
                "Se houver cargo de Fisioterapeuta/Fisioterapia, lista de 4 a 6 tópicos resumindo o "
                "conteúdo programático cobrado para Fisioterapeuta neste certame/banca."
            ),
        )
        cargos: List[CargoExtraido] = Field(description="Cargos citados na notícia.")

    PYDANTIC_OK = True
except ImportError:  # pragma: no cover
    PYDANTIC_OK = False

SYSTEM_INSTRUCTION = (
    "Você é um especialista em editais de concursos públicos brasileiros em São Paulo. "
    "Extraia cidade, banca, data da prova objetiva (DD/MM/AAAA), regime jurídico (Estatutário, CLT, "
    "Residência, Militar Temporário ou Processo Seletivo), benefícios (VA, VR, VT com valores quando houver), "
    "jornada semanal e a lista de cargos com escolaridade e salário específico do cargo. "
    "Classifique cargos como 'Escriturário', 'Agente Administrativo', 'Assistente Administrativo', "
    "'Oficial Legislativo', 'Inspetor de Alunos', 'Monitor' e 'Agente Comunitário de Saúde' como 'medio' "
    "quando o edital contemplar nível médio e não exigir curso técnico. "
    "Se houver cargo de Fisioterapeuta/Fisioterapia, preencha resumo_conteudo_fisio com os tópicos do "
    "conteúdo programático voltados para Fisioterapeuta neste concurso."
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

    # Se usar_busca=True (ex.: novos concursos de Fisioterapia), tenta primeiro com Google Search Grounding
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
                    break  # cai imediatamente para o modelo rápido sem tools
                time.sleep(10 * tentativa)
    return None


# --------------------------------------------------------------------------- #
# 4) Conteúdo Programático Padrão (Fallback Inteligente)
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
        f"Conhecimentos Específicos ({cargo_nome}): Rotinas administrativas, atendimento ao público, noções de Administração Pública, Direito Constitucional/Administrativo e legislação municipal/estadual do órgão",
    ]


# --------------------------------------------------------------------------- #
# 5) Classificação e Montagem dos Cards Enriquecidos
# --------------------------------------------------------------------------- #
CARGOS_MEDIO_CONHECIDOS = re.compile(
    r"\b(agente\s+administrativo|assistente\s+administrativo|auxiliar\s+administrativo|"
    r"escritur[áa]rio|oficial\s+legislativo|oficial\s+de\s+finan[çc]as|inspetor\s+de\s+alunos|"
    r"agente\s+comunit[áa]rio\s+de\s+sa[úu]de|agente\s+de\s+combate\s+[àa]s\s+endemias|"
    r"agente\s+de\s+controle\s+de\s+endemias|agente\s+de\s+fiscaliza[çc][ãa]o|"
    r"monitor\s+de\s+transporte|monitor\s+de\s+creche|recepcionista|almoxarife|"
    r"assistente\s+de\s+suporte\s+acad[êe]mico)\b",
    re.I,
)


def eh_novo_24h(info: dict, agora: datetime) -> bool:
    """Retorna True somente se o concurso NÃO fazia parte da base anterior (baseline)
    e apareceu pela primeira vez nas últimas 24 horas."""
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


def montar_concurso(c: dict, info: dict, enriquecidos: Dict[str, dict], agora: datetime) -> None:
    url = c["url"]
    enriq = enriquecidos.get(url, {})
    ia = info.get("ia") or {}
    det = info.get("detalhes") or {}

    # Localização e distâncias para Ribeirão Preto e Jarinu
    cidade_ia = enriq.get("cidade") or ia.get("cidade")
    cidade = detectar_cidade(c["orgao"], c["titulo"], url, det.get("texto", ""), cidade_ia)
    dist = info_distancia(cidade)
    c["cidade"] = dist["cidade"]
    c["km_ribeirao_preto"] = dist["km_ribeirao_preto"]
    c["km_jarinu"] = dist["km_jarinu"]

    # Metadados gerais do certame
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

    # Plaquinha de concurso novo (últimas 24h vs período anterior)
    c["first_seen_ts"] = info.get("first_seen_ts", "2026-10-20T07:00:00-03:00")
    c["is_baseline"] = bool(info.get("is_baseline", False))
    c["novo"] = eh_novo_24h(info, agora)

    # ---------------- 1) FISIOTERAPIA ---------------- #
    fisio_linhas = info.get("fisio_linhas", [])
    c["fisio_linhas"] = fisio_linhas
    c["fisio"] = bool(enriq.get("fisio")) or bool(fisio_linhas) or bool(FISIO_REGEX.search(c.get("cargos_resumo", "")))

    if c["fisio"]:
        f_enriq = enriq.get("fisio") or {}
        # Procura cargo de fisioterapia na saída da IA caso não esteja em enriquecidos
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
            "beneficios": f_enriq.get("beneficios") or c["beneficios_gerais"],
            "resumo_conteudo": (
                f_enriq.get("resumo_conteudo")
                or ia.get("resumo_conteudo_fisio")
                or conteudo_padrao_fisio(c["banca"], c["regime_geral"])
            ),
        }

    # ---------------- 2) NÍVEL MÉDIO > R$ 5.000 ---------------- #
    c["medio_confirmado"] = []
    c["medio_sem_salario"] = []
    c["medio_possivel"] = False

    if enriq.get("medio_excluido"):
        return

    if enriq.get("medio"):
        for item in enriq["medio"]:
            c["medio_confirmado"].append(item)
        return

    sal_max = max(
        [v for v in (c.get("salario_max_listagem"), info.get("salario_max_texto")) if v] or [0]
    ) or None
    c["salario_max"] = sal_max
    if sal_max is not None and sal_max <= SALARIO_MINIMO_MEDIO:
        return

    if ia.get("cargos"):
        for cargo in ia["cargos"]:
            esc = cargo.get("escolaridade")
            nome_c = cargo.get("nome", "")
            # Corrige bug onde IA marcava cargos administrativos clássicos como 'desconhecida'
            if esc == "desconhecida" and CARGOS_MEDIO_CONHECIDOS.search(nome_c):
                esc = "medio"
            if esc != "medio":
                continue
            s = cargo.get("salario")
            v_im, t_cr, v_txt = extrair_vagas_info(cargo.get("vagas"))
            item_fmt = {
                "nome": nome_c,
                "vagas": v_txt,
                "vagas_imediatas": v_im,
                "tem_cr": t_cr,
                "salario": s,
                "salario_detalhe": f"{brl(s)} (base)" if s else f"Faixa do edital: {c['faixa_salarial']}",
                "carga_horaria": cargo.get("carga_horaria") or c["jornada_geral"],
                "regime": cargo.get("regime") or c["regime_geral"],
                "beneficios": c["beneficios_gerais"],
                "resumo_conteudo": conteudo_padrao_medio(nome_c, c["banca"]),
            }
            if s and s > SALARIO_MINIMO_MEDIO:
                c["medio_confirmado"].append(item_fmt)
            elif s is None:
                c["medio_sem_salario"].append(item_fmt)
        c["medio_possivel"] = not c["medio_confirmado"] and bool(c["medio_sem_salario"])
    elif info.get("tem_medio"):
        c["medio_possivel"] = True


# --------------------------------------------------------------------------- #
# 6) Pipeline Principal
# --------------------------------------------------------------------------- #
def tem_nivel_medio(c: dict, texto: str) -> bool:
    if re.search(r"m[ée]dio", c.get("niveis", ""), re.I):
        return True
    return bool(re.search(r"n[íi]vel m[ée]dio|ensino m[ée]dio", texto, re.I))


def candidato_relevante(c: dict, info: Optional[dict]) -> bool:
    """Indica se vale a pena buscar detalhes completos / IA para este concurso."""
    if info and info.get("fisio_linhas"):
        return True
    if FISIO_REGEX.search(c.get("cargos_resumo", "")) or FISIO_REGEX.search(c.get("titulo", "")):
        return True
    sal = max([v for v in (c.get("salario_max_listagem"), (info or {}).get("salario_max_texto")) if v] or [0])
    tem_med = bool(re.search(r"m[ée]dio", c.get("niveis", ""), re.I)) or bool((info or {}).get("tem_medio"))
    return tem_med and (sal == 0 or sal > SALARIO_MINIMO_MEDIO)


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)
    cache: Dict[str, dict] = load_json(CACHE_FILE, {})
    enriquecidos: Dict[str, dict] = load_json(ENRIQUECIDOS_FILE, {})
    agora = datetime.now(BRT)
    hoje = agora.strftime("%Y-%m-%d")

    # Se o cache já existia mas ainda não tinha controle de baseline/timestamp,
    # marca os registros existentes como baseline (período anterior) para não
    # rotular falsamente todos os 160 concursos antigos como "NOVO (últimas 24h)".
    for u, item in cache.items():
        if "first_seen_ts" not in item:
            item["first_seen_ts"] = "2026-10-20T07:00:00-03:00"
            item["is_baseline"] = True

    log(f"Baixando listagem: {LISTING_URL}")
    todos = parse_listing(fetch(LISTING_URL))
    concursos = [c for c in todos if c["uf"] == UF_ALVO]
    log(f"{len(todos)} concursos no Sudeste, {len(concursos)} em {UF_ALVO}.")
    log("IA: " + (f"ativada ({GEMINI_MODEL})" if GEMINI_API_KEY else "desativada (sem GEMINI_API_KEY)"))

    for i, c in enumerate(concursos, 1):
        url = c["url"]
        info = cache.get(url)
        eh_url_nova = info is None
        precisa_detalhes = eh_url_nova or (
            candidato_relevante(c, info) and not (info or {}).get("detalhes")
        )
        quer_ia = (
            bool(GEMINI_API_KEY)
            and url not in enriquecidos
            and candidato_relevante(c, info)
            and not (info or {}).get("ia")
        )

        if precisa_detalhes or quer_ia:
            log(f"[{i}/{len(concursos)}] Analisando detalhes: {c['orgao']}")
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

        if info is None:
            continue
        montar_concurso(c, info, enriquecidos, agora)

    ativos = {c["url"] for c in concursos}
    cache = {u: v for u, v in cache.items() if u in ativos}
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    fisio = [c for c in concursos if c.get("fisio")]
    medio_ok = [c for c in concursos if c.get("medio_confirmado")]
    medio_pos = [c for c in concursos if c.get("medio_possivel")]
    novos_24h = sum(1 for c in (fisio + medio_ok + medio_pos) if c.get("novo"))
    gerado_em = agora.strftime("%d/%m/%Y %H:%M")

    RESULTS_FILE.write_text(
        json.dumps(
            {
                "gerado_em": gerado_em,
                "gerado_em_iso": agora.isoformat(),
                "fonte": LISTING_URL,
                "total_sp": len(concursos),
                "ia_ativa": bool(GEMINI_API_KEY) or bool(enriquecidos),
                "novos_ultimas_24h": novos_24h,
                "fisioterapia": fisio,
                "nivel_medio_acima_5000": medio_ok,
                "nivel_medio_possiveis": medio_pos,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    HTML_FILE.write_text(
        render_html(fisio, medio_ok, medio_pos, len(concursos), gerado_em, agora.isoformat()),
        encoding="utf-8",
    )
    log(
        f"Concluído! Fisioterapia: {len(fisio)} | Nível Médio > R$5k: {len(medio_ok)} | "
        f"Possíveis: {len(medio_pos)} | Novos (24h): {novos_24h}"
    )
    log(f"Página PWA gerada: {HTML_FILE}")
    return 0


# --------------------------------------------------------------------------- #
# 7) Renderização HTML + PWA + Filtros Avançados
# --------------------------------------------------------------------------- #
def e(s: Any) -> str:
    return html.escape(str(s if s is not None else ""))


def data_iso_sort(data_br: str) -> str:
    """Converte 'DD/MM/AAAA' em 'AAAA-MM-DD' para ordenação cronológica."""
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
        topicos = fd.get("resumo_conteudo") or []
        icone_cargo = "🩺"
    elif modo == "medio":
        itens = c.get("medio_confirmado") or [{}]
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
        topicos = prim.get("resumo_conteudo") or []
        icone_cargo = "💼"
    else:
        itens = c.get("medio_sem_salario") or []
        nomes = [x.get("nome", "") for x in itens if x.get("nome")]
        cargo_titulo = ", ".join(nomes[:4]) + (f" (+{len(nomes)-4})" if len(nomes) > 4 else "") if nomes else "Cargos de Nível Médio"
        vagas_im = sum(x.get("vagas_imediatas", 0) for x in itens)
        tem_cr = True
        vagas_txt = f"{vagas_im} vaga(s) + CR" if vagas_im > 0 else "Cadastro de Reserva (CR)"
        sal_val = c.get("salario_max")
        sal_exib = c.get("faixa_salarial") or (f"Até {brl(sal_val)}" if sal_val else "Consultar edital")
        sal_det = "Salário individual por cargo na tabela do edital completo"
        carga = c.get("jornada_geral") or "Consultar edital"
        regime = c.get("regime_geral") or "Consultar edital"
        beneficios = c.get("beneficios_gerais") or "Consultar edital"
        topicos = conteudo_padrao_medio(nomes[0] if nomes else "Nível Médio", c.get("banca", ""))
        icone_cargo = "🔍"

    cidade = c.get("cidade") or "São Paulo"
    km_rp = c.get("km_ribeirao_preto")
    km_ja = c.get("km_jarinu")
    km_rp_attr = km_rp if km_rp is not None else 9999
    km_ja_attr = km_ja if km_ja is not None else 9999
    sal_attr = sal_val if sal_val is not None else 0
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
        chips_dist += f'<span class="chip-dist" title="Distância aproximada até Ribeirão Preto/SP">🧭 {km_rp} km de Rib. Preto</span>'
    if km_ja is not None:
        chips_dist += f'<span class="chip-dist" title="Distância aproximada até Jarinu/SP">🧭 {km_ja} km de Jarinu</span>'

    arqs_str = " • ".join(c.get("arquivos_edital") or ["Edital Completo"])
    botoes = (
        f'<a class="btn-link primario" href="{e(c.get("link_edital"))}" target="_blank" rel="noopener" '
        f'title="{e(arqs_str)}">📄 Edital &amp; Conteúdo Programático</a>'
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
        else "📚 Ver Resumo do Conteúdo Programático"
    )

    busca_str = norm(
        f"{c.get('orgao')} {c.get('titulo')} {cidade} {cargo_titulo} {c.get('banca')} {regime} {beneficios}"
    )

    return f"""
    <article class="card"
      data-busca="{e(busca_str)}"
      data-cidade="{e(cidade)}"
      data-km-rp="{km_rp_attr}"
      data-km-jarinu="{km_ja_attr}"
      data-salario="{sal_attr}"
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
        <div class="loc-row">{chips_dist}</div>
        <p class="titulo">{e(c['titulo'])}</p>
      </header>

      <div class="cargo-banner">
        <div class="cargo-nome">{icone_cargo} <strong>{e(cargo_titulo)}</strong></div>
        <span class="badge-vagas">{e(vagas_txt)}</span>
      </div>

      <div class="info-grid">
        <div class="info-box destaque-sal">
          <span class="lbl">💰 Salário Bruto do Cargo</span>
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
          <span class="lbl">⏱️ Horas por Semana</span>
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
          <p class="prog-arq">📑 <b>Documentos do Edital:</b> {e(arqs_str)}</p>
          <ul>{lista_topicos}</ul>
          <a class="prog-cta" href="{e(c.get('link_edital'))}" target="_blank" rel="noopener">
            👉 Abrir Anexo de Conteúdo Programático no Edital Oficial
          </a>
        </div>
      </details>
    </article>"""


def render_secao(id_: str, titulo: str, desc: str, itens: List[dict], modo: str, ativo: bool = False) -> str:
    corpo = "".join(render_card(c, modo) for c in itens)
    cls = "tab-panel ativo" if ativo else "tab-panel"
    return f"""
  <section id="{id_}" class="{cls}" data-total="{len(itens)}">
    <div class="sec-head">
      <h2>{titulo} <small class="sec-count">({len(itens)})</small></h2>
      <p class="desc">{desc}</p>
    </div>
    <div class="grid">{corpo}</div>
    <p class="vazio" style="display:{'none' if itens else 'block'};">
      Nenhum concurso encontrado com os filtros selecionados.
    </p>
  </section>"""


def render_html(fisio: List[dict], medio_ok: List[dict], medio_pos: List[dict], total_sp: int, gerado_em: str, gerado_iso: str) -> str:
    # Lista única de cidades presentes nos cards para popular o filtro de Cidade
    cidades_map: Dict[str, tuple[Optional[int], Optional[int]]] = {}
    for c in fisio + medio_ok + medio_pos:
        cid = c.get("cidade")
        if cid and cid not in cidades_map:
            cidades_map[cid] = (c.get("km_ribeirao_preto"), c.get("km_jarinu"))
    opcoes_cidades = '<option value="">Todas as cidades de SP</option>' + "".join(
        f'<option value="{e(cid)}">{e(cid)} '
        f'({f"{rp} km Rib. Preto" if rp is not None else ""}'
        f'{" · " if rp is not None and ja is not None else ""}'
        f'{f"{ja} km Jarinu" if ja is not None else ""})</option>'
        for cid, (rp, ja) in sorted(cidades_map.items())
    )

    novos_count = sum(1 for c in (fisio + medio_ok + medio_pos) if c.get("novo"))

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0f172a">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Concursos SP">
<meta name="description" content="Concursos abertos em São Paulo para Fisioterapeuta/Fisioterapia e Nível Médio acima de R$ 5.000,00 com salário exato, VA/VR/VT, carga horária, regime e data da prova.">
<link rel="manifest" href="./manifest.webmanifest">
<link rel="icon" type="image/png" sizes="192x192" href="./icon-192.png">
<link rel="apple-touch-icon" href="./icon-192.png">
<title>Concursos SP — Fisioterapia &amp; Nível Médio</title>
<style>
  :root {{
    --bg:#0b1120; --surface:#111827; --card:#1e293b; --card2:#0f172a;
    --border:#334155; --muted:#94a3b8; --txt:#f1f5f9;
    --acc:#22d3ee; --ok:#4ade80; --warn:#fbbf24; --new:#f43f5e;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif; background:var(--bg); color:var(--txt); line-height:1.45; }}
  .container {{ max-width:1280px; margin:auto; padding:0 18px; }}

  /* Cabeçalho e Botão PWA */
  header.app-bar {{ padding:22px 0 14px; border-bottom:1px solid #1e293b; background:linear-gradient(180deg,#0f172a 0%,#0b1120 100%); }}
  .bar-row {{ display:flex; justify-content:space-between; align-items:flex-start; gap:14px; flex-wrap:wrap; }}
  h1 {{ margin:0 0 4px; font-size:1.55rem; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
  .meta {{ color:var(--muted); font-size:.88rem; }}
  .meta a {{ color:var(--acc); text-decoration:none; }}
  .btn-pwa {{
    background:linear-gradient(135deg,#22d3ee,#38bdf8); color:#082f49; border:none;
    padding:10px 18px; border-radius:999px; font-weight:700; font-size:.92rem;
    cursor:pointer; display:inline-flex; align-items:center; gap:8px;
    box-shadow:0 4px 14px rgba(34,211,238,.25); transition:transform .15s;
  }}
  .btn-pwa:hover {{ transform:translateY(-1px); }}

  /* Estatísticas */
  .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; margin:16px 0 6px; }}
  .stat {{ background:var(--card); padding:12px 15px; border-radius:12px; border:1px solid var(--border); }}
  .stat b {{ font-size:1.45rem; display:block; color:var(--acc); }}
  .stat span {{ font-size:.83rem; color:var(--muted); }}

  /* Navegação por Abas */
  nav.tabs {{ display:flex; gap:8px; flex-wrap:wrap; margin:16px 0 12px; }}
  nav.tabs button {{
    background:var(--card); color:var(--txt); border:1px solid var(--border);
    padding:11px 18px; border-radius:999px; cursor:pointer; font-size:.94rem;
    transition:all .15s;
  }}
  nav.tabs button.ativo {{ background:var(--acc); color:#082f49; border-color:var(--acc); font-weight:700; }}

  /* Painel de Filtros */
  .filtros-panel {{
    background:var(--surface); border:1px solid var(--border); border-radius:14px;
    padding:14px 16px; margin-bottom:18px;
  }}
  .filtros-head {{ display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:10px; }}
  .filtros-head strong {{ font-size:.95rem; color:var(--acc); }}
  .filtros-actions {{ display:flex; align-items:center; gap:12px; flex-wrap:wrap; }}
  .chk-novo {{ display:inline-flex; align-items:center; gap:6px; font-size:.86rem; cursor:pointer; background:#1e293b; padding:6px 12px; border-radius:999px; border:1px solid var(--border); }}
  .btn-limpar {{ background:transparent; color:var(--muted); border:1px solid var(--border); padding:6px 12px; border-radius:8px; cursor:pointer; font-size:.83rem; }}
  .btn-limpar:hover {{ color:var(--txt); border-color:var(--acc); }}
  .filtros-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr)); gap:10px; }}
  .f-item {{ display:flex; flex-direction:column; gap:4px; }}
  .f-item label {{ font-size:.76rem; color:var(--muted); font-weight:600; text-transform:uppercase; letter-spacing:.03em; }}
  .f-item input, .f-item select {{
    width:100%; padding:9px 11px; border-radius:9px; border:1px solid var(--border);
    background:var(--card2); color:var(--txt); font-size:.9rem;
  }}
  .f-item input:focus, .f-item select:focus {{ outline:none; border-color:var(--acc); }}

  /* Seções e Grid de Cards */
  main {{ padding-bottom:50px; }}
  .tab-panel {{ display:none; }}
  .tab-panel.ativo {{ display:block; }}
  .sec-head h2 {{ margin:8px 0 4px; font-size:1.25rem; }}
  .sec-head h2 small {{ color:var(--muted); font-weight:400; }}
  .desc {{ color:var(--muted); margin:0 0 14px; font-size:.9rem; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(380px,1fr)); gap:16px; }}
  @media (max-width:480px) {{ .grid {{ grid-template-columns:1fr; }} }}

  /* Card Rico */
  .card {{
    background:var(--card); border-radius:16px; padding:16px;
    display:flex; flex-direction:column; gap:12px;
    border:1px solid var(--border); box-shadow:0 4px 16px rgba(0,0,0,.22);
  }}
  .head-top {{ display:flex; justify-content:space-between; align-items:flex-start; gap:8px; }}
  .card h3 {{ margin:0; font-size:1.1rem; line-height:1.3; }}
  .card h3 a {{ color:var(--acc); text-decoration:none; }}
  .card h3 a:hover {{ text-decoration:underline; }}
  .badge-novo {{
    background:linear-gradient(135deg,#f43f5e,#fb7185); color:#fff;
    font-size:.72rem; padding:4px 9px; border-radius:999px; font-weight:800;
    white-space:nowrap; letter-spacing:.02em; box-shadow:0 2px 10px rgba(244,63,94,.4);
    animation:pulso 2s infinite;
  }}
  @keyframes pulso {{ 0%,100% {{ transform:scale(1); }} 50% {{ transform:scale(1.04); }} }}

  .loc-row {{ display:flex; gap:6px; flex-wrap:wrap; margin-top:6px; }}
  .chip-loc {{ background:#082f49; color:#7dd3fc; border:1px solid #0369a1; font-size:.76rem; padding:2px 9px; border-radius:999px; font-weight:600; }}
  .chip-dist {{ background:var(--card2); color:var(--muted); border:1px solid var(--border); font-size:.75rem; padding:2px 8px; border-radius:999px; }}
  .titulo {{ margin:6px 0 0; color:var(--muted); font-size:.84rem; }}

  .cargo-banner {{
    background:var(--card2); border:1px solid #1e3a5f; border-radius:10px;
    padding:9px 12px; display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap;
  }}
  .cargo-nome {{ font-size:.94rem; color:#e0f2fe; }}
  .badge-vagas {{ background:#064e3b; color:#6ee7b7; font-size:.76rem; padding:3px 9px; border-radius:999px; font-weight:700; }}

  .info-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:8px; }}
  @media (max-width:440px) {{ .info-grid {{ grid-template-columns:1fr; }} }}
  .info-box {{
    background:var(--card2); border:1px solid #263349; border-radius:10px;
    padding:9px 11px; display:flex; flex-direction:column; gap:2px;
  }}
  .info-box .lbl {{ font-size:.72rem; color:var(--muted); text-transform:uppercase; letter-spacing:.02em; }}
  .info-box .val {{ font-size:1.1rem; color:var(--ok); }}
  .info-box .val-sm {{ font-size:.88rem; color:var(--txt); }}
  .info-box .sub {{ font-size:.75rem; color:var(--muted); }}
  .destaque-sal {{ border-color:#14532d; background:rgba(20,83,45,.18); }}
  .destaque-prova .val-sm {{ color:#38bdf8; }}
  .destaque-prazo .val-sm {{ color:var(--warn); }}

  /* Botões de Link e Conteúdo Programático */
  .links-row {{ display:flex; gap:7px; flex-wrap:wrap; }}
  .btn-link {{
    background:var(--card2); color:var(--txt); border:1px solid var(--border);
    padding:6px 11px; border-radius:8px; font-size:.8rem; text-decoration:none;
    font-weight:600; transition:border-color .15s;
  }}
  .btn-link:hover {{ border-color:var(--acc); color:var(--acc); }}
  .btn-link.primario {{ background:#083344; color:#67e8f9; border-color:#0e7490; }}

  details.prog-box {{
    background:var(--card2); border:1px solid var(--border); border-radius:10px;
    padding:8px 12px; margin-top:auto;
  }}
  details.prog-box summary {{ cursor:pointer; font-size:.85rem; font-weight:600; color:var(--acc); }}
  .prog-body {{ margin-top:8px; font-size:.83rem; color:#cbd5e1; }}
  .prog-arq {{ margin:0 0 6px; font-size:.79rem; color:var(--muted); }}
  .prog-body ul {{ margin:0 0 8px; padding-left:18px; display:flex; flex-direction:column; gap:4px; }}
  .prog-cta {{ display:inline-block; color:var(--ok); font-weight:600; text-decoration:none; font-size:.82rem; }}
  .prog-cta:hover {{ text-decoration:underline; }}

  .vazio {{ color:var(--muted); text-align:center; padding:30px 10px; font-size:.98rem; }}

  /* Modal de instalação PWA */
  .modal-bg {{
    position:fixed; inset:0; background:rgba(0,0,0,.7); display:none;
    align-items:center; justify-content:center; padding:18px; z-index:999;
  }}
  .modal-bg.aberto {{ display:flex; }}
  .modal {{
    background:var(--card); border:1px solid var(--border); border-radius:16px;
    max-width:460px; width:100%; padding:20px;
  }}
  .modal h3 {{ margin:0 0 10px; color:var(--acc); }}
  .modal ol {{ padding-left:20px; font-size:.92rem; line-height:1.55; }}
  .modal button {{
    margin-top:12px; width:100%; padding:10px; border-radius:10px;
    border:none; background:var(--acc); color:#082f49; font-weight:700; cursor:pointer;
  }}
</style>
</head>
<body>
  <header class="app-bar">
    <div class="container">
      <div class="bar-row">
        <div>
          <h1>🔎 Concursos São Paulo — Fisioterapia &amp; Nível Médio</h1>
          <div class="meta">
            Atualizado em <b>{gerado_em}</b> (Brasília) · Fonte:
            <a href="{LISTING_URL}" target="_blank" rel="noopener">PCI Concursos — Sudeste (SP)</a>
          </div>
        </div>
        <button id="btnInstall" class="btn-pwa" type="button">📲 Baixar App (PWA)</button>
      </div>

      <div class="stats">
        <div class="stat"><b>{total_sp}</b><span>concursos abertos em SP</span></div>
        <div class="stat"><b>{len(fisio)}</b><span>vagas de Fisioterapia</span></div>
        <div class="stat"><b>{len(medio_ok)}</b><span>Nível Médio &gt; R$ 5.000</span></div>
        <div class="stat"><b>{len(medio_pos)}</b><span>Possíveis (verificar edital)</span></div>
        <div class="stat"><b id="statNovos">{novos_count}</b><span>Novos (últimas 24h)</span></div>
      </div>
    </div>
  </header>

  <div class="container">
    <nav class="tabs">
      <button data-tab="fisio" class="ativo">🩺 Fisioterapeuta / Fisioterapia (<span class="cnt">{len(fisio)}</span>)</button>
      <button data-tab="medio">💰 Nível Médio &gt; R$ 5.000 (<span class="cnt">{len(medio_ok)}</span>)</button>
      <button data-tab="possiveis">🔍 Possíveis — Nível Médio (<span class="cnt">{len(medio_pos)}</span>)</button>
    </nav>

    <section class="filtros-panel" aria-label="Filtros de concursos">
      <div class="filtros-head">
        <strong>🎛️ Filtrar e Ordenar Concursos</strong>
        <div class="filtros-actions">
          <label class="chk-novo">
            <input type="checkbox" id="fNovo"> ✨ Apenas novos (últimas 24h)
          </label>
          <button type="button" id="btnLimpar" class="btn-limpar">Limpar filtros</button>
        </div>
      </div>
      <div class="filtros-grid">
        <div class="f-item">
          <label for="fBusca">🔍 Cidade, Órgão ou Cargo</label>
          <input id="fBusca" type="search" placeholder="Ex.: Ribeirão, Matão, IBAM...">
        </div>
        <div class="f-item">
          <label for="fCidade">🏙️ Cidade (SP)</label>
          <select id="fCidade">{opcoes_cidades}</select>
        </div>
        <div class="f-item">
          <label for="fKmRp">📍 Proximidade de Ribeirão Preto/SP</label>
          <select id="fKmRp">
            <option value="">Qualquer distância</option>
            <option value="50">Até 50 km de Ribeirão Preto</option>
            <option value="100">Até 100 km de Ribeirão Preto</option>
            <option value="150">Até 150 km de Ribeirão Preto</option>
            <option value="220">Até 220 km de Ribeirão Preto</option>
            <option value="300">Até 300 km de Ribeirão Preto</option>
            <option value="400">Até 400 km de Ribeirão Preto</option>
          </select>
        </div>
        <div class="f-item">
          <label for="fKmJa">📍 Proximidade de Jarinu/SP</label>
          <select id="fKmJa">
            <option value="">Qualquer distância</option>
            <option value="50">Até 50 km de Jarinu</option>
            <option value="100">Até 100 km de Jarinu</option>
            <option value="150">Até 150 km de Jarinu</option>
            <option value="250">Até 250 km de Jarinu</option>
            <option value="350">Até 350 km de Jarinu</option>
          </select>
        </div>
        <div class="f-item">
          <label for="fSalario">💵 Salário Bruto Mínimo</label>
          <select id="fSalario">
            <option value="0">Qualquer valor</option>
            <option value="2500">A partir de R$ 2.500,00</option>
            <option value="3500">A partir de R$ 3.500,00</option>
            <option value="4000">A partir de R$ 4.000,00</option>
            <option value="4500">A partir de R$ 4.500,00</option>
            <option value="5000">A partir de R$ 5.000,00</option>
            <option value="6000">A partir de R$ 6.000,00</option>
            <option value="8000">A partir de R$ 8.000,00</option>
          </select>
        </div>
        <div class="f-item">
          <label for="fVagas">👥 Número de Vagas</label>
          <select id="fVagas">
            <option value="todas">Todas (Vagas imediatas + CR)</option>
            <option value="1">Com vagas imediatas (≥ 1 vaga)</option>
            <option value="2">2 ou mais vagas imediatas (≥ 2)</option>
            <option value="3">3 ou mais vagas imediatas (≥ 3)</option>
            <option value="cr">Somente Cadastro de Reserva (CR)</option>
          </select>
        </div>
        <div class="f-item">
          <label for="fRegime">🏛️ Regime de Contratação</label>
          <select id="fRegime">
            <option value="">Todos os regimes</option>
            <option value="estatutario">Estatutário (Efetivo)</option>
            <option value="clt">CLT (Celetista)</option>
            <option value="outros">Residência / Militar / Seletivo</option>
          </select>
        </div>
        <div class="f-item">
          <label for="fHoras">⏱️ Carga Horária Semanal</label>
          <select id="fHoras">
            <option value="">Qualquer carga horária</option>
            <option value="20">Até 20h semanais</option>
            <option value="30">Até 30h semanais</option>
            <option value="36">Até 36h semanais</option>
            <option value="40">Até 40h semanais</option>
          </select>
        </div>
        <div class="f-item">
          <label for="fOrdem">↕️ Ordenar por</label>
          <select id="fOrdem">
            <option value="padrao">Padrão</option>
            <option value="rp">Mais próximos de Ribeirão Preto/SP</option>
            <option value="jarinu">Mais próximos de Jarinu/SP</option>
            <option value="salario">Maior salário bruto</option>
            <option value="vagas">Maior nº de vagas imediatas</option>
            <option value="prova">Data da prova mais próxima</option>
            <option value="inscricao">Inscrições encerrando primeiro</option>
            <option value="novos">Concursos novos (24h) primeiro</option>
          </select>
        </div>
      </div>
    </section>

    <main>
      {render_secao(
          "fisio",
          "Fisioterapeuta / Fisioterapia — Estado de São Paulo",
          "Valores exatos do cargo, benefícios (VA/VR/VT), regime estatutário/CLT, carga horária semanal, data da prova e conteúdo programático.",
          fisio,
          "fisio",
          ativo=True,
      )}
      {render_secao(
          "medio",
          "Nível Médio com Remuneração Acima de R$ 5.000,00",
          "Cargos que exigem apenas ensino médio completo com ganhos confirmados acima de R$ 5.000,00 (salário base ou base + benefício fixo).",
          medio_ok,
          "medio",
      )}
      {render_secao(
          "possiveis",
          "Possíveis Nível Médio — Verificar Tabela de Vencimentos no Edital",
          "Concursos com vagas de nível médio e teto salarial do certame acima de R$ 5.000,00 cujo salário específico do cargo deve ser conferido na tabela anexa do edital.",
          medio_pos,
          "possivel",
      )}
    </main>
  </div>

  <!-- Modal de Instrução de Instalação PWA -->
  <div id="modalPwa" class="modal-bg" role="dialog" aria-modal="true">
    <div class="modal">
      <h3>📲 Instalar Aplicativo Concursos SP</h3>
      <p style="margin:0 0 8px;color:var(--muted);font-size:.9rem;">
        Você pode instalar este painel como um aplicativo no celular ou computador (funciona até offline):
      </p>
      <ol>
        <li><b>No Chrome / Edge (PC ou Android):</b> clique no ícone de instalação <b>⊕</b> na barra de endereços ou no menu <b>⋮ → Instalar aplicativo / Adicionar à tela inicial</b>.</li>
        <li><b>No iPhone / iPad (Safari):</b> toque em <b>Compartilhar (⬆️)</b> e escolha <b>"Adicionar à Tela de Início"</b>.</li>
      </ol>
      <button type="button" id="fecharModal">Entendi</button>
    </div>
  </div>

<script>
  // 1) Atualização dinâmica da plaquinha de "CONCURSO NOVO (24h)" no navegador
  (function atualizarNovos24h() {{
    const agora = Date.now();
    let totalNovos = 0;
    document.querySelectorAll('.card').forEach(card => {{
      const isBaseline = card.dataset.isBaseline === '1';
      const ts = Date.parse(card.dataset.firstSeenTs || '');
      const ehNovo = !isBaseline && !isNaN(ts) && (agora - ts) >= 0 && (agora - ts) <= 86400000;
      card.dataset.novo = ehNovo ? '1' : '0';
      const badge = card.querySelector('.badge-novo');
      if (ehNovo) {{
        totalNovos++;
        if (!badge) {{
          const span = document.createElement('span');
          span.className = 'badge-novo';
          span.textContent = '✨ CONCURSO NOVO · 24h';
          card.querySelector('.head-top').appendChild(span);
        }}
      }} else if (badge) {{
        badge.remove();
      }}
    }});
    const elStat = document.getElementById('statNovos');
    if (elStat) elStat.textContent = totalNovos;
  }})();

  // 2) Navegação entre abas
  const btns = document.querySelectorAll('nav.tabs button');
  function abrirTab(tab) {{
    btns.forEach(b => b.classList.toggle('ativo', b.dataset.tab === tab));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('ativo', p.id === tab));
    history.replaceState(null, '', '#' + tab);
  }}
  btns.forEach(b => b.addEventListener('click', () => abrirTab(b.dataset.tab)));
  const hashInicial = location.hash.slice(1);
  if (['fisio', 'medio', 'possiveis'].includes(hashInicial)) abrirTab(hashInicial);

  // 3) Filtragem e Ordenação Completa
  const fBusca = document.getElementById('fBusca');
  const fCidade = document.getElementById('fCidade');
  const fKmRp = document.getElementById('fKmRp');
  const fKmJa = document.getElementById('fKmJa');
  const fSalario = document.getElementById('fSalario');
  const fVagas = document.getElementById('fVagas');
  const fRegime = document.getElementById('fRegime');
  const fHoras = document.getElementById('fHoras');
  const fOrdem = document.getElementById('fOrdem');
  const fNovo = document.getElementById('fNovo');

  function normStr(s) {{
    return (s || '').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
  }}

  function aplicarFiltros() {{
    const q = normStr(fBusca.value);
    const cid = fCidade.value;
    const maxRp = fKmRp.value ? Number(fKmRp.value) : null;
    const maxJa = fKmJa.value ? Number(fKmJa.value) : null;
    const minSal = Number(fSalario.value || 0);
    const vagasMode = fVagas.value;
    const regime = fRegime.value;
    const maxHoras = fHoras.value ? Number(fHoras.value) : null;
    const soNovos = fNovo.checked;
    const ordem = fOrdem.value;

    document.querySelectorAll('.tab-panel').forEach(panel => {{
      const grid = panel.querySelector('.grid');
      const cards = Array.from(grid.querySelectorAll('.card'));
      let visiveis = 0;

      cards.forEach(c => {{
        let ok = true;
        if (q && !c.dataset.busca.includes(q)) ok = false;
        if (ok && cid && c.dataset.cidade !== cid) ok = false;
        if (ok && maxRp !== null && Number(c.dataset.kmRp) > maxRp) ok = false;
        if (ok && maxJa !== null && Number(c.dataset.kmJarinu) > maxJa) ok = false;
        if (ok && minSal > 0 && Number(c.dataset.salario) < minSal) ok = false;
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

      // Ordenação
      if (ordem !== 'padrao') {{
        cards.sort((a, b) => {{
          if (ordem === 'rp') return Number(a.dataset.kmRp) - Number(b.dataset.kmRp);
          if (ordem === 'jarinu') return Number(a.dataset.kmJarinu) - Number(b.dataset.kmJarinu);
          if (ordem === 'salario') return Number(b.dataset.salario) - Number(a.dataset.salario);
          if (ordem === 'vagas') return Number(b.dataset.vagas) - Number(a.dataset.vagas);
          if (ordem === 'prova') return (a.dataset.prova || '').localeCompare(b.dataset.prova || '');
          if (ordem === 'inscricao') return (a.dataset.inscricao || '').localeCompare(b.dataset.inscricao || '');
          if (ordem === 'novos') return Number(b.dataset.novo) - Number(a.dataset.novo);
          return 0;
        }});
        cards.forEach(c => grid.appendChild(c));
      }}

      panel.querySelector('.sec-count').textContent = `(${{visiveis}})`;
      const btnTab = document.querySelector(`nav.tabs button[data-tab="${{panel.id}}"] .cnt`);
      if (btnTab) btnTab.textContent = visiveis;
      panel.querySelector('.vazio').style.display = visiveis === 0 ? 'block' : 'none';
    }});
  }}

  [fBusca, fCidade, fKmRp, fKmJa, fSalario, fVagas, fRegime, fHoras, fOrdem, fNovo].forEach(el => {{
    el.addEventListener('input', aplicarFiltros);
    el.addEventListener('change', aplicarFiltros);
  }});

  document.getElementById('btnLimpar').addEventListener('click', () => {{
    fBusca.value = '';
    fCidade.value = '';
    fKmRp.value = '';
    fKmJa.value = '';
    fSalario.value = '0';
    fVagas.value = 'todas';
    fRegime.value = '';
    fHoras.value = '';
    fOrdem.value = 'padrao';
    fNovo.checked = false;
    aplicarFiltros();
  }});

  // 4) PWA — Service Worker e Botão de Instalação
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

  document.getElementById('fecharModal').addEventListener('click', () => {{
    modalPwa.classList.remove('aberto');
  }});
  modalPwa.addEventListener('click', (e) => {{
    if (e.target === modalPwa) modalPwa.classList.remove('aberto');
  }});
</script>
</body>
</html>"""


if __name__ == "__main__":
    sys.exit(main())
