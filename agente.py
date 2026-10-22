"""
Agente de Busca de Concursos — PCI Concursos (SP + Brasil Todo)

Funcionalidades:
  1. Monitora diariamente os concursos do Estado de São Paulo (SP) e de todo o Brasil
     (todas as 27 UFs + Concursos Nacionais) no PCI Concursos.
  2. Aba 1 — Fisioterapia (SP): Salário bruto separado em destaque e soma com auxílios
     abaixo em fonte menor, benefícios (VA, VR, VT), regime (Estatutário / CLT /
     Residência / Militar / Seletivo), carga horária semanal, data da prova, taxa e
     isenção de inscrição, requisitos do edital e resumo do conteúdo programático.
  3. Aba 2 — Nível Médio > R$ 5.000 (SP): Cargos de nível médio com remuneração
     confirmada acima de R$ 5.000,00, salário bruto separado + soma com auxílios,
     isenção da taxa e especificações técnicas exigidas no edital.
  4. Aba 3 — Nível Médio / Técnico (Outras Faixas Salariais — SP): Todos os concursos
     de nível médio e técnico em SP separados por faixa salarial selecionável em botões.
  5. Aba 4 — Provas Anteriores (Por Banca e Cargo): Busca direta de provas anteriores
     exclusivamente por Banca Organizadora e Cargo (nunca por cidade).
  6. Aba 5 — Buscar Cargo Específico (SP / Outros Estados / Brasil Todo): Permite digitar
     qualquer cargo e filtrar por qualquer Estado (UF) ou no Brasil todo.
  7. Aviso automático de inscrições próximas ao encerramento + botão de filtro dedicado
     e botão "Aplicar Filtros" com alinhamento e espaçamento refinados.
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
from datetime import date, datetime, timedelta, timezone
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
DIAS_ALERTA_ENCERRAMENTO = 10
FISIO_REGEX = re.compile(r"\bfisioterap(?:euta|ia|êutico|eutas)\b", re.I)
SCHEMA_VERSION = 5

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


def norm_slug(s: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-")


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
# Gerador de Links de Provas Anteriores por BANCA e CARGO (Nunca por Cidade)
# --------------------------------------------------------------------------- #
def extrair_cargo_busca_provas(cargo_raw: str) -> str:
    if not cargo_raw:
        return "Conhecimentos Gerais"
    c = re.split(r"[/—\-]|\(", cargo_raw)[0].strip()
    c = re.sub(r"\b(r1|sus|edital.*|area.*|tnm|exclusivo.*|masculino.*|feminino.*)\b", "", c, flags=re.I).strip()
    c = re.sub(r"\s+[IVX]+$", "", c).strip()
    cn = norm(c)
    if "oficial temporario" in cn or "fisioterapia" in cn or "fisioterapeuta" in cn:
        return "Fisioterapeuta"
    if "guarda civil" in cn or "guarda municipal" in cn:
        return "Guarda Municipal"
    if "suporte ao atendimento" in cn or "apoio escolar" in cn or "desenvolvimento infantil" in cn or "servicos infantis" in cn:
        return "Monitor"
    return c or "Agente Administrativo"


def extrair_banca_busca_provas(banca_raw: str) -> str:
    if not banca_raw or "consultar" in norm(banca_raw) or "proprio" in norm(banca_raw):
        return ""
    b = re.split(r"[/—\-]|\(", banca_raw)[0].strip()
    bn = norm(b)
    mapa_bancas = {
        "vunesp": "VUNESP",
        "ibam": "IBAM",
        "avanca sp": "Avança",
        "indepac": "INDEPAC",
        "conscam": "CONSCAM",
        "consesp": "CONSESP",
        "fundacao fafipa": "FAFIPA",
        "fafipa": "FAFIPA",
        "instituto mais": "Instituto Mais",
        "instituto avalia": "Avalia",
        "instituto unique": "Unique",
        "instituto indec": "INDEC",
        "indec": "INDEC",
        "igecs": "IGECS",
        "aplicativa assessoria": "Aplicativa",
        "instituto aplicativa": "Aplicativa",
        "gl consultoria": "GL Consultoria",
        "imperio concursos": "Império",
        "ipell consultoria": "IPELL",
        "instituto ibepp": "IBEPP",
        "sigmarh": "SigmaRH",
        "marinha": "Marinha",
        "unesp": "UNESP",
        "funcamp": "FUNCAMP",
        "famesp": "FAMESP",
    }
    for k, v in mapa_bancas.items():
        if k in bn:
            return v
    return b


def gerar_links_provas_banca_cargo(cargo_raw: str, banca_raw: str) -> Dict[str, str]:
    """
    Gera links de Provas Anteriores pesquisando por CARGO e BANCA (nunca por cidade).
    """
    cargo_limpo = extrair_cargo_busca_provas(cargo_raw)
    banca_limpa = extrair_banca_busca_provas(banca_raw)
    c_slug = norm_slug(cargo_limpo)
    b_slug = norm_slug(banca_limpa)

    if b_slug and c_slug:
        url_combo = f"https://www.pciconcursos.com.br/provas/{c_slug}-{b_slug}"
        label_combo = f"{cargo_limpo} · {banca_limpa}"
    elif c_slug:
        url_combo = f"https://www.pciconcursos.com.br/provas/{c_slug}"
        label_combo = cargo_limpo
    else:
        url_combo = "https://www.pciconcursos.com.br/provas/"
        label_combo = "Provas Anteriores"

    url_cargo = f"https://www.pciconcursos.com.br/provas/{c_slug}" if c_slug else "https://www.pciconcursos.com.br/provas/"
    url_banca = f"https://www.pciconcursos.com.br/provas/{b_slug}" if b_slug else ""

    return {
        "url_combo": url_combo,
        "url_cargo": url_cargo,
        "url_banca": url_banca,
        "cargo_busca": cargo_limpo,
        "banca_busca": banca_limpa or "Todas as Bancas",
        "label_combo": label_combo,
    }


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
    "jose pedro de oliveira": "campinas",
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
        return {
            "cidade": "São Paulo (Estado)",
            "km_ribeirao_preto": None,
            "km_jarinu": None,
            "lat": -23.5505,
            "lon": -46.6333,
        }
    info = MUNICIPIOS_SP.get(norm(cidade))
    if not info:
        return {
            "cidade": cidade,
            "km_ribeirao_preto": None,
            "km_jarinu": None,
            "lat": -23.5505,
            "lon": -46.6333,
        }
    return {
        "cidade": info["nome"],
        "km_ribeirao_preto": info["km_ribeirao_preto"],
        "km_jarinu": info["km_jarinu"],
        "lat": info.get("lat", -23.5505),
        "lon": info.get("lon", -46.6333),
    }


# --------------------------------------------------------------------------- #
# Utilidades HTTP, Datas e Formatação
# --------------------------------------------------------------------------- #
def fetch(url: str, retries: int = 3) -> str:
    if not (url and url.startswith("https://www.pciconcursos.com.br/")):
        raise RuntimeError(f"URL bloqueada por política de segurança (domínio não autorizado): {url}")
    for tentativa in range(1, retries + 1):
        try:
            r = session.get(url, timeout=60, allow_redirects=True)
            r.raise_for_status()
            if not r.url.startswith("https://www.pciconcursos.com.br/"):
                raise RuntimeError(f"Redirecionamento externo bloqueado: {r.url}")
            if len(r.content) > 5_000_000:
                raise RuntimeError(f"Resposta excedeu limite de segurança (5 MB): {url}")
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


def extrair_data_final_br(texto_data: str) -> Optional[date]:
    """Extrai a última data DD/MM/AAAA de uma string como '22/10 a 05/11/2026'."""
    matches = re.findall(r"(\d{2})/(\d{2})/(\d{4})", texto_data or "")
    if not matches:
        return None
    d_str, m_str, y_str = matches[-1]
    try:
        return date(int(y_str), int(m_str), int(d_str))
    except ValueError:
        return None


def calcular_status_inscricao(inscricao_ate: str, hoje_dt: date) -> Dict[str, Any]:
    dt_fim = extrair_data_final_br(inscricao_ate)
    if not dt_fim:
        return {
            "data_fim_iso": "9999-12-31",
            "dias_restantes": 999,
            "encerrando": False,
            "encerrada": False,
            "aviso_texto": "",
        }
    dias = (dt_fim - hoje_dt).days
    iso = dt_fim.isoformat()
    if dias < 0:
        return {
            "data_fim_iso": iso,
            "dias_restantes": dias,
            "encerrando": False,
            "encerrada": True,
            "aviso_texto": "⛔ Inscrições encerradas",
        }
    if dias == 0:
        return {
            "data_fim_iso": iso,
            "dias_restantes": 0,
            "encerrando": True,
            "encerrada": False,
            "aviso_texto": "🚨 ÚLTIMO DIA DE INSCRIÇÃO (Encerra hoje!)",
        }
    if dias == 1:
        return {
            "data_fim_iso": iso,
            "dias_restantes": 1,
            "encerrando": True,
            "encerrada": False,
            "aviso_texto": "⚠️ INSCRIÇÕES ENCERRANDO · Termina amanhã (1 dia)!",
        }
    if dias <= DIAS_ALERTA_ENCERRAMENTO:
        return {
            "data_fim_iso": iso,
            "dias_restantes": dias,
            "encerrando": True,
            "encerrada": False,
            "aviso_texto": f"⏳ INSCRIÇÕES ENCERRANDO · Faltam {dias} dias!",
        }
    return {
        "data_fim_iso": iso,
        "dias_restantes": dias,
        "encerrando": False,
        "encerrada": False,
        "aviso_texto": f"Faltam {dias} dias para encerrar",
    }


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
# 2) Extração de texto, cargos (<li>), taxa/isenção e metadados da notícia
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


def parse_isencao(texto: str) -> str:
    frases = [
        re.sub(r"\s+", " ", f).strip()
        for f in re.split(r"(?<=[.!?;])\s+|\n+", texto or "")
        if f.strip()
    ]
    achados = []
    for f in frases:
        if len(f) > 300:
            continue
        if re.search(
            r"(taxa\s+de\s+inscri|taxas\s+de\s+inscri|valor\s+da\s+inscri|valor\s+da\s+taxa|"
            r"isen[çc][ãa]o|redu[çc][ãa]o\s+d[ae]\s+taxa|redu[çc][ãa]o\s+de\s+50%|"
            r"n[ãa]o\s+haver[áa]\s+cobran[çc]a|inscri[çc][õo]es\s+s[ãa]o\s+gratuitas|gratuitamente)",
            f,
            re.I,
        ):
            if f not in achados:
                achados.append(f)
    if achados:
        resumo = " ".join(achados[:2])
        if not re.search(r"isen[çc]|redu[çc]|gratuit|cobran[çc]a", resumo, re.I):
            resumo += " (Hipóteses de isenção/redução: consultar edital — geralmente CadÚnico/baixa renda ou doadores de sangue/medula)."
        return resumo
    if re.search(r"exclusiv[oa]\s+para\s+pessoas?\s+com\s+defici[êe]ncia|vaga.*pcd", texto or "", re.I):
        return "Inscrição gratuita (seleção exclusiva PcD — sem cobrança de taxa informada no edital)."
    return "Consultar edital para valores de taxa e requisitos de isenção (CadÚnico, doadores de sangue/medula ou lei municipal/estadual)."


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
    for a in soup.select("#links a"):
        txt = a.get_text(" ", strip=True)
        if "edital-pdf-link" in (a.get("class") or []) or "edital" in txt.lower() or "errata" in txt.lower() or "aviso" in txt.lower():
            if txt and txt not in arquivos_edital:
                arquivos_edital.append(txt)

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
        "link_banca": link_banca,
        "nome_banca": nome_banca,
        "data_prova": parse_data_prova(texto),
        "regime": parse_regime(texto),
        "beneficios": parse_beneficios(texto),
        "jornada": parse_jornada(texto),
        "isencao": parse_isencao(texto),
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
            description="Salário/vencimento bruto base específico deste cargo em R$ (número). Use null se não informado.",
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
        isencao: Optional[str] = Field(
            default=None,
            description="Resumo do valor da taxa de inscrição e se há isenção/redução de taxa e seus requisitos.",
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
    "(VA, VR, VT com valores quando houver), taxa de inscrição e requisitos de isenção, "
    "jornada semanal e a lista de cargos com escolaridade, salário bruto base específico e "
    "requisitos técnicos para assumir o cargo."
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


def formatar_bruto_e_soma_auxilios(sal_bruto: Optional[float], beneficios_txt: str, faixa_edital: str) -> tuple[Optional[float], str, str]:
    """
    Retorna (salario_total, salario_bruto_exib, salario_detalhe_menor) garantindo SEMPRE
    o Salário Bruto separado no valor principal e a soma com auxílios embaixo menor.
    """
    if not sal_bruto:
        return None, faixa_edital or "Consultar edital", f"Faixa bruta no edital: {faixa_edital} (+ auxílios legais)"

    bruto_str = brl(sal_bruto)
    ben_txt = beneficios_txt or ""
    # Verifica se há valor em R$ nos benefícios
    m_diario = re.search(r"di[áa]ri[oa]\s+de\s+R\$\s*([\d.]+,\d{2})", ben_txt, re.I)
    if m_diario:
        val_dia = parse_brl(m_diario.group(1)) or 0.0
        mensal_est = round(val_dia * 22, 2)
        total = round(sal_bruto + mensal_est, 2)
        return (
            total,
            bruto_str,
            f"Bruto: {bruto_str} + {brl(val_dia)}/dia (~{brl(mensal_est)}/mês VA) = {brl(total)} com auxílios",
        )

    vals_ben = [parse_brl(v) for v in re.findall(r"R\$\s*([\d.]+,\d{2})", ben_txt)]
    vals_ben = [v for v in vals_ben if v and 50.0 <= v <= 3500.0]
    if vals_ben:
        soma_ben = round(sum(vals_ben), 2)
        total = round(sal_bruto + soma_ben, 2)
        return (
            total,
            bruto_str,
            f"Bruto: {bruto_str} + {brl(soma_ben)} (auxílios) = {brl(total)} com auxílios",
        )

    return sal_bruto, bruto_str, f"Bruto: {bruto_str} (vencimento base no edital) + benefícios legais"


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
    c["lat"] = dist["lat"]
    c["lon"] = dist["lon"]

    c["banca"] = (
        enriq.get("banca")
        or ia.get("banca")
        or det.get("nome_banca")
        or "Consultar edital"
    )
    c["site_banca"] = enriq.get("site_banca") or det.get("link_banca") or ""
    c["link_edital"] = f"{url}#links"
    c["arquivos_edital"] = det.get("arquivos_edital") or ["EDITAL COMPLETO E ANEXOS"]
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
    c["isencao"] = (
        enriq.get("isencao")
        or ia.get("isencao")
        or det.get("isencao")
        or parse_isencao(det.get("texto", ""))
    )
    c["faixa_salarial"] = parse_faixa_salarial(det.get("texto", ""), c.get("vagas_salario", ""))

    # Status do prazo de inscrição (encerrando nos próximos dias vs encerrada)
    st_insc = calcular_status_inscricao(c.get("inscricao_ate", ""), agora.date())
    c["inscricao_status"] = st_insc

    # Lista completa de cargos deste concurso para a Busca por Cargo Específico
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

        sal_bruto = (
            f_enriq.get("salario_bruto")
            or f_enriq.get("salario_base")
            or f_enriq.get("salario")
            or cargo_ia_fisio.get("salario")
        )
        ben_fisio = f_enriq.get("beneficios") or c["beneficios_gerais"]
        sal_tot_auto, bruto_exib_auto, sal_det_auto = formatar_bruto_e_soma_auxilios(
            sal_bruto, ben_fisio, c["faixa_salarial"]
        )
        sal_det = f_enriq.get("salario_detalhe") or sal_det_auto
        sal_total = f_enriq.get("salario_total") or sal_tot_auto or sal_bruto

        c["fisio_detalhes"] = {
            "cargo": f_enriq.get("cargo") or cargo_ia_fisio.get("nome") or re.sub(r"\s*\([^)]*\)", "", linha_bruta).strip(),
            "vagas": vagas_txt,
            "vagas_imediatas": vagas_im,
            "tem_cr": tem_cr,
            "salario": sal_bruto,
            "salario_bruto": sal_bruto,
            "salario_total": sal_total,
            "salario_exibicao": brl(sal_bruto) if sal_bruto else bruto_exib_auto,
            "salario_detalhe": sal_det,
            "carga_horaria": f_enriq.get("carga_horaria") or cargo_ia_fisio.get("carga_horaria") or c["jornada_geral"],
            "regime": f_enriq.get("regime") or cargo_ia_fisio.get("regime") or c["regime_geral"],
            "escolaridade_tipo": "superior",
            "requisitos": (
                f_enriq.get("requisitos")
                or cargo_ia_fisio.get("requisitos")
                or "Ensino Superior completo em Fisioterapia + Registro regular ativo no CREFITO-3."
            ),
            "beneficios": ben_fisio,
            "resumo_conteudo": (
                f_enriq.get("resumo_conteudo")
                or ia.get("resumo_conteudo_fisio")
                or conteudo_padrao_fisio(c["banca"], c["regime_geral"])
            ),
        }

    # ---------------- 2) NÍVEL MÉDIO / TÉCNICO ---------------- #
    c["medio_confirmado"] = []
    c["medio_outros"] = []
    sal_max = max([v for v in (c.get("salario_max_listagem"), info.get("salario_max_texto")) if v] or [0]) or None
    c["salario_max"] = sal_max
    niveis_str = c.get("niveis", "")

    if enriq.get("medio"):
        for item in enriq["medio"]:
            c["medio_confirmado"].append(item)
            c["medio_outros"].append(item)
    elif enriq.get("medio_outros"):
        for item in enriq["medio_outros"]:
            c["medio_outros"].append(item)
    elif not enriq.get("medio_excluido"):
        tem_med_listagem = bool(re.search(r"m[ée]dio|t[ée]cnico", niveis_str, re.I))
        if tem_med_listagem or info.get("tem_medio"):
            cargos_med = []
            if c.get("cargos_resumo") and "Vários" not in c["cargos_resumo"]:
                for p in [x.strip() for x in c["cargos_resumo"].split(",") if x.strip()]:
                    if not re.search(
                        r"\b(m[ée]dico|professor|docente|peb|diretor|psic[óo]logo|engenheiro|arquiteto|advogado|procurador|contador|economista|auditor|enfermeiro|dentista|farmac[êe]utico|nutricionista|fisioterapeuta|terapeuta|assistente\s+social)\b",
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

            if cargos_med:
                nomes_limpos = [re.sub(r"\s*\([^)]*\)", "", x).strip() for x in cargos_med[:4]]
                nome_exib = " / ".join(nomes_limpos)
                if len(cargos_med) > 4:
                    nome_exib += f" (+{len(cargos_med) - 4} cargos)"

                v_im, t_cr, v_txt = extrair_vagas_info(c.get("vagas_salario"))
                esc_tipo, req_txt = inferir_requisitos_cargo(nome_exib, niveis_str)

                tem_superior = "Superior" in niveis_str
                sal_bruto = sal_max if (sal_max and not tem_superior) else (min(sal_max, 3200.0) if sal_max else None)
                sal_total, _, sal_det = formatar_bruto_e_soma_auxilios(
                    sal_bruto, c["beneficios_gerais"], c["faixa_salarial"]
                )

                item_auto = {
                    "nome": nome_exib,
                    "vagas": v_txt,
                    "vagas_imediatas": v_im,
                    "tem_cr": t_cr,
                    "salario": sal_bruto,
                    "salario_bruto": sal_bruto,
                    "salario_total": sal_total,
                    "salario_detalhe": sal_det,
                    "carga_horaria": c["jornada_geral"],
                    "regime": c["regime_geral"],
                    "escolaridade_tipo": esc_tipo,
                    "requisitos": req_txt,
                    "beneficios": c["beneficios_gerais"],
                    "resumo_conteudo": conteudo_padrao_medio(nomes_limpos[0], c["banca"]),
                }
                if sal_bruto and sal_bruto > SALARIO_MINIMO_MEDIO and not tem_superior:
                    c["medio_confirmado"].append(item_auto)
                c["medio_outros"].append(item_auto)

    # ---------------- 3) NÍVEL SUPERIOR (SP) ---------------- #
    c["superior_itens"] = []
    from render_site import inferir_formacoes_multidisciplinares, inferir_requisitos_superior

    tem_sup_listagem = "Superior" in niveis_str or bool(c.get("fisio"))
    cargos_sup = []
    padrao_sup = re.compile(
        r"\b(auditor|fiscal\s+de\s+tributos|fiscal\s+tribut[áa]rio|fiscal\s+de\s+rendas|controlador\s+interno|"
        r"analista|contador|economista|administrador|advogado|procurador|jur[íi]dico|defensor|juiz|promotor|"
        r"m[ée]dico|enfermeiro|psic[óo]logo|engenheiro|arquiteto|farmac[êe]utico|nutricionista|dentista|cirurgi[ãa]o|"
        r"fisioterapeuta|terapeuta\s+ocupacional|fonoaudi[óo]logo|biom[ée]dico|assistente\s+social|veterin[áa]rio|"
        r"professor|docente|peb|pedagogo|diretor|coordenador|orientador|especialista|gestor|bibliotec[áa]rio|"
        r"soci[óo]logo|bi[óo]logo|qu[íi]mico|ge[óo]logo|estat[íi]stico|jornalista|comunicador|tesoureiro)\b",
        re.I,
    )
    for cl in cargos_todos:
        if padrao_sup.search(cl) and not re.search(r"\b(t[ée]cnico\s+em|auxiliar\s+de)\b", cl, re.I):
            cargos_sup.append(cl)
    if not cargos_sup and c.get("cargos_resumo") and "Vários" not in c["cargos_resumo"]:
        for p in [x.strip() for x in c["cargos_resumo"].split(",") if x.strip()]:
            if padrao_sup.search(p) and not re.search(r"\b(t[ée]cnico\s+em|auxiliar\s+de)\b", p, re.I):
                cargos_sup.append(p)
    if not cargos_sup and c.get("fisio"):
        cargos_sup.append((c.get("fisio_detalhes") or {}).get("cargo") or "Fisioterapeuta")
    if not cargos_sup and tem_sup_listagem:
        resumo_c = c.get("cargos_resumo") or "Cargos de Nível Superior (ver edital)"
        cargos_sup.append(resumo_c)

    if tem_sup_listagem or cargos_sup:
        nomes_sup = [re.sub(r"\s*\([^)]*\)", "", x).strip() for x in cargos_sup[:4]]
        nome_sup_exib = " / ".join(nomes_sup) if nomes_sup else "Cargos de Nível Superior"
        if len(cargos_sup) > 4:
            nome_sup_exib += f" (+{len(cargos_sup) - 4} cargos)"

        v_im_s, t_cr_s, v_txt_s = extrair_vagas_info(c.get("vagas_salario"))
        sal_bruto_s = sal_max
        if c.get("fisio") and not sal_bruto_s:
            sal_bruto_s = (c.get("fisio_detalhes") or {}).get("salario_bruto")
        sal_total_s, _, sal_det_s = formatar_bruto_e_soma_auxilios(
            sal_bruto_s, c["beneficios_gerais"], c["faixa_salarial"]
        )
        req_sup = inferir_requisitos_superior(nome_sup_exib, cargos_todos)
        formacoes_info = inferir_formacoes_multidisciplinares(cargos_todos, c.get("cargos_resumo", ""), c.get("titulo", ""))
        c["formacoes_aceitas"] = formacoes_info["descricao"]
        c["termos_formacao"] = formacoes_info["termos_busca"]

        c["superior_itens"].append(
            {
                "nome": nome_sup_exib,
                "vagas": v_txt_s,
                "vagas_imediatas": v_im_s,
                "tem_cr": t_cr_s,
                "salario": sal_bruto_s,
                "salario_bruto": sal_bruto_s,
                "salario_total": sal_total_s,
                "salario_detalhe": sal_det_s,
                "carga_horaria": c["jornada_geral"],
                "regime": c["regime_geral"],
                "escolaridade_tipo": "superior",
                "requisitos": req_sup,
                "beneficios": c["beneficios_gerais"],
                "resumo_conteudo": conteudo_padrao_medio(nomes_sup[0] if nomes_sup else "Nível Superior", c["banca"]),
            }
        )


# --------------------------------------------------------------------------- #
# 6) Coleta Nacional (Brasil Todo + Todos os Estados)
# --------------------------------------------------------------------------- #
def coletar_concursos_brasil(cache_sp: Dict[str, dict], enriquecidos: Dict[str, dict], hoje_dt: date) -> List[dict]:
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
    log(f"Total de concursos listados no Brasil: {len(lista_br)}")

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
                    "isencao": det["isencao"],
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

    catalogo_br = []
    for it in lista_br:
        st_insc = calcular_status_inscricao(it.get("inscricao_ate", ""), hoje_dt)
        if st_insc["encerrada"]:
            continue

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

        from render_site import (
            UF_COORDS,
            data_iso_sort as _data_iso,
            faixa_salarial_slug as _faixa_slug,
            horas_num as _horas_num,
            inferir_formacoes_multidisciplinares as _inferir_formacoes,
            inferir_plano_carreira as _plano_carreira,
            niveis_tokens as _niveis_tokens,
            regime_categoria as _regime_cat,
        )

        uf_str = it["uf"] or "BR"
        cidade_sp = None
        lat_val, lon_val = UF_COORDS.get(uf_str, (-15.7975, -47.8919))
        if uf_str == "SP":
            cidade_sp = detectar_cidade(it["orgao"], it["titulo"], u, "", enriq.get("cidade") or sp_ia.get("cidade"))
            d_info = info_distancia(cidade_sp)
            cidade_sp = d_info["cidade"]
            lat_val = d_info["lat"]
            lon_val = d_info["lon"]

        banca_nome = (
            enriq.get("banca")
            or sp_ia.get("banca")
            or sp_det.get("nome_banca")
            or br_det.get("nome_banca")
            or "Consultar edital"
        )
        cargo_ref = cargos_lista[0] if cargos_lista else (it.get("cargos_resumo") or "Agente Administrativo")
        links_provas = gerar_links_provas_banca_cargo(cargo_ref, banca_nome)

        regime_val = (
            enriq.get("regime")
            or sp_ia.get("regime_geral")
            or sp_det.get("regime")
            or br_det.get("regime")
            or "Consultar edital"
        )
        benef_val = (
            enriq.get("beneficios")
            or sp_ia.get("beneficios")
            or sp_det.get("beneficios")
            or br_det.get("beneficios")
            or "Consultar edital"
        )
        jornada_val = (
            sp_ia.get("jornada_geral")
            or sp_det.get("jornada")
            or br_det.get("jornada")
            or "Consultar edital"
        )
        data_prova_val = (
            enriq.get("data_prova")
            or sp_ia.get("data_prova")
            or sp_det.get("data_prova")
            or br_det.get("data_prova")
            or "Consultar edital"
        )
        sal_max_val = it.get("salario_max_listagem")
        vagas_im_val, _, vagas_txt_val = extrair_vagas_info(it.get("vagas_salario"))
        sal_total_val, sal_exib_val, sal_det_val = formatar_bruto_e_soma_auxilios(
            sal_max_val, benef_val, it.get("vagas_salario") or "Consultar edital"
        )
        if sal_max_val:
            sal_exib_val = f"Até {brl(sal_max_val)}"

        form_info = _inferir_formacoes(cargos_lista, it.get("cargos_resumo", ""), it.get("titulo", ""))

        catalogo_br.append(
            {
                "url": u,
                "orgao": it["orgao"],
                "titulo": it["titulo"],
                "uf": uf_str,
                "regiao": it["regiao"],
                "cidade": cidade_sp or uf_str or "Nacional",
                "lat": lat_val,
                "lon": lon_val,
                "vagas_salario": it["vagas_salario"],
                "vagas_im": vagas_im_val,
                "vagas_txt": vagas_txt_val,
                "salario_max": sal_max_val,
                "salario_total": sal_total_val or sal_max_val,
                "salario_exib": sal_exib_val,
                "salario_det": sal_det_val,
                "faixa": _faixa_slug(sal_max_val, sal_total_val),
                "cargos_resumo": it["cargos_resumo"],
                "niveis": it["niveis"],
                "niveis_tokens": _niveis_tokens(it.get("niveis", ""), ""),
                "inscricao_ate": it["inscricao_ate"] or "Consultar edital",
                "inscricao_iso": st_insc["data_fim_iso"],
                "dias_restantes": st_insc["dias_restantes"],
                "encerrando": st_insc["encerrando"],
                "aviso_inscricao": st_insc["aviso_texto"],
                "novo": eh_novo_24h(sp_info, datetime.now(BRT)) if sp_info else False,
                "data_prova": data_prova_val,
                "prova_iso": _data_iso(data_prova_val),
                "banca": banca_nome,
                "site_banca": enriq.get("site_banca") or sp_det.get("link_banca") or br_det.get("link_banca") or "",
                "url_provas": links_provas["url_combo"],
                "label_provas": links_provas["label_combo"],
                "regime": regime_val,
                "regime_cat": _regime_cat(regime_val),
                "beneficios": benef_val,
                "carreira": _plano_carreira(it["orgao"], regime_val, benef_val, it.get("niveis", "")),
                "isencao": (
                    enriq.get("isencao")
                    or sp_ia.get("isencao")
                    or sp_det.get("isencao")
                    or br_det.get("isencao")
                    or "Consultar edital para taxa e requisitos de isenção."
                ),
                "jornada": jornada_val,
                "horas_num": _horas_num(jornada_val),
                "cargos": cargos_lista[:80],
                "formacoes_aceitas": form_info["descricao"],
                "termos_formacao": form_info["termos_busca"],
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


def _preencher_links_provas_sp(c: dict) -> None:
    banca_nome = c.get("banca") or "Consultar edital"
    mapa = {}
    if c.get("fisio"):
        cg = (c.get("fisio_detalhes") or {}).get("cargo") or "Fisioterapeuta"
        mapa["fisio"] = gerar_links_provas_banca_cargo(cg, banca_nome)
    if c.get("medio_confirmado"):
        cg = c["medio_confirmado"][0].get("nome") or "Agente Administrativo"
        mapa["medio5k"] = gerar_links_provas_banca_cargo(cg, banca_nome)
    if c.get("medio_outros"):
        cg = c["medio_outros"][0].get("nome") or "Agente Administrativo"
        mapa["medio_todos"] = gerar_links_provas_banca_cargo(cg, banca_nome)
    if c.get("superior_itens"):
        cg = c["superior_itens"][0].get("nome") or "Analista"
        mapa["superior_sp"] = gerar_links_provas_banca_cargo(cg, banca_nome)
    c["links_provas_map"] = mapa


def main() -> int:
    from render_site import render_html

    DATA_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)
    cache: Dict[str, dict] = load_json(CACHE_FILE, {})
    enriquecidos: Dict[str, dict] = load_json(ENRIQUECIDOS_FILE, {})
    agora = datetime.now(BRT)
    hoje = agora.strftime("%Y-%m-%d")
    hoje_dt = agora.date()

    for u, item in cache.items():
        if "first_seen_ts" not in item:
            item["first_seen_ts"] = "2026-10-20T07:00:00-03:00"
            item["is_baseline"] = True

    log(f"Baixando listagem principal (Sudeste): {LISTING_URL}")
    todos = parse_listing(fetch(LISTING_URL), regiao_padrao="Sudeste")
    concursos_todos_sp = [c for c in todos if c["uf"] == UF_ALVO]
    log(f"{len(todos)} concursos no Sudeste, {len(concursos_todos_sp)} em {UF_ALVO}.")

    for i, c in enumerate(concursos_todos_sp, 1):
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
            log(f"[{i}/{len(concursos_todos_sp)}] Analisando detalhes SP: {c['orgao']}")
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

    catalogo_brasil = coletar_concursos_brasil(cache, enriquecidos, hoje_dt)
    cache_br_map = load_json(CACHE_BRASIL_FILE, {})

    concursos_vigentes: List[dict] = []
    for c in concursos_todos_sp:
        url = c["url"]
        info = cache.get(url)
        if info is None:
            continue
        if url in cache_br_map and not (info.get("detalhes") or {}).get("cargos_li"):
            info.setdefault("detalhes", {})["cargos_li"] = cache_br_map[url].get("cargos_li", [])
        montar_concurso_sp(c, info, enriquecidos, agora)
        _preencher_links_provas_sp(c)
        # Mantém apenas concursos com inscrições vigentes (não encerradas)
        if not (c.get("inscricao_status") or {}).get("encerrada", False):
            concursos_vigentes.append(c)

    ativos = {c["url"] for c in concursos_todos_sp}
    cache = {u: v for u, v in cache.items() if u in ativos}
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    fisio = [c for c in concursos_vigentes if c.get("fisio")]
    medio_ok = [c for c in concursos_vigentes if c.get("medio_confirmado")]
    medio_todos = [c for c in concursos_vigentes if c.get("medio_outros")]
    medio_todos.sort(
        key=lambda x: max([it.get("salario_bruto") or it.get("salario") or 0 for it in x.get("medio_outros", [])] or [0]),
        reverse=True,
    )
    superior_sp = [c for c in concursos_vigentes if c.get("superior_itens")]
    superior_sp.sort(
        key=lambda x: max([it.get("salario_bruto") or it.get("salario") or 0 for it in x.get("superior_itens", [])] or [0]),
        reverse=True,
    )

    urls_vistas = set()
    novos_24h = 0
    encerrando_count = 0
    for c in fisio + medio_todos + superior_sp:
        if c["url"] not in urls_vistas:
            urls_vistas.add(c["url"])
            if c.get("novo"):
                novos_24h += 1
            if (c.get("inscricao_status") or {}).get("encerrando"):
                encerrando_count += 1

    # Catálogo de Provas Anteriores por Banca e Cargo (sem duplicar por cidade)
    pares_provas_vistos = set()
    catalogo_provas_banca_cargo = []
    for c in fisio + medio_todos + superior_sp:
        banca_raw = c.get("banca") or "Consultar edital"
        if c.get("fisio"):
            c_nome = (c.get("fisio_detalhes") or {}).get("cargo") or "Fisioterapeuta"
            lp = gerar_links_provas_banca_cargo(c_nome, banca_raw)
            chave_par = (lp["cargo_busca"], lp["banca_busca"])
            if chave_par not in pares_provas_vistos:
                pares_provas_vistos.add(chave_par)
                catalogo_provas_banca_cargo.append({
                    "cargo": lp["cargo_busca"],
                    "banca": lp["banca_busca"],
                    "banca_original": banca_raw,
                    "escolaridade": "Ensino Superior (Fisioterapia)",
                    "url_combo": lp["url_combo"],
                    "url_cargo": lp["url_cargo"],
                    "url_banca": lp["url_banca"],
                    "exemplo_orgao": c["orgao"],
                    "data_prova": c.get("data_prova") or "Consultar edital",
                })
        for m_it in c.get("medio_outros") or []:
            c_nome = m_it.get("nome") or "Agente Administrativo"
            lp = gerar_links_provas_banca_cargo(c_nome, banca_raw)
            chave_par = (lp["cargo_busca"], lp["banca_busca"])
            if chave_par not in pares_provas_vistos:
                pares_provas_vistos.add(chave_par)
                catalogo_provas_banca_cargo.append({
                    "cargo": lp["cargo_busca"],
                    "banca": lp["banca_busca"],
                    "banca_original": banca_raw,
                    "escolaridade": "Nível Médio / Técnico",
                    "url_combo": lp["url_combo"],
                    "url_cargo": lp["url_cargo"],
                    "url_banca": lp["url_banca"],
                    "exemplo_orgao": c["orgao"],
                    "data_prova": c.get("data_prova") or "Consultar edital",
                })
        for s_it in c.get("superior_itens") or []:
            c_nome = s_it.get("nome") or "Analista"
            lp = gerar_links_provas_banca_cargo(c_nome, banca_raw)
            chave_par = (lp["cargo_busca"], lp["banca_busca"])
            if chave_par not in pares_provas_vistos:
                pares_provas_vistos.add(chave_par)
                catalogo_provas_banca_cargo.append({
                    "cargo": lp["cargo_busca"],
                    "banca": lp["banca_busca"],
                    "banca_original": banca_raw,
                    "escolaridade": "Ensino Superior",
                    "url_combo": lp["url_combo"],
                    "url_cargo": lp["url_cargo"],
                    "url_banca": lp["url_banca"],
                    "exemplo_orgao": c["orgao"],
                    "data_prova": c.get("data_prova") or "Consultar edital",
                })

    gerado_em = agora.strftime("%d/%m/%Y %H:%M")

    RESULTS_FILE.write_text(
        json.dumps(
            {
                "gerado_em": gerado_em,
                "gerado_em_iso": agora.isoformat(),
                "fonte": LISTING_URL,
                "total_sp": len(concursos_vigentes),
                "total_brasil": len(catalogo_brasil),
                "ia_ativa": bool(GEMINI_API_KEY) or bool(enriquecidos),
                "novos_ultimas_24h": novos_24h,
                "encerrando_proximos_dias": encerrando_count,
                "fisioterapia": fisio,
                "nivel_medio_todas_faixas": medio_todos,
                "nivel_superior_sp": superior_sp,
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
            catalogo_provas_banca_cargo=catalogo_provas_banca_cargo,
            total_sp=len(concursos_vigentes),
            gerado_em=gerado_em,
            listing_url=LISTING_URL,
            pix_key=PIX_KEY,
            superior_sp=superior_sp,
            municipios_sp=MUNICIPIOS_SP,
        ),
        encoding="utf-8",
    )
    log(
        f"Concluído! Fisioterapia: {len(fisio)} | Nível Médio: {len(medio_todos)} | "
        f"Nível Superior (SP): {len(superior_sp)} | Brasil: {len(catalogo_brasil)}"
    )
    log(f"Página gerada: {HTML_FILE}")
    return 0



if __name__ == '__main__':
    sys.exit(main())
