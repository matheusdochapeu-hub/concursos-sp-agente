"""
Módulo de Renderização HTML/CSS/JS — Painel "Concursos"
"""
from __future__ import annotations

import html
import io
import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

BRT = timezone(timedelta(hours=-3))
DIAS_ALERTA_ENCERRAMENTO = 10

# Coordenadas aproximadas por UF (para cálculo de distância quando fora de SP)
UF_COORDS = {
    "SP": (-23.5505, -46.6333), "RJ": (-22.9068, -43.1729), "MG": (-19.9167, -43.9345),
    "ES": (-20.3155, -40.3128), "PR": (-25.4284, -49.2733), "SC": (-27.5954, -48.5480),
    "RS": (-30.0346, -51.2177), "DF": (-15.7975, -47.8919), "GO": (-16.6869, -49.2648),
    "MS": (-20.4697, -54.6201), "MT": (-15.6014, -56.0979), "BA": (-12.9714, -38.5014),
    "PE": (-8.0476, -34.8770), "CE": (-3.7172, -38.5433), "RN": (-5.7945, -35.2110),
    "PB": (-7.1195, -34.8450), "AL": (-9.6658, -35.7350), "SE": (-10.9472, -37.0731),
    "MA": (-2.5307, -44.3068), "PI": (-5.0892, -42.8016), "PA": (-1.4558, -48.4902),
    "AM": (-3.1190, -60.0217), "RO": (-8.7619, -63.9039), "TO": (-10.1753, -48.2982),
    "AC": (-9.9754, -67.8249), "AP": (0.0349, -51.0694), "RR": (2.8235, -60.6758),
    "BR": (-15.7975, -47.8919),
}


def e(s: Any) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def safe_url(u: Any) -> str:
    s = str(u or "").strip()
    if s.startswith(("https://", "http://")):
        return html.escape(s, quote=True)
    return "#"


def safe_json_for_script(obj: Any) -> str:
    return (
        json.dumps(obj, ensure_ascii=False)
        .replace("</", "<\\/")
        .replace("<!--", "<\\!--")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def brl(v: Optional[float]) -> str:
    if v is None:
        return "Consultar edital"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_qr_pix_svg(payload: str) -> str:
    try:
        import segno

        qr = segno.make(payload, error="m")
        buf = io.BytesIO()
        qr.save(buf, kind="svg", xmldecl=False, scale=4, border=2, dark="#143321", light="#ffffff")
        return buf.getvalue().decode("utf-8")
    except Exception:
        return '<div style="padding:24px;color:#143321;font-weight:700;">Use o botão abaixo para copiar a chave Pix</div>'


def data_iso_sort(data_br: str) -> str:
    matches = re.findall(r"(\d{2})/(\d{2})/(\d{4})", data_br or "")
    if matches:
        d_str, m_str, y_str = matches[-1]
        return f"{y_str}-{m_str}-{d_str}"
    return "9999-12-31"


def horas_num(carga: str) -> int:
    nums = [int(n) for n in re.findall(r"\b(\d+)\s*h", (carga or "").lower())]
    if not nums:
        nums = [int(n) for n in re.findall(r"\b(\d+)\s*hora", (carga or "").lower())]
    return min(nums) if nums else 40


def regime_categoria(regime: str) -> str:
    r = (regime or "").lower()
    if "estatut" in r and "clt" not in r:
        return "estatutario"
    if "clt" in r or "celetista" in r:
        return "clt"
    if "estatut" in r:
        return "estatutario"
    return "outros"


def faixa_salarial_slug(sal_bruto: Optional[float], sal_total: Optional[float] = None) -> str:
    ref = sal_total if (sal_total and sal_total > 5000) else sal_bruto
    if ref is None or ref <= 0:
        return "consultar"
    if ref <= 2500:
        return "ate2500"
    if ref <= 3500:
        return "2500a3500"
    if ref <= 5000:
        return "3500a5000"
    return "acima5000"


def niveis_tokens(niveis_str: str, esc_tipo: str = "") -> str:
    t = ((niveis_str or "") + " " + (esc_tipo or "")).lower()
    out = set()
    if "fundament" in t:
        out.add("fundamental")
    if "médio" in t or "medio" in t:
        out.add("medio")
    if "técnic" in t or "tecnic" in t or esc_tipo == "medio_tecnico":
        out.add("medio_tecnico")
        out.add("medio")
    if "superior" in t or esc_tipo == "superior":
        out.add("superior")
    if not out:
        out.update(["fundamental", "medio", "medio_tecnico", "superior"])
    return ",".join(sorted(out))


def inferir_plano_carreira(orgao: str, regime: str, beneficios: str, requisitos: str) -> str:
    o = (orgao or "").lower()
    r = (regime or "").lower()
    b = (beneficios or "").lower()
    req = (requisitos or "").lower()

    if "tjsp" in o or "tribunal de justiça" in o:
        return "Sim — Plano de Cargos e Carreiras do Judiciário Paulista (progressão anual por níveis/referências, adicional por tempo de serviço — quinquênio, sexta-parte e adicionais de qualificação universitária/pós-graduação)."
    if "unesp" in o or "unicamp" in o or "usp" in o:
        return "Sim — Carreira Técnico-Administrativa Universitária Paulista (progressão horizontal e vertical por mérito e titulação + quinquênio e sexta-parte)."
    if "marinha" in o or "militar" in r or "rm2" in r:
        return "Sim (Carreira Militar Temporária RM2 até 8 anos) — Progressão de Guarda-Marinha (R$ 9.575) para 2º Tenente (após 6 meses), 1º Tenente (após 1 ano) e Capitão-Tenente (no 7º ano)."
    if "residência" in r or "bolsa" in r:
        return "Não possui plano de carreira permanente — Programa de Residência Multiprofissional em Saúde com duração fixa de 2 anos (60h/sem) e certificação de título de especialista."
    if "câmara" in o or "camara" in o:
        extra = " + Gratificação por Formação no Ensino Superior" if "gratificação" in b or "formação" in req else ""
        return f"Sim — Plano de Carreira próprio do Poder Legislativo Municipal (progressão por letras/referências, quinquênio e estabilidade constitucional após estágio probatório{extra})."
    if "setec" in o or "prudenprev" in o or "fjpo" in o:
        extra = " + Prêmio de Produtividade de até 85%" if "produtividade" in b else ""
        return f"Sim — Carreira Autárquica/Fundacional Municipal Efetiva (progressão funcional no quadro de pessoal e adicionais por tempo de serviço{extra})."
    if "estatut" in r:
        return "Sim — Regime Estatutário Efetivo com Plano de Cargos, Carreiras e Vencimentos (PCCV) municipal, progressão funcional por tempo/mérito, quinquênio/anuênio e estabilidade após 3 anos."
    if "clt" in r or "celetista" in r:
        return "Parcial (Quadro Permanente CLT) — Reajustes anuais da categoria, recolhimento mensal de 8% de FGTS e progressão conforme plano de empregos públicos do órgão."
    if "seletivo" in r or "tempor" in r:
        return "Não possui plano de carreira permanente — Contratação por tempo determinado (Processo Seletivo Simplificado) sem progressão de carreira."
    return "Progressão conforme Estatuto / Plano de Cargos do órgão (consultar edital completo)."


def badge_escolaridade_html(esc_tipo: str, niveis_txt: str = "") -> str:
    if esc_tipo == "superior":
        return '<span class="esc-badge esc-sup">🎓 Ensino Superior + Conselho</span>'
    if esc_tipo == "medio_tecnico":
        return '<span class="esc-badge esc-tec">🛠️ Nível Médio / Curso Técnico</span>'
    if esc_tipo == "fundamental":
        return '<span class="esc-badge esc-fund">📘 Nível Fundamental</span>'
    if niveis_txt:
        return f'<span class="esc-badge esc-med">🎓 {e(niveis_txt)}</span>'
    return '<span class="esc-badge esc-med">📗 Exige Apenas Ensino Médio</span>'


# Regras: cargo -> formações aceitas (cargos de nível superior costumam admitir várias graduações)
_REGRAS_FORMACAO = [
    (r"auditor|fiscal\s+de\s+tributos|fiscal\s+tribut|fiscal\s+de\s+rendas|agente\s+fiscal|fiscal\s+fazend",
     ["Direito", "Ciências Contábeis", "Economia", "Administração"]),
    (r"controlador|controle\s+interno|auditoria",
     ["Direito", "Ciências Contábeis", "Economia", "Administração"]),
    (r"contador|cont[áa]bil", ["Ciências Contábeis"]),
    (r"economista", ["Ciências Econômicas"]),
    (r"administrador|analista\s+(administrativo|de\s+gest|de\s+recursos)|gestor",
     ["Administração", "Economia", "Ciências Contábeis", "Direito", "Gestão Pública"]),
    (r"analista\s+(de\s+)?(t\.?i\b|tecnologia|sistemas|inform)|desenvolvedor",
     ["Ciência da Computação", "Sistemas de Informação", "Engenharia da Computação", "Análise de Sistemas"]),
    (r"procurador|advogado|jur[ií]dic|assessor\s+jur", ["Direito (OAB)"]),
    (r"assistente\s+social", ["Serviço Social (CRESS)"]),
    (r"psic[oó]log", ["Psicologia (CRP)"]),
    (r"pedagog|coordenador\s+pedag|supervisor\s+(de\s+ensino|escolar)|diretor\s+de\s+escola",
     ["Pedagogia", "Licenciatura plena"]),
    (r"engenheir", ["Engenharia na área do cargo (CREA)"]),
    (r"arquitet", ["Arquitetura e Urbanismo (CAU)"]),
    (r"fisioterap", ["Fisioterapia (CREFITO)"]),
    (r"enfermeir", ["Enfermagem (COREN)"]),
    (r"m[eé]dico\s+veterin", ["Medicina Veterinária (CRMV)"]),
    (r"m[eé]dic", ["Medicina (CRM)"]),
    (r"farmac", ["Farmácia (CRF)"]),
    (r"nutricion", ["Nutrição (CRN)"]),
    (r"dentista|cirurgi[aã]o", ["Odontologia (CRO)"]),
    (r"professor|docente|\bpeb\b", ["Licenciatura na disciplina"]),
    (r"bibliotec", ["Biblioteconomia (CRB)"]),
    (r"jornalist|comunicador", ["Jornalismo", "Comunicação Social"]),
    (r"estat[ií]stic", ["Estatística", "Matemática"]),
]

# Termos que, ao serem buscados, também devem encontrar editais de cargos multidisciplinares
_TERMOS_EQUIV = {
    "Direito": ["advogado", "bacharel em direito", "direito"],
    "Ciências Contábeis": ["contador", "contabilidade", "ciencias contabeis"],
    "Economia": ["economista", "economia", "ciencias economicas"],
    "Ciências Econômicas": ["economista", "economia"],
    "Administração": ["administrador", "administracao"],
}


def inferir_formacoes_multidisciplinares(cargos, resumo: str = "", titulo: str = "") -> dict:
    """Detecta cargos que aceitam mais de uma graduação (ex.: Auditor Fiscal -> Direito, Contábeis, Economia)."""
    if isinstance(cargos, str):
        cargos = [cargos]
    texto = " ".join(list(cargos or []) + [resumo or "", titulo or ""]).lower()
    formacoes: List[str] = []
    for padrao, forms in _REGRAS_FORMACAO:
        if re.search(padrao, texto, re.I):
            for f_ in forms:
                if f_ not in formacoes:
                    formacoes.append(f_)
    termos: List[str] = []
    for f_ in formacoes:
        for t in _TERMOS_EQUIV.get(f_, []):
            if t not in termos:
                termos.append(t)
        base = re.sub(r"\s*\(.*?\)", "", f_).strip().lower()
        if base and base not in termos:
            termos.append(base)
    if len(formacoes) > 1:
        desc = "Aceita formações diversas: " + ", ".join(formacoes) + " (confirmar no edital)."
    elif formacoes:
        desc = "Formação: " + formacoes[0] + "."
    else:
        desc = ""
    return {"descricao": desc, "termos_busca": termos}


def inferir_requisitos_superior(nome: str, cargos=None) -> str:
    info = inferir_formacoes_multidisciplinares(cargos or [nome], nome, "")
    base = "Exige Ensino Superior completo (graduação reconhecida pelo MEC)."
    if info["descricao"]:
        base += " " + info["descricao"]
    base += " Verifique no edital registro em conselho de classe, experiência e demais exigências do cargo."
    return base


def render_card_sp(c: dict, modo: str, card_idx: int) -> str:
    if modo == "fisio":
        fd = c.get("fisio_detalhes") or {}
        cargo_titulo = fd.get("cargo") or "Fisioterapeuta"
        vagas_txt = fd.get("vagas") or "CR"
        vagas_im = fd.get("vagas_imediatas", 0)
        tem_cr = fd.get("tem_cr", True)
        sal_bruto = fd.get("salario_bruto") or fd.get("salario")
        sal_total = fd.get("salario_total") or sal_bruto
        sal_exib = brl(sal_bruto) if sal_bruto else (c.get("faixa_salarial") or "Consultar edital")
        sal_det = fd.get("salario_detalhe") or ""
        carga = fd.get("carga_horaria") or c.get("jornada_geral") or "Consultar edital"
        regime = fd.get("regime") or c.get("regime_geral") or "Consultar edital"
        beneficios = fd.get("beneficios") or c.get("beneficios_gerais") or "Consultar edital"
        esc_tipo = fd.get("escolaridade_tipo") or "superior"
        requisitos = fd.get("requisitos") or "Ensino Superior completo em Fisioterapia + Registro no CREFITO-3."
        topicos = fd.get("resumo_conteudo") or []
        icone_cargo = "🩺"
    else:
        if modo == "superior_sp":
            chave = "superior_itens"
        else:
            chave = "medio_confirmado" if modo == "medio5k" else "medio_outros"
        itens = c.get(chave) or [{}]
        prim = itens[0]
        cargo_titulo = " / ".join(x.get("nome", "") for x in itens if x.get("nome"))
        vagas_txt = prim.get("vagas") or "CR"
        vagas_im = sum(x.get("vagas_imediatas", 0) for x in itens)
        tem_cr = any(x.get("tem_cr", True) for x in itens)
        sals_brutos = [x.get("salario_bruto") or x.get("salario") for x in itens if (x.get("salario_bruto") or x.get("salario"))]
        sal_bruto = max(sals_brutos) if sals_brutos else c.get("salario_max")
        sal_total = prim.get("salario_total") or sal_bruto
        sal_exib = brl(sal_bruto) if sal_bruto else (c.get("faixa_salarial") or "Consultar edital")
        sal_det = prim.get("salario_detalhe") or ""
        carga = prim.get("carga_horaria") or c.get("jornada_geral") or "Consultar edital"
        regime = prim.get("regime") or c.get("regime_geral") or "Consultar edital"
        beneficios = prim.get("beneficios") or c.get("beneficios_gerais") or "Consultar edital"
        esc_tipo = prim.get("escolaridade_tipo") or "medio"
        requisitos = prim.get("requisitos") or "Exige Ensino Médio completo conforme especificações do Anexo I do edital."
        topicos = prim.get("resumo_conteudo") or []
        icone_cargo = "🎓" if modo == "superior_sp" else "💼"
        if modo == "superior_sp" and c.get("formacoes_aceitas") and c["formacoes_aceitas"] not in requisitos:
            requisitos = requisitos + " " + c["formacoes_aceitas"]

    cidade = c.get("cidade") or "São Paulo"
    lat = c.get("lat") if c.get("lat") is not None else -23.5505
    lon = c.get("lon") if c.get("lon") is not None else -46.6333
    sal_bruto_attr = sal_bruto if sal_bruto is not None else 0
    sal_total_attr = sal_total if sal_total is not None else sal_bruto_attr
    faixa_attr = faixa_salarial_slug(sal_bruto, sal_total)
    horas_attr = horas_num(carga)
    reg_cat = regime_categoria(regime)
    prova_sort = data_iso_sort(c.get("data_prova", ""))
    niveis_attr = niveis_tokens(c.get("niveis", ""), esc_tipo)
    orgao_nome = c.get("orgao") or c.get("titulo") or "Órgão Concursal"
    carreira_txt = inferir_plano_carreira(orgao_nome, regime, beneficios, requisitos)

    st_insc = c.get("inscricao_status") or {}
    insc_sort = st_insc.get("data_fim_iso", "9999-12-31")
    encerrando_bool = bool(st_insc.get("encerrando"))
    dias_rest = st_insc.get("dias_restantes", 999)
    aviso_insc = st_insc.get("aviso_texto", "")

    badges_topo = ""
    if encerrando_bool:
        badges_topo += f'<span class="badge-encerrando">{e(aviso_insc)}</span>'
    if c.get("novo"):
        badges_topo += '<span class="badge-novo">✨ CONCURSO NOVO · 24h</span>'

    chips_dist = f'<span class="chip-loc">📍 {e(cidade)}/SP</span>'
    chips_dist += '<span class="chip-dist chip-km-ref" hidden></span>'

    banca_nome = c.get("banca") or "Consultar edital"
    links_provas = c.get("links_provas_map", {}).get(modo) or {
        "url_combo": "https://www.pciconcursos.com.br/provas/",
        "label_combo": "Provas Anteriores",
    }

    arqs_str = " • ".join(c.get("arquivos_edital") or ["Edital Completo"])
    isencao_txt = c.get("isencao") or "Consultar edital para taxa e requisitos de isenção."
    card_uid = f"sp-{modo}-{card_idx}"

    botoes = (
        f'<a class="btn-link primario" href="{safe_url(c.get("link_edital"))}" target="_blank" rel="noopener noreferrer" '
        f'title="{e(arqs_str)}">📄 Edital &amp; Anexos</a>'
    )
    if c.get("site_banca") and safe_url(c["site_banca"]) != "#":
        botoes += (
            f'<a class="btn-link" href="{safe_url(c["site_banca"])}" target="_blank" rel="noopener noreferrer">'
            f'🌐 Banca ({e(banca_nome)})</a>'
        )
    botoes += (
        f'<a class="btn-link btn-provas" href="{safe_url(links_provas["url_combo"])}" target="_blank" rel="noopener noreferrer" '
        f'title="Provas anteriores por Cargo e Banca ({e(links_provas["label_combo"])})">'
        f'📝 Provas ({e(links_provas["label_combo"])})</a>'
        f'<button type="button" class="btn-link btn-share-card" data-share-uid="{card_uid}">📤 Compartilhar</button>'
        f'<button type="button" class="btn-add-compare" data-compare-uid="{card_uid}">➕ Adicionar para comparar</button>'
    )

    lista_topicos = "".join(f"<li>{e(t)}</li>" for t in topicos)
    label_prog = (
        "📚 Ver Resumo do Conteúdo Programático (Fisioterapeuta)"
        if modo == "fisio"
        else "📚 Ver Resumo do Conteúdo Programático do Edital"
    )
    classe_prazo = "info-box destaque-prazo prazo-urgente" if encerrando_bool else "info-box destaque-prazo"
    sub_prazo = aviso_insc if aviso_insc else (c.get("vagas_salario") or "")

    return f"""
    <article class="card{' card-urgente' if encerrando_bool else ''}"
      id="{card_uid}"
      data-uid="{card_uid}"
      data-idx="{card_idx}"
      data-orgao="{e(c.get('orgao') or c.get('titulo') or '')}"
      data-titulo="{e(c.get('titulo') or c.get('orgao') or '')}"
      data-url="{safe_url(c.get('url', ''))}"
      data-link-edital="{safe_url(c.get('link_edital'))}"
      data-cargo="{e(cargo_titulo)}"
      data-vagas-txt="{e(vagas_txt)}"
      data-cidade="{e(cidade)}"
      data-uf="SP"
      data-lat="{lat}"
      data-lon="{lon}"
      data-salario="{sal_bruto_attr}"
      data-salario-total="{sal_total_attr}"
      data-salario-exib="{e(sal_exib)}"
      data-salario-det="{e(sal_det)}"
      data-beneficios="{e(beneficios)}"
      data-regime-txt="{e(regime)}"
      data-carreira="{e(carreira_txt)}"
      data-jornada-txt="{e(carga)}"
      data-data-prova-txt="{e(c.get('data_prova') or 'Consultar edital')}"
      data-banca-txt="{e(banca_nome)}"
      data-inscricao-txt="{e(c.get('inscricao_ate') or 'Consultar edital')}"
      data-isencao-txt="{e(isencao_txt)}"
      data-requisitos-txt="{e(requisitos)}"
      data-faixa="{faixa_attr}"
      data-escolaridade="{esc_tipo}"
      data-niveis-lista="{niveis_attr}"
      data-vagas="{vagas_im}"
      data-tem-cr="{1 if tem_cr else 0}"
      data-regime="{reg_cat}"
      data-horas="{horas_attr}"
      data-prova="{prova_sort}"
      data-inscricao="{insc_sort}"
      data-dias-restantes="{dias_rest}"
      data-encerrando="{1 if encerrando_bool else 0}"
      data-novo="{1 if c.get('novo') else 0}"
      data-first-seen-ts="{e(c.get('first_seen_ts'))}"
      data-formacoes="{e(' '.join(c.get('termos_formacao') or []))}"
      data-is-baseline="{1 if c.get('is_baseline') else 0}">
      <header class="card-head">
        <div class="head-top">
          <h3><a href="{safe_url(c.get('url', ''))}" target="_blank" rel="noopener noreferrer">{e(c.get('orgao') or c.get('titulo') or 'Concurso')}</a></h3>
          <div class="badges-col">{badges_topo}</div>
        </div>
        <div class="loc-row">
          {chips_dist}
          {badge_escolaridade_html(esc_tipo)}
        </div>
        <p class="titulo">{e(c.get('titulo') or c.get('orgao') or '')}</p>
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
          <span class="lbl">💰 Remuneração do Cargo (Bruto)</span>
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
          <small class="sub">Banca: {e(banca_nome)}</small>
        </div>
        <div class="{classe_prazo}">
          <span class="lbl">⏰ Inscrições até</span>
          <strong class="val-sm">{e(c.get('inscricao_ate') or 'Consultar edital')}</strong>
          <small class="sub sub-prazo-status">{e(sub_prazo)}</small>
        </div>
      </div>

      <div class="isencao-box">
        <div class="isencao-title">🎟️ Taxa de Inscrição &amp; Isenção</div>
        <p class="isencao-text">{e(isencao_txt)}</p>
      </div>

      <div class="links-row">{botoes}</div>

      <details class="prog-box">
        <summary>{label_prog}</summary>
        <div class="prog-body">
          <p class="prog-arq">📑 <b>Documentos e Anexos:</b> {e(arqs_str)}</p>
          <p class="prog-arq">📈 <b>Plano de Carreira:</b> {e(carreira_txt)}</p>
          <ul>{lista_topicos}</ul>
          <a class="prog-cta" href="{safe_url(c.get('link_edital'))}" target="_blank" rel="noopener noreferrer">
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
    corpo = "".join(render_card_sp(c, modo, idx) for idx, c in enumerate(itens, 1))
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
      Nenhum concurso encontrado com os filtros selecionados. Clique em "Limpar Filtros" acima para ver todos.
    </p>
  </section>"""


# Lista expandida com 75 Cargos Rápidos para a Aba de Busca Nacional
CARGOS_RAPIDOS_MAX = [
    # Saúde
    "Fisioterapeuta", "Enfermeiro", "Técnico de Enfermagem", "Auxiliar de Enfermagem",
    "Farmacêutico", "Psicólogo", "Nutricionista", "Dentista", "Cirurgião-Dentista",
    "Terapeuta Ocupacional", "Fonoaudiólogo", "Biomédico", "Assistente Social",
    "Médico", "Médico Veterinário", "Educador Físico", "Técnico em Radiologia",
    "Técnico em Farmácia", "Técnico em Laboratório", "Auxiliar em Saúde Bucal",
    "Agente Comunitário de Saúde", "Agente de Combate às Endemias", "Cuidador",
    # Administrativo, Legislativo e Judiciário
    "Agente Administrativo", "Assistente Administrativo", "Auxiliar Administrativo",
    "Escriturário", "Oficial Administrativo", "Escrevente Técnico Judiciário",
    "Oficial de Justiça", "Analista Administrativo", "Oficial Legislativo",
    "Apoio Administrativo", "Recepcionista", "Almoxarife", "Telefonista",
    "Secretário Escolar", "Arquivista", "Assistente de Suporte Acadêmico",
    # Fiscal, Contábil e Jurídico
    "Fiscal", "Agente de Fiscalização", "Fiscal Tributário", "Fiscal de Obras",
    "Fiscal de Posturas", "Fiscal Ambiental", "Fiscal Sanitário", "Contador",
    "Técnico em Contabilidade", "Tesoureiro", "Controlador Interno",
    "Procurador", "Advogado", "Auditor Fiscal",
    # Educação e Social
    "Professor", "Pedagogo", "Coordenador Pedagógico", "Diretor de Escola",
    "Inspetor de Alunos", "Monitor Escolar", "Monitor de Transporte Escolar",
    "Auxiliar de Desenvolvimento Infantil", "Profissional de Apoio Escolar",
    "Orientador Social",
    # Engenharia, TI e Técnico
    "Engenheiro Civil", "Engenheiro Ambiental", "Engenheiro Agrônomo",
    "Engenheiro Eletricista", "Arquiteto", "Analista de TI",
    "Técnico em Informática", "Técnico em Segurança do Trabalho",
    "Técnico em Edificações", "Técnico Agrícola", "Topógrafo", "Desenhista",
    # Segurança e Operacional
    "Guarda Municipal", "Agente de Trânsito", "Motorista", "Operador de Máquinas",
    "Eletricista", "Mecânico", "Vigia", "Auxiliar de Serviços Gerais",
    "Cozinheiro", "Merendeira",
]


# Google OAuth Client ID (público, não é segredo). Cole aqui o seu ID ou defina a variável de
# ambiente GOOGLE_CLIENT_ID antes de rodar o agente. Formato: 123456789-abc.apps.googleusercontent.com
import os as _os

GOOGLE_CLIENT_ID = (
    _os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    or "1006150921481-phsaf0s3j0ie65d69j3l1uth3b895148.apps.googleusercontent.com"
)

# Webhook centralizado da Planilha Google (Apps Script) para contabilizar acessos e logins de terceiros em tempo real
AUDIT_WEBHOOK_URL = (
    _os.environ.get("AUDIT_WEBHOOK_URL", "").strip()
    or "https://script.google.com/macros/s/AKfycby4DRby4jG-nE9V9c4IGcFgpI14U7Jc76eQy0fQww-ME0AJDCOq9bGcmhxN-0ETnYtJbw/exec"
)

# Capitais usadas como cidade de referência: (nome, UF, lat, lon)
CAPITAIS_REF = [
    ("Rio Branco", "AC", -9.9747, -67.8243), ("Maceió", "AL", -9.6658, -35.7353),
    ("Macapá", "AP", 0.0349, -51.0694), ("Manaus", "AM", -3.1190, -60.0217),
    ("Salvador", "BA", -12.9714, -38.5014), ("Fortaleza", "CE", -3.7319, -38.5267),
    ("Brasília", "DF", -15.7939, -47.8828), ("Vitória", "ES", -20.3155, -40.3128),
    ("Goiânia", "GO", -16.6869, -49.2648), ("São Luís", "MA", -2.5307, -44.3068),
    ("Cuiabá", "MT", -15.6014, -56.0979), ("Campo Grande", "MS", -20.4697, -54.6201),
    ("Belo Horizonte", "MG", -19.9167, -43.9345), ("Belém", "PA", -1.4558, -48.5044),
    ("João Pessoa", "PB", -7.1195, -34.8450), ("Curitiba", "PR", -25.4284, -49.2733),
    ("Recife", "PE", -8.0476, -34.8770), ("Teresina", "PI", -5.0892, -42.8019),
    ("Rio de Janeiro", "RJ", -22.9068, -43.1729), ("Natal", "RN", -5.7945, -35.2110),
    ("Porto Alegre", "RS", -30.0346, -51.2177), ("Porto Velho", "RO", -8.7612, -63.9004),
    ("Boa Vista", "RR", 2.8235, -60.6758), ("Florianópolis", "SC", -27.5954, -48.5480),
    ("Aracaju", "SE", -10.9472, -37.0731), ("Palmas", "TO", -10.1844, -48.3336),
]


def render_html(
    fisio: List[dict],
    medio_ok: List[dict],
    medio_todos: List[dict],
    catalogo_brasil: List[dict],
    catalogo_provas_banca_cargo: List[dict],
    total_sp: int,
    gerado_em: str,
    listing_url: str,
    pix_key: str,
    superior_sp: Optional[List[dict]] = None,
    municipios_sp: Optional[dict] = None,
) -> str:
    superior_sp = superior_sp or []
    cidades_set = sorted({c.get("cidade") for c in (fisio + medio_todos + superior_sp) if c.get("cidade")})
    botoes_cidades = (
        '<button type="button" class="pill-btn ativo" data-filter="cidade" data-val="">Todas as Cidades</button>'
        + "".join(
            f'<button type="button" class="pill-btn" data-filter="cidade" data-val="{e(cid)}">{e(cid)}</button>'
            for cid in cidades_set
        )
    )

    urls_unicas = {}
    for c in fisio + medio_todos + superior_sp:
        u_key = c.get("url") or c.get("titulo") or ""
        if u_key:
            urls_unicas[u_key] = c
    novos_count = sum(1 for c in urls_unicas.values() if c.get("novo"))
    encerrando_count = sum(1 for c in urls_unicas.values() if (c.get("inscricao_status") or {}).get("encerrando"))

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

    bancas_provas_lista = [
        "VUNESP", "IBAM", "Avança", "INDEPAC", "CONSCAM", "CONSESP", "FAFIPA",
        "Instituto Mais", "Avalia", "Unique", "INDEC", "IGECS", "Aplicativa",
        "ACCESS", "GL Consultoria", "Império", "Marinha", "UNESP", "FGV", "Cebraspe", "FCC", "IBFC",
    ]
    botoes_bancas_provas = (
        '<button type="button" class="pill-btn prova-banca-btn ativo" data-banca="">Todas as Bancas</button>'
        + "".join(
            f'<button type="button" class="pill-btn prova-banca-btn" data-banca="{e(b)}">{e(b)}</button>'
            for b in bancas_provas_lista
        )
    )

    cargos_provas_lista = [
        "Fisioterapeuta", "Escrevente Técnico Judiciário", "Agente Administrativo",
        "Assistente Administrativo", "Auxiliar Administrativo", "Escriturário",
        "Oficial Administrativo", "Oficial Legislativo", "Agente de Fiscalização",
        "Fiscal", "Técnico de Enfermagem", "Auxiliar de Enfermagem",
        "Técnico em Segurança do Trabalho", "Guarda Municipal", "Almoxarife",
        "Agente Comunitário de Saúde", "Monitor", "Assistente de Suporte Acadêmico",
    ]
    botoes_cargos_provas = (
        '<button type="button" class="pill-btn prova-cargo-btn ativo" data-cargo="">Todos os Cargos</button>'
        + "".join(
            f'<button type="button" class="pill-btn prova-cargo-btn" data-cargo="{e(cg)}">{e(cg)}</button>'
            for cg in cargos_provas_lista
        )
    )

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

    botoes_cargos_rapidos = (
        '<button type="button" class="pill-btn cargo-quick ativo" data-cargo="">Mostrar Todos os Cargos</button>'
        + "".join(
            f'<button type="button" class="pill-btn cargo-quick" data-cargo="{e(cg)}">{e(cg)}</button>'
            for cg in CARGOS_RAPIDOS_MAX
        )
    )

    # Cidades para o campo "Minha cidade de referência" (SP + capitais) -> [nome, UF, lat, lon]
    cidades_ref = []
    for _k, _m in (municipios_sp or {}).items():
        if _m.get("lat") is not None and _m.get("lon") is not None:
            cidades_ref.append([_m.get("nome") or _k.title(), "SP", _m["lat"], _m["lon"]])
    for _nome, _uf, _la, _lo in CAPITAIS_REF:
        if not any(x[0] == _nome and x[1] == _uf for x in cidades_ref):
            cidades_ref.append([_nome, _uf, _la, _lo])
    cidades_ref.sort(key=lambda x: (x[0].lower(), x[1]))
    cidades_ref_json = safe_json_for_script(cidades_ref)
    opcoes_cidades_ref = "".join(f'<option value="{e(x[0])} - {x[1]}"></option>' for x in cidades_ref)

    qr_svg = gerar_qr_pix_svg(pix_key)
    catalogo_json = safe_json_for_script(catalogo_brasil)
    provas_json = safe_json_for_script(catalogo_provas_banca_cargo)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<meta name="referrer" content="strict-origin-when-cross-origin">
<meta http-equiv="X-Content-Type-Options" content="nosniff">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' https://accounts.google.com https://apis.google.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://accounts.google.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://script.google.com https://script.googleusercontent.com https://api.counterapi.dev https://accounts.google.com https://*.google.com https://www.googleapis.com https://oauth2.googleapis.com https://*.googleapis.com; frame-src https://accounts.google.com https://*.google.com;">
<meta name="theme-color" content="#006b2d">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Concursos">
<meta name="description" content="Concursos — Painel diário de editais no Brasil e SP, Fisioterapia, Nível Médio/Técnico, Comparador de Concursos e Provas Anteriores por Banca e Cargo.">
<link rel="manifest" href="./manifest.webmanifest">
<link rel="icon" type="image/png" sizes="192x192" href="./icon-192.png">
<link rel="apple-touch-icon" href="./icon-192.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&amp;family=Plus+Jakarta+Sans:wght@400;500;600;700;800&amp;display=swap" rel="stylesheet">
<script src="https://accounts.google.com/gsi/client" async defer></script>
<title>Concursos</title>
<style>
  :root {{
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
    --urgente-bg: #fff1f2;
    --urgente-border: #fda4af;
    --urgente-txt: #be123c;
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

  *, *::before, *::after {{ box-sizing: border-box; }}
  html {{
    width: 100%;
    max-width: 100%;
    overflow-x: hidden;
    -webkit-text-size-adjust: 100%;
  }}
  body {{
    width: 100%;
    max-width: 100%;
    overflow-x: hidden;
    position: relative;
    margin: 0;
    padding: 0;
    font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--txt);
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }}
  .container {{
    width: 100%;
    max-width: 1340px;
    margin: 0 auto;
    padding: 0 16px;
    box-sizing: border-box;
  }}

  header.app-bar {{
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
    overflow: hidden;
    background: linear-gradient(135deg, var(--br-blue-dark) 0%, var(--br-blue) 42%, var(--br-green-dark) 100%);
    color: #ffffff;
    padding: 22px 0 20px;
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
    margin-bottom: 6px;
  }}
  h1 {{
    margin: 0 0 6px;
    font-family: 'Fraunces', Georgia, serif;
    font-size: 2.15rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: #ffffff;
  }}
  .meta {{ color: rgba(255, 255, 255, 0.88); font-size: 0.9rem; }}
  .meta a {{ color: var(--br-yellow); font-weight: 600; text-decoration: none; }}
  .meta a:hover {{ text-decoration: underline; }}

  .header-actions-col {{
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
    min-width: 215px;
  }}
  .btn-app-install {{
    background: var(--br-yellow);
    color: var(--br-blue-dark);
    border: 2px solid #ffffff;
    min-height: 42px;
    padding: 9px 20px;
    border-radius: 999px;
    font-weight: 800;
    font-size: 0.9rem;
    font-family: inherit;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.22);
    transition: transform 0.15s, box-shadow 0.15s;
  }}
  .btn-app-install:hover {{ transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0, 0, 0, 0.28); }}
  .btn-header-pix {{
    background: #286e34;
    color: #ffffff;
    border: 2px solid rgba(255, 255, 255, 0.85);
    min-height: 40px;
    padding: 8px 20px;
    border-radius: 999px;
    font-weight: 800;
    font-size: 0.88rem;
    font-family: inherit;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.2);
    transition: transform 0.15s, background 0.15s;
  }}
  .btn-header-pix:hover {{ background: #1f5829; transform: translateY(-2px); }}

  /* Abas e Botão "Função comparar" */
  .tabs-wrap {{
    width: 100%;
    max-width: 100%;
    overflow: hidden;
    margin: 22px 0 18px;
    box-sizing: border-box;
  }}
  nav.tabs {{
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(225px, 1fr));
    gap: 12px;
    align-items: stretch;
  }}
  .tab-item {{ display: flex; align-items: stretch; gap: 8px; }}
  .tab-btn {{
    flex: 1;
    background: var(--surface);
    color: var(--txt);
    border: 2px solid var(--border);
    padding: 12px 14px;
    border-radius: 14px;
    cursor: pointer;
    font-family: inherit;
    font-size: 0.91rem;
    font-weight: 700;
    text-align: left;
    display: flex;
    align-items: center;
    gap: 8px;
    box-shadow: var(--shadow-sm);
    transition: all 0.16s ease;
  }}
  .tab-btn:hover {{ border-color: var(--br-green); background: var(--br-green-soft); }}
  .tab-item.ativo .tab-btn {{
    background: var(--br-green);
    color: #ffffff;
    border-color: var(--br-green-dark);
    box-shadow: 0 6px 18px rgba(0, 151, 57, 0.25);
  }}
  .tab-count-box {{
    min-width: 70px;
    background: var(--br-blue-soft);
    border: 2px solid var(--br-blue-border);
    color: var(--br-blue);
    border-radius: 14px;
    padding: 6px 9px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    box-shadow: var(--shadow-sm);
  }}
  .tab-count-box b {{ font-size: 1.12rem; line-height: 1.1; font-weight: 800; }}
  .tab-count-box small {{ font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.04em; font-weight: 700; }}
  .tab-item.ativo .tab-count-box {{
    background: var(--br-yellow);
    border-color: #eab308;
    color: var(--br-blue-dark);
    box-shadow: 0 6px 18px rgba(254, 221, 0, 0.35);
  }}

  /* Backdrop da Barra Lateral */
  .sidebar-backdrop {{
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.55);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    z-index: 998;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.28s ease, visibility 0.28s ease;
  }}
  .sidebar-backdrop.aberto {{
    opacity: 1;
    visibility: visible;
  }}

  /* Barra Lateral de Filtros (Drawer Off-Canvas - Mobile e Desktop) */
  .sidebar-filtros {{
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(520px, 94vw);
    height: 100vh;
    max-height: 100vh;
    background: #ffffff;
    box-shadow: -10px 0 38px rgba(0, 0, 0, 0.28);
    z-index: 999;
    display: flex;
    flex-direction: column;
    transform: translateX(105%);
    transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    box-sizing: border-box;
    overflow: hidden;
  }}
  .sidebar-filtros.aberto {{
    transform: translateX(0);
  }}
  .sidebar-filtros-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    background: linear-gradient(135deg, var(--br-blue-dark), var(--br-blue));
    color: #ffffff;
    border-bottom: 3px solid var(--br-yellow);
    flex-shrink: 0;
  }}
  .sidebar-head-info h3 {{
    margin: 0;
    font-size: 1.15rem;
    font-weight: 800;
    display: flex;
    align-items: center;
    gap: 8px;
    color: #ffffff;
  }}
  .sidebar-head-info p {{
    margin: 4px 0 0;
    font-size: 0.82rem;
    color: rgba(255, 255, 255, 0.88);
  }}
  .sidebar-close-btn {{
    background: rgba(255, 255, 255, 0.16);
    color: #ffffff;
    border: 1.5px solid rgba(255, 255, 255, 0.4);
    width: 38px;
    height: 38px;
    border-radius: 50%;
    cursor: pointer;
    font-size: 1.15rem;
    display: flex;
    align-items: center;
    justify-content: center;
    line-height: 1;
    transition: all 0.15s;
  }}
  .sidebar-close-btn:hover {{
    background: rgba(255, 255, 255, 0.32);
    transform: scale(1.06);
  }}
  .sidebar-filtros-body {{
    flex: 1;
    overflow-y: auto;
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    -webkit-overflow-scrolling: touch;
  }}
  .sidebar-filtros .f-group {{
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
    padding: 12px 14px;
    background: var(--surface-alt);
    border-radius: 12px;
    border: 1px solid #e3eee7;
  }}
  .sidebar-filtros-foot {{
    display: flex;
    gap: 10px;
    padding: 14px 18px;
    background: #ffffff;
    border-top: 2px solid var(--border);
    box-shadow: 0 -6px 20px rgba(0, 0, 0, 0.07);
    flex-shrink: 0;
  }}
  .sidebar-filtros-foot .btn-limpar {{
    flex: 1;
    min-height: 44px;
    font-weight: 800;
  }}
  .sidebar-filtros-foot .btn-aplicar {{
    flex: 2;
    min-height: 44px;
    font-weight: 800;
    font-size: 0.95rem;
  }}

  /* Barra de Controle Compacta e Limpa no Topo */
  .main-control-bar {{
    background: var(--surface);
    border: 2px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 12px 16px;
    margin-bottom: 18px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    box-shadow: var(--shadow-sm);
  }}
  .toolbar-busca-cargo {{
    flex: 1;
    min-width: 260px;
    position: relative;
  }}
  .toolbar-busca-cargo input {{
    width: 100%;
    height: 42px;
    padding: 8px 36px 8px 16px;
    border-radius: 999px;
    border: 2px solid var(--br-blue-border);
    background: var(--surface-alt);
    font-family: inherit;
    font-size: 0.92rem;
    font-weight: 600;
    color: var(--txt);
    box-sizing: border-box;
    transition: all 0.15s;
  }}
  .toolbar-busca-cargo input:focus {{
    outline: none;
    border-color: var(--br-green);
    background: #ffffff;
    box-shadow: 0 0 0 3px rgba(0, 151, 57, 0.14);
  }}
  .toolbar-busca-cargo .btn-clear-inline {{
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    color: var(--muted);
    font-size: 1.05rem;
    cursor: pointer;
    padding: 2px 6px;
    line-height: 1;
  }}
  .toolbar-left-actions {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }}
  .toolbar-actions {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }}
  .btn-abrir-sidebar {{
    background: var(--br-green);
    color: #ffffff;
    border: 2px solid var(--br-green-dark);
    min-height: 42px;
    padding: 8px 18px;
    border-radius: 999px;
    cursor: pointer;
    font-family: inherit;
    font-weight: 800;
    font-size: 0.92rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    box-shadow: 0 3px 12px rgba(0, 151, 57, 0.25);
    transition: all 0.15s ease;
  }}
  .btn-abrir-sidebar:hover {{
    background: var(--br-green-dark);
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(0, 151, 57, 0.35);
  }}
  .badge-filtros-cnt {{
    background: var(--br-yellow);
    color: var(--br-blue-dark);
    font-size: 0.76rem;
    font-weight: 900;
    padding: 2px 7px;
    border-radius: 999px;
    line-height: 1.2;
    border: 1px solid #ca8a04;
  }}

  /* Barra de Chips Ativos */
  .active-filters-bar {{
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    padding: 10px 14px;
    margin-bottom: 18px;
    background: var(--surface-alt);
    border: 1.5px dashed var(--br-green-border);
    border-radius: 12px;
    font-size: 0.82rem;
  }}
  .af-label {{
    font-weight: 800;
    color: var(--br-green-dark);
    text-transform: uppercase;
    font-size: 0.72rem;
  }}
  .af-chips {{
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }}
  .af-chip {{
    background: #ffffff;
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 4px 11px;
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--txt);
    display: inline-flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
    transition: all 0.14s;
  }}
  .af-chip:hover {{
    border-color: #ef4444;
    color: #b91c1c;
    background: #fef2f2;
  }}
  .af-btn-clear {{
    background: none;
    border: none;
    color: var(--br-blue);
    font-weight: 800;
    font-size: 0.8rem;
    cursor: pointer;
    text-decoration: underline;
    margin-left: auto;
  }}

  /* Botão Flutuante (FAB) */
  .btn-fab-filtros {{
    position: fixed;
    top: 14px;
    left: 14px;
    bottom: auto !important;
    right: auto !important;
    background: var(--br-blue);
    color: #ffffff;
    border: 2px solid #ffffff;
    padding: 8px 16px;
    border-radius: 999px;
    box-shadow: 0 4px 18px rgba(0, 39, 118, 0.45);
    z-index: 920;
    font-family: inherit;
    font-size: 0.88rem;
    font-weight: 800;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    transition: all 0.18s ease;
  }}
  .btn-fab-filtros:hover {{
    background: var(--br-blue-dark);
    transform: translateY(-2px) scale(1.03);
    box-shadow: 0 8px 24px rgba(0, 39, 118, 0.55);
  }}
  .btn-comparar-toggle {{
    background: var(--br-yellow);
    color: var(--br-blue-dark);
    border: 2px solid #eab308;
    min-height: 38px;
    padding: 7px 16px;
    border-radius: 999px;
    cursor: pointer;
    font-family: inherit;
    font-weight: 800;
    font-size: 0.85rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    box-shadow: 0 3px 10px rgba(254, 221, 0, 0.3);
    transition: all 0.15s;
  }}
  .btn-comparar-toggle:hover {{ transform: translateY(-1px); background: #fde047; }}
  .btn-comparar-toggle.ativo {{
    background: var(--br-blue);
    color: #ffffff;
    border-color: var(--br-blue-dark);
    box-shadow: 0 4px 14px rgba(0, 39, 118, 0.35);
  }}
  .btn-aplicar {{
    background: var(--br-green);
    color: #ffffff;
    border: 1.5px solid var(--br-green-dark);
    min-height: 38px;
    padding: 7px 17px;
    border-radius: 999px;
    cursor: pointer;
    font-family: inherit;
    font-weight: 800;
    font-size: 0.85rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    box-shadow: 0 3px 10px rgba(0, 151, 57, 0.22);
    transition: all 0.15s;
  }}
  .btn-aplicar:hover {{ background: var(--br-green-dark); transform: translateY(-1px); }}
  .btn-limpar, .btn-recolher {{
    background: var(--surface-alt);
    color: var(--br-blue);
    border: 1.5px solid var(--br-blue-border);
    min-height: 38px;
    padding: 7px 15px;
    border-radius: 999px;
    cursor: pointer;
    font-family: inherit;
    font-weight: 700;
    font-size: 0.84rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    transition: all 0.15s;
  }}
  .btn-limpar:hover, .btn-recolher:hover {{ background: var(--br-blue); color: #ffffff; }}

  .filter-groups {{ display: flex; flex-direction: column; gap: 10px; }}
  .f-group {{
    display: grid;
    grid-template-columns: 230px 1fr;
    align-items: center;
    gap: 14px;
    padding: 10px 14px;
    background: var(--surface-alt);
    border-radius: 12px;
    border: 1px solid #e3eee7;
  }}
  @media (max-width: 780px) {{
    .f-group {{ grid-template-columns: 1fr; align-items: flex-start; gap: 8px; }}
  }}
  .f-label {{
    font-size: 0.8rem;
    font-weight: 800;
    color: var(--br-green-dark);
    text-transform: uppercase;
    letter-spacing: 0.03em;
    line-height: 1.3;
  }}
  .pill-row {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }}
  .pill-row.recolhido {{ display: none !important; }}
  .toast-filtro {{
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%) translateY(20px);
    background: #0f172a;
    color: #ffffff;
    padding: 10px 20px;
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 600;
    box-shadow: 0 10px 25px rgba(0,0,0,0.25);
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.25s ease, transform 0.25s ease;
    z-index: 10001;
  }}
  .toast-filtro.visivel {{
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }}
  .pill-btn {{
    background: #ffffff;
    color: var(--txt);
    border: 1.5px solid var(--border);
    min-height: 35px;
    padding: 6px 14px;
    border-radius: 999px;
    font-family: inherit;
    font-size: 0.82rem;
    font-weight: 600;
    line-height: 1.2;
    cursor: pointer;
    transition: all 0.14s ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
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
  .pill-btn.pill-urgente {{
    border-color: var(--urgente-border);
    background: var(--urgente-bg);
    color: var(--urgente-txt);
    font-weight: 700;
  }}
  .pill-btn.pill-urgente.ativo {{
    background: var(--urgente-txt);
    color: #ffffff;
    border-color: #881337;
  }}
  .pill-btn.pill-gold.ativo {{
    background: var(--br-green);
    color: #ffffff;
    border-color: var(--br-green-dark);
  }}
  .mini-cnt {{
    background: rgba(0, 39, 118, 0.1);
    color: inherit;
    padding: 2px 7px;
    border-radius: 999px;
    font-size: 0.73rem;
    font-weight: 800;
  }}
  .pill-btn.ativo .mini-cnt {{
    background: var(--br-yellow);
    color: var(--br-blue-dark);
  }}
  .pill-btn.sem-resultados, .uf-btn.sem-resultados, .cargo-quick.sem-resultados {{
    opacity: 0.42 !important;
  }}

  .filtros-foot {{
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 10px;
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px dashed var(--border);
  }}
  .feedback-filtro {{
    font-size: 0.82rem;
    font-weight: 700;
    color: var(--br-green-dark);
    opacity: 0;
    transition: opacity 0.2s;
  }}
  .feedback-filtro.visivel {{ opacity: 1; }}

  .faixa-highlight-bar {{
    background: var(--br-yellow-soft);
    border: 2px solid var(--br-yellow-border);
    border-radius: 14px;
    padding: 14px 18px;
    margin-bottom: 18px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .faixa-bar-lbl {{ font-size: 0.88rem; font-weight: 800; color: var(--br-blue-dark); }}

  main {{ padding-bottom: 90px; }}
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
  .count-box-lg span {{ font-size: 0.78rem; font-weight: 700; text-transform: uppercase; color: var(--br-yellow); }}
  .desc {{ color: var(--muted); margin: 0 0 14px; font-size: 0.94rem; }}

  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 20px;
    align-items: stretch;
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
  }}
  @media (max-width: 680px) {{ .grid {{ grid-template-columns: 1fr !important; }} }}

  .card {{
    background: var(--surface);
    border-radius: var(--radius-lg);
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 13px;
    border: 2px solid var(--border);
    border-top: 5px solid var(--br-green);
    box-shadow: var(--shadow-sm);
    transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
    position: relative;
  }}
  .card.card-urgente {{ border-top-color: #e11d48; }}
  .card:hover {{ transform: translateY(-2px); box-shadow: var(--shadow-md); border-color: var(--br-green-border); }}

  /* Estilo quando a Função Comparar está ativa */
  body.modo-comparar .card {{
    cursor: pointer;
    border-style: dashed;
    border-color: var(--br-blue);
  }}
  body.modo-comparar .card:hover {{
    background: #f9fcfa;
    border-color: var(--br-green);
  }}
  .card.selecionado-comparar {{
    border: 3px solid var(--br-green) !important;
    box-shadow: 0 0 0 4px rgba(254, 221, 0, 0.55), var(--shadow-md) !important;
    background: #f4fbf6 !important;
  }}
  .btn-add-compare {{
    display: none;
    background: var(--br-yellow);
    color: var(--br-blue-dark);
    border: 2px solid #eab308;
    min-height: 36px;
    padding: 7px 14px;
    border-radius: 10px;
    font-family: inherit;
    font-size: 0.82rem;
    font-weight: 800;
    cursor: pointer;
    align-items: center;
    justify-content: center;
    gap: 6px;
    transition: all 0.15s;
  }}
  body.modo-comparar .btn-add-compare {{
    display: inline-flex;
  }}
  .card.selecionado-comparar .btn-add-compare {{
    background: var(--br-green);
    color: #ffffff;
    border-color: var(--br-green-dark);
  }}

  .head-top {{
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
    width: 100%;
  }}
  .badges-col {{
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    width: 100%;
  }}
  .card h3 {{
    margin: 0;
    font-size: 1.18rem;
    line-height: 1.35;
    font-weight: 800;
    width: 100%;
    word-break: normal !important;
    overflow-wrap: break-word !important;
  }}
  .card h3 a {{
    color: var(--br-blue);
    text-decoration: none;
    display: inline;
    word-break: normal !important;
  }}
  .card h3 a:hover {{ color: var(--br-green); text-decoration: underline; }}

  .badge-novo {{
    background: var(--br-yellow);
    color: var(--br-blue-dark);
    border: 1.5px solid #eab308;
    font-size: 0.72rem;
    padding: 4px 10px;
    border-radius: 999px;
    font-weight: 800;
    white-space: nowrap;
  }}
  .badge-encerrando {{
    background: var(--urgente-bg);
    color: var(--urgente-txt);
    border: 1.5px solid var(--urgente-border);
    font-size: 0.72rem;
    padding: 4px 10px;
    border-radius: 999px;
    font-weight: 800;
    white-space: nowrap;
  }}

  .loc-row {{ display: flex; gap: 7px; flex-wrap: wrap; margin-top: 8px; align-items: center; }}
  .chip-loc {{
    background: var(--br-green-soft);
    color: var(--br-green-dark);
    border: 1px solid var(--br-green-border);
    font-size: 0.77rem;
    padding: 4px 10px;
    border-radius: 999px;
    font-weight: 700;
  }}
  .chip-dist {{
    background: var(--surface-alt);
    color: var(--muted);
    border: 1px solid var(--border);
    font-size: 0.75rem;
    padding: 4px 9px;
    border-radius: 999px;
    font-weight: 600;
  }}
  .esc-badge {{ font-size: 0.74rem; padding: 4px 10px; border-radius: 999px; font-weight: 800; }}
  .esc-fund {{ background: #e0f2fe; color: #075985; border: 1px solid #7dd3fc; }}
  .esc-med {{ background: #dcfce7; color: #14532d; border: 1px solid #86efac; }}
  .esc-tec {{ background: #fef9c3; color: #713f12; border: 1px solid #fde047; }}
  .esc-sup {{ background: var(--br-blue-soft); color: var(--br-blue); border: 1px solid var(--br-blue-border); }}

  .titulo {{ margin: 6px 0 0; color: var(--muted); font-size: 0.85rem; }}

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

  .req-box {{
    background: var(--br-yellow-soft);
    border: 1.5px solid var(--br-yellow-border);
    border-left: 5px solid #eab308;
    border-radius: 11px;
    padding: 10px 13px;
  }}
  .req-title {{
    font-size: 0.75rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--br-yellow-text);
    margin-bottom: 3px;
  }}
  .req-text {{ margin: 0; font-size: 0.84rem; color: #422006; font-weight: 500; line-height: 1.45; }}

  .isencao-box {{
    background: var(--br-blue-soft);
    border: 1.5px solid var(--br-blue-border);
    border-left: 5px solid var(--br-blue);
    border-radius: 11px;
    padding: 10px 13px;
  }}
  .isencao-title {{
    font-size: 0.75rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--br-blue);
    margin-bottom: 3px;
  }}
  .isencao-text {{ margin: 0; font-size: 0.83rem; color: #1e293b; font-weight: 500; line-height: 1.45; }}

  .info-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    align-items: stretch;
  }}
  @media (max-width: 440px) {{ .info-grid {{ grid-template-columns: 1fr; }} }}
  .info-box {{
    background: var(--surface-alt);
    border: 1px solid var(--border);
    border-radius: 11px;
    padding: 11px 13px;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    gap: 4px;
  }}
  .info-box .lbl {{
    font-size: 0.72rem;
    color: var(--muted);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.02em;
  }}
  .info-box .val {{
    font-size: 1.24rem;
    font-weight: 800;
    color: var(--br-green-dark);
    line-height: 1.2;
  }}
  .info-box .val-sm {{ font-size: 0.88rem; font-weight: 700; color: var(--txt); line-height: 1.3; }}
  .info-box .sub {{ font-size: 0.75rem; color: var(--muted); line-height: 1.38; font-weight: 500; }}
  .destaque-sal {{ background: var(--br-green-soft); border-color: var(--br-green-border); }}
  .destaque-prova .val-sm {{ color: var(--br-blue); }}
  .destaque-prazo .val-sm {{ color: #b45309; }}
  .destaque-prazo.prazo-urgente {{ background: var(--urgente-bg); border-color: var(--urgente-border); }}
  .destaque-prazo.prazo-urgente .val-sm, .destaque-prazo.prazo-urgente .sub {{ color: var(--urgente-txt); font-weight: 700; }}

  .links-row {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
  .btn-link {{
    background: var(--surface-alt);
    color: var(--br-blue);
    border: 1.5px solid var(--br-blue-border);
    min-height: 36px;
    padding: 7px 12px;
    border-radius: 10px;
    font-size: 0.8rem;
    font-family: inherit;
    text-decoration: none;
    font-weight: 700;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    line-height: 1.2;
    transition: all 0.15s;
  }}
  .btn-link:hover {{ background: var(--br-blue); color: #ffffff; }}
  .btn-link.primario {{ background: var(--br-green); color: #ffffff; border-color: var(--br-green-dark); }}
  .btn-link.primario:hover {{ background: var(--br-green-dark); }}
  .btn-share-card {{
    background: #eef4ff;
    color: var(--br-blue);
    border-color: #93c5fd;
  }}

  details.prog-box {{
    background: var(--surface-alt);
    border: 1.5px solid var(--border);
    border-radius: 11px;
    padding: 10px 14px;
    margin-top: auto;
  }}
  details.prog-box summary {{ cursor: pointer; font-size: 0.85rem; font-weight: 800; color: var(--br-blue); line-height: 1.35; }}
  .prog-body {{ margin-top: 10px; font-size: 0.84rem; color: var(--txt); }}
  .prog-arq {{ margin: 0 0 8px; font-size: 0.8rem; color: var(--muted); }}
  .prog-body ul {{ margin: 0 0 12px; padding-left: 20px; display: flex; flex-direction: column; gap: 7px; }}
  .prog-body li {{ line-height: 1.48; padding-left: 3px; }}
  .prog-cta {{ display: inline-flex; align-items: center; gap: 6px; color: var(--br-green-dark); font-weight: 800; text-decoration: none; font-size: 0.83rem; }}
  .prog-cta:hover {{ text-decoration: underline; }}

  .busca-cargo-panel {{
    background: var(--surface);
    border: 2px solid var(--br-blue-border);
    border-top: 5px solid var(--br-blue);
    border-radius: var(--radius-lg);
    padding: 20px 22px;
    margin-bottom: 22px;
    box-shadow: var(--shadow-sm);
    display: flex;
    flex-direction: column;
    gap: 16px;
  }}
  .cargo-input-row {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }}
  .cargo-input-wrap {{ flex: 1; min-width: 240px; position: relative; }}
  .cargo-input-wrap input {{
    width: 100%;
    height: 44px;
    padding: 10px 15px;
    border-radius: 12px;
    border: 2px solid var(--br-blue-border);
    background: var(--surface-alt);
    color: var(--txt);
    font-family: inherit;
    font-size: 0.94rem;
    font-weight: 600;
  }}
  .cargo-input-wrap input:focus {{
    outline: none;
    border-color: var(--br-green);
    background: #ffffff;
    box-shadow: 0 0 0 4px rgba(0, 151, 57, 0.12);
  }}
  .cargos-match-list {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }}
  .cargo-tag {{
    background: var(--br-green-soft);
    color: var(--br-green-dark);
    border: 1px solid var(--br-green-border);
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.76rem;
    font-weight: 700;
  }}

  /* Barra Flutuante da Função Comparar */
  .compare-dock {{
    position: fixed;
    bottom: 18px;
    left: 50%;
    transform: translateX(-50%);
    width: min(960px, calc(100% - 28px));
    background: linear-gradient(135deg, var(--br-blue-dark), var(--br-blue));
    color: #ffffff;
    border: 3px solid var(--br-yellow);
    border-radius: 20px;
    padding: 14px 20px;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.38);
    z-index: 950;
    display: none;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    flex-wrap: wrap;
  }}
  .compare-dock.visivel {{ display: flex; }}
  .compare-slots {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 1;
    flex-wrap: wrap;
  }}
  .c-slot {{
    flex: 1;
    min-width: 210px;
    background: rgba(255, 255, 255, 0.12);
    border: 1.5px dashed rgba(254, 221, 0, 0.65);
    border-radius: 12px;
    padding: 9px 13px;
    font-size: 0.83rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }}
  .c-slot.preenchido {{
    background: rgba(0, 151, 57, 0.35);
    border-style: solid;
    border-color: var(--br-yellow);
    font-weight: 700;
  }}
  .c-slot-rm {{
    background: rgba(255, 255, 255, 0.2);
    color: #ffffff;
    border: none;
    border-radius: 50%;
    width: 24px;
    height: 24px;
    cursor: pointer;
    font-weight: 800;
    line-height: 1;
  }}
  .btn-executar-comparar {{
    background: var(--br-yellow);
    color: var(--br-blue-dark);
    border: 2px solid #ffffff;
    min-height: 44px;
    padding: 10px 22px;
    border-radius: 999px;
    font-family: inherit;
    font-size: 0.95rem;
    font-weight: 800;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
    transition: all 0.15s;
  }}
  .btn-executar-comparar:disabled {{
    opacity: 0.45;
    cursor: not-allowed;
  }}
  .btn-executar-comparar:not(:disabled):hover {{
    transform: scale(1.04);
    background: #fde047;
  }}

  /* Modal de Comparação Lado a Lado */
  .compare-modal {{
    background: #ffffff;
    border-radius: 22px;
    max-width: 1020px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
    padding: 24px 26px;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.38);
    color: var(--txt);
  }}
  .cmp-summary-banner {{
    background: linear-gradient(135deg, var(--br-green-soft), var(--br-yellow-soft));
    border: 2px solid var(--br-green-border);
    border-radius: 16px;
    padding: 16px 20px;
    margin-bottom: 18px;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 14px;
  }}
  .cmp-kpi {{
    background: #ffffff;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 11px 14px;
  }}
  .cmp-kpi span {{
    display: block;
    font-size: 0.72rem;
    font-weight: 800;
    color: var(--muted);
    text-transform: uppercase;
  }}
  .cmp-kpi strong {{
    font-size: 1.02rem;
    color: var(--br-blue-dark);
    font-weight: 800;
  }}
  .cmp-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.87rem;
  }}
  .cmp-table th, .cmp-table td {{
    border: 1px solid var(--border);
    padding: 11px 14px;
    text-align: left;
    vertical-align: top;
  }}
  .cmp-table th {{
    background: var(--br-blue);
    color: #ffffff;
    font-weight: 800;
    font-size: 0.92rem;
  }}
  .cmp-table td.cmp-crit {{
    background: var(--surface-alt);
    font-weight: 800;
    color: var(--br-green-dark);
    width: 210px;
  }}
  .cmp-win {{
    background: #ecfdf5;
    font-weight: 700;
  }}

  /* Botões de Compartilhamento no Modal */
  .share-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 10px;
    margin-top: 14px;
  }}
  .btn-share-opt {{
    padding: 12px 16px;
    border-radius: 12px;
    border: none;
    font-family: inherit;
    font-size: 0.9rem;
    font-weight: 800;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: #ffffff;
    text-decoration: none;
  }}
  .btn-zap {{ background: #16a34a; }}
  .btn-zap:hover {{ background: #15803d; }}
  .btn-tg {{ background: #0284c7; }}
  .btn-tg:hover {{ background: #0369a1; }}
  .btn-native {{ background: var(--br-blue); }}
  .btn-copy-share {{ background: #334155; }}
  .share-preview-box {{
    width: 100%;
    min-height: 150px;
    padding: 12px;
    border-radius: 12px;
    border: 1.5px solid var(--border);
    background: var(--surface-alt);
    font-family: inherit;
    font-size: 0.83rem;
    color: var(--txt);
    resize: vertical;
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

  footer.app-footer {{
    margin-top: 44px;
    padding: 32px 0 48px;
    border-top: 2px solid var(--border);
    background: linear-gradient(180deg, var(--surface) 0%, var(--br-green-soft) 100%);
    text-align: center;
  }}
  .footer-coffee-wrap {{ display: flex; flex-direction: column; align-items: center; gap: 12px; }}
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
  .btn-coffee:hover {{ background: #1f5829; transform: translateY(-2px); }}
  .footer-note {{ color: var(--muted); font-size: 0.85rem; margin: 4px 0 0; }}

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
  .pix-head {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }}
  .pix-head h3 {{
    margin: 0;
    font-family: 'Fraunces', Georgia, serif;
    font-size: 1.35rem;
    color: #286e34;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .pix-close {{ background: transparent; border: none; font-size: 1.25rem; color: #889990; cursor: pointer; padding: 4px 8px; line-height: 1; }}
  .pix-close:hover {{ color: #2c3e35; }}
  .pix-desc {{ margin: 0 0 18px; font-size: 0.93rem; line-height: 1.55; color: #6b726e; }}
  .pix-qr-box {{
    display: inline-flex;
    padding: 12px;
    background: #ffffff;
    border: 2px solid #dfe7e2;
    border-radius: 16px;
    margin-bottom: 12px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.04);
  }}
  .pix-qr-box svg {{ display: block; width: 210px; height: 210px; }}
  .pix-receiver {{ margin: 0 0 16px; font-size: 0.84rem; color: #7c8782; font-weight: 500; }}
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
  }}
  .btn-copy-pix:hover {{ background: #1f5829; }}

  /* Bloqueio de Login Obrigatório com Conta Google */
  body.bloqueado-login {{
    overflow: hidden;
  }}
  body.bloqueado-login > header,
  body.bloqueado-login > .container,
  body.bloqueado-login > footer {{
    filter: blur(8px);
    pointer-events: none;
    user-select: none;
  }}
  .login-gate-bg {{
    position: fixed;
    inset: 0;
    background: linear-gradient(135deg, rgba(0, 27, 82, 0.88) 0%, rgba(0, 92, 36, 0.9) 100%);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 18px;
    z-index: 2500;
  }}
  .login-gate-bg.oculto {{ display: none; }}
  .login-card {{
    background: #ffffff;
    border-radius: 22px;
    border-top: 6px solid var(--br-yellow);
    max-width: 460px;
    width: 100%;
    padding: 28px 28px 26px;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.42);
    text-align: center;
    color: var(--txt);
  }}
  .login-badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--br-green-soft);
    color: var(--br-green-dark);
    border: 1px solid var(--br-green-border);
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 0.76rem;
    font-weight: 800;
    text-transform: uppercase;
    margin-bottom: 10px;
  }}
  .login-card h2 {{
    margin: 0 0 8px;
    font-family: 'Fraunces', Georgia, serif;
    font-size: 1.65rem;
    color: var(--br-blue-dark);
  }}
  .login-card p {{
    margin: 0 0 18px;
    font-size: 0.9rem;
    color: var(--muted);
    line-height: 1.5;
  }}
  .btn-google-official {{
    width: 100%;
    background: #ffffff;
    color: #1f2937;
    border: 2px solid #cbd5e1;
    min-height: 48px;
    padding: 10px 18px;
    border-radius: 999px;
    font-family: inherit;
    font-size: 0.96rem;
    font-weight: 800;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 11px;
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.07);
    transition: all 0.15s;
  }}
  .btn-google-official:hover {{
    border-color: #4285F4;
    background: #f8fafc;
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(66, 133, 244, 0.18);
  }}
  .google-form-box {{
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1.5px dashed var(--border);
    text-align: left;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .google-form-box label {{
    font-size: 0.78rem;
    font-weight: 800;
    color: var(--br-blue-dark);
    text-transform: uppercase;
  }}
  .google-form-box input {{
    width: 100%;
    height: 42px;
    padding: 8px 13px;
    border-radius: 10px;
    border: 1.5px solid var(--border);
    font-family: inherit;
    font-size: 0.9rem;
  }}
  .google-form-box input:focus {{
    outline: none;
    border-color: #4285F4;
    box-shadow: 0 0 0 3px rgba(66, 133, 244, 0.15);
  }}
  .login-erro {{
    color: #be123c;
    background: #fff1f2;
    border: 1px solid #fda4af;
    border-radius: 9px;
    padding: 8px 11px;
    font-size: 0.81rem;
    font-weight: 700;
    display: none;
  }}
  .user-profile-pill {{
    display: none;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    background: rgba(255, 255, 255, 0.14);
    border: 1.5px solid rgba(255, 255, 255, 0.4);
    color: #ffffff;
    padding: 5px 10px 5px 12px;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 700;
  }}
  .user-profile-pill.visivel {{ display: inline-flex; }}
  .btn-logout-google {{
    background: rgba(255, 255, 255, 0.22);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.45);
    border-radius: 999px;
    padding: 3px 9px;
    font-family: inherit;
    font-size: 0.72rem;
    font-weight: 800;
    cursor: pointer;
  }}
  .btn-logout-google:hover {{ background: #be123c; border-color: #fda4af; }}
  .btn-dev-secret {{
    display: none !important;
    background: #0f172a;
    color: var(--br-yellow);
    border: 2px solid var(--br-yellow);
    min-height: 38px;
    padding: 7px 15px;
    border-radius: 999px;
    font-family: inherit;
    font-size: 0.82rem;
    font-weight: 800;
    cursor: pointer;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }}
  .btn-dev-secret.visivel {{ display: inline-flex !important; }}

  /* ===== Cidade de referência, blocos de busca, veredito da comparação ===== */
  .chip-km-ref[hidden] {{ display: none !important; }}
  .ref-body {{ display: flex; flex-direction: column; gap: 6px; min-width: 0; }}
  .ref-row {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
  .ref-row input {{
    flex: 1 1 240px; min-width: 0; min-height: 40px; padding: 8px 14px;
    border: 1.5px solid var(--border); border-radius: 999px; font-family: inherit; font-size: 0.9rem;
    background: #fff; color: var(--txt);
  }}
  .ref-row input:focus {{ outline: 2px solid var(--br-green); border-color: var(--br-green); }}
  .ref-msg {{ color: var(--muted); font-size: 0.78rem; line-height: 1.4; }}
  .busca-bloco {{ margin-bottom: 18px; }}
  .toggle-head {{
    display: flex; justify-content: space-between; align-items: center;
    gap: 10px; margin-bottom: 8px; flex-wrap: wrap;
  }}
  .btn-recolher-mini {{ min-height: 32px !important; padding: 4px 12px !important; font-size: 0.77rem !important; }}
  .btn-pdf {{ background: var(--br-blue); color: #fff; border: 1.5px solid var(--br-blue-dark); }}
  .print-only {{ display: none; }}

  .cmp-veredito {{
    border: 2px solid var(--br-green); background: var(--br-green-soft);
    border-radius: 14px; padding: 14px 16px; margin-bottom: 16px;
  }}
  .cmp-vered-head {{ font-weight: 800; font-size: 1.05rem; color: var(--br-green-dark); margin-bottom: 8px; }}
  .cmp-vered-top {{ list-style: none; margin: 0 0 12px; padding: 0; display: grid; gap: 6px; }}
  .cmp-vered-top li {{
    background: #fff; border: 1.5px solid var(--br-green); border-radius: 10px;
    padding: 9px 12px; font-size: 0.93rem; line-height: 1.4;
  }}
  .cmp-vered-list {{ display: grid; gap: 6px; }}
  .cmp-v-row {{
    display: grid; grid-template-columns: 28px 1fr auto; gap: 10px; align-items: start;
    background: #fff; border: 1px solid var(--border); border-radius: 10px; padding: 8px 12px;
  }}
  .cmp-v-row .ic {{ font-size: 1.15rem; }}
  .cmp-v-row b {{ display: block; font-size: 0.82rem; color: var(--br-blue); }}
  .cmp-v-row p {{ margin: 2px 0 0; font-size: 0.86rem; line-height: 1.4; }}
  .cmp-v-row .tag {{
    font-size: 0.72rem; font-weight: 800; padding: 3px 9px; border-radius: 999px;
    background: var(--br-yellow); color: var(--br-blue-dark); white-space: nowrap;
  }}
  .cmp-v-row.empate .tag {{ background: #e5e7eb; color: #374151; }}

  @media print {{
    body.imprimindo-comp > *:not(#modalComparar) {{ display: none !important; }}
    body.imprimindo-comp {{ background: #fff !important; }}
    body.imprimindo-comp #modalComparar {{
      position: static !important; display: block !important; background: #fff !important;
      padding: 0 !important; overflow: visible !important;
    }}
    body.imprimindo-comp .compare-modal {{
      max-height: none !important; overflow: visible !important; box-shadow: none !important;
      width: 100% !important; max-width: none !important; border: 0 !important;
    }}
    body.imprimindo-comp .no-print, body.imprimindo-comp .pix-close {{ display: none !important; }}
    body.imprimindo-comp .print-only {{ display: block !important; }}
    body.imprimindo-comp .cmp-table {{ font-size: 10px; }}
    body.imprimindo-comp .cmp-veredito, body.imprimindo-comp tr {{ break-inside: avoid; }}
  }}

  /* ===== Layout mobile e tablet 100% responsivo (ocupa toda a largura da tela sem sobras brancas) ===== */
  @media (max-width: 900px) {{
    html, body {{
      width: 100% !important;
      max-width: 100% !important;
      overflow-x: hidden !important;
    }}
    .container {{
      padding: 0 12px !important;
      width: 100% !important;
      max-width: 100% !important;
      box-sizing: border-box !important;
    }}
    header.app-bar {{
      width: 100% !important;
      max-width: 100% !important;
      padding: 16px 0 14px !important;
      box-sizing: border-box !important;
    }}
    .bar-row {{
      flex-direction: column !important;
      align-items: stretch !important;
      gap: 12px !important;
      width: 100% !important;
      max-width: 100% !important;
    }}
    h1 {{ font-size: 1.65rem !important; line-height: 1.15 !important; }}
    .brand-badge {{ font-size: 0.66rem !important; padding: 3px 10px !important; }}
    .meta {{ font-size: 0.8rem !important; line-height: 1.5 !important; }}

    .header-actions-col {{
      display: grid !important;
      grid-template-columns: 1fr 1fr !important;
      gap: 8px !important;
      min-width: 0 !important;
      width: 100% !important;
      max-width: 100% !important;
    }}
    .header-actions-col > * {{ width: 100% !important; min-width: 0 !important; }}
    .header-actions-col .btn-app-install,
    .header-actions-col .btn-header-pix {{
      min-height: 42px !important; padding: 8px 10px !important; font-size: 0.8rem !important;
    }}
    .header-actions-col .btn-dev-secret:not(.visivel) {{ display: none !important; }}
    .header-actions-col .btn-dev-secret.visivel {{
      display: inline-flex !important;
      grid-column: 1 / -1 !important;
      width: 100% !important;
      min-height: 42px !important;
      padding: 8px 10px !important;
      font-size: 0.8rem !important;
    }}
    .user-profile-pill {{
      grid-column: 1 / -1 !important;
      max-width: 100% !important;
      width: 100% !important;
      justify-content: space-between !important;
      box-sizing: border-box !important;
    }}
    #userProfileText {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 62vw; }}

    .tabs-wrap {{
      width: 100% !important;
      max-width: 100% !important;
      overflow: hidden !important;
      margin: 14px 0 12px !important;
      box-sizing: border-box !important;
    }}
    nav.tabs {{
      display: flex !important;
      flex-wrap: nowrap !important;
      overflow-x: auto !important;
      overflow-y: hidden !important;
      width: 100% !important;
      max-width: 100% !important;
      min-width: 0 !important;
      gap: 8px !important;
      padding: 2px 2px 8px 2px !important;
      scroll-snap-type: x proximity !important;
      -webkit-overflow-scrolling: touch !important;
      scrollbar-width: thin !important;
      box-sizing: border-box !important;
    }}
    .tab-item {{
      flex: 0 0 auto !important;
      scroll-snap-align: start !important;
      gap: 6px !important;
      max-width: 85vw !important;
    }}
    .tab-btn {{
      white-space: nowrap !important;
      font-size: 0.84rem !important;
      padding: 10px 12px !important;
      flex: 0 0 auto !important;
    }}
    .tab-count-box {{
      min-width: 52px !important;
      padding: 4px 6px !important;
    }}

    .sec-title-row {{ flex-direction: column !important; align-items: flex-start !important; gap: 8px !important; }}
    .sec-title-row h2 {{ font-size: 1.12rem !important; line-height: 1.25 !important; }}
    .desc {{ font-size: 0.85rem !important; line-height: 1.45 !important; }}

    .busca-bloco,
    .busca-cargo-panel,
    .filtros-panel,
    .tab-panel,
    .grid {{
      width: 100% !important;
      max-width: 100% !important;
      min-width: 0 !important;
      box-sizing: border-box !important;
    }}
    .main-control-bar {{
      flex-direction: column !important;
      align-items: stretch !important;
      padding: 12px !important;
      gap: 10px !important;
    }}
    .toolbar-busca-cargo {{ width: 100% !important; min-width: 0 !important; }}
    .toolbar-left-actions {{
      display: grid !important;
      grid-template-columns: 1fr 1fr !important;
      gap: 8px !important;
      width: 100% !important;
    }}
    .toolbar-actions {{
      display: grid !important;
      grid-template-columns: 1fr 1fr !important;
      gap: 8px !important;
      width: 100% !important;
    }}
    .btn-abrir-sidebar {{ width: 100% !important; }}
    .btn-comparar-toggle {{ width: 100% !important; }}
    .sidebar-filtros {{
      width: 100vw !important;
      max-width: 100vw !important;
    }}
    .sidebar-filtros-head {{ padding: 14px 16px !important; }}
    .sidebar-filtros-body {{ padding: 12px 14px !important; }}
    .sidebar-filtros-foot {{ padding: 12px 14px !important; }}
    .btn-fab-filtros {{
      top: 12px !important;
      left: 12px !important;
      bottom: auto !important;
      right: auto !important;
      padding: 7px 13px !important;
      font-size: 0.82rem !important;
    }}
    .f-group {{
      grid-template-columns: 1fr !important;
      align-items: flex-start !important;
      gap: 8px !important;
      padding: 10px 10px !important;
      width: 100% !important;
      box-sizing: border-box !important;
    }}
    .f-label {{ font-size: 0.76rem !important; }}
    .pill-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      width: 100%;
      max-width: 100%;
      box-sizing: border-box;
    }}
    .pill-btn {{
      font-size: 0.8rem !important;
      max-width: 100% !important;
      white-space: normal !important;
      word-break: normal !important;
      box-sizing: border-box !important;
    }}

    .cargo-input-row {{
      flex-direction: column !important;
      align-items: stretch !important;
      width: 100% !important;
      gap: 8px !important;
    }}
    .cargo-input-wrap {{
      width: 100% !important;
      min-width: 0 !important;
      flex: 1 1 100% !important;
    }}
    .cargo-input-wrap input {{
      width: 100% !important;
      max-width: 100% !important;
      box-sizing: border-box !important;
    }}
    .cargo-input-row .btn-aplicar, .cargo-input-row .btn-limpar {{ width: 100% !important; }}
    .toggle-head {{ flex-direction: column !important; align-items: flex-start !important; }}

    .grid {{ grid-template-columns: 1fr !important; }}
    .card {{
      width: 100% !important;
      max-width: 100% !important;
      min-width: 0 !important;
      box-sizing: border-box !important;
      overflow: hidden !important;
      word-break: normal !important;
      overflow-wrap: break-word !important;
    }}
    .head-top {{
      flex-direction: column !important;
      align-items: flex-start !important;
      gap: 6px !important;
      width: 100% !important;
    }}
    .badges-col {{
      flex-direction: row !important;
      flex-wrap: wrap !important;
      align-items: center !important;
      gap: 5px !important;
      width: 100% !important;
    }}
    .card h3 {{
      font-size: 1.12rem !important;
      line-height: 1.36 !important;
      width: 100% !important;
      word-break: normal !important;
      overflow-wrap: break-word !important;
    }}
    .card h3 a {{
      word-break: normal !important;
      overflow-wrap: break-word !important;
    }}
    .loc-row {{
      display: flex !important;
      flex-wrap: wrap !important;
      gap: 6px !important;
      width: 100% !important;
      margin-top: 6px !important;
    }}
    .card .titulo {{
      font-size: 0.86rem !important;
      line-height: 1.4 !important;
      word-break: normal !important;
    }}
    .cargo-nome {{ font-size: 0.95rem !important; }}
    .info-grid {{ grid-template-columns: 1fr !important; }}
    .links-row > * {{ flex: 1 1 100% !important; justify-content: center !important; text-align: center !important; }}

    .compare-modal {{ width: 100% !important; max-width: 100% !important; max-height: 92vh !important; padding: 14px 12px !important; border-radius: 16px !important; }}
    .cmp-summary-banner {{ grid-template-columns: 1fr !important; }}
    .cmp-table {{ display: block !important; overflow-x: auto !important; font-size: 0.78rem !important; width: 100% !important; }}
    .cmp-v-row {{ grid-template-columns: 24px 1fr !important; }}
    .cmp-v-row .tag {{ grid-column: 2 !important; justify-self: start !important; }}
  }}
</style>
</head>
<body class="bloqueado-login">
  <!-- Tela de Login Obrigatório com Conta Google -->
  <div id="loginGateOverlay" class="login-gate-bg" role="dialog" aria-modal="true" aria-labelledby="tituloLoginGoogle">
    <div class="login-card">
      <div class="login-badge">🔒 Acesso Exclusivo Autenticado</div>
      <h2 id="tituloLoginGoogle">Entrar no Concursos</h2>
      <p>
        Faça login com sua <b>Conta Google</b> para acessar o painel completo de editais vigentes no Brasil e em São Paulo.
      </p>

      <!-- Container Oficial do Google Identity Services (quando Client ID OAuth configurado) -->
      <div id="gsiButtonContainer" style="display:flex;justify-content:center;margin-bottom:8px;"></div>

      <!-- Opção de alternar formulário manual -->
      <div id="opcaoManualLogin" style="margin:8px 0 12px;text-align:center;">
        <button type="button" id="btnAlternarManual" style="background:#f1f5f9;border:1px solid #cbd5e1;color:var(--br-blue);font-size:0.83rem;font-weight:700;padding:8px 14px;border-radius:10px;cursor:pointer;font-family:inherit;width:100%;transition:background 0.15s;">
          ✍️ Entrar diretamente com Nome e E-mail
        </button>
      </div>

      <!-- Botão Oficial Google Sign-In -->
      <button type="button" id="btnGoogleSignInMain" class="btn-google-official">
        <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true">
          <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
          <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
          <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
          <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
        </svg>
        <span>Continuar com Conta Google</span>
      </button>

      <form id="formLoginGoogle" class="google-form-box" autocomplete="on">
        <div>
          <label for="inputGoogleNome">Seu Nome</label>
          <input id="inputGoogleNome" name="name" type="text" required placeholder="Ex.: Matheus Ribeiro" autocomplete="name">
        </div>
        <div>
          <label for="inputGoogleEmail">E-mail da Conta Google (@gmail.com / @usp.br / Google)</label>
          <input id="inputGoogleEmail" name="email" type="email" required placeholder="seu.email@gmail.com ou @usp.br" autocomplete="email">
        </div>
        <div id="msgErroLoginGoogle" class="login-erro"></div>
        <button type="submit" class="btn-aplicar" style="width:100%;min-height:42px;font-size:.92rem;">
          ✅ Autenticar com Conta Google e Acessar
        </button>
      </form>
      <small style="display:block;margin-top:12px;font-size:.74rem;color:var(--muted);">
        🔒 Conexão protegida · Sua sessão permanece salva neste dispositivo.
      </small>
    </div>
  </div>

  <header class="app-bar">
    <div class="container">
      <div class="bar-row">
        <div>
          <div class="brand-badge">🇧🇷 Monitoramento Diário de Editais · SP &amp; Brasil</div>
          <h1>Concursos</h1>
          <div class="meta">
            Atualizado em <b>{gerado_em}</b> (Brasília) · <b>{total_sp}</b> editais vigentes em SP e <b>{len(catalogo_brasil)}</b> no Brasil · Fonte:
            <a href="{safe_url(listing_url)}" target="_blank" rel="noopener noreferrer">PCI Concursos</a>
          </div>
        </div>
        <div class="header-actions-col">
          <div id="userProfileChip" class="user-profile-pill" title="Conta Google Conectada">
            <span id="userProfileText">👤 Conectado</span>
            <button type="button" id="btnLogoutGoogle" class="btn-logout-google">Sair</button>
          </div>
          <button id="btnInstall" class="btn-app-install" type="button">📲 Baixar Aplicativo</button>
          <button id="btnHeaderPix" class="btn-header-pix" type="button">☕ Me pague um café</button>
          <button id="btnDevPanel" class="btn-dev-secret" type="button">🔐 Contador de Acessos (Dev)</button>
        </div>
      </div>
    </div>
  </header>

  <div class="container">
    <!-- Abas com "Buscar Cargo" como Página Inicial -->
    <div class="tabs-wrap">
      <nav class="tabs" aria-label="Categorias de Concursos">
        <div class="tab-item ativo" data-tab="busca_cargo">
          <button type="button" class="tab-btn">🔎 Buscar Cargo</button>
          <div class="tab-count-box" title="Concursos vigentes em todos os estados do Brasil">
            <b class="cnt" data-cnt-for="busca_cargo">{len(catalogo_brasil)}</b>
            <small>vigentes</small>
          </div>
        </div>

        <div class="tab-item" data-tab="fisio">
          <button type="button" class="tab-btn">🩺 Fisioterapia</button>
          <div class="tab-count-box" title="Concursos vigentes para Fisioterapia em SP">
            <b class="cnt" data-cnt-for="fisio">{len(fisio)}</b>
            <small>vigentes</small>
          </div>
        </div>

        <div class="tab-item" data-tab="medio_todos">
          <button type="button" class="tab-btn">📗 Nível Médio</button>
          <div class="tab-count-box" title="Concursos vigentes de Nível Médio e Técnico em SP">
            <b class="cnt" data-cnt-for="medio_todos">{len(medio_todos)}</b>
            <small>vigentes</small>
          </div>
        </div>

        <div class="tab-item" data-tab="superior_sp">
          <button type="button" class="tab-btn">🎓 Nível Superior</button>
          <div class="tab-count-box" title="Concursos vigentes de Nível Superior em SP">
            <b class="cnt" data-cnt-for="superior_sp">{len(superior_sp)}</b>
            <small>vigentes</small>
          </div>
        </div>

        <div class="tab-item" data-tab="provas_anteriores">
          <button type="button" class="tab-btn">📝 Provas Anteriores</button>
          <div class="tab-count-box" title="Busca de Provas Anteriores por Banca e Cargo">
            <b class="cnt" data-cnt-for="provas_anteriores">{len(catalogo_provas_banca_cargo)}</b>
            <small>banca/cargo</small>
          </div>
        </div>
      </nav>
    </div>

    <!-- Barra de Controle Compacta e Limpa: Filtros no Canto Superior Esquerdo -->
    <div id="barraControlePrincipal" class="main-control-bar" aria-label="Ações de busca e filtros">
      <div class="toolbar-left-actions">
        <button type="button" id="btnAbrirSidebarFiltros" class="btn-abrir-sidebar" aria-label="Abrir filtros dos concursos">
          <span class="icon">🎛️</span>
          <span class="txt">Filtros</span>
          <span id="badgeFiltrosAtivos" class="badge-filtros-cnt" style="display:none;">0</span>
        </button>

        <button type="button" id="btnToggleComparar" class="btn-comparar-toggle" aria-label="Função comparar">
          <span>⚖️</span>
          <span class="txt">Comparar</span>
        </button>
      </div>

      <div id="wrapBuscaCargoToolbar" class="toolbar-busca-cargo">
        <input id="inputCargoEspecifico" type="search" autocomplete="off" placeholder="🔎 Digite o cargo desejado... Ex.: Fisioterapeuta, Contador, Auditor Fiscal">
        <button type="button" id="btnLimparCargo" class="btn-clear-inline" title="Limpar busca" style="display:none;">✕</button>
      </div>
    </div>

    <!-- Barra de Chips de Filtros Ativos (aparece somente se houver algum filtro ativo) -->
    <div id="barraFiltrosAtivos" class="active-filters-bar" style="display:none;">
      <span class="af-label">Filtros ativos:</span>
      <div id="chipsFiltrosAtivos" class="af-chips"></div>
      <button type="button" id="btnLimparFiltrosRapido" class="af-btn-clear" title="Limpar todos os filtros">Limpar tudo ✕</button>
    </div>

    <!-- Botão Flutuante (FAB) nos cantos para acesso imediato aos filtros ao rolar a página -->
    <button type="button" id="btnFabFiltros" class="btn-fab-filtros" title="Abrir filtros dos concursos" aria-label="Abrir filtros">
      <span class="fab-icon">🎛️</span>
      <span class="fab-text">Filtros</span>
      <span id="badgeFabFiltrosAtivos" class="badge-filtros-cnt" style="display:none;">0</span>
    </button>

    <!-- Backdrop da Barra Lateral de Filtros -->
    <div id="backdropSidebarFiltros" class="sidebar-backdrop" aria-hidden="true"></div>

    <!-- BARRA LATERAL DE FILTROS (DRAWER OFF-CANVAS) -->
    <aside id="painelFiltrosSp" class="sidebar-filtros" role="dialog" aria-modal="true" aria-labelledby="tituloSidebarFiltros">
      <div class="sidebar-filtros-head">
        <div class="sidebar-head-info">
          <h3 id="tituloSidebarFiltros">🎛️ Filtros dos Concursos</h3>
          <p><span id="sidebarCountEncontrados">Carregando...</span> concursos encontrados</p>
        </div>
        <button type="button" id="btnFecharSidebarFiltros" class="sidebar-close-btn" aria-label="Fechar barra de filtros">✕</button>
      </div>

      <div class="sidebar-filtros-body">
        <!-- Bloco de Cargos Rápidos e Estados (Visível na aba Buscar Cargo) -->
        <div id="blocoBuscaCargo" class="sidebar-busca-extra">
          <div class="f-group">
            <div class="toggle-head">
              <div class="f-label">2️⃣ Escolha o Estado (UF) ou Brasil Todo:</div>
              <button type="button" id="btnToggleUfs" class="btn-recolher btn-recolher-mini">🔼 Recolher Estados</button>
            </div>
            <div class="pill-row" id="rowUfsBrasil">{botoes_ufs}</div>
          </div>

          <div class="f-group" style="margin-top:10px;">
            <div class="toggle-head">
              <div class="f-label">⚡ {len(CARGOS_RAPIDOS_MAX)} Cargos Rápidos (1 clique):</div>
              <button type="button" id="btnToggleCargosRapidos" class="btn-recolher btn-recolher-mini">🔼 Recolher Cargos Rápidos</button>
            </div>
            <div class="pill-row" id="rowCargosRapidos">{botoes_cargos_rapidos}</div>
          </div>
        </div>

        <div class="f-group">
          <div class="f-label">⏳ Prazo &amp; Destaques</div>
          <div class="pill-row">
            <button type="button" class="pill-btn ativo" data-filter="encerrando" data-val="">Todos os Prazos</button>
            <button type="button" class="pill-btn pill-urgente" data-filter="encerrando" data-val="1">
              ⏳ Inscrições Encerrando <span class="mini-cnt" id="cntEncerrandoBtn">{encerrando_count}</span>
            </button>
            <button type="button" class="pill-btn" data-filter="novo" data-val="1">
              ✨ Concursos Novos · 24h <span class="mini-cnt">{novos_count}</span>
            </button>
          </div>
        </div>

        <div class="f-group f-group-ref">
          <div class="f-label">📍 Minha cidade de referência (opcional)</div>
          <div class="ref-body">
            <div class="ref-row">
              <input id="inputCidadeRef" type="text" list="listaCidadesRef" autocomplete="off" maxlength="80" placeholder="Digite sua cidade. Ex.: Campinas - SP">
              <button type="button" id="btnLimparCidadeRef" class="btn-limpar">✖ Remover</button>
            </div>
            <datalist id="listaCidadesRef">{opcoes_cidades_ref}</datalist>
            <small id="msgCidadeRef" class="ref-msg">Escolha sua cidade para ver a distância e filtrar por proximidade.</small>
            <div class="pill-row" style="margin-top:8px;">
              <button type="button" class="pill-btn ativo" data-filter="kmRef" data-val="">Qualquer distância</button>
              <button type="button" class="pill-btn" data-filter="kmRef" data-val="50">Até 50 km</button>
              <button type="button" class="pill-btn" data-filter="kmRef" data-val="100">Até 100 km</button>
              <button type="button" class="pill-btn" data-filter="kmRef" data-val="150">Até 150 km</button>
              <button type="button" class="pill-btn" data-filter="kmRef" data-val="250">Até 250 km</button>
              <button type="button" class="pill-btn" data-filter="kmRef" data-val="350">Até 350 km</button>
            </div>
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
          <div class="f-label">🎓 Nível de Escolaridade</div>
          <div class="pill-row">
            <button type="button" class="pill-btn ativo" data-filter="escolaridade" data-val="">Todos os Níveis</button>
            <button type="button" class="pill-btn" data-filter="escolaridade" data-val="fundamental">📘 Nível Fundamental</button>
            <button type="button" class="pill-btn" data-filter="escolaridade" data-val="medio">📗 Ensino Médio</button>
            <button type="button" class="pill-btn" data-filter="escolaridade" data-val="medio_tecnico">🛠️ Curso Técnico</button>
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
            <button type="button" class="pill-btn" data-filter="vagas" data-val="cr">Somente CR</button>
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
          <div class="f-label">🏙️ Cidade (SP)</div>
          <div class="pill-row">{botoes_cidades}</div>
        </div>

        <div class="f-group">
          <div class="f-label">↕️ Ordenar Resultados</div>
          <div class="pill-row">
            <button type="button" class="pill-btn ativo" data-filter="ordem" data-val="padrao">Ordenação Padrão</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="inscricao">Inscrição encerrando</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="salario">Maior Salário</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="proximo">Mais perto de mim</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="vagas">Mais Vagas Imediatas</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="prova">Prova mais próxima</button>
          </div>
        </div>
      </div>

      <div class="sidebar-filtros-foot">
        <button type="button" id="btnLimparSidebar" class="btn-limpar">🔄 Limpar Filtros</button>
        <button type="button" id="btnAplicarSidebar" class="btn-aplicar">✅ Ver Concursos (<span id="sidebarCountBotao">0</span>)</button>
      </div>
    </aside>

    <main>
      <!-- PÁGINA INICIAL (ABA 1): Busca por Cargo Específico (Brasil Todo / Outros Estados / SP) -->
      <section id="busca_cargo" class="tab-panel ativo">
        <div class="sec-head">
          <div class="sec-title-row">
            <h2>🔎 Buscar Cargo — Brasil Todo, Estados ou SP</h2>
            <div class="count-box-lg" title="Concursos vigentes encontrados">
              <b id="countBuscaCargo">{len(catalogo_brasil)}</b>
              <span>vigentes</span>
            </div>
          </div>
          <p class="desc">
            Use a barra de busca acima para digitar qualquer cargo ou abra os <b>Filtros</b> para selecionar estados, cargos rápidos, faixas salariais e escolaridade.
          </p>
        </div>
        <div id="gridBuscaCargo" class="grid"></div>
        <p id="vazioBuscaCargo" class="vazio" style="display:none;">
          Nenhum concurso encontrado com os filtros atuais. Clique em "Limpar Filtros" ou selecione "🇧🇷 Brasil Todo".
        </p>
      </section>

      {render_secao(
          "fisio",
          "🩺",
          "Fisioterapia — Estado de São Paulo",
          "Salário bruto separado em destaque e soma com auxílios menor abaixo, benefícios (VA/VR/VT), isenção da taxa, regime, carga horária e conteúdo programático.",
          fisio,
          "fisio",
          ativo=False,
      )}
      {render_secao(
          "medio_todos",
          "📗",
          "Nível Médio &amp; Técnico — SP",
          "Cargos de Nível Médio e Técnico nos editais de São Paulo, com salário bruto separado e soma com auxílios menor, isenção da taxa e requisitos do edital. Use a faixa de remuneração abaixo.",
          medio_todos,
          "medio_todos",
      )}
      {render_secao(
          "superior_sp",
          "🎓",
          "Nível Superior — Estado de São Paulo",
          "Cargos de Nível Superior (analistas, auditores, advogados, contadores, engenheiros, professores e outros). Cargos que aceitam várias formações mostram todas as graduações aceitas.",
          superior_sp,
          "superior_sp",
      )}

      <!-- ABA 5: Provas Anteriores (Pesquisa por BANCA e CARGO, Nunca por Cidade) -->
      <section id="provas_anteriores" class="tab-panel">
        <div class="sec-head">
          <div class="sec-title-row">
            <h2>📝 Provas Anteriores — Pesquisa por Banca e Cargo</h2>
            <div class="count-box-lg">
              <b id="countProvasBancaCargo">{len(catalogo_provas_banca_cargo)}</b>
              <span>combinações</span>
            </div>
          </div>
          <p class="desc">
            Pesquise e baixe provas anteriores e gabaritos filtrando exclusivamente por <b>Banca Organizadora</b> e <b>Cargo</b> (sem vincular a cidade).
          </p>
        </div>

        <div class="busca-cargo-panel">
          <div>
            <div class="f-label" style="margin-bottom:8px;">1️⃣ Escolha ou Digite o Cargo e a Banca Organizadora:</div>
            <div class="cargo-input-row">
              <div class="cargo-input-wrap">
                <input id="inputProvaCargo" type="search" autocomplete="off" placeholder="Cargo... Ex.: Fisioterapeuta, Escrevente, Agente Administrativo">
              </div>
              <div class="cargo-input-wrap">
                <input id="inputProvaBanca" type="search" autocomplete="off" placeholder="Banca... Ex.: VUNESP, IBAM, Avança, INDEPAC, CONSCAM">
              </div>
              <button type="button" id="btnAbrirProvaDireta" class="btn-aplicar">🔎 Abrir Provas (Cargo + Banca)</button>
              <button type="button" id="btnLimparProvas" class="btn-limpar">🔄 Limpar</button>
            </div>
          </div>

          <div>
            <div class="f-label" style="margin-bottom:8px;">🏛️ Filtrar por Banca Organizadora:</div>
            <div class="pill-row" id="rowBancasProvas">{botoes_bancas_provas}</div>
          </div>

          <div>
            <div class="f-label" style="margin-bottom:8px;">💼 Filtrar por Cargo:</div>
            <div class="pill-row" id="rowCargosProvas">{botoes_cargos_provas}</div>
          </div>
        </div>

        <div id="gridProvasBancaCargo" class="grid"></div>
      </section>
    </main>
  </div>

  <!-- Barra Flutuante da Função Comparar -->
  <div id="barraComparar" class="compare-dock" role="region" aria-label="Seleção de Concursos para Comparar">
    <div class="compare-slots">
      <div id="slotComp1" class="c-slot">1️⃣ Clique em um concurso ou no botão <b>+ Adicionar</b></div>
      <div id="slotComp2" class="c-slot">2️⃣ Clique no segundo concurso para comparar</div>
    </div>
    <div style="display:flex;gap:8px;align-items:center;">
      <button type="button" id="btnExecutarComparar" class="btn-executar-comparar" disabled>🚀 Comparar!</button>
      <button type="button" id="btnFecharModoComparar" class="btn-limpar" style="background:rgba(255,255,255,0.15);color:#fff;border-color:rgba(255,255,255,0.4);">✕ Sair</button>
    </div>
  </div>

  <!-- Modal Lado a Lado da Função Comparar -->
  <div id="modalComparar" class="modal-bg" role="dialog" aria-modal="true" aria-labelledby="tituloComparar">
    <div class="compare-modal">
      <div class="pix-head">
        <h3 id="tituloComparar">⚖️ Comparativo Detalhado de Concursos</h3>
        <button type="button" id="fecharModalComparar" class="pix-close" aria-label="Fechar">✕</button>
      </div>
      <div id="corpoModalComparar"></div>
      <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:18px;flex-wrap:wrap;">
        <button type="button" id="btnBaixarPdfComparacao" class="btn-share-opt btn-pdf no-print">📄 Baixar PDF</button>
        <button type="button" id="btnCompartilharComparacaoZap" class="btn-share-opt btn-zap no-print">🟢 Compartilhar no WhatsApp</button>
        <button type="button" id="btnFecharCompRodape" class="btn-limpar no-print">Fechar</button>
      </div>
    </div>
  </div>

  <!-- Modal de Compartilhamento de Concurso (WhatsApp, Telegram, Link e Outros Apps) -->
  <div id="modalCompartilhar" class="modal-bg" role="dialog" aria-modal="true" aria-labelledby="tituloCompartilhar">
    <div class="pix-modal" style="max-width:540px;text-align:left;">
      <div class="pix-head">
        <h3 id="tituloCompartilhar">📤 Compartilhar Concurso</h3>
        <button type="button" id="fecharModalCompartilhar" class="pix-close" aria-label="Fechar">✕</button>
      </div>
      <p class="pix-desc" style="text-align:left;margin-bottom:10px;">
        Confira o resumo abaixo e escolha onde deseja compartilhar:
      </p>
      <textarea id="textoCompartilhar" class="share-preview-box" readonly></textarea>
      <div class="share-grid">
        <a id="linkShareZap" class="btn-share-opt btn-zap" href="#" target="_blank" rel="noopener noreferrer">🟢 WhatsApp</a>
        <a id="linkShareTelegram" class="btn-share-opt btn-tg" href="#" target="_blank" rel="noopener noreferrer">✈️ Telegram</a>
        <button type="button" id="btnShareNativo" class="btn-share-opt btn-native">📱 Outros Apps</button>
        <button type="button" id="btnCopiarShare" class="btn-share-opt btn-copy-share">🔗 Copiar Texto e Link</button>
      </div>
    </div>
  </div>

  <!-- Modal Exclusivo do Desenvolvedor: Contador de Acessos (Apenas via Link Específico) -->
  <div id="modalDevStats" class="modal-bg" role="dialog" aria-modal="true" aria-labelledby="tituloDevStats">
    <div class="compare-modal" style="max-width:780px;">
      <div class="pix-head">
        <h3 id="tituloDevStats">🔐 Painel do Desenvolvedor — Contador de Acessos</h3>
        <button type="button" id="fecharModalDevStats" class="pix-close" aria-label="Fechar">✕</button>
      </div>

      <!-- Banner de Status do Modo Desenvolvedor -->
      <div style="background:#f1f5f9;border:1.5px solid #cbd5e1;border-radius:12px;padding:12px 14px;margin-bottom:14px;">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <div>
            <b style="color:var(--br-blue-dark);font-size:0.86rem;">🛡️ Status: Modo Administrador Ativo</b>
            <div style="font-size:0.77rem;color:var(--muted);margin-top:2px;">
              Visitantes normais <b>NUNCA</b> veem este botão nem este painel. Apenas você tem acesso após digitar a chave.
            </div>
          </div>
          <button type="button" id="btnSairModoDev" style="background:#fee2e2;color:#991b1b;border:1px solid #fca5a5;padding:6px 12px;border-radius:8px;font-size:0.8rem;font-weight:700;cursor:pointer;">
            🚪 Sair do Modo Dev (Ocultar Botão)
          </button>
        </div>
      </div>

      <!-- Banner da Planilha Google Conectada -->
      <div style="background:#f0fdf4;border:1.5px solid #bbf7d0;border-radius:12px;padding:10px 14px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <div style="font-size:0.83rem;color:#166534;">
          📊 <b>Planilha Google Conectada:</b> Acessos e logins de terceiros são gravados em tempo real na sua planilha central.
        </div>
        <a href="https://drive.google.com/" target="_blank" rel="noopener noreferrer" style="font-size:0.8rem;color:#15803d;font-weight:700;text-decoration:underline;">
          Abrir Google Drive ↗
        </a>
      </div>

      <div class="cmp-summary-banner" style="margin-bottom:16px;">
        <div class="cmp-kpi">
          <span>🌐 Total Geral de Acessos</span>
          <strong id="kpiTotalAcessosGlobais">Carregando...</strong>
        </div>
        <div class="cmp-kpi">
          <span>🔑 Logins com Conta Google</span>
          <strong id="kpiTotalLoginsGlobais">Carregando...</strong>
        </div>
        <div class="cmp-kpi">
          <span>💻 Acessos Neste Dispositivo</span>
          <strong id="kpiAcessosLocais">0</strong>
        </div>
        <div class="cmp-kpi">
          <span>👥 Usuários Únicos (Contas)</span>
          <strong id="kpiUsuariosUnicos">0</strong>
        </div>
      </div>

      <div style="margin-bottom:16px;">
        <div class="f-label" style="margin-bottom:6px;">📋 Histórico em Tempo Real de Acessos e Logins (Planilha Google):</div>
        <div style="max-height:220px;overflow-y:auto;border:1px solid var(--border);border-radius:12px;">
          <table class="cmp-table" style="font-size:.8rem;">
            <thead>
              <tr>
                <th>Data / Hora</th>
                <th>Usuário (Conta Google)</th>
                <th>Evento / Aba</th>
              </tr>
            </thead>
            <tbody id="tabelaLogsDev"></tbody>
          </table>
        </div>
      </div>

      <details class="prog-box" style="margin-bottom:14px;">
        <summary>📊 Webhook da Planilha Google (Acessos e Logins de Terceiros)</summary>
        <div class="prog-body">
          <p style="margin:0 0 8px;font-size:0.82rem;line-height:1.4;">
            URL do Web App do Google Apps Script que recebe e registra os acessos e logins de todos os usuários:
          </p>
          <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
            <input id="inputDevWebhookUrl" type="text" placeholder="https://script.google.com/macros/s/.../exec" style="flex:1;min-width:240px;padding:8px 12px;border-radius:8px;border:1px solid var(--border);">
            <button type="button" id="btnSalvarWebhookUrl" class="btn-aplicar">Salvar URL</button>
            <button type="button" id="btnRestaurarWebhookUrl" style="background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;padding:8px 12px;border-radius:8px;font-size:0.82rem;font-weight:700;cursor:pointer;">Restaurar Padrão</button>
          </div>
        </div>
      </details>

      <details class="prog-box" style="margin-bottom:14px;">
        <summary>⚙️ Configurar Google OAuth Client ID (Opcional — Google Cloud Console)</summary>
        <div class="prog-body">
          <p style="margin:0 0 8px;font-size:0.82rem;line-height:1.4;">
            Se desejar usar o botão oficial de 1 toque do Google ("Continuar como..."), cole o <b>Client ID</b> do Google Cloud Console:
          </p>
          <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
            <input id="inputDevGoogleClientId" type="text" placeholder="Ex.: 123456789-abc.apps.googleusercontent.com" style="flex:1;min-width:240px;padding:8px 12px;border-radius:8px;border:1px solid var(--border);">
            <button type="button" id="btnSalvarClientId" class="btn-aplicar">Salvar Client ID</button>
            <button type="button" id="btnLimparDevClientId" style="background:#fee2e2;color:#991b1b;border:1px solid #fca5a5;padding:8px 12px;border-radius:8px;font-size:0.82rem;font-weight:700;cursor:pointer;">🗑️ Remover Client ID</button>
          </div>
          <div style="margin-top:8px;padding:8px 10px;background:#fff1f2;border:1px solid #fda4af;border-radius:8px;font-size:0.75rem;color:#9f1239;line-height:1.4;">
            ⚠️ <b>Aviso sobre Erro 401: invalid_client ("The OAuth client was not found"):</b><br>
            Esse erro do Google indica que o Client ID informado não existe nos servidores do Google ou foi digitado com erro.<br>
            • Se vir esse erro, clique em <b>"🗑️ Remover Client ID"</b> acima para voltar imediatamente ao login limpo.<br>
            • Para usar Client ID do Google Cloud: certifique-se de criar como <b>"Aplicativo da Web"</b> com Origem JavaScript autorizada <code>https://matheusdochapeu-hub.github.io</code>.
          </div>
        </div>
      </details>

      <div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;">
        <button type="button" id="btnExportarLogsDev" class="btn-link primario">📥 Exportar Relatório JSON</button>
        <button type="button" id="btnFecharDevRodape" class="btn-limpar">Fechar Painel</button>
      </div>
    </div>
  </div>

  <div id="msgFiltroAplicado" class="toast-filtro" aria-live="polite">✓ Filtros atualizados</div>

  <!-- Rodapé com botão "☕ Me pague um café" -->
  <footer class="app-footer">
    <div class="container footer-coffee-wrap">
      <button type="button" id="btnAbrirPix" class="btn-coffee">☕ Me pague um café</button>
      <p class="footer-note">Painel gratuito atualizado diariamente · Feito com carinho por Matheus Rodrigues Ribeiro</p>
    </div>
  </footer>

  <!-- Modal "💚 Manda um Pix!" -->
  <div id="modalPix" class="modal-bg" role="dialog" aria-modal="true" aria-labelledby="tituloPix">
    <div class="pix-modal">
      <div class="pix-head">
        <h3 id="tituloPix">💚 Manda um Pix!</h3>
        <button type="button" id="fecharModalPix" class="pix-close" aria-label="Fechar">✕</button>
      </div>
      <p class="pix-desc">
        Este app é gratuito e feito com carinho. Se ele te ajudou, considere apoiar com um Pix de qualquer valor — é opcional e muito bem-vindo! 💚
      </p>
      <div class="pix-qr-box" aria-label="QR Code Pix">{qr_svg}</div>
      <p class="pix-receiver">Recebedor: Matheus · São Paulo</p>
      <button type="button" id="btnCopiarPix" class="btn-copy-pix">📋 Copiar chave Pix</button>
    </div>
  </div>

  <!-- Modal de Instrução de Instalação do Aplicativo -->
  <div id="modalApp" class="modal-bg" role="dialog" aria-modal="true">
    <div class="pix-modal" style="text-align:left;">
      <div class="pix-head">
        <h3>📲 Instalar Aplicativo</h3>
        <button type="button" id="fecharModalApp" class="pix-close" aria-label="Fechar">✕</button>
      </div>
      <p class="pix-desc" style="text-align:left;">
        Instale este painel no seu celular ou computador para acesso rápido:
      </p>
      <ol style="padding-left:20px;font-size:.9rem;line-height:1.6;color:#2c3e35;">
        <li><b>No Chrome / Edge (PC ou Android):</b> clique no ícone <b>⊕</b> na barra de endereços ou no menu <b>⋮ → Instalar aplicativo</b>.</li>
        <li><b>No iPhone / iPad (Safari):</b> toque em <b>Compartilhar (⬆️)</b> e escolha <b>"Adicionar à Tela de Início"</b>.</li>
      </ol>
      <button type="button" id="btnEntendiApp" class="btn-copy-pix" style="margin-top:12px;">Entendi</button>
    </div>
  </div>

<script>
  const CATALOGO_BRASIL = {catalogo_json};
  const CATALOGO_PROVAS = {provas_json};
  const PIX_PAYLOAD = {safe_json_for_script(pix_key)};
  const DIAS_ALERTA = {DIAS_ALERTA_ENCERRAMENTO};
  const APP_PUBLIC_URL = window.location.href.split('?')[0].split('#')[0];

  function normStr(s) {{
    return (s || '').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
  }}
  function normSlug(s) {{
    return normStr(s).replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  }}
  // Sanitização rigorosa contra XSS (inclusive em atributos HTML entre aspas)
  function escHtml(s) {{
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
      .replace(/`/g, '&#96;');
  }}
  // Validação estrita de URL contra esquemas javascript: / data: / vbscript:
  function safeUrl(u) {{
    const s = String(u || '').trim();
    if (/^https?:\\/\\//i.test(s)) return escHtml(s);
    return '#';
  }}
  function fmtBrl(n) {{
    if (!n || isNaN(n) || n <= 0) return 'Consultar edital';
    return 'R$ ' + Number(n).toLocaleString('pt-BR', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
  }}

  function parseBrl(str) {{
    if (!str) return 0;
    const s = String(str).replace(/[^\\d.,]/g, '').trim();
    if (!s) return 0;
    const clean = s.replace(/\\./g, '').replace(',', '.');
    const val = parseFloat(clean);
    return isNaN(val) ? 0 : val;
  }}

  function calcFaixaSlug(salBruto, salTotal) {{
    const ref = (salTotal && salTotal > 5000) ? salTotal : salBruto;
    if (!ref || ref <= 0) return 'consultar';
    if (ref <= 2500) return 'ate2500';
    if (ref <= 3500) return '2500a3500';
    if (ref <= 5000) return '3500a5000';
    return 'acima5000';
  }}

  function resolverSalarioParaCargo(item, termo, cargosCasados, escolaridadeFiltro) {{
    let auxilioNum = 0;
    if (item.beneficios) {{
      const mDia = item.beneficios.match(/di[aá]ri[oa]\\s+de\\s+R\\$\\s*([\\d.]+([,.]\\d{{2}})?)/i);
      if (mDia) {{
        auxilioNum = Math.round(parseBrl(mDia[1]) * 22);
      }} else {{
        const matches = Array.from(item.beneficios.matchAll(/R\\$\\s*([\\d.]+([,.]\\d{{2}})?)/g));
        for (const m of matches) {{
          const val = parseBrl(m[1]);
          if (val >= 50 && val <= 3500) auxilioNum += val;
        }}
      }}
    }}

    const mapSal = item.cargos_salarios || {{}};
    const normTermo = termo ? normStr(termo) : '';

    function buscarNoMapa(nome) {{
      if (!nome) return null;
      const n = normStr(nome.split('(')[0]);
      if (mapSal[n]) return mapSal[n];
      for (const k in mapSal) {{
        if (n.includes(k) || k.includes(n)) return mapSal[k];
      }}
      return null;
    }}

    let salEncontrado = null;
    let nomeCargoAchado = '';

    if (normTermo) {{
      salEncontrado = buscarNoMapa(normTermo);
      if (salEncontrado) nomeCargoAchado = termo;
    }}

    if (!salEncontrado && cargosCasados && cargosCasados.length > 0) {{
      for (const cg of cargosCasados) {{
        const s = buscarNoMapa(cg);
        if (s) {{
          salEncontrado = s;
          nomeCargoAchado = cg.split('(')[0].trim();
          break;
        }}
      }}
    }}

    const REGEX_FUND = /cozinheir|merendeir|auxiliar|servicos\\s*gerais|limpeza|gari|coveir|vigia|bracal|copeir|pedreir|pintor|soldador|borracheir|carpinteir|encanador|eletricista|operador|tratorista|motorista|leiturista|frentista|telefonista|aferidor|apreensor|padeiro|ajudante/i;
    const REGEX_MED = /oficial|assistente|escritur|recepcionista|tecnico|fiscal|agente\\s*comunit|agente\\s*de\\s*combate|cuidador|almoxarife|orientador|desenhista|salva-vidas/i;
    const REGEX_SUP = /fisioterapeuta|medico|procurador|advogado|engenheiro|arquiteto|contador|auditor|psicologo|dentista|enfermeir|farmaceutico|nutricionista|terapeuta|fonoaudiologo|veterinario|museologo|analista/i;

    const textoAlvo = normTermo || (cargosCasados && cargosCasados[0] ? normStr(cargosCasados[0]) : '');

    let nivelRotulo = '';
    if (!salEncontrado && textoAlvo) {{
      if (REGEX_FUND.test(textoAlvo)) {{
        // Regra de Ouro para Nível Fundamental:
        // O teto municipal para cargos operacionais nunca deve ultrapassar R$ 4.500,00!
        if (item.salario_min && item.salario_min <= 4500) {{
          salEncontrado = item.salario_min;
          nivelRotulo = 'Nível Fundamental';
        }} else {{
          // Safeguard absoluto: edital sem piso identificado ou com valor inconsistente
          return {{
            salario_num: 0,
            salario_total: (auxilioNum > 0 ? auxilioNum : 0),
            salario_exib: 'Piso Municipal / A consultar',
            salario_det: `Nível Fundamental · Edital com teto de até ${{fmtBrl(item.salario_max)}} (consulte o Anexo I do edital para o vencimento deste cargo)${{auxilioNum > 0 ? ' | + ' + fmtBrl(auxilioNum) + ' em benefícios' : ''}}`,
            especifico: true
          }};
        }}
      }} else if (REGEX_MED.test(textoAlvo)) {{
        // Regra de Ouro para Nível Médio / Técnico:
        if (item.salario_medio && item.salario_medio <= 7000) {{
          salEncontrado = item.salario_medio;
          nivelRotulo = 'Nível Médio/Técnico';
        }} else if (item.salario_min && item.salario_min <= 6000) {{
          salEncontrado = item.salario_min;
          nivelRotulo = 'Nível Médio/Técnico';
        }} else if (item.salario_max && item.salario_max <= 6000) {{
          salEncontrado = item.salario_max;
          nivelRotulo = 'Nível Médio/Técnico';
        }} else {{
          return {{
            salario_num: 0,
            salario_total: (auxilioNum > 0 ? auxilioNum : 0),
            salario_exib: 'Piso da Categoria / A consultar',
            salario_det: `Nível Médio/Técnico · Edital com teto de até ${{fmtBrl(item.salario_max)}} (consulte o Anexo I do edital)${{auxilioNum > 0 ? ' | + ' + fmtBrl(auxilioNum) + ' em benefícios' : ''}}`,
            especifico: true
          }};
        }}
      }} else if (REGEX_SUP.test(textoAlvo)) {{
        if (item.salario_max) {{
          salEncontrado = item.salario_max;
          nivelRotulo = 'Nível Superior';
        }}
      }}
    }}

    if (!salEncontrado && !normTermo && escolaridadeFiltro) {{
      if (escolaridadeFiltro === 'fundamental' && item.salario_min && item.salario_min <= 4500) {{
        salEncontrado = item.salario_min;
        nivelRotulo = 'Nível Fundamental';
      }} else if (escolaridadeFiltro === 'superior' && item.salario_max) {{
        salEncontrado = item.salario_max;
        nivelRotulo = 'Nível Superior';
      }}
    }}

    if (salEncontrado) {{
      const salBruto = salEncontrado;
      const salTot = auxilioNum > 0 ? (salBruto + auxilioNum) : salBruto;
      const exib = fmtBrl(salBruto);
      let det = `Bruto: ${{exib}}`;
      if (auxilioNum > 0) {{
        det += ` + ${{fmtBrl(auxilioNum)}} (auxílios) = ${{fmtBrl(salTot)}} com auxílios`;
      }} else if (item.beneficios && item.beneficios !== 'Consultar edital') {{
        det += ` + benefícios legais (${{item.beneficios}})`;
      }}
      if (nivelRotulo) det += ` · ${{nivelRotulo}}`;
      else if (item.salario_faixa && item.salario_min && item.salario_max && item.salario_min < item.salario_max) {{
        det += ` · Faixa geral do edital: ${{item.salario_faixa}}`;
      }}
      return {{
        salario_num: salBruto,
        salario_total: salTot,
        salario_exib: exib,
        salario_det: det,
        especifico: true
      }};
    }}

    if (item.salario_min && item.salario_max && item.salario_min < item.salario_max) {{
      const faixaStr = item.salario_faixa || `${{fmtBrl(item.salario_min)}} a ${{fmtBrl(item.salario_max)}}`;
      let det = `Varia conforme o cargo · Edital com ${{(item.cargos || []).length}} cargos`;
      if (auxilioNum > 0) det += ` | + até ${{fmtBrl(auxilioNum)}} em auxílios`;
      else if (item.beneficios && item.beneficios !== 'Consultar edital') det += ` | Benefícios: ${{item.beneficios}}`;
      return {{
        salario_num: item.salario_max,
        salario_total: (auxilioNum > 0 ? item.salario_max + auxilioNum : item.salario_total || item.salario_max),
        salario_exib: faixaStr,
        salario_det: det,
        especifico: false
      }};
    }}

    return {{
      salario_num: item.salario_max || 0,
      salario_total: item.salario_total || item.salario_max || 0,
      salario_exib: item.salario_exib || (item.salario_max ? `Até ${{fmtBrl(item.salario_max)}}` : 'Consultar edital'),
      salario_det: item.salario_det || (item.beneficios ? `Benefícios: ${{item.beneficios}}` : 'Consultar edital'),
      especifico: false
    }};
  }}

  function calcularDistanciaCidadesKm(lat1, lon1, lat2, lon2) {{
    const a1 = Number(lat1), o1 = Number(lon1), a2 = Number(lat2), o2 = Number(lon2);
    if (isNaN(a1) || isNaN(o1) || isNaN(a2) || isNaN(o2)) return null;
    if (Math.abs(a1 - a2) < 0.001 && Math.abs(o1 - o2) < 0.001) return 0;
    const R = 6371.0;
    const dLat = (a2 - a1) * Math.PI / 180;
    const dLon = (o2 - o1) * Math.PI / 180;
    const p1 = a1 * Math.PI / 180;
    const p2 = a2 * Math.PI / 180;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dLon / 2) ** 2;
    const linear = 2 * R * Math.asin(Math.sqrt(h));
    return Math.round(linear * 1.22);
  }}

  // ===== Cidade de referência (opcional): o usuário escolhe; distâncias = Haversine * 1.22 =====
  const CIDADES_REF = {cidades_ref_json};
  const REF_STORAGE_KEY = 'concursos_cidade_ref_v1';
  let cidadeRef = null;

  function kmDaReferencia(lat, lon) {{
    if (!cidadeRef) return null;
    return calcularDistanciaCidadesKm(cidadeRef.lat, cidadeRef.lon, lat, lon);
  }}
  function textoDistanciaRef(km) {{
    if (km == null || !cidadeRef) return '';
    return km === 0 ? `🧭 Na sua cidade (${{cidadeRef.nome}})` : `🧭 ~${{km}} km de ${{cidadeRef.nome}}`;
  }}
  function acharCidadeRef(txt) {{
    const q = normStr((txt || '').trim());
    if (!q) return null;
    let achada = CIDADES_REF.find(c => normStr(c[0] + ' - ' + c[1]) === q);
    if (!achada) {{
      const porNome = CIDADES_REF.filter(c => normStr(c[0]) === q);
      if (porNome.length > 0) achada = porNome.find(c => c[1] === 'SP') || porNome[0];
    }}
    return achada ? {{ nome: achada[0], uf: achada[1], lat: achada[2], lon: achada[3] }} : null;
  }}
  function atualizarDistanciasRef() {{
    document.querySelectorAll('.card').forEach(card => {{
      const km = kmDaReferencia(card.dataset.lat, card.dataset.lon);
      card.dataset.kmRef = km == null ? '9999' : String(km);
      const chip = card.querySelector('.chip-km-ref');
      if (chip) {{
        chip.textContent = textoDistanciaRef(km);
        chip.hidden = (km == null);
      }}
    }});
  }}

  // Extrai valores em R$ de VA, VR, VT de um texto de benefícios
  function extrairValoresBeneficios(txt) {{
    const s = txt || '';
    const matches = [...s.matchAll(/R\\$\\s*([\\d.]+,\\d{{2}})/g)];
    let soma = 0;
    matches.forEach(m => {{
      const v = parseFloat(m[1].replace(/\\./g, '').replace(',', '.'));
      if (!isNaN(v) && v >= 30 && v <= 4000) {{
        soma += s.toLowerCase().includes('diário') || s.toLowerCase().includes('diario') ? v * 22 : v;
      }}
    }});
    return Math.round(soma * 100) / 100;
  }}

  // 1) Alertas em tempo real (24h e Inscrições Encerrando)
  (function atualizarAlertasTempoReal() {{
    const agoraMs = Date.now();
    const hojeLocal = new Date();
    hojeLocal.setHours(0, 0, 0, 0);
    const urlsEncerrando = new Set();

    document.querySelectorAll('.card').forEach(card => {{
      const isBaseline = card.dataset.isBaseline === '1';
      const ts = Date.parse(card.dataset.firstSeenTs || '');
      const ehNovo = !isBaseline && !isNaN(ts) && (agoraMs - ts) >= 0 && (agoraMs - ts) <= 86400000;
      card.dataset.novo = ehNovo ? '1' : '0';

      const isoFim = card.dataset.inscricao || '';
      if (isoFim && isoFim !== '9999-12-31') {{
        const partes = isoFim.split('-').map(Number);
        if (partes.length === 3) {{
          const dtFim = new Date(partes[0], partes[1] - 1, partes[2]);
          dtFim.setHours(0, 0, 0, 0);
          const diffDias = Math.round((dtFim - hojeLocal) / 86400000);
          card.dataset.diasRestantes = String(diffDias);
          const encerrando = diffDias >= 0 && diffDias <= DIAS_ALERTA;
          card.dataset.encerrando = encerrando ? '1' : '0';
          card.classList.toggle('card-urgente', encerrando);

          if (encerrando && card.dataset.url) urlsEncerrando.add(card.dataset.url);

          let txtAviso = '';
          if (diffDias < 0) txtAviso = '⛔ Inscrições encerradas';
          else if (diffDias === 0) txtAviso = '🚨 ÚLTIMO DIA DE INSCRIÇÃO (Encerra hoje!)';
          else if (diffDias === 1) txtAviso = '⚠️ INSCRIÇÕES ENCERRANDO · Termina amanhã!';
          else if (diffDias <= DIAS_ALERTA) txtAviso = `⏳ INSCRIÇÕES ENCERRANDO · Faltam ${{diffDias}} dias!`;
          else txtAviso = `Faltam ${{diffDias}} dias para encerrar`;

          const subPrazo = card.querySelector('.sub-prazo-status');
          const boxPrazo = card.querySelector('.destaque-prazo');
          if (subPrazo) subPrazo.textContent = txtAviso;
          if (boxPrazo) boxPrazo.classList.toggle('prazo-urgente', encerrando);
        }}
      }}
    }});
    const cntBtn = document.getElementById('cntEncerrandoBtn');
    if (cntBtn && urlsEncerrando.size > 0) cntBtn.textContent = urlsEncerrando.size;
  }})();

  // 2) Controle da Barra Lateral de Filtros (Drawer Off-Canvas)
  const sidebarFiltros = document.getElementById('painelFiltrosSp');
  const backdropSidebarFiltros = document.getElementById('backdropSidebarFiltros');
  const btnAbrirSidebarFiltros = document.getElementById('btnAbrirSidebarFiltros');
  const btnFabFiltros = document.getElementById('btnFabFiltros');
  const btnFecharSidebarFiltros = document.getElementById('btnFecharSidebarFiltros');
  const btnAplicarSidebar = document.getElementById('btnAplicarSidebar');
  const btnLimparSidebar = document.getElementById('btnLimparSidebar');

  function abrirSidebarFiltros() {{
    if (!sidebarFiltros || !backdropSidebarFiltros) return;
    sidebarFiltros.classList.add('aberto');
    backdropSidebarFiltros.classList.add('aberto');
    document.body.style.overflow = 'hidden';
    atualizarUIFiltrosSidebar();
  }}

  function fecharSidebarFiltros() {{
    if (!sidebarFiltros || !backdropSidebarFiltros) return;
    sidebarFiltros.classList.remove('aberto');
    backdropSidebarFiltros.classList.remove('aberto');
    document.body.style.overflow = '';
  }}

  if (btnAbrirSidebarFiltros) btnAbrirSidebarFiltros.addEventListener('click', abrirSidebarFiltros);
  if (btnFabFiltros) btnFabFiltros.addEventListener('click', abrirSidebarFiltros);
  if (btnFecharSidebarFiltros) btnFecharSidebarFiltros.addEventListener('click', fecharSidebarFiltros);
  if (backdropSidebarFiltros) backdropSidebarFiltros.addEventListener('click', fecharSidebarFiltros);

  document.addEventListener('keydown', (e) => {{
    if (e.key === 'Escape' && sidebarFiltros && sidebarFiltros.classList.contains('aberto')) {{
      fecharSidebarFiltros();
    }}
  }});

  // Botão de Recolher / Expandir Cargos Rápidos na Barra Lateral
  const btnToggleCargosRapidos = document.getElementById('btnToggleCargosRapidos');
  const rowCargosRapidos = document.getElementById('rowCargosRapidos');
  if (btnToggleCargosRapidos && rowCargosRapidos) {{
    btnToggleCargosRapidos.addEventListener('click', () => {{
      const recolhido = rowCargosRapidos.classList.toggle('recolhido');
      rowCargosRapidos.style.setProperty('display', recolhido ? 'none' : 'flex', recolhido ? 'important' : '');
      btnToggleCargosRapidos.innerHTML = recolhido ? '⚡ Mostrar {len(CARGOS_RAPIDOS_MAX)} Cargos Rápidos' : '🔼 Recolher Cargos Rápidos';
    }});
  }}

  // Botão de Recolher / Expandir Estados (UF) na Barra Lateral
  const btnToggleUfs = document.getElementById('btnToggleUfs');
  const rowUfsBrasil = document.getElementById('rowUfsBrasil');
  if (btnToggleUfs && rowUfsBrasil) {{
    btnToggleUfs.addEventListener('click', () => {{
      const recolhido = rowUfsBrasil.classList.toggle('recolhido');
      rowUfsBrasil.style.setProperty('display', recolhido ? 'none' : 'flex', recolhido ? 'important' : '');
      btnToggleUfs.innerHTML = recolhido ? '🌍 Mostrar Estados' : '🔼 Recolher Estados';
    }});
  }}

  // 3) Navegação entre as Abas (Buscar Cargo, Fisioterapia, Nível Médio, Nível Superior e Provas Anteriores)
  const tabItems = document.querySelectorAll('.tab-item');
  function abrirTab(tab) {{
    tabItems.forEach(item => item.classList.toggle('ativo', item.dataset.tab === tab));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('ativo', p.id === tab));
    const isProvas = (tab === 'provas_anteriores');
    const isBusca = (tab === 'busca_cargo');

    const controlBar = document.getElementById('barraControlePrincipal');
    if (controlBar) controlBar.style.display = isProvas ? 'none' : 'flex';
    if (btnFabFiltros) btnFabFiltros.style.display = isProvas ? 'none' : 'inline-flex';

    const wrapBusca = document.getElementById('wrapBuscaCargoToolbar');
    if (wrapBusca) wrapBusca.style.display = isBusca ? 'block' : 'none';

    const sidebarExtra = document.getElementById('blocoBuscaCargo');
    if (sidebarExtra) sidebarExtra.style.display = isBusca ? 'block' : 'none';

    history.replaceState(null, '', '#' + tab);
    if (isBusca) renderizarBuscaCargo();
    if (isProvas) renderizarProvasAnteriores();
    atualizarUIFiltrosSidebar();
  }}
  tabItems.forEach(item => item.addEventListener('click', () => abrirTab(item.dataset.tab)));
  const hashInicial = location.hash.slice(1);
  if (['fisio', 'medio_todos', 'superior_sp', 'provas_anteriores', 'busca_cargo'].includes(hashInicial)) {{
    abrirTab(hashInicial);
  }}

  // 4) Filtros Unificados (Funcionam tanto nas abas de SP quanto na aba "Buscar Cargo")
  const estadoFiltros = {{
    encerrando: '',
    novo: '',
    kmRef: '',
    faixa: '',
    escolaridade: '',
    vagas: 'todas',
    regime: '',
    horas: '',
    cidade: '',
    ordem: 'padrao'
  }};

  function contarFiltrosAtivos() {{
    let cnt = 0;
    if (estadoFiltros.encerrando) cnt++;
    if (estadoFiltros.novo) cnt++;
    if (estadoFiltros.kmRef && cidadeRef) cnt++;
    if (estadoFiltros.faixa) cnt++;
    if (estadoFiltros.escolaridade) cnt++;
    if (estadoFiltros.vagas && estadoFiltros.vagas !== 'todas') cnt++;
    if (estadoFiltros.regime) cnt++;
    if (estadoFiltros.horas) cnt++;
    if (estadoFiltros.cidade) cnt++;
    if (estadoFiltros.ordem && estadoFiltros.ordem !== 'padrao') cnt++;
    if (ufSelecionada && ufSelecionada !== 'TODOS') cnt++;
    const termo = (inputCargo ? inputCargo.value.trim() : '');
    if (termo) cnt++;
    return cnt;
  }}

  function obterTotalConcursosVisiveis() {{
    const abaAtiva = document.querySelector('.tab-panel.ativo');
    if (!abaAtiva) return 0;
    if (abaAtiva.id === 'busca_cargo') {{
      const cnt = document.getElementById('countBuscaCargo');
      return cnt ? Number(cnt.textContent) || 0 : 0;
    }}
    const secCount = abaAtiva.querySelector('.sec-count');
    return secCount ? Number(secCount.textContent) || 0 : 0;
  }}

  function recalcularContadoresBotoesFiltro() {{
    const abaAtiva = document.querySelector('.tab-panel.ativo');
    const isBusca = !abaAtiva || abaAtiva.id === 'busca_cargo';
    const isProvas = abaAtiva && abaAtiva.id === 'provas_anteriores';
    if (isProvas) return;

    function setBtnCount(btn, count) {{
      if (!btn) return;
      let span = btn.querySelector('.mini-cnt');
      if (!span) {{
        span = document.createElement('span');
        span.className = 'mini-cnt';
        btn.appendChild(span);
      }}
      span.textContent = count;
      btn.classList.toggle('sem-resultados', count === 0 && !btn.classList.contains('ativo'));
    }}

    if (isBusca) {{
      const termoRaw = (inputCargo ? inputCargo.value : '').trim();
      const termo = normStr(termoRaw);

      function passaItem(item, overrideFiltros = {{}}, overrideUf, overrideTermo) {{
        const f = Object.assign({{}}, estadoFiltros, overrideFiltros);
        const uf = (overrideUf !== undefined) ? overrideUf : ufSelecionada;
        if (uf && uf !== 'TODOS' && item.uf !== uf) return false;

        if (f.encerrando === '1' && !item.encerrando) return false;
        if (f.novo === '1' && !item.novo) return false;
        if (f.cidade && item.cidade !== f.cidade) return false;
        if (f.kmRef && cidadeRef) {{
          const km = kmDaReferencia(item.lat, item.lon);
          if (km == null || km > Number(f.kmRef)) return false;
        }}
        if (f.faixa) {{
          const t = (overrideTermo !== undefined) ? overrideTermo : termo;
          const resolved = resolverSalarioParaCargo(item, t, null, f.escolaridade);
          if (resolved.especifico) {{
            if (calcFaixaSlug(resolved.salario_num, resolved.salario_total) !== f.faixa) return false;
          }} else if (item.salario_min && item.salario_max && item.salario_min < item.salario_max) {{
            const minFaixa = calcFaixaSlug(item.salario_min, item.salario_min);
            const maxFaixa = calcFaixaSlug(item.salario_max, item.salario_total || item.salario_max);
            const faixasOrdem = ['ate2500', '2500a3500', '3500a5000', 'acima5000'];
            const idxF = faixasOrdem.indexOf(f.faixa);
            const idxMin = faixasOrdem.indexOf(minFaixa);
            const idxMax = faixasOrdem.indexOf(maxFaixa);
            if (idxF !== -1 && idxMin !== -1 && idxMax !== -1) {{
              if (idxF < idxMin || idxF > idxMax) return false;
            }} else if (item.faixa !== f.faixa) {{
              return false;
            }}
          }} else if (item.faixa !== f.faixa) {{
            return false;
          }}
        }}
        if (f.escolaridade) {{
          const nivs = (item.niveis_tokens || '').split(',');
          if (!nivs.includes(f.escolaridade)) return false;
        }}
        if (f.vagas && f.vagas !== 'todas') {{
          const v = Number(item.vagas_im || 0);
          if (f.vagas === 'cr' && v > 0) return false;
          if (f.vagas !== 'cr' && v < Number(f.vagas)) return false;
        }}
        if (f.regime && item.regime_cat !== f.regime) return false;
        if (f.horas && Number(item.horas_num || 40) > Number(f.horas)) return false;

        const t = (overrideTermo !== undefined) ? normStr(overrideTermo) : termo;
        if (t) {{
          let matched = false;
          for (const cg of (item.cargos || [])) {{
            if (normStr(cg).includes(t)) {{ matched = true; break; }}
          }}
          if (!matched && normStr((item.orgao || '') + ' ' + (item.titulo || '') + ' ' + (item.cargos_resumo || '')).includes(t)) {{
            matched = true;
          }}
          if (!matched && t.length >= 4 && (item.termos_formacao || []).some(tf => normStr(tf).includes(t))) {{
            matched = true;
          }}
          if (!matched) return false;
        }}
        return true;
      }}

      // 1) Contagem exata do estado atual
      let totalAtual = 0;
      for (let i = 0; i < CATALOGO_BRASIL.length; i++) {{
        if (passaItem(CATALOGO_BRASIL[i])) totalAtual++;
      }}
      const countSpan = document.getElementById('sidebarCountEncontrados');
      if (countSpan) countSpan.textContent = totalAtual.toLocaleString('pt-BR');
      const botaoSpan = document.getElementById('sidebarCountBotao');
      if (botaoSpan) botaoSpan.textContent = totalAtual.toLocaleString('pt-BR');

      // 2) Atualiza cada botão [data-filter] na barra lateral
      document.querySelectorAll('#painelFiltrosSp [data-filter]').forEach(btn => {{
        const chave = btn.dataset.filter;
        const val = btn.dataset.val;
        if (chave === 'ordem') return;

        let c = 0;
        const override = {{}};
        override[chave] = val;
        for (let i = 0; i < CATALOGO_BRASIL.length; i++) {{
          if (passaItem(CATALOGO_BRASIL[i], override)) c++;
        }}
        setBtnCount(btn, c);
      }});

      // 3) Atualiza cada botão de UF (.uf-btn)
      document.querySelectorAll('#painelFiltrosSp .uf-btn').forEach(btn => {{
        const uf = btn.dataset.uf;
        let c = 0;
        for (let i = 0; i < CATALOGO_BRASIL.length; i++) {{
          if (passaItem(CATALOGO_BRASIL[i], {{}}, uf)) c++;
        }}
        setBtnCount(btn, c);
      }});

      // 4) Atualiza cada botão de Cargo Rápido (.cargo-quick)
      document.querySelectorAll('#painelFiltrosSp .cargo-quick').forEach(btn => {{
        const cg = btn.dataset.cargo;
        let c = 0;
        for (let i = 0; i < CATALOGO_BRASIL.length; i++) {{
          if (passaItem(CATALOGO_BRASIL[i], {{}}, undefined, cg)) c++;
        }}
        setBtnCount(btn, c);
      }});

    }} else {{
      // Para as abas de SP
      const panel = abaAtiva;
      const cards = Array.from(panel.querySelectorAll('.card'));

      function passaCard(c, overrideFiltros = {{}}) {{
        const f = Object.assign({{}}, estadoFiltros, overrideFiltros);
        const soEncerrando = f.encerrando === '1';
        const soNovos = f.novo === '1';
        const maxRef = (f.kmRef && cidadeRef) ? Number(f.kmRef) : null;
        const faixa = f.faixa;
        const esc = f.escolaridade;
        const vagasMode = f.vagas;
        const regime = f.regime;
        const maxHoras = f.horas ? Number(f.horas) : null;
        const cid = f.cidade;

        if (soEncerrando && c.dataset.encerrando !== '1') return false;
        if (soNovos && c.dataset.novo !== '1') return false;
        if (cid && c.dataset.cidade !== cid) return false;
        if (maxRef !== null && Number(c.dataset.kmRef) > maxRef) return false;
        if (faixa && c.dataset.faixa !== faixa) return false;
        if (esc) {{
          const niveis = (c.dataset.niveisLista || c.dataset.escolaridade || '').split(',');
          if (!niveis.includes(esc) && c.dataset.escolaridade !== esc) return false;
        }}
        if (vagasMode && vagasMode !== 'todas') {{
          const v = Number(c.dataset.vagas);
          if (vagasMode === 'cr' && v > 0) return false;
          if (vagasMode !== 'cr' && v < Number(vagasMode)) return false;
        }}
        if (regime && c.dataset.regime !== regime) return false;
        if (maxHoras !== null && Number(c.dataset.horas) > maxHoras) return false;
        return true;
      }}

      let totalAtual = 0;
      cards.forEach(c => {{ if (passaCard(c)) totalAtual++; }});
      const countSpan = document.getElementById('sidebarCountEncontrados');
      if (countSpan) countSpan.textContent = totalAtual.toLocaleString('pt-BR');
      const botaoSpan = document.getElementById('sidebarCountBotao');
      if (botaoSpan) botaoSpan.textContent = totalAtual.toLocaleString('pt-BR');

      document.querySelectorAll('#painelFiltrosSp [data-filter]').forEach(btn => {{
        const chave = btn.dataset.filter;
        const val = btn.dataset.val;
        if (chave === 'ordem') return;

        let c = 0;
        const override = {{}};
        override[chave] = val;
        cards.forEach(card => {{ if (passaCard(card, override)) c++; }});
        setBtnCount(btn, c);
      }});
    }}
  }}

  function atualizarUIFiltrosSidebar() {{
    recalcularContadoresBotoesFiltro();

    const ativosCnt = contarFiltrosAtivos();
    const badgeTopo = document.getElementById('badgeFiltrosAtivos');
    const badgeFab = document.getElementById('badgeFabFiltrosAtivos');
    if (badgeTopo) {{
      badgeTopo.textContent = ativosCnt;
      badgeTopo.style.display = ativosCnt > 0 ? 'inline-flex' : 'none';
    }}
    if (badgeFab) {{
      badgeFab.textContent = ativosCnt;
      badgeFab.style.display = ativosCnt > 0 ? 'inline-flex' : 'none';
    }}

    renderizarChipsFiltrosAtivos();
  }}

  function renderizarChipsFiltrosAtivos() {{
    const container = document.getElementById('barraFiltrosAtivos');
    const chipsEl = document.getElementById('chipsFiltrosAtivos');
    if (!container || !chipsEl) return;

    const chips = [];
    const termo = (inputCargo ? inputCargo.value.trim() : '');
    if (termo) {{
      chips.push({{
        label: `🎯 Cargo: "${{termo}}"`,
        limpar: () => {{
          inputCargo.value = '';
          const btnClear = document.getElementById('btnLimparCargo');
          if (btnClear) btnClear.style.display = 'none';
          document.querySelectorAll('.cargo-quick').forEach(b => b.classList.toggle('ativo', b.dataset.cargo === ''));
          renderizarBuscaCargo();
          atualizarUIFiltrosSidebar();
        }}
      }});
    }}
    if (ufSelecionada && ufSelecionada !== 'TODOS') {{
      chips.push({{
        label: `📍 Estado: ${{ufSelecionada}}`,
        limpar: () => {{
          ufSelecionada = 'TODOS';
          document.querySelectorAll('.uf-btn').forEach(b => b.classList.toggle('ativo', b.dataset.uf === 'TODOS'));
          renderizarBuscaCargo();
          atualizarUIFiltrosSidebar();
        }}
      }});
    }}
    if (estadoFiltros.encerrando) {{
      chips.push({{
        label: '⏳ Inscrições Encerrando',
        limpar: () => {{
          estadoFiltros.encerrando = '';
          sincronizarBotoesFiltro();
          aplicarFiltrosSp();
          atualizarUIFiltrosSidebar();
        }}
      }});
    }}
    if (estadoFiltros.novo) {{
      chips.push({{
        label: '✨ Concursos Novos (24h)',
        limpar: () => {{
          estadoFiltros.novo = '';
          sincronizarBotoesFiltro();
          aplicarFiltrosSp();
          atualizarUIFiltrosSidebar();
        }}
      }});
    }}
    if (estadoFiltros.kmRef && cidadeRef) {{
      chips.push({{
        label: `🚗 Até ${{estadoFiltros.kmRef}}km de ${{cidadeRef.nome.split('-')[0].trim()}}`,
        limpar: () => {{
          estadoFiltros.kmRef = '';
          sincronizarBotoesFiltro();
          aplicarFiltrosSp();
          atualizarUIFiltrosSidebar();
        }}
      }});
    }}
    if (estadoFiltros.faixa) {{
      const mapa = {{ ate2500: 'Até R$ 2.500', '2500a3500': 'R$ 2.500 a 3.500', '3500a5000': 'R$ 3.500 a 5.000', acima5000: '> R$ 5.000' }};
      chips.push({{
        label: `💵 ${{mapa[estadoFiltros.faixa] || estadoFiltros.faixa}}`,
        limpar: () => {{
          estadoFiltros.faixa = '';
          sincronizarBotoesFiltro();
          aplicarFiltrosSp();
          atualizarUIFiltrosSidebar();
        }}
      }});
    }}
    if (estadoFiltros.escolaridade) {{
      const mapa = {{ fundamental: '📘 Fundamental', medio: '📗 Médio', medio_tecnico: '🛠️ Técnico', superior: '🎓 Superior' }};
      chips.push({{
        label: mapa[estadoFiltros.escolaridade] || estadoFiltros.escolaridade,
        limpar: () => {{
          estadoFiltros.escolaridade = '';
          sincronizarBotoesFiltro();
          aplicarFiltrosSp();
          atualizarUIFiltrosSidebar();
        }}
      }});
    }}
    if (estadoFiltros.vagas && estadoFiltros.vagas !== 'todas') {{
      const mapa = {{ '1': '≥ 1 Vaga', '3': '≥ 3 Vagas', '5': '≥ 5 Vagas', cr: 'Somente CR' }};
      chips.push({{
        label: `👥 ${{mapa[estadoFiltros.vagas] || estadoFiltros.vagas}}`,
        limpar: () => {{
          estadoFiltros.vagas = 'todas';
          sincronizarBotoesFiltro();
          aplicarFiltrosSp();
          atualizarUIFiltrosSidebar();
        }}
      }});
    }}
    if (estadoFiltros.regime) {{
      const mapa = {{ estatutario: 'Estatutário', clt: 'CLT', outros: 'Residência/Seletivo' }};
      chips.push({{
        label: `🏛️ ${{mapa[estadoFiltros.regime] || estadoFiltros.regime}}`,
        limpar: () => {{
          estadoFiltros.regime = '';
          sincronizarBotoesFiltro();
          aplicarFiltrosSp();
          atualizarUIFiltrosSidebar();
        }}
      }});
    }}
    if (estadoFiltros.horas) {{
      chips.push({{
        label: `⏰ Até ${{estadoFiltros.horas}}h/sem`,
        limpar: () => {{
          estadoFiltros.horas = '';
          sincronizarBotoesFiltro();
          aplicarFiltrosSp();
          atualizarUIFiltrosSidebar();
        }}
      }});
    }}
    if (estadoFiltros.cidade) {{
      chips.push({{
        label: `🏙️ ${{estadoFiltros.cidade}}`,
        limpar: () => {{
          estadoFiltros.cidade = '';
          sincronizarBotoesFiltro();
          aplicarFiltrosSp();
          atualizarUIFiltrosSidebar();
        }}
      }});
    }}
    if (estadoFiltros.ordem && estadoFiltros.ordem !== 'padrao') {{
      const mapa = {{ inscricao: 'Inscrição', salario: 'Maior Salário', proximo: 'Mais perto', vagas: 'Mais vagas', prova: 'Prova' }};
      chips.push({{
        label: `↕️ ${{mapa[estadoFiltros.ordem] || estadoFiltros.ordem}}`,
        limpar: () => {{
          estadoFiltros.ordem = 'padrao';
          sincronizarBotoesFiltro();
          aplicarFiltrosSp();
          atualizarUIFiltrosSidebar();
        }}
      }});
    }}

    if (chips.length === 0) {{
      container.style.display = 'none';
      chipsEl.innerHTML = '';
      return;
    }}

    container.style.display = 'flex';
    chipsEl.innerHTML = chips.map((c, idx) => `
      <button type="button" class="af-chip" data-chip-idx="${{idx}}">
        <span>${{escHtml(c.label)}}</span>
        <span aria-hidden="true">✕</span>
      </button>
    `).join('');

    chipsEl.querySelectorAll('[data-chip-idx]').forEach(btn => {{
      btn.addEventListener('click', () => {{
        const idx = Number(btn.dataset.chipIdx);
        if (chips[idx] && chips[idx].limpar) chips[idx].limpar();
      }});
    }});
  }}

  const btnLimparRapido = document.getElementById('btnLimparFiltrosRapido');
  if (btnLimparRapido) {{
    btnLimparRapido.addEventListener('click', () => limparTodosFiltros());
  }}

  function sincronizarBotoesFiltro() {{
    document.querySelectorAll('[data-filter]').forEach(btn => {{
      const chave = btn.dataset.filter;
      const val = btn.dataset.val;
      btn.classList.toggle('ativo', estadoFiltros[chave] === val);
    }});
  }}

  function mostrarFeedbackFiltro() {{
    const el = document.getElementById('msgFiltroAplicado');
    if (!el) return;
    el.classList.add('visivel');
    clearTimeout(el._timer);
    el._timer = setTimeout(() => el.classList.remove('visivel'), 1800);
  }}

  function cardPassaNosFiltros(c) {{
    const soEncerrando = estadoFiltros.encerrando === '1';
    const soNovos = estadoFiltros.novo === '1';
    const maxRef = (estadoFiltros.kmRef && cidadeRef) ? Number(estadoFiltros.kmRef) : null;
    const faixa = estadoFiltros.faixa;
    const esc = estadoFiltros.escolaridade;
    const vagasMode = estadoFiltros.vagas;
    const regime = estadoFiltros.regime;
    const maxHoras = estadoFiltros.horas ? Number(estadoFiltros.horas) : null;
    const cid = estadoFiltros.cidade;

    if (soEncerrando && c.dataset.encerrando !== '1') return false;
    if (soNovos && c.dataset.novo !== '1') return false;
    if (cid && c.dataset.cidade !== cid) return false;
    if (maxRef !== null && Number(c.dataset.kmRef) > maxRef) return false;
    if (faixa && c.dataset.faixa !== faixa) return false;
    if (esc) {{
      const niveis = (c.dataset.niveisLista || c.dataset.escolaridade || '').split(',');
      if (!niveis.includes(esc) && c.dataset.escolaridade !== esc) return false;
    }}
    if (vagasMode !== 'todas') {{
      const v = Number(c.dataset.vagas);
      if (vagasMode === 'cr' && v > 0) return false;
      if (vagasMode !== 'cr' && v < Number(vagasMode)) return false;
    }}
    if (regime && c.dataset.regime !== regime) return false;
    if (maxHoras !== null && Number(c.dataset.horas) > maxHoras) return false;
    return true;
  }}

  function aplicarFiltrosSp(comFeedback = false) {{
    const ordem = estadoFiltros.ordem;

    ['fisio', 'medio_todos', 'superior_sp'].forEach(panelId => {{
      const panel = document.getElementById(panelId);
      if (!panel) return;
      const grid = panel.querySelector('.grid');
      const cards = Array.from(grid.querySelectorAll('.card'));
      let visiveis = 0;

      cards.forEach(c => {{
        const ok = cardPassaNosFiltros(c);
        c.style.display = ok ? '' : 'none';
        if (ok) visiveis++;
      }});

      if (ordem !== 'padrao') {{
        cards.sort((a, b) => {{
          if (ordem === 'proximo') return Number(a.dataset.kmRef || 9999) - Number(b.dataset.kmRef || 9999);
          if (ordem === 'salario') return Number(b.dataset.salario) - Number(a.dataset.salario);
          if (ordem === 'vagas') return Number(b.dataset.vagas) - Number(a.dataset.vagas);
          if (ordem === 'prova') return (a.dataset.prova || '').localeCompare(b.dataset.prova || '');
          if (ordem === 'inscricao') return (a.dataset.inscricao || '').localeCompare(b.dataset.inscricao || '');
          return 0;
        }});
        cards.forEach(c => grid.appendChild(c));
      }} else {{
        cards.sort((a, b) => Number(a.dataset.idx || 0) - Number(b.dataset.idx || 0));
        cards.forEach(c => grid.appendChild(c));
      }}

      const secCount = panel.querySelector('.sec-count');
      if (secCount) secCount.textContent = visiveis;
      const tabCnt = document.querySelector(`[data-cnt-for="${{panelId}}"]`);
      if (tabCnt) tabCnt.textContent = visiveis;
      panel.querySelector('.vazio').style.display = visiveis === 0 ? 'block' : 'none';
    }});

    renderizarBuscaCargo();
    const msgRef = document.getElementById('msgCidadeRef');
    if (msgRef && estadoFiltros.kmRef && !cidadeRef) {{
      msgRef.textContent = '⚠️ Escolha primeiro a sua cidade de referência para filtrar por distância.';
    }}
    if (comFeedback) mostrarFeedbackFiltro();
    atualizarUIFiltrosSidebar();
  }}

  document.querySelectorAll('[data-filter]').forEach(btn => {{
    btn.addEventListener('click', () => {{
      const chave = btn.dataset.filter;
      const val = btn.dataset.val;
      if (chave === 'novo' && val === '1') {{
        estadoFiltros.novo = estadoFiltros.novo === '1' ? '' : '1';
      }} else if (chave === 'encerrando' && val === '1') {{
        estadoFiltros.encerrando = estadoFiltros.encerrando === '1' ? '' : '1';
      }} else {{
        estadoFiltros[chave] = val;
      }}
      sincronizarBotoesFiltro();
      aplicarFiltrosSp(false);
    }});
  }});

  function limparTodosFiltros() {{
    estadoFiltros.encerrando = '';
    estadoFiltros.novo = '';
    estadoFiltros.kmRef = '';
    estadoFiltros.faixa = '';
    estadoFiltros.escolaridade = '';
    estadoFiltros.vagas = 'todas';
    estadoFiltros.regime = '';
    estadoFiltros.horas = '';
    estadoFiltros.cidade = '';
    estadoFiltros.ordem = 'padrao';
    ufSelecionada = 'TODOS';
    if (inputCargo) inputCargo.value = '';
    const btnClear = document.getElementById('btnLimparCargo');
    if (btnClear) btnClear.style.display = 'none';
    document.querySelectorAll('.cargo-quick').forEach(b => b.classList.toggle('ativo', b.dataset.cargo === ''));
    document.querySelectorAll('.uf-btn').forEach(b => b.classList.toggle('ativo', b.dataset.uf === 'TODOS'));
    sincronizarBotoesFiltro();
    aplicarFiltrosSp(true);
    atualizarUIFiltrosSidebar();
  }}

  if (btnAplicarSidebar) {{
    btnAplicarSidebar.addEventListener('click', () => {{
      aplicarFiltrosSp(true);
      fecharSidebarFiltros();
      const abaAtiva = document.querySelector('.tab-panel.ativo');
      if (abaAtiva) abaAtiva.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }});
  }}
  if (btnLimparSidebar) {{
    btnLimparSidebar.addEventListener('click', () => limparTodosFiltros());
  }}

  // 5) Aba 4: Provas Anteriores por BANCA e CARGO
  const inputProvaCargo = document.getElementById('inputProvaCargo');
  const inputProvaBanca = document.getElementById('inputProvaBanca');
  const gridProvasBancaCargo = document.getElementById('gridProvasBancaCargo');
  const countProvasBancaCargo = document.getElementById('countProvasBancaCargo');

  function montarUrlProva(cargoStr, bancaStr) {{
    const cSlug = normSlug(cargoStr);
    const bSlug = normSlug(bancaStr);
    if (cSlug && bSlug) return `https://www.pciconcursos.com.br/provas/${{cSlug}}-${{bSlug}}`;
    if (cSlug) return `https://www.pciconcursos.com.br/provas/${{cSlug}}`;
    if (bSlug) return `https://www.pciconcursos.com.br/provas/${{bSlug}}`;
    return 'https://www.pciconcursos.com.br/provas/';
  }}

  function renderizarProvasAnteriores() {{
    const qCargo = normStr(inputProvaCargo.value.trim());
    const qBanca = normStr(inputProvaBanca.value.trim());

    let lista = CATALOGO_PROVAS.filter(p => {{
      if (qCargo && !normStr(p.cargo).includes(qCargo)) return false;
      if (qBanca && !normStr(p.banca + ' ' + p.banca_original).includes(qBanca)) return false;
      return true;
    }});

    if ((qCargo || qBanca) && lista.length === 0) {{
      const cNome = inputProvaCargo.value.trim() || 'Todos os Cargos';
      const bNome = inputProvaBanca.value.trim() || 'Todas as Bancas';
      lista = [{{
        cargo: cNome,
        banca: bNome,
        banca_original: bNome,
        escolaridade: 'Busca Personalizada por Banca e Cargo',
        url_combo: montarUrlProva(inputProvaCargo.value.trim(), inputProvaBanca.value.trim()),
        url_cargo: montarUrlProva(inputProvaCargo.value.trim(), ''),
        url_banca: inputProvaBanca.value.trim() ? montarUrlProva('', inputProvaBanca.value.trim()) : ''
      }}];
    }}

    countProvasBancaCargo.textContent = lista.length;

    gridProvasBancaCargo.innerHTML = lista.map(p => {{
      const btnBanca = p.url_banca
        ? `<a class="btn-link" href="${{safeUrl(p.url_banca)}}" target="_blank" rel="noopener noreferrer">🏛️ Todas da Banca (${{escHtml(p.banca)}})</a>`
        : '';
      return `
        <article class="card">
          <header class="card-head">
            <div class="head-top">
              <h3><a href="${{safeUrl(p.url_combo)}}" target="_blank" rel="noopener noreferrer">📝 ${{escHtml(p.cargo)}} — Banca ${{escHtml(p.banca)}}</a></h3>
              <span class="esc-badge esc-sup">${{escHtml(p.escolaridade)}}</span>
            </div>
            <p class="titulo">Busca de provas anteriores exclusivamente por <b>Cargo</b> e <b>Banca Organizadora</b> (sem filtro de cidade)</p>
          </header>
          <div class="cargo-banner">
            <div class="cargo-nome">🎯 <strong>Cargo: ${{escHtml(p.cargo)}}</strong></div>
            <span class="badge-vagas">Banca: ${{escHtml(p.banca_original)}}</span>
          </div>
          <div class="info-grid">
            <div class="info-box destaque-sal">
              <span class="lbl">💼 Cargo Pesquisado</span>
              <strong class="val-sm" style="color:var(--br-green-dark);">${{escHtml(p.cargo)}}</strong>
            </div>
            <div class="info-box destaque-prova">
              <span class="lbl">🏛️ Banca Organizadora</span>
              <strong class="val-sm">${{escHtml(p.banca_original)}}</strong>
            </div>
          </div>
          <div class="links-row" style="margin-top:auto;">
            <a class="btn-link primario" href="${{safeUrl(p.url_combo)}}" target="_blank" rel="noopener noreferrer">
              📥 Provas: ${{escHtml(p.cargo)}} + ${{escHtml(p.banca)}}
            </a>
            <a class="btn-link" href="${{safeUrl(p.url_cargo)}}" target="_blank" rel="noopener noreferrer">
              📚 Todas do Cargo (${{escHtml(p.cargo)}})
            </a>
            ${{btnBanca}}
          </div>
        </article>`;
    }}).join('');
  }}

  document.querySelectorAll('.prova-banca-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      inputProvaBanca.value = btn.dataset.banca;
      document.querySelectorAll('.prova-banca-btn').forEach(b => b.classList.toggle('ativo', b === btn));
      renderizarProvasAnteriores();
    }});
  }});
  document.querySelectorAll('.prova-cargo-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      inputProvaCargo.value = btn.dataset.cargo;
      document.querySelectorAll('.prova-cargo-btn').forEach(b => b.classList.toggle('ativo', b === btn));
      renderizarProvasAnteriores();
    }});
  }});
  if (inputProvaCargo) inputProvaCargo.addEventListener('input', () => renderizarProvasAnteriores());
  if (inputProvaBanca) inputProvaBanca.addEventListener('input', () => renderizarProvasAnteriores());
  document.getElementById('btnAbrirProvaDireta').addEventListener('click', () => {{
    window.open(montarUrlProva(inputProvaCargo.value.trim(), inputProvaBanca.value.trim()), '_blank', 'noopener');
  }});
  document.getElementById('btnLimparProvas').addEventListener('click', () => {{
    inputProvaCargo.value = '';
    inputProvaBanca.value = '';
    document.querySelectorAll('.prova-banca-btn').forEach(b => b.classList.toggle('ativo', b.dataset.banca === ''));
    document.querySelectorAll('.prova-cargo-btn').forEach(b => b.classList.toggle('ativo', b.dataset.cargo === ''));
    renderizarProvasAnteriores();
  }});
  renderizarProvasAnteriores();

  // 6) Aba 5: Busca por Outro Cargo com TODOS os Filtros Integrados
  let ufSelecionada = 'TODOS';
  const inputCargo = document.getElementById('inputCargoEspecifico');
  const gridBusca = document.getElementById('gridBuscaCargo');
  const vazioBusca = document.getElementById('vazioBuscaCargo');
  const countBuscaCargo = document.getElementById('countBuscaCargo');
  const tabCntBusca = document.querySelector('[data-cnt-for="busca_cargo"]');

  function itemBrPassaNosFiltros(item) {{
    if (estadoFiltros.encerrando === '1' && !item.encerrando) return false;
    if (estadoFiltros.novo === '1' && !item.novo) return false;
    if (estadoFiltros.cidade && item.cidade !== estadoFiltros.cidade) return false;
    if (estadoFiltros.kmRef && cidadeRef) {{
      const kmRefItem = kmDaReferencia(item.lat, item.lon);
      if (kmRefItem == null || kmRefItem > Number(estadoFiltros.kmRef)) return false;
    }}
    if (estadoFiltros.faixa) {{
      const termoRaw = (inputCargo ? inputCargo.value : '').trim();
      const resolved = resolverSalarioParaCargo(item, termoRaw, null, estadoFiltros.escolaridade);
      if (resolved.especifico) {{
        if (calcFaixaSlug(resolved.salario_num, resolved.salario_total) !== estadoFiltros.faixa) return false;
      }} else if (item.salario_min && item.salario_max && item.salario_min < item.salario_max) {{
        const minFaixa = calcFaixaSlug(item.salario_min, item.salario_min);
        const maxFaixa = calcFaixaSlug(item.salario_max, item.salario_total || item.salario_max);
        const faixasOrdem = ['ate2500', '2500a3500', '3500a5000', 'acima5000'];
        const idxF = faixasOrdem.indexOf(estadoFiltros.faixa);
        const idxMin = faixasOrdem.indexOf(minFaixa);
        const idxMax = faixasOrdem.indexOf(maxFaixa);
        if (idxF !== -1 && idxMin !== -1 && idxMax !== -1) {{
          if (idxF < idxMin || idxF > idxMax) return false;
        }} else if (item.faixa !== estadoFiltros.faixa) {{
          return false;
        }}
      }} else if (item.faixa !== estadoFiltros.faixa) {{
        return false;
      }}
    }}
    if (estadoFiltros.escolaridade) {{
      const nivs = (item.niveis_tokens || '').split(',');
      if (!nivs.includes(estadoFiltros.escolaridade)) return false;
    }}
    if (estadoFiltros.vagas !== 'todas') {{
      const v = Number(item.vagas_im || 0);
      if (estadoFiltros.vagas === 'cr' && v > 0) return false;
      if (estadoFiltros.vagas !== 'cr' && v < Number(estadoFiltros.vagas)) return false;
    }}
    if (estadoFiltros.regime && item.regime_cat !== estadoFiltros.regime) return false;
    if (estadoFiltros.horas && Number(item.horas_num || 40) > Number(estadoFiltros.horas)) return false;
    return true;
  }}

  function renderizarBuscaCargo() {{
    const termoRaw = (inputCargo.value || '').trim();
    const termo = normStr(termoRaw);

    let filtrados = [];
    for (let idx = 0; idx < CATALOGO_BRASIL.length; idx++) {{
      const item = CATALOGO_BRASIL[idx];
      if (ufSelecionada !== 'TODOS' && item.uf !== ufSelecionada) continue;
      if (!itemBrPassaNosFiltros(item)) continue;

      let cargosCasados = [];
      if (termo) {{
        for (const cg of (item.cargos || [])) {{
          if (normStr(cg).includes(termo)) cargosCasados.push(cg);
        }}
        const cabecalhoMatch = normStr(item.orgao + ' ' + item.titulo + ' ' + item.cargos_resumo).includes(termo);
        // Cargos que aceitam várias formações (ex.: Auditor Fiscal aceita Direito, Contábeis, Economia)
        const formacaoMatch = termo.length >= 4 && (item.termos_formacao || []).some(t => normStr(t).includes(termo));
        if (formacaoMatch && cargosCasados.length === 0) {{
          const multi = (item.cargos || []).filter(cg => /auditor|fiscal|controlador|analista|gestor|administrador|tribut/i.test(normStr(cg)));
          cargosCasados = multi.length > 0 ? multi : (item.cargos || []).slice(0, 3);
        }}
        if (cargosCasados.length === 0 && !cabecalhoMatch) continue;
      }} else {{
        cargosCasados = (item.cargos || []).slice(0, 4);
      }}
      filtrados.push({{ item, cargosCasados, idx }});
    }}

    const ordem = estadoFiltros.ordem;
    if (ordem !== 'padrao') {{
      filtrados.sort((a, b) => {{
        const ia = a.item, ib = b.item;
        if (ordem === 'proximo') return (kmDaReferencia(ia.lat, ia.lon) ?? 9999) - (kmDaReferencia(ib.lat, ib.lon) ?? 9999);
        if (ordem === 'salario') {{
          const resA = resolverSalarioParaCargo(ia, termo, a.cargosCasados, estadoFiltros.escolaridade);
          const resB = resolverSalarioParaCargo(ib, termo, b.cargosCasados, estadoFiltros.escolaridade);
          return (resB.salario_num ?? 0) - (resA.salario_num ?? 0);
        }}
        if (ordem === 'vagas') return (ib.vagas_im ?? 0) - (ia.vagas_im ?? 0);
        if (ordem === 'prova') return (ia.prova_iso || '9999-12-31').localeCompare(ib.prova_iso || '9999-12-31');
        if (ordem === 'inscricao') return (ia.inscricao_iso || '9999-12-31').localeCompare(ib.inscricao_iso || '9999-12-31');
        return 0;
      }});
    }}

    countBuscaCargo.textContent = filtrados.length;
    if (tabCntBusca) tabCntBusca.textContent = filtrados.length;
    vazioBusca.style.display = filtrados.length === 0 ? 'block' : 'none';

    const fatia = filtrados;
    gridBusca.innerHTML = fatia.map(({{ item, cargosCasados, idx }}) => {{
      const uid = `br-${{idx}}`;
      const resolved = resolverSalarioParaCargo(item, termo, cargosCasados, estadoFiltros.escolaridade);
      const cargoDestaque = cargosCasados.length > 0
        ? cargosCasados.slice(0, 3).join(' · ') + (cargosCasados.length > 3 ? ` (+${{cargosCasados.length - 3}})` : '')
        : (item.cargos_resumo || 'Conferir cargos no edital');

      let chips = `<span class="chip-loc">📍 ${{escHtml(item.cidade)}} (${{escHtml(item.uf)}})</span>`;
      const kmRefItem = kmDaReferencia(item.lat, item.lon);
      if (kmRefItem != null) chips += `<span class="chip-dist chip-km-ref">${{escHtml(textoDistanciaRef(kmRefItem))}}</span>`;
      const notaFormacao = item.formacoes_aceitas
        ? `<div class="req-box"><div class="req-title">🎓 Formações aceitas</div><p class="req-text">${{escHtml(item.formacoes_aceitas)}}</p></div>`
        : '';

      const badgeUrgente = item.encerrando
        ? `<span class="badge-encerrando">${{escHtml(item.aviso_inscricao)}}</span>`
        : '';

      const tagsHtml = (item.cargos || []).slice(0, 6).map(c => `<span class="cargo-tag">${{escHtml(c)}}</span>`).join('');
      const cargoParaProva = cargosCasados.length > 0 ? cargosCasados[0].split('(')[0].trim() : (termoRaw || cargoDestaque.split('·')[0].trim());
      const urlProvaDinamica = montarUrlProva(cargoParaProva, item.banca !== 'Consultar edital' ? item.banca : '');
      const selClass = comparacaoSelecionados.some(x => x.uid === uid) ? ' selecionado-comparar' : '';

      return `
        <article class="card${{item.encerrando ? ' card-urgente' : ''}}${{selClass}}"
          id="${{uid}}"
          data-uid="${{uid}}"
          data-orgao="${{escHtml(item.orgao)}}"
          data-titulo="${{escHtml(item.titulo)}}"
          data-url="${{safeUrl(item.url)}}"
          data-link-edital="${{safeUrl(item.url)}}#links"
          data-cargo="${{escHtml(cargoDestaque)}}"
          data-vagas-txt="${{escHtml(item.vagas_txt || item.vagas_salario || 'Ver edital')}}"
          data-cidade="${{escHtml(item.cidade)}}"
          data-uf="${{escHtml(item.uf)}}"
          data-lat="${{item.lat}}"
          data-lon="${{item.lon}}"
          data-km-ref="${{kmRefItem ?? 9999}}"
          data-salario="${{resolved.salario_num || 0}}"
          data-salario-total="${{resolved.salario_total || resolved.salario_num || 0}}"
          data-salario-exib="${{escHtml(resolved.salario_exib)}}"
          data-salario-det="${{escHtml(resolved.salario_det)}}"
          data-beneficios="${{escHtml(item.beneficios)}}"
          data-regime-txt="${{escHtml(item.regime)}}"
          data-carreira="${{escHtml(item.carreira)}}"
          data-jornada-txt="${{escHtml(item.jornada)}}"
          data-data-prova-txt="${{escHtml(item.data_prova)}}"
          data-banca-txt="${{escHtml(item.banca)}}"
          data-inscricao-txt="${{escHtml(item.inscricao_ate)}}"
          data-isencao-txt="${{escHtml(item.isencao)}}"
          data-requisitos-txt="Escolaridade exigida no edital: ${{escHtml(item.niveis || 'Consultar Anexo I')}}${{item.formacoes_aceitas ? ' · ' + escHtml(item.formacoes_aceitas) : ''}}"
          data-horas="${{item.horas_num || 40}}"
          data-vagas="${{item.vagas_im || 0}}">
          <header class="card-head">
            <div class="head-top">
              <h3><a href="${{safeUrl(item.url)}}" target="_blank" rel="noopener noreferrer">${{escHtml(item.orgao)}}</a></h3>
              <div class="badges-col">
                ${{badgeUrgente}}
                <span class="esc-badge esc-sup">${{escHtml(item.niveis || 'Vários Níveis')}}</span>
              </div>
            </div>
            <div class="loc-row">${{chips}}</div>
            <p class="titulo">${{escHtml(item.titulo)}}</p>
          </header>

          <div class="cargo-banner">
            <div class="cargo-nome">🎯 <strong>${{escHtml(cargoDestaque)}}</strong></div>
            <span class="badge-vagas">${{escHtml(item.vagas_txt || 'Ver edital')}}</span>
          </div>

          ${{notaFormacao}}
          <div class="info-grid">
            <div class="info-box destaque-sal">
              <span class="lbl">💰 Remuneração do Cargo (Bruto)</span>
              <strong class="val">${{escHtml(resolved.salario_exib)}}</strong>
              <small class="sub">${{escHtml(resolved.salario_det)}}</small>
            </div>
            <div class="info-box">
              <span class="lbl">🎁 Benefícios (VA / VR / VT)</span>
              <strong class="val-sm">${{escHtml(item.beneficios)}}</strong>
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
            <div class="info-box destaque-prazo${{item.encerrando ? ' prazo-urgente' : ''}}" style="grid-column: 1 / -1;">
              <span class="lbl">⏰ Inscrições até</span>
              <strong class="val-sm">${{escHtml(item.inscricao_ate)}} · ${{escHtml(item.aviso_inscricao || ('Região: ' + item.regiao))}}</strong>
            </div>
          </div>

          <div class="isencao-box">
            <div class="isencao-title">🎟️ Taxa de Inscrição &amp; Isenção</div>
            <p class="isencao-text">${{escHtml(item.isencao)}}</p>
          </div>

          ${{tagsHtml ? `<div><div class="f-label" style="font-size:.7rem;margin-bottom:4px;">📋 Principais Cargos no Edital:</div><div class="cargos-match-list">${{tagsHtml}}</div></div>` : ''}}

          <div class="links-row" style="margin-top:auto;">
            <a class="btn-link primario" href="${{safeUrl(item.url)}}#links" target="_blank" rel="noopener noreferrer">📄 Edital &amp; Anexos</a>
            <a class="btn-link" href="${{safeUrl(urlProvaDinamica)}}" target="_blank" rel="noopener noreferrer">📝 Provas (Cargo + Banca)</a>
            <button type="button" class="btn-link btn-share-card" data-share-uid="${{uid}}">📤 Compartilhar</button>
            <button type="button" class="btn-add-compare" data-compare-uid="${{uid}}">${{selClass ? '✅ Selecionado' : '➕ Adicionar para comparar'}}</button>
          </div>
        </article>`;
    }}).join('');
  }}

  const btnLimparCargo = document.getElementById('btnLimparCargo');
  inputCargo.addEventListener('input', () => {{
    if (btnLimparCargo) btnLimparCargo.style.display = inputCargo.value.trim() ? 'block' : 'none';
    document.querySelectorAll('.cargo-quick').forEach(b => {{
      b.classList.toggle('ativo', normStr(b.dataset.cargo) === normStr(inputCargo.value.trim()));
    }});
    renderizarBuscaCargo();
    atualizarUIFiltrosSidebar();
  }});
  if (btnLimparCargo) {{
    btnLimparCargo.addEventListener('click', () => {{
      inputCargo.value = '';
      btnLimparCargo.style.display = 'none';
      document.querySelectorAll('.cargo-quick').forEach(b => b.classList.toggle('ativo', b.dataset.cargo === ''));
      renderizarBuscaCargo();
      atualizarUIFiltrosSidebar();
    }});
  }}
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

  // 7) FUNÇÃO COMPARAR (Selecionar 2 Concursos e Comparar Tudo Lado a Lado)
  let modoCompararAtivo = false;
  let comparacaoSelecionados = [];
  let ultimoResumoComparacao = '';

  const btnToggleComparar = document.getElementById('btnToggleComparar');
  const barraComparar = document.getElementById('barraComparar');
  const slotComp1 = document.getElementById('slotComp1');
  const slotComp2 = document.getElementById('slotComp2');
  const btnExecutarComparar = document.getElementById('btnExecutarComparar');
  const modalComparar = document.getElementById('modalComparar');
  const corpoModalComparar = document.getElementById('corpoModalComparar');

  function lerDadosDoCard(cardEl) {{
    const d = cardEl.dataset;
    return {{
      uid: d.uid,
      orgao: d.orgao || '',
      titulo: d.titulo || '',
      url: d.url || '',
      linkEdital: d.linkEdital || d.url || '',
      cargo: d.cargo || '',
      vagasTxt: d.vagasTxt || '',
      vagasNum: Number(d.vagas || 0),
      cidade: d.cidade || '',
      uf: d.uf || 'SP',
      lat: Number(d.lat),
      lon: Number(d.lon),
      salarioBruto: Number(d.salario || 0),
      salarioTotal: Number(d.salarioTotal || d.salario || 0),
      salarioExib: d.salarioExib || '',
      salarioDet: d.salarioDet || '',
      beneficios: d.beneficios || 'Consultar edital',
      regimeTxt: d.regimeTxt || 'Consultar edital',
      carreira: d.carreira || 'Consultar edital',
      jornadaTxt: d.jornadaTxt || 'Consultar edital',
      horasNum: Number(d.horas || 40),
      dataProvaTxt: d.dataProvaTxt || 'Consultar edital',
      bancaTxt: d.bancaTxt || 'Consultar edital',
      inscricaoTxt: d.inscricaoTxt || 'Consultar edital',
      isencaoTxt: d.isencaoTxt || 'Consultar edital',
      requisitosTxt: d.requisitosTxt || 'Consultar edital'
    }};
  }}

  function atualizarUIComparacao() {{
    document.body.classList.toggle('modo-comparar', modoCompararAtivo);
    btnToggleComparar.classList.toggle('ativo', modoCompararAtivo);
    btnToggleComparar.innerHTML = modoCompararAtivo
      ? `⚖️ Função comparar ativa (${{comparacaoSelecionados.length}}/2)`
      : '⚖️ Função comparar';
    barraComparar.classList.toggle('visivel', modoCompararAtivo || comparacaoSelecionados.length > 0);

    document.querySelectorAll('.card[data-uid]').forEach(card => {{
      const uid = card.dataset.uid;
      const idx = comparacaoSelecionados.findIndex(x => x.uid === uid);
      const sel = idx !== -1;
      card.classList.toggle('selecionado-comparar', sel);
      const btn = card.querySelector('.btn-add-compare');
      if (btn) {{
        btn.innerHTML = sel ? `✅ Selecionado #${{idx + 1}} (Remover)` : '➕ Adicionar para comparar';
      }}
    }});

    [slotComp1, slotComp2].forEach((slotEl, i) => {{
      const item = comparacaoSelecionados[i];
      if (item) {{
        slotEl.classList.add('preenchido');
        slotEl.innerHTML = `
          <span>#${{i + 1}} <b>${{escHtml(item.orgao)}}</b> (${{escHtml(item.cidade)}}/${{escHtml(item.uf)}})</span>
          <button type="button" class="c-slot-rm" data-rm-idx="${{i}}" title="Remover">✕</button>`;
      }} else {{
        slotEl.classList.remove('preenchido');
        slotEl.innerHTML = i === 0
          ? '1️⃣ Clique em um concurso ou no botão <b>+ Adicionar</b>'
          : '2️⃣ Clique no segundo concurso para comparar';
      }}
    }});

    btnExecutarComparar.disabled = comparacaoSelecionados.length < 2;
  }}

  function alternarSelecaoConcurso(cardEl) {{
    if (!cardEl || !cardEl.dataset.uid) return;
    const uid = cardEl.dataset.uid;
    const existenteIdx = comparacaoSelecionados.findIndex(x => x.uid === uid);
    if (existenteIdx !== -1) {{
      comparacaoSelecionados.splice(existenteIdx, 1);
    }} else {{
      if (comparacaoSelecionados.length >= 2) {{
        comparacaoSelecionados.shift();
      }}
      comparacaoSelecionados.push(lerDadosDoCard(cardEl));
    }}
    atualizarUIComparacao();
  }}

  btnToggleComparar.addEventListener('click', () => {{
    modoCompararAtivo = !modoCompararAtivo;
    atualizarUIComparacao();
  }});

  document.getElementById('btnFecharModoComparar').addEventListener('click', () => {{
    modoCompararAtivo = false;
    comparacaoSelecionados = [];
    atualizarUIComparacao();
  }});

  barraComparar.addEventListener('click', (e) => {{
    const rmBtn = e.target.closest('[data-rm-idx]');
    if (rmBtn) {{
      const idx = Number(rmBtn.dataset.rmIdx);
      comparacaoSelecionados.splice(idx, 1);
      atualizarUIComparacao();
    }}
  }});

  function abrirModalComparativo() {{
    if (comparacaoSelecionados.length < 2) return;
    const A = comparacaoSelecionados[0];
    const B = comparacaoSelecionados[1];

    const diffBruto = Math.abs(A.salarioBruto - B.salarioBruto);
    const maiorBruto = A.salarioBruto > B.salarioBruto ? A.orgao : (B.salarioBruto > A.salarioBruto ? B.orgao : 'Empate');
    const pctBruto = (A.salarioBruto > 0 && B.salarioBruto > 0)
      ? ((diffBruto / Math.min(A.salarioBruto, B.salarioBruto)) * 100).toFixed(1) + '%'
      : '';
    const txtDiffBruto = (A.salarioBruto > 0 && B.salarioBruto > 0)
      ? (diffBruto === 0 ? 'Salários brutos idênticos' : `${{fmtBrl(diffBruto)}}/mês (${{pctBruto}}) a favor de ${{maiorBruto}} · Em 1 ano (13 salários): ${{fmtBrl(diffBruto * 13)}}`)
      : 'Conferir faixa salarial no edital';

    const diffTotal = Math.abs(A.salarioTotal - B.salarioTotal);
    const maiorTotal = A.salarioTotal > B.salarioTotal ? A.orgao : (B.salarioTotal > A.salarioTotal ? B.orgao : 'Empate');
    const txtDiffTotal = (A.salarioTotal > 0 && B.salarioTotal > 0)
      ? (diffTotal === 0 ? 'Remuneração total idêntica' : `${{fmtBrl(diffTotal)}}/mês a mais com auxílios em ${{maiorTotal}}`)
      : 'Conferir auxílios no edital';

    const valorHoraA = (A.salarioBruto > 0 && A.horasNum > 0) ? (A.salarioBruto / (A.horasNum * 4.5)) : null;
    const valorHoraB = (B.salarioBruto > 0 && B.horasNum > 0) ? (B.salarioBruto / (B.horasNum * 4.5)) : null;

    const distEntreCidades = calcularDistanciaCidadesKm(A.lat, A.lon, B.lat, B.lon);
    const txtDistCidades = distEntreCidades === 0
      ? `Mesma cidade (${{A.cidade}}/${{A.uf}})`
      : (distEntreCidades != null ? `~${{distEntreCidades}} km entre ${{A.cidade}}/${{A.uf}} e ${{B.cidade}}/${{B.uf}}` : 'Cidades em estados distintos');

    const benValA = extrairValoresBeneficios(A.beneficios);
    const benValB = extrairValoresBeneficios(B.beneficios);
    const diffBen = Math.abs(benValA - benValB);
    const txtDiffBen = (benValA > 0 || benValB > 0)
      ? `A: ${{benValA > 0 ? fmtBrl(benValA) : 'Ver edital'}} vs B: ${{benValB > 0 ? fmtBrl(benValB) : 'Ver edital'}} (Diferença quantificada: ${{fmtBrl(diffBen)}}/mês)`
      : 'Ambos conforme estatuto/edital (sem valor fixo detalhado no resumo)';

    const conflitoProva = (A.dataProvaTxt !== 'Consultar edital' && A.dataProvaTxt === B.dataProvaTxt)
      ? `⚠️ ATENÇÃO: Ambos têm prova marcada na MESMA DATA (${{A.dataProvaTxt}})!`
      : `✅ Datas diferentes (${{A.dataProvaTxt}} vs ${{B.dataProvaTxt}}) — você pode prestar os dois!`;

    // ===== Veredito direto: quem paga mais, tem mais vantagens e mais estabilidade =====
    const kmRefA = kmDaReferencia(A.lat, A.lon);
    const kmRefB = kmDaReferencia(B.lat, B.lon);
    const rotA = `${{A.orgao}} (${{A.cidade}}/${{A.uf}})`;
    const rotB = `${{B.orgao}} (${{B.cidade}}/${{B.uf}})`;
    const nomeDe = (v) => (v === 'A' ? rotA : rotB);
    function pontosEstabilidade(x) {{
      const r = normStr(x.regimeTxt);
      let pts = 0;
      if (/estatut/.test(r)) pts = 3;
      else if (/clt|celetist|emprego publico/.test(r)) pts = 1;
      const c = normStr(x.carreira);
      if (/plano|progress|evolu|promoc|carreira/.test(c) && !/(nao|sem) (ha|ident|prev|exist|consta)/.test(c)) pts += 1;
      return pts;
    }}
    let ptsA = 0, ptsB = 0;
    const linhasVer = [];
    function registrarVer(icone, titulo, venc, texto) {{
      if (venc === 'A') ptsA++;
      if (venc === 'B') ptsB++;
      linhasVer.push({{ icone, titulo, venc, texto }});
    }}

    // 1) Salário bruto
    if (A.salarioBruto > 0 && B.salarioBruto > 0 && A.salarioBruto !== B.salarioBruto) {{
      const v = A.salarioBruto > B.salarioBruto ? 'A' : 'B';
      registrarVer('💰', 'Quem paga mais (salário bruto)', v, `${{nomeDe(v)}} paga ${{fmtBrl(diffBruto)}} a mais por mês (${{pctBruto}}).`);
    }} else {{
      registrarVer('💰', 'Quem paga mais (salário bruto)', null, (A.salarioBruto > 0 && A.salarioBruto === B.salarioBruto) ? 'Salários brutos iguais.' : 'Sem dados suficientes: confira o salário no edital.');
    }}
    // 2) Total com auxílios
    if (A.salarioTotal > 0 && B.salarioTotal > 0 && A.salarioTotal !== B.salarioTotal) {{
      const v = A.salarioTotal > B.salarioTotal ? 'A' : 'B';
      registrarVer('➕', 'Ganho mensal total (com auxílios)', v, `${{nomeDe(v)}} rende ${{fmtBrl(diffTotal)}} a mais por mês somando os auxílios.`);
    }} else {{
      registrarVer('➕', 'Ganho mensal total (com auxílios)', null, 'Totais iguais ou sem dados suficientes.');
    }}
    // 3) Valor por hora
    if (valorHoraA && valorHoraB && Math.abs(valorHoraA - valorHoraB) > 0.01) {{
      const v = valorHoraA > valorHoraB ? 'A' : 'B';
      registrarVer('⏱️', 'Melhor valor por hora trabalhada', v, `${{nomeDe(v)}}: ${{fmtBrl(Math.max(valorHoraA, valorHoraB))}}/h contra ${{fmtBrl(Math.min(valorHoraA, valorHoraB))}}/h.`);
    }} else {{
      registrarVer('⏱️', 'Melhor valor por hora trabalhada', null, 'Sem diferença relevante ou sem dados de jornada.');
    }}
    // 4) Jornada
    if (A.horasNum !== B.horasNum && A.horasNum > 0 && B.horasNum > 0) {{
      const v = A.horasNum < B.horasNum ? 'A' : 'B';
      registrarVer('🕒', 'Menor jornada semanal', v, `${{nomeDe(v)}} trabalha ${{Math.abs(A.horasNum - B.horasNum)}}h a menos por semana (${{Math.min(A.horasNum, B.horasNum)}}h contra ${{Math.max(A.horasNum, B.horasNum)}}h).`);
    }} else {{
      registrarVer('🕒', 'Menor jornada semanal', null, 'Jornadas iguais ou não informadas.');
    }}
    // 5) Benefícios
    if (benValA !== benValB) {{
      const v = benValA > benValB ? 'A' : 'B';
      registrarVer('🎁', 'Mais benefícios (VA/VR/VT)', v, `${{nomeDe(v)}} oferece cerca de ${{fmtBrl(diffBen)}} a mais por mês em benefícios com valor informado.`);
    }} else {{
      registrarVer('🎁', 'Mais benefícios (VA/VR/VT)', null, (benValA > 0) ? 'Benefícios equivalentes.' : 'Nenhum dos dois informa valores de benefícios; veja o edital.');
    }}
    // 6) Estabilidade
    const estA = pontosEstabilidade(A), estB = pontosEstabilidade(B);
    if (estA !== estB) {{
      const v = estA > estB ? 'A' : 'B';
      const w = v === 'A' ? A : B, l = v === 'A' ? B : A;
      registrarVer('🛡️', 'Maior estabilidade', v, `${{nomeDe(v)}} é mais estável: ${{w.regimeTxt}} contra ${{l.regimeTxt}}. Regime estatutário garante estabilidade após o estágio probatório; CLT pode ser desligado.`);
    }} else {{
      registrarVer('🛡️', 'Maior estabilidade', null, `Estabilidade equivalente (${{A.regimeTxt}} · ${{B.regimeTxt}}).`);
    }}
    // 7) Vagas
    if (A.vagasNum !== B.vagasNum) {{
      const v = A.vagasNum > B.vagasNum ? 'A' : 'B';
      registrarVer('👥', 'Mais vagas imediatas', v, `${{nomeDe(v)}} tem mais vagas imediatas (${{Math.max(A.vagasNum, B.vagasNum)}} contra ${{Math.min(A.vagasNum, B.vagasNum)}}) — maior chance de aprovação.`);
    }} else {{
      registrarVer('👥', 'Mais vagas imediatas', null, 'Mesmo número de vagas imediatas ou somente cadastro de reserva.');
    }}

    const vencFin = (A.salarioTotal > 0 && B.salarioTotal > 0 && A.salarioTotal !== B.salarioTotal)
      ? (A.salarioTotal > B.salarioTotal ? 'A' : 'B')
      : ((A.salarioBruto > 0 && B.salarioBruto > 0 && A.salarioBruto !== B.salarioBruto) ? (A.salarioBruto > B.salarioBruto ? 'A' : 'B') : null);
    const vencEst = estA !== estB ? (estA > estB ? 'A' : 'B') : null;
    const vencGeral = ptsA !== ptsB ? (ptsA > ptsB ? 'A' : 'B') : null;
    const totalCrit = linhasVer.length;
    const topoVer = [
      `💰 Compensa mais financeiramente: ${{vencFin ? nomeDe(vencFin) : 'empate / dados insuficientes'}}`,
      `🛡️ Maior estabilidade: ${{vencEst ? nomeDe(vencEst) : 'equivalente'}}`,
      `🏆 Mais vantagens no geral: ${{vencGeral ? nomeDe(vencGeral) + ` (vence em ${{Math.max(ptsA, ptsB)}} de ${{totalCrit}} critérios; o outro vence em ${{Math.min(ptsA, ptsB)}})` : `empate técnico (${{ptsA}} x ${{ptsB}})`}}`
    ];
    const txtVeredito = topoVer.join('\\n') + '\\n' + linhasVer.filter(l => l.venc).map(l => `• ${{l.titulo}}: ${{l.texto}}`).join('\\n');
    const htmlVeredito = `
      <div class="print-only"><h2>Comparativo de Concursos — gerado em ${{new Date().toLocaleDateString('pt-BR')}}</h2></div>
      <div class="cmp-veredito">
        <div class="cmp-vered-head">🏆 Resultado direto da comparação</div>
        <ul class="cmp-vered-top">${{topoVer.map(t => `<li>${{escHtml(t)}}</li>`).join('')}}</ul>
        <div class="cmp-vered-list">
          ${{linhasVer.map(l => `
            <div class="cmp-v-row${{l.venc ? '' : ' empate'}}">
              <span class="ic">${{l.icone}}</span>
              <div><b>${{escHtml(l.titulo)}}</b><p>${{escHtml(l.texto)}}</p></div>
              <span class="tag">${{l.venc === 'A' ? '1️⃣ Concurso 1' : (l.venc === 'B' ? '2️⃣ Concurso 2' : 'Empate')}}</span>
            </div>`).join('')}}
        </div>
      </div>`;

    corpoModalComparar.innerHTML = `
      ${{htmlVeredito}}
      <div class="cmp-summary-banner">
        <div class="cmp-kpi">
          <span>💰 Diferença Salarial (Bruto)</span>
          <strong>${{escHtml(txtDiffBruto)}}</strong>
        </div>
        <div class="cmp-kpi">
          <span>🎁 Diferença Total (Com Auxílios)</span>
          <strong>${{escHtml(txtDiffTotal)}}</strong>
        </div>
        <div class="cmp-kpi">
          <span>🧭 Distância Entre as Cidades</span>
          <strong>${{escHtml(txtDistCidades)}}</strong>
        </div>
        <div class="cmp-kpi">
          <span>📅 Compatibilidade de Provas</span>
          <strong>${{escHtml(conflitoProva)}}</strong>
        </div>
      </div>

      <table class="cmp-table">
        <thead>
          <tr>
            <th>Critério Analisado</th>
            <th>1️⃣ ${{escHtml(A.orgao)}} (${{escHtml(A.cidade)}}/${{escHtml(A.uf)}})</th>
            <th>2️⃣ ${{escHtml(B.orgao)}} (${{escHtml(B.cidade)}}/${{escHtml(B.uf)}})</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="cmp-crit">🎯 Cargo Comparado</td>
            <td><b>${{escHtml(A.cargo)}}</b></td>
            <td><b>${{escHtml(B.cargo)}}</b></td>
          </tr>
          <tr>
            <td class="cmp-crit">💰 Salário Bruto (Separado)</td>
            <td class="${{A.salarioBruto > B.salarioBruto ? 'cmp-win' : ''}}"><b>${{escHtml(A.salarioExib)}}</b></td>
            <td class="${{B.salarioBruto > A.salarioBruto ? 'cmp-win' : ''}}"><b>${{escHtml(B.salarioExib)}}</b></td>
          </tr>
          <tr>
            <td class="cmp-crit">➕ Soma com Auxílios</td>
            <td class="${{A.salarioTotal > B.salarioTotal ? 'cmp-win' : ''}}">${{escHtml(A.salarioDet)}}</td>
            <td class="${{B.salarioTotal > A.salarioTotal ? 'cmp-win' : ''}}">${{escHtml(B.salarioDet)}}</td>
          </tr>
          <tr>
            <td class="cmp-crit">⏱️ Jornada Semanal &amp; Valor/Hora</td>
            <td class="${{A.horasNum < B.horasNum ? 'cmp-win' : ''}}">
              <b>${{escHtml(A.jornadaTxt)}}</b><br>
              <small>${{valorHoraA ? `Valor aproximado: ${{fmtBrl(valorHoraA)}}/hora trabalhada` : ''}}</small>
            </td>
            <td class="${{B.horasNum < A.horasNum ? 'cmp-win' : ''}}">
              <b>${{escHtml(B.jornadaTxt)}}</b><br>
              <small>${{valorHoraB ? `Valor aproximado: ${{fmtBrl(valorHoraB)}}/hora trabalhada` : ''}}</small>
            </td>
          </tr>
          <tr>
            <td class="cmp-crit">🎁 Benefícios (VA, VR, VT)</td>
            <td>${{escHtml(A.beneficios)}}<br><small style="color:var(--muted);">${{escHtml(txtDiffBen)}}</small></td>
            <td>${{escHtml(B.beneficios)}}</td>
          </tr>
          <tr>
            <td class="cmp-crit">🏛️ Regime de Contratação</td>
            <td><b>${{escHtml(A.regimeTxt)}}</b></td>
            <td><b>${{escHtml(B.regimeTxt)}}</b></td>
          </tr>
          <tr>
            <td class="cmp-crit">📈 Plano de Crescimento na Carreira</td>
            <td>${{escHtml(A.carreira)}}</td>
            <td>${{escHtml(B.carreira)}}</td>
          </tr>
          <tr>
            <td class="cmp-crit">📍 Localização &amp; Distância</td>
            <td class="${{(kmRefA != null && kmRefB != null && kmRefA < kmRefB) ? 'cmp-win' : ''}}">
              <b>${{escHtml(A.cidade)}}/${{escHtml(A.uf)}}</b><br>
              ${{kmRefA != null ? escHtml(textoDistanciaRef(kmRefA)) : '<small>Escolha sua cidade de referência nos filtros para ver a distância.</small>'}}
            </td>
            <td class="${{(kmRefA != null && kmRefB != null && kmRefB < kmRefA) ? 'cmp-win' : ''}}">
              <b>${{escHtml(B.cidade)}}/${{escHtml(B.uf)}}</b><br>
              ${{kmRefB != null ? escHtml(textoDistanciaRef(kmRefB)) : '<small>—</small>'}}
            </td>
          </tr>
          <tr>
            <td class="cmp-crit">👥 Vagas no Edital</td>
            <td class="${{A.vagasNum > B.vagasNum ? 'cmp-win' : ''}}"><b>${{escHtml(A.vagasTxt)}}</b></td>
            <td class="${{B.vagasNum > A.vagasNum ? 'cmp-win' : ''}}"><b>${{escHtml(B.vagasTxt)}}</b></td>
          </tr>
          <tr>
            <td class="cmp-crit">📅 Data da Prova &amp; Banca</td>
            <td><b>${{escHtml(A.dataProvaTxt)}}</b> · Banca: ${{escHtml(A.bancaTxt)}}</td>
            <td><b>${{escHtml(B.dataProvaTxt)}}</b> · Banca: ${{escHtml(B.bancaTxt)}}</td>
          </tr>
          <tr>
            <td class="cmp-crit">⏰ Inscrições &amp; Isenção</td>
            <td><b>Até ${{escHtml(A.inscricaoTxt)}}</b><br><small>${{escHtml(A.isencaoTxt)}}</small></td>
            <td><b>Até ${{escHtml(B.inscricaoTxt)}}</b><br><small>${{escHtml(B.isencaoTxt)}}</small></td>
          </tr>
          <tr>
            <td class="cmp-crit">🎓 Requisitos Técnicos</td>
            <td>${{escHtml(A.requisitosTxt)}}</td>
            <td>${{escHtml(B.requisitosTxt)}}</td>
          </tr>
        </tbody>
      </table>`;

    ultimoResumoComparacao =
      `⚖️ *COMPARATIVO DE CONCURSOS*\n\n` +
      `1️⃣ *${{A.orgao}} (${{A.cidade}}/${{A.uf}})*\n` +
      `• Cargo: ${{A.cargo}}\n• Salário Bruto: ${{A.salarioExib}} (${{A.salarioDet}})\n• Benefícios: ${{A.beneficios}}\n• Regime/Jornada: ${{A.regimeTxt}} (${{A.jornadaTxt}})\n• Prova: ${{A.dataProvaTxt}} | Inscrições até: ${{A.inscricaoTxt}}\n\n` +
      `2️⃣ *${{B.orgao}} (${{B.cidade}}/${{B.uf}})*\n` +
      `• Cargo: ${{B.cargo}}\n• Salário Bruto: ${{B.salarioExib}} (${{B.salarioDet}})\n• Benefícios: ${{B.beneficios}}\n• Regime/Jornada: ${{B.regimeTxt}} (${{B.jornadaTxt}})\n• Prova: ${{B.dataProvaTxt}} | Inscrições até: ${{B.inscricaoTxt}}\n\n` +
      `🏆 *RESULTADO DIRETO*\n${{txtVeredito}}\n\n` +
      `📊 *Diferença Salarial Bruta:* ${{txtDiffBruto}}\n` +
      `🧭 *Distância entre as cidades:* ${{txtDistCidades}}\n` +
      `🔗 Veja no app: ${{APP_PUBLIC_URL}}`;

    modalComparar.classList.add('aberto');
  }}

  btnExecutarComparar.addEventListener('click', abrirModalComparativo);
  document.getElementById('fecharModalComparar').addEventListener('click', () => modalComparar.classList.remove('aberto'));
  document.getElementById('btnFecharCompRodape').addEventListener('click', () => modalComparar.classList.remove('aberto'));
  modalComparar.addEventListener('click', (e) => {{
    if (e.target === modalComparar) modalComparar.classList.remove('aberto');
  }});
  // Baixar comparação em PDF: usa a impressão do navegador (opção "Salvar como PDF")
  document.getElementById('btnBaixarPdfComparacao').addEventListener('click', () => {{
    const tituloOriginal = document.title;
    document.title = 'Comparativo-Concursos';
    document.body.classList.add('imprimindo-comp');
    const limpar = () => {{
      document.body.classList.remove('imprimindo-comp');
      document.title = tituloOriginal;
      window.removeEventListener('afterprint', limpar);
    }};
    window.addEventListener('afterprint', limpar);
    setTimeout(() => window.print(), 80);
  }});
  document.getElementById('btnCompartilharComparacaoZap').addEventListener('click', () => {{
    window.open(`https://api.whatsapp.com/send?text=${{encodeURIComponent(ultimoResumoComparacao)}}`, '_blank', 'noopener,noreferrer');
  }});

  // 8) COMPARTILHAMENTO DE CONCURSO (WhatsApp, Telegram, Web Share API e Copiar Link)
  const modalCompartilhar = document.getElementById('modalCompartilhar');
  const textoCompartilhar = document.getElementById('textoCompartilhar');
  const linkShareZap = document.getElementById('linkShareZap');
  const linkShareTelegram = document.getElementById('linkShareTelegram');
  const btnShareNativo = document.getElementById('btnShareNativo');
  const btnCopiarShare = document.getElementById('btnCopiarShare');
  let dadosShareAtual = null;

  function abrirCompartilhamentoCard(cardEl) {{
    if (!cardEl) return;
    const d = lerDadosDoCard(cardEl);
    const msg =
      `📢 *CONCURSO: ${{d.orgao}} (${{d.cidade}}/${{d.uf}})*\n` +
      `🎯 *Cargo:* ${{d.cargo}}\n` +
      `💰 *Salário Bruto:* ${{d.salarioExib}}\n` +
      `➕ *Com Auxílios:* ${{d.salarioDet}}\n` +
      `🎁 *Benefícios:* ${{d.beneficios}}\n` +
      `👥 *Vagas:* ${{d.vagasTxt}}\n` +
      `🏛️ *Regime e Jornada:* ${{d.regimeTxt}} · ${{d.jornadaTxt}}\n` +
      `📅 *Data da Prova:* ${{d.dataProvaTxt}} (Banca: ${{d.bancaTxt}})\n` +
      `⏰ *Inscrições até:* ${{d.inscricaoTxt}}\n` +
      `🎟️ *Taxa/Isenção:* ${{d.isencaoTxt}}\n\n` +
      `📄 *Edital e Anexos:* ${{d.linkEdital}}\n` +
      `📲 *Painel Concursos:* ${{APP_PUBLIC_URL}}`;

    dadosShareAtual = {{ title: `Concurso ${{d.orgao}} — ${{d.cargo}}`, text: msg, url: d.url || APP_PUBLIC_URL }};
    textoCompartilhar.value = msg;
    linkShareZap.href = `https://api.whatsapp.com/send?text=${{encodeURIComponent(msg)}}`;
    linkShareTelegram.href = `https://t.me/share/url?url=${{encodeURIComponent(d.url || APP_PUBLIC_URL)}}&text=${{encodeURIComponent(msg)}}`;
    modalCompartilhar.classList.add('aberto');
  }}

  btnShareNativo.addEventListener('click', async () => {{
    if (!dadosShareAtual) return;
    if (navigator.share) {{
      try {{
        await navigator.share(dadosShareAtual);
      }} catch (_) {{}}
    }} else {{
      btnCopiarShare.click();
    }}
  }});

  btnCopiarShare.addEventListener('click', async () => {{
    const txt = textoCompartilhar.value;
    try {{
      await navigator.clipboard.writeText(txt);
    }} catch (_) {{
      textoCompartilhar.select();
      document.execCommand('copy');
    }}
    const orig = btnCopiarShare.innerHTML;
    btnCopiarShare.innerHTML = '✅ Copiado!';
    setTimeout(() => {{ btnCopiarShare.innerHTML = orig; }}, 2200);
  }});

  document.getElementById('fecharModalCompartilhar').addEventListener('click', () => modalCompartilhar.classList.remove('aberto'));
  modalCompartilhar.addEventListener('click', (e) => {{
    if (e.target === modalCompartilhar) modalCompartilhar.classList.remove('aberto');
  }});

  // Delegação global de cliques nos cards (Compartilhar e Adicionar para Comparar / Clique no Card)
  document.addEventListener('click', (e) => {{
    const btnShare = e.target.closest('.btn-share-card');
    if (btnShare) {{
      e.preventDefault();
      e.stopPropagation();
      const card = btnShare.closest('.card');
      abrirCompartilhamentoCard(card);
      return;
    }}

    const btnComp = e.target.closest('.btn-add-compare');
    if (btnComp) {{
      e.preventDefault();
      e.stopPropagation();
      const card = btnComp.closest('.card');
      alternarSelecaoConcurso(card);
      return;
    }}

    if (modoCompararAtivo) {{
      const card = e.target.closest('.card[data-uid]');
      const clicouInterativo = e.target.closest('a, button, summary, details, input');
      if (card && !clicouInterativo) {{
        alternarSelecaoConcurso(card);
      }}
    }}
  }});

  renderizarBuscaCargo();

  // Inicialização da cidade de referência (campo opcional nos filtros)
  (function iniciarCidadeRef() {{
    const inp = document.getElementById('inputCidadeRef');
    const btnLimpar = document.getElementById('btnLimparCidadeRef');
    const msg = document.getElementById('msgCidadeRef');
    const MSG_PADRAO = msg.textContent;

    function aplicarRef(obj, persistir) {{
      cidadeRef = obj;
      if (obj) {{
        inp.value = `${{obj.nome}} - ${{obj.uf}}`;
        msg.textContent = `✓ Distâncias calculadas a partir de ${{obj.nome}}/${{obj.uf}} (estimativa por estrada).`;
      }} else {{
        msg.textContent = MSG_PADRAO;
        estadoFiltros.kmRef = '';
        sincronizarBotoesFiltro();
      }}
      if (persistir) {{
        try {{
          if (obj) localStorage.setItem(REF_STORAGE_KEY, JSON.stringify([obj.nome, obj.uf]));
          else localStorage.removeItem(REF_STORAGE_KEY);
        }} catch (err) {{ /* armazenamento indisponível */ }}
      }}
      atualizarDistanciasRef();
      aplicarFiltrosSp(false);
    }}

    function aoDigitar() {{
      const valor = inp.value.trim();
      if (!valor) {{
        if (cidadeRef) aplicarRef(null, true);
        return;
      }}
      const achada = acharCidadeRef(valor);
      if (achada) aplicarRef(achada, true);
    }}
    inp.addEventListener('input', aoDigitar);
    inp.addEventListener('change', aoDigitar);
    btnLimpar.addEventListener('click', () => {{
      inp.value = '';
      aplicarRef(null, true);
    }});

    try {{
      const salvo = JSON.parse(localStorage.getItem(REF_STORAGE_KEY) || 'null');
      if (Array.isArray(salvo) && salvo.length === 2) {{
        const achada = acharCidadeRef(`${{salvo[0]}} - ${{salvo[1]}}`);
        if (achada) aplicarRef(achada, false);
      }}
    }} catch (err) {{ /* ignora valor inválido */ }}
  }})();

  // 9) Modal Pix (Topo "☕ Me pague um café" + Rodapé "☕ Me pague um café")
  const modalPix = document.getElementById('modalPix');
  const btnAbrirPix = document.getElementById('btnAbrirPix');
  const btnHeaderPix = document.getElementById('btnHeaderPix');
  const fecharModalPix = document.getElementById('fecharModalPix');
  const btnCopiarPix = document.getElementById('btnCopiarPix');

  btnAbrirPix.addEventListener('click', () => modalPix.classList.add('aberto'));
  btnHeaderPix.addEventListener('click', () => modalPix.classList.add('aberto'));
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

  // 10) Service Worker e Instalação do Aplicativo
  let deferredPrompt = null;
  const btnInstall = document.getElementById('btnInstall');
  const modalApp = document.getElementById('modalApp');

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
      modalApp.classList.add('aberto');
    }}
  }});
  document.getElementById('fecharModalApp').addEventListener('click', () => modalApp.classList.remove('aberto'));
  document.getElementById('btnEntendiApp').addEventListener('click', () => modalApp.classList.remove('aberto'));
  modalApp.addEventListener('click', (e) => {{
    if (e.target === modalApp) modalApp.classList.remove('aberto');
  }});

  // 11) LOGIN OBRIGATÓRIO COM CONTA GOOGLE + CONTADOR DE ACESSOS DO DESENVOLVEDOR (VIA LINK ESPECÍFICO)
  const SESSION_STORAGE_KEY = 'concursos_google_session_v1';
  const AUDIT_LOG_KEY = 'concursos_dev_audit_logs_v1';
  const LOCAL_VIEWS_KEY = 'concursos_dev_local_views_v1';
  const OAUTH_CLIENT_ID_KEY = 'concursos_google_client_id_v1';
  const GOOGLE_CLIENT_ID_FIXO = {safe_json_for_script(GOOGLE_CLIENT_ID)};
  // Client ID: o definido no código tem prioridade; senão o salvo no painel do desenvolvedor
  function obterClientId() {{
    const salvo = (localStorage.getItem(OAUTH_CLIENT_ID_KEY) || '').trim().replace(/^["']|["']$/g, '');
    const fixo = (GOOGLE_CLIENT_ID_FIXO || '').trim().replace(/^["']|["']$/g, '');
    const id = fixo || salvo;
    if (!id) return '';
    return (id.toLowerCase().endsWith('.apps.googleusercontent.com') && id.includes('-')) ? id : '';
  }}

  const AUDIT_WEBHOOK_KEY = 'concursos_audit_webhook_url_v1';
  const AUDIT_WEBHOOK_URL_FIXO = {safe_json_for_script(AUDIT_WEBHOOK_URL)};
  function obterAuditWebhookUrl() {{
    const salvo = (localStorage.getItem(AUDIT_WEBHOOK_KEY) || '').trim();
    const fixo = (AUDIT_WEBHOOK_URL_FIXO || '').trim();
    return fixo || salvo;
  }}

  // Hash SHA-256 da chave secreta exclusiva do link do desenvolvedor
  const DEV_TOKEN_SHA256 = 'ad4ccc5a97c1e5c805713136e2fce68343de39b526c672dd0133759a9c4e6400';
  const DEV_EMAILS_SHA256 = new Set([
    '7ed55ef0211954fe092379280e274bd49b9a7808f783ad7fb3e59c51b55f7ba6',
    '66c256084aaf7fa6b0223307f4d3a72faa1b704e94c13a10408f6fa5963a51db'
  ]);

  const loginGateOverlay = document.getElementById('loginGateOverlay');
  const formLoginGoogle = document.getElementById('formLoginGoogle');
  const inputGoogleNome = document.getElementById('inputGoogleNome');
  const inputGoogleEmail = document.getElementById('inputGoogleEmail');
  const msgErroLoginGoogle = document.getElementById('msgErroLoginGoogle');
  const userProfileChip = document.getElementById('userProfileChip');
  const userProfileText = document.getElementById('userProfileText');
  const btnLogoutGoogle = document.getElementById('btnLogoutGoogle');
  const btnDevPanel = document.getElementById('btnDevPanel');
  const modalDevStats = document.getElementById('modalDevStats');

  function sha256PureJs(ascii) {{
    function rightRotate(value, amount) {{ return (value >>> amount) | (value << (32 - amount)); }}
    const mathPow = Math.pow, maxWord = mathPow(2, 32);
    let result = '';
    const words = [], asciiBitLength = ascii.length * 8;
    let hash = [], k = [];
    let primeCounter = 0;
    const isComposite = {{}};
    for (let candidate = 2; primeCounter < 64; candidate++) {{
      if (!isComposite[candidate]) {{
        for (let i = 0; i < 313; i += candidate) isComposite[i] = candidate;
        hash[primeCounter] = (mathPow(candidate, .5) * maxWord) | 0;
        k[primeCounter++] = (mathPow(candidate, 1 / 3) * maxWord) | 0;
      }}
    }}
    ascii += '\\x80';
    while (ascii.length % 64 - 56) ascii += '\\x00';
    for (let i = 0; i < ascii.length; i++) {{
      const j = ascii.charCodeAt(i);
      if (j >> 8) return '';
      words[i >> 2] |= j << ((3 - i) % 4) * 8;
    }}
    words[words.length] = ((asciiBitLength / maxWord) | 0);
    words[words.length] = (asciiBitLength);
    for (let j = 0; j < words.length;) {{
      const w = words.slice(j, j += 16);
      const oldHash = hash;
      hash = hash.slice(0, 8);
      for (let i = 0; i < 64; i++) {{
        const w15 = w[i - 15], w2 = w[i - 2];
        const a = hash[0], e = hash[4];
        const temp1 = hash[7]
          + (rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25))
          + ((e & hash[5]) ^ ((~e) & hash[6]))
          + k[i]
          + (w[i] = (i < 16) ? w[i] : (
              w[i - 16]
              + (rightRotate(w15, 7) ^ rightRotate(w15, 18) ^ (w15 >>> 3))
              + w[i - 7]
              + (rightRotate(w2, 17) ^ rightRotate(w2, 19) ^ (w2 >>> 10))
            ) | 0);
        const temp2 = (rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22))
          + ((a & hash[1]) ^ (a & hash[2]) ^ (hash[1] & hash[2]));
        hash = [(temp1 + temp2) | 0].concat(hash);
        hash[4] = (hash[4] + temp1) | 0;
      }}
      for (let i = 0; i < 8; i++) hash[i] = (hash[i] + oldHash[i]) | 0;
    }}
    for (let i = 0; i < 8; i++) {{
      for (let j = 3; j + 1; j--) {{
        const b = (hash[i] >> (j * 8)) & 255;
        result += ((b < 16) ? 0 : '') + b.toString(16);
      }}
    }}
    return result;
  }}

  async function sha256Hex(texto) {{
    const limpo = String(texto || '').trim();
    if (window.crypto && window.crypto.subtle) {{
      try {{
        const msgBuffer = new TextEncoder().encode(limpo);
        const hashBuffer = await window.crypto.subtle.digest('SHA-256', msgBuffer);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
      }} catch (_) {{}}
    }}
    return sha256PureJs(unescape(encodeURIComponent(limpo)));
  }}

  function registrarEventoAuditoria(usuarioStr, eventoStr) {{
    try {{
      const logs = JSON.parse(localStorage.getItem(AUDIT_LOG_KEY) || '[]');
      logs.unshift({{
        ts: new Date().toLocaleString('pt-BR'),
        usuario: String(usuarioStr || 'Visitante').slice(0, 120),
        evento: String(eventoStr || 'Acesso').slice(0, 120)
      }});
      localStorage.setItem(AUDIT_LOG_KEY, JSON.stringify(logs.slice(0, 200)));
    }} catch (_) {{}}
  }}

  let globalViewsCount = null;
  let globalLoginsCount = null;

  async function enviarRegistroAcessoGlobal(nomeStr, emailStr, eventoStr) {{
    try {{
      const webhookUrl = obterAuditWebhookUrl();
      if (!webhookUrl) return;
      const payload = JSON.stringify({{
        nome: String(nomeStr || 'Visitante').slice(0, 120),
        email: String(emailStr || '-').slice(0, 120),
        evento: String(eventoStr || 'Acesso à página').slice(0, 120),
        ua: (navigator.userAgent || '').slice(0, 150)
      }});
      if (navigator.sendBeacon) {{
        navigator.sendBeacon(webhookUrl, new Blob([payload], {{ type: 'text/plain;charset=utf-8' }}));
      }} else {{
        fetch(webhookUrl, {{
          method: 'POST',
          mode: 'no-cors',
          headers: {{ 'Content-Type': 'text/plain;charset=utf-8' }},
          body: payload
        }}).catch(() => {{}});
      }}
    }} catch (_) {{}}
  }}

  function lerSessaoGoogle() {{
    try {{
      const raw = localStorage.getItem(SESSION_STORAGE_KEY);
      if (!raw) return null;
      const s = JSON.parse(raw);
      if (!s || !s.email || !s.expiresAt || Date.now() > Number(s.expiresAt)) {{
        localStorage.removeItem(SESSION_STORAGE_KEY);
        return null;
      }}
      return s;
    }} catch (_) {{
      return null;
    }}
  }}

  function aplicarSessaoAutenticada(sessao) {{
    document.body.classList.remove('bloqueado-login');
    loginGateOverlay.classList.add('oculto');
    userProfileChip.classList.add('visivel');
    userProfileText.textContent = `👤 ${{sessao.name || sessao.email}} (${{sessao.email}})`;
  }}

  // Contabiliza cada acesso à página (usuários autenticados ou visitantes) no Google Sheets e localmente
  (async function contabilizarAcessoInicial() {{
    const viewsLocais = Number(localStorage.getItem(LOCAL_VIEWS_KEY) || '0') + 1;
    localStorage.setItem(LOCAL_VIEWS_KEY, String(viewsLocais));

    const sessaoExistente = lerSessaoGoogle();
    if (sessaoExistente) {{
      aplicarSessaoAutenticada(sessaoExistente);
      registrarEventoAuditoria(`${{sessaoExistente.name}} <${{sessaoExistente.email}}>`, 'Acesso (sessão ativa)');
      await enviarRegistroAcessoGlobal(sessaoExistente.name, sessaoExistente.email, 'Acesso (sessão ativa)');
    }} else {{
      registrarEventoAuditoria('Visitante', 'Acesso à página');
      await enviarRegistroAcessoGlobal('Visitante', '-', 'Acesso à página');
    }}
  }})();

  async function concluirLoginGoogle(nome, email, metodo = 'Google Sign-In') {{
    const emailLimpo = String(email || '').trim().toLowerCase();
    const nomeLimpo = String(nome || '').trim() || emailLimpo.split('@')[0];

    const sessao = {{
      name: nomeLimpo,
      email: emailLimpo,
      method: metodo,
      loginAt: new Date().toISOString(),
      expiresAt: Date.now() + 30 * 86400000
    }};
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(sessao));
    aplicarSessaoAutenticada(sessao);
    registrarEventoAuditoria(`${{nomeLimpo}} <${{emailLimpo}}>`, `Login (${{metodo}})`);
    await enviarRegistroAcessoGlobal(nomeLimpo, emailLimpo, `Login (${{metodo}})`);

    // Ativa automaticamente o painel do desenvolvedor se for o e-mail autorizado
    const hEmail = await sha256Hex(emailLimpo);
    if (DEV_EMAILS_SHA256.has(hEmail)) {{
      try {{ sessionStorage.setItem('concursos_dev_autenticado', '1'); }} catch (_) {{}}
      if (btnDevPanel) btnDevPanel.classList.add('visivel');
      atualizarPainelDevStats();
    }}
  }}

  // Validação de JWT do Google Identity Services (quando Client ID configurado)
  function decodificarJwtGoogle(credential) {{
    try {{
      const partes = String(credential || '').split('.');
      if (partes.length !== 3) return null;
      let base64 = partes[1].replace(/-/g, '+').replace(/_/g, '/');
      const pad = (4 - (base64.length % 4)) % 4;
      if (pad < 4) base64 += '='.repeat(pad);
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      const payload = JSON.parse(jsonPayload);
      if (!payload || !payload.email) return null;
      return payload;
    }} catch (err) {{
      console.error('Erro ao decodificar JWT Google:', err);
      return null;
    }}
  }}

  window.handleGoogleCredentialResponse = function(response) {{
    const cred = response && response.credential;
    if (!cred) {{
      console.warn('Resposta Google sem credencial:', response);
      return;
    }}
    const p = decodificarJwtGoogle(cred);
    if (p && p.email) {{
      concluirLoginGoogle(p.name || p.given_name || p.email, p.email, 'Google One-Tap');
    }} else {{
      console.warn('Não foi possível extrair dados do token Google.');
      msgErroLoginGoogle.textContent = 'Não foi possível validar seu login Google. Por favor, preencha abaixo para continuar.';
      msgErroLoginGoogle.style.display = 'block';
      formLoginGoogle.style.display = 'block';
    }}
  }};

  // Login Google automático: com Client ID configurado o Google mostra a conta já logada no
  // navegador/celular ("Continuar como ..."), sem digitar nada.
  let gsiIniciado = false;
  function iniciarGoogleIdentity() {{
    const clientId = obterClientId();
    const gsiCont = document.getElementById('gsiButtonContainer');
    const opcManual = document.getElementById('opcaoManualLogin');

    if (!clientId) {{
      btnGoogleMain.style.display = 'inline-flex';
      formLoginGoogle.style.display = 'block';
      if (opcManual) opcManual.style.display = 'none';
      if (gsiCont) gsiCont.style.display = 'none';
      return;
    }}

    if (!(window.google && window.google.accounts && window.google.accounts.id)) {{
      setTimeout(iniciarGoogleIdentity, 200);
      return;
    }}

    if (gsiIniciado) return;

    try {{
      window.google.accounts.id.initialize({{
        client_id: clientId,
        callback: window.handleGoogleCredentialResponse,
        auto_select: false,
        cancel_on_tap_outside: false
      }});

      if (gsiCont) {{
        gsiCont.style.display = 'flex';
        gsiCont.innerHTML = '';
        window.google.accounts.id.renderButton(
          gsiCont,
          {{
            type: 'standard',
            theme: 'outline',
            size: 'large',
            text: 'continue_with',
            shape: 'pill',
            logo_alignment: 'left',
            width: 280,
            locale: 'pt-BR'
          }}
        );
      }}

      gsiIniciado = true;
      btnGoogleMain.style.display = 'none';
      formLoginGoogle.style.display = 'none';
      if (opcManual) opcManual.style.display = 'block';

      if (!lerSessaoGoogle()) {{
        window.google.accounts.id.prompt((notification) => {{
          if (notification.isNotDisplayed && notification.isNotDisplayed()) {{
            console.log('Google One-Tap não exibido:', notification.getNotDisplayedReason ? notification.getNotDisplayedReason() : '');
            formLoginGoogle.style.display = 'block';
            if (opcManual) opcManual.style.display = 'none';
          }}
          if (notification.isSkippedMoment && notification.isSkippedMoment()) {{
            console.log('Google One-Tap dispensado:', notification.getSkippedReason ? notification.getSkippedReason() : '');
            formLoginGoogle.style.display = 'block';
            if (opcManual) opcManual.style.display = 'none';
          }}
        }});
      }}
    }} catch (err) {{
      console.error('Erro ao inicializar Google Sign-In:', err);
      gsiIniciado = false;
      btnGoogleMain.style.display = 'inline-flex';
      formLoginGoogle.style.display = 'block';
    }}
  }}

  const btnGoogleMain = document.getElementById('btnGoogleSignInMain');
  const btnAlternarManual = document.getElementById('btnAlternarManual');
  if (btnAlternarManual) {{
    btnAlternarManual.addEventListener('click', () => {{
      const estaOculto = (formLoginGoogle.style.display === 'none');
      formLoginGoogle.style.display = estaOculto ? 'block' : 'none';
      btnAlternarManual.textContent = estaOculto
        ? '🔼 Recolher formulário manual'
        : '✍️ Ou preencher nome e e-mail manualmente';
    }});
  }}

  window.addEventListener('load', iniciarGoogleIdentity);
  window.addEventListener('DOMContentLoaded', iniciarGoogleIdentity);
  window.onGoogleLibraryLoad = iniciarGoogleIdentity;
  if (document.readyState === 'complete') iniciarGoogleIdentity();

  btnGoogleMain.addEventListener('click', () => {{
    const clientId = obterClientId();
    if (clientId && window.google && window.google.accounts && window.google.accounts.id) {{
      iniciarGoogleIdentity();
      window.google.accounts.id.prompt();
    }} else {{
      inputGoogleEmail.focus();
      msgErroLoginGoogle.textContent = 'ℹ️ Informe seu e-mail abaixo para acessar. Para login automático em 1 clique, ative o Client ID no painel do desenvolvedor.';
      msgErroLoginGoogle.style.display = 'block';
    }}
  }});

  formLoginGoogle.addEventListener('submit', async (e) => {{
    e.preventDefault();
    msgErroLoginGoogle.style.display = 'none';
    const nome = inputGoogleNome.value.trim();
    const email = inputGoogleEmail.value.trim().toLowerCase();

    const regexEmail = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
    const ehContaGoogleValida = regexEmail.test(email) && (
      email.endsWith('@gmail.com') ||
      email.endsWith('@googlemail.com') ||
      email.endsWith('@usp.br') ||
      email.includes('.edu.') ||
      email.includes('@')
    );

    if (!nome || nome.length < 2) {{
      msgErroLoginGoogle.textContent = '⚠️ Informe seu nome completo para continuar.';
      msgErroLoginGoogle.style.display = 'block';
      return;
    }}
    if (!ehContaGoogleValida) {{
      msgErroLoginGoogle.textContent = '⚠️ Informe um e-mail válido da sua Conta Google (ex.: @gmail.com ou @usp.br).';
      msgErroLoginGoogle.style.display = 'block';
      return;
    }}

    await concluirLoginGoogle(nome, email, 'Conta Google');
  }});

  btnLogoutGoogle.addEventListener('click', () => {{
    const atual = lerSessaoGoogle();
    if (atual) registrarEventoAuditoria(`${{atual.name}} <${{atual.email}}>`, 'Logout');
    localStorage.removeItem(SESSION_STORAGE_KEY);
    userProfileChip.classList.remove('visivel');
    document.body.classList.add('bloqueado-login');
    loginGateOverlay.classList.remove('oculto');
  }});

  // Verifica sessão existente ao abrir a página
  const sessaoExistente = lerSessaoGoogle();
  if (sessaoExistente) {{
    aplicarSessaoAutenticada(sessaoExistente);
  }}

  // 12) PAINEL SECRETO DO DESENVOLVEDOR (CONTADOR DE ACESSOS VIA LINK ESPECÍFICO)
  async function atualizarPainelDevStats() {{
    const viewsLocais = Number(localStorage.getItem(LOCAL_VIEWS_KEY) || '1');
    const logsLocais = JSON.parse(localStorage.getItem(AUDIT_LOG_KEY) || '[]');
    const contasUnicasLocais = new Set(logsLocais.map(l => l.usuario).filter(Boolean));

    document.getElementById('kpiAcessosLocais').textContent = viewsLocais.toLocaleString('pt-BR');

    let dadosRemotos = null;
    const webhookUrl = obterAuditWebhookUrl();
    if (webhookUrl) {{
      try {{
        const sep = webhookUrl.includes('?') ? '&' : '?';
        const r = await fetch(webhookUrl + sep + 'action=stats&t=' + Date.now(), {{
          cache: 'no-store'
        }});
        if (r.ok) {{
          dadosRemotos = await r.json();
        }}
      }} catch (err) {{
        console.warn('Erro ao consultar estatísticas remotas da Planilha Google:', err);
      }}
    }}

    if (dadosRemotos && typeof dadosRemotos.totalAcessos === 'number') {{
      const gViews = Math.max(dadosRemotos.totalAcessos, viewsLocais);
      const listaLogs = Array.isArray(dadosRemotos.logs) ? dadosRemotos.logs : [];
      const loginsReais = listaLogs.filter(l => (l.evento || '').toLowerCase().includes('login')).length;
      const gLogins = Math.max(loginsReais, Number(dadosRemotos.totalLogins) || 0, contasUnicasLocais.size);
      const gUnicos = Math.max(Number(dadosRemotos.usuariosUnicos) || 0, contasUnicasLocais.size);

      globalViewsCount = gViews;
      globalLoginsCount = gLogins;

      document.getElementById('kpiTotalAcessosGlobais').textContent = gViews.toLocaleString('pt-BR');
      document.getElementById('kpiTotalLoginsGlobais').textContent = gLogins.toLocaleString('pt-BR');
      document.getElementById('kpiAcessosLocais').textContent = viewsLocais.toLocaleString('pt-BR');
      document.getElementById('kpiUsuariosUnicos').textContent = gUnicos.toLocaleString('pt-BR');

      if (btnDevPanel) {{
        btnDevPanel.innerHTML = `📊 Acessos: <b>${{gViews.toLocaleString('pt-BR')}}</b> (Dev)`;
      }}

      const logsParaExibir = (listaLogs.length > 0) ? listaLogs : logsLocais;
      const tbody = document.getElementById('tabelaLogsDev');
      tbody.innerHTML = logsParaExibir.slice(0, 100).map(l => {{
        let tsStr = l.ts;
        try {{
          const d = new Date(l.ts);
          if (!isNaN(d.getTime())) {{
            tsStr = d.toLocaleString('pt-BR', {{ timeZone: 'America/Sao_Paulo' }});
          }}
        }} catch (_) {{}}
        const ev = String(l.evento || 'Acesso');
        const isLogin = ev.toLowerCase().includes('login');
        const badgeStyle = isLogin
          ? 'background:#dcfce7;color:#166534;border:1px solid #86efac;padding:3px 9px;border-radius:999px;font-weight:700;'
          : 'background:#e0f2fe;color:#0369a1;border:1px solid #7dd3fc;padding:3px 9px;border-radius:999px;font-weight:700;';
        const icon = isLogin ? '🔑 ' : '🌐 ';
        return `
          <tr>
            <td style="white-space:nowrap;font-size:0.78rem;">${{escHtml(tsStr)}}</td>
            <td><b>${{escHtml(l.usuario)}}</b></td>
            <td><span style="${{badgeStyle}}">${{icon}}${{escHtml(ev)}}</span></td>
          </tr>
        `;
      }}).join('') || '<tr><td colspan="3">Nenhum evento registrado ainda.</td></tr>';
    }} else {{
      document.getElementById('kpiTotalAcessosGlobais').textContent = viewsLocais.toLocaleString('pt-BR');
      document.getElementById('kpiTotalLoginsGlobais').textContent = Math.max(1, contasUnicasLocais.size).toLocaleString('pt-BR');
      document.getElementById('kpiUsuariosUnicos').textContent = Math.max(1, contasUnicasLocais.size).toLocaleString('pt-BR');

      if (btnDevPanel) {{
        btnDevPanel.innerHTML = `📊 Acessos: <b>${{viewsLocais.toLocaleString('pt-BR')}}</b> (Dev)`;
      }}

      const tbody = document.getElementById('tabelaLogsDev');
      tbody.innerHTML = logsLocais.slice(0, 50).map(l => `
        <tr>
          <td style="white-space:nowrap;font-size:0.78rem;">${{escHtml(l.ts)}}</td>
          <td><b>${{escHtml(l.usuario)}}</b></td>
          <td><span style="background:#e0f2fe;color:#0369a1;padding:3px 9px;border-radius:999px;font-weight:700;">🌐 ${{escHtml(l.evento)}}</span></td>
        </tr>
      `).join('') || '<tr><td colspan="3">Nenhum evento registrado ainda.</td></tr>';
    }}

    document.getElementById('inputDevGoogleClientId').value = obterClientId();
    if (document.getElementById('inputDevWebhookUrl')) {{
      document.getElementById('inputDevWebhookUrl').value = obterAuditWebhookUrl();
    }}
  }}

  (async function verificarLinkDesenvolvedor() {{
    const params = new URLSearchParams(window.location.search);
    const devParam = params.get('dev') || '';
    let autorizadoDev = false;

    // 1) Autorização automática para os e-mails registrados do desenvolvedor
    const sessaoAtual = lerSessaoGoogle();
    if (sessaoAtual && sessaoAtual.email) {{
      const hEmail = await sha256Hex(sessaoAtual.email);
      if (DEV_EMAILS_SHA256.has(hEmail)) {{
        autorizadoDev = true;
      }}
    }}

    // 2) Autorização por parâmetro secreto ?dev= ou sessão anterior
    if (devParam) {{
      const hashParam = await sha256Hex(devParam);
      if (hashParam === DEV_TOKEN_SHA256) {{
        autorizadoDev = true;
        try {{
          sessionStorage.setItem('concursos_dev_autenticado', '1');
          // Limpa o parâmetro ?dev= da URL para não poluir histórico nem ser compartilhado por acidente
          const u = new URL(window.location.href);
          u.searchParams.delete('dev');
          window.history.replaceState({{}}, document.title, u.pathname + (u.search ? u.search : '') + u.hash);
        }} catch (_) {{}}
      }}
    }} else if (!autorizadoDev) {{
      try {{
        if (sessionStorage.getItem('concursos_dev_autenticado') === '1') {{
          autorizadoDev = true;
        }}
      }} catch (_) {{}}
    }}

    if (autorizadoDev) {{
      btnDevPanel.classList.add('visivel');
      await atualizarPainelDevStats();
      if (devParam) {{
        modalDevStats.classList.add('aberto');
      }}
    }} else {{
      btnDevPanel.classList.remove('visivel');
    }}
  }})();

  btnDevPanel.addEventListener('click', async () => {{
    await atualizarPainelDevStats();
    modalDevStats.classList.add('aberto');
  }});
  document.getElementById('fecharModalDevStats').addEventListener('click', () => modalDevStats.classList.remove('aberto'));
  document.getElementById('btnFecharDevRodape').addEventListener('click', () => modalDevStats.classList.remove('aberto'));
  modalDevStats.addEventListener('click', (e) => {{
    if (e.target === modalDevStats) modalDevStats.classList.remove('aberto');
  }});

  const btnSairModoDev = document.getElementById('btnSairModoDev');
  if (btnSairModoDev) {{
    btnSairModoDev.addEventListener('click', () => {{
      try {{ sessionStorage.removeItem('concursos_dev_autenticado'); }} catch (_) {{}}
      btnDevPanel.classList.remove('visivel');
      modalDevStats.classList.remove('aberto');
      alert('Modo Desenvolvedor desativado! O botão [🔐 Contador de Acessos] foi completamente ocultado, exatamente como qualquer visitante comum visualiza o site.');
    }});
  }}

  const btnLimparDevClientId = document.getElementById('btnLimparDevClientId');
  if (btnLimparDevClientId) {{
    btnLimparDevClientId.addEventListener('click', () => {{
      if (confirm('Deseja remover o Google Client ID customizado e retornar ao modo de login padrão?')) {{
        localStorage.removeItem(OAUTH_CLIENT_ID_KEY);
        alert('Client ID removido com sucesso! O aplicativo será recarregado.');
        window.location.reload();
      }}
    }});
  }}

  document.getElementById('btnSalvarClientId').addEventListener('click', () => {{
    const raw = document.getElementById('inputDevGoogleClientId').value;
    const cid = raw.trim().replace(/^["']|["']$/g, '');
    if (cid) {{
      if (!cid.toLowerCase().endsWith('.apps.googleusercontent.com') || !cid.includes('-')) {{
        alert('Atenção: O formato do Client ID parece incorreto. Ele deve terminar com ".apps.googleusercontent.com" e conter um hífen.');
      }}
      localStorage.setItem(OAUTH_CLIENT_ID_KEY, cid);
      alert('Client ID OAuth Google salvo com sucesso! O login do Google será atualizado agora.');
      gsiIniciado = false;
      iniciarGoogleIdentity();
      modalDevStats.classList.remove('aberto');
    }} else {{
      localStorage.removeItem(OAUTH_CLIENT_ID_KEY);
      alert('Client ID removido.');
      location.reload();
    }}
  }});

  const btnSalvarWebhookUrl = document.getElementById('btnSalvarWebhookUrl');
  if (btnSalvarWebhookUrl) {{
    btnSalvarWebhookUrl.addEventListener('click', () => {{
      const raw = (document.getElementById('inputDevWebhookUrl').value || '').trim();
      if (raw) {{
        localStorage.setItem(AUDIT_WEBHOOK_KEY, raw);
        alert('URL do Webhook da Planilha Google salva com sucesso!');
      }} else {{
        localStorage.removeItem(AUDIT_WEBHOOK_KEY);
        alert('URL personalizada removida. Usando URL padrão da Planilha Google.');
      }}
      atualizarPainelDevStats();
    }});
  }}

  const btnRestaurarWebhookUrl = document.getElementById('btnRestaurarWebhookUrl');
  if (btnRestaurarWebhookUrl) {{
    btnRestaurarWebhookUrl.addEventListener('click', () => {{
      localStorage.removeItem(AUDIT_WEBHOOK_KEY);
      if (document.getElementById('inputDevWebhookUrl')) {{
        document.getElementById('inputDevWebhookUrl').value = obterAuditWebhookUrl();
      }}
      alert('Restaurada a URL oficial da Planilha Google configurada no código.');
      atualizarPainelDevStats();
    }});
  }}

  document.getElementById('btnExportarLogsDev').addEventListener('click', () => {{
    const relatorio = {{
      exportado_em: new Date().toISOString(),
      acessos_locais: Number(localStorage.getItem(LOCAL_VIEWS_KEY) || '1'),
      acessos_globais: globalViewsCount,
      logins_globais: globalLoginsCount,
      historico: JSON.parse(localStorage.getItem(AUDIT_LOG_KEY) || '[]')
    }};
    const blob = new Blob([JSON.stringify(relatorio, null, 2)], {{ type: 'application/json' }});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'relatorio-acessos-concursos.json';
    a.click();
    URL.revokeObjectURL(url);
  }});
</script>
</body>
</html>"""
