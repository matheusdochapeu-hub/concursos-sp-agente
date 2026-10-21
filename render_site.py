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
    return html.escape(str(s if s is not None else ""))


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
        icone_cargo = "💼"

    cidade = c.get("cidade") or "São Paulo"
    lat = c.get("lat") if c.get("lat") is not None else -23.5505
    lon = c.get("lon") if c.get("lon") is not None else -46.6333
    km_rp = c.get("km_ribeirao_preto")
    km_ja = c.get("km_jarinu")
    km_rp_attr = km_rp if km_rp is not None else 9999
    km_ja_attr = km_ja if km_ja is not None else 9999
    sal_bruto_attr = sal_bruto if sal_bruto is not None else 0
    sal_total_attr = sal_total if sal_total is not None else sal_bruto_attr
    faixa_attr = faixa_salarial_slug(sal_bruto, sal_total)
    horas_attr = horas_num(carga)
    reg_cat = regime_categoria(regime)
    prova_sort = data_iso_sort(c.get("data_prova", ""))
    niveis_attr = niveis_tokens(c.get("niveis", ""), esc_tipo)
    carreira_txt = inferir_plano_carreira(c["orgao"], regime, beneficios, requisitos)

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
    if km_rp is not None:
        chips_dist += f'<span class="chip-dist">🧭 {km_rp} km de Rib. Preto</span>'
    if km_ja is not None:
        chips_dist += f'<span class="chip-dist">🧭 {km_ja} km de Jarinu</span>'

    banca_nome = c.get("banca") or "Consultar edital"
    links_provas = c.get("links_provas_map", {}).get(modo) or {
        "url_combo": "https://www.pciconcursos.com.br/provas/",
        "label_combo": "Provas Anteriores",
    }

    arqs_str = " • ".join(c.get("arquivos_edital") or ["Edital Completo"])
    isencao_txt = c.get("isencao") or "Consultar edital para taxa e requisitos de isenção."
    card_uid = f"sp-{modo}-{card_idx}"

    botoes = (
        f'<a class="btn-link primario" href="{e(c.get("link_edital"))}" target="_blank" rel="noopener" '
        f'title="{e(arqs_str)}">📄 Edital &amp; Anexos</a>'
    )
    if c.get("site_banca"):
        botoes += (
            f'<a class="btn-link" href="{e(c["site_banca"])}" target="_blank" rel="noopener">'
            f'🌐 Banca ({e(banca_nome)})</a>'
        )
    botoes += (
        f'<a class="btn-link btn-provas" href="{e(links_provas["url_combo"])}" target="_blank" rel="noopener" '
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
      data-orgao="{e(c['orgao'])}"
      data-titulo="{e(c['titulo'])}"
      data-url="{e(c['url'])}"
      data-link-edital="{e(c.get('link_edital'))}"
      data-cargo="{e(cargo_titulo)}"
      data-vagas-txt="{e(vagas_txt)}"
      data-cidade="{e(cidade)}"
      data-uf="SP"
      data-lat="{lat}"
      data-lon="{lon}"
      data-km-rp="{km_rp_attr}"
      data-km-jarinu="{km_ja_attr}"
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
      data-is-baseline="{1 if c.get('is_baseline') else 0}">
      <header class="card-head">
        <div class="head-top">
          <h3><a href="{e(c['url'])}" target="_blank" rel="noopener">{e(c['orgao'])}</a></h3>
          <div class="badges-col">{badges_topo}</div>
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
) -> str:
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

    qr_svg = gerar_qr_pix_svg(pix_key)
    catalogo_json = json.dumps(catalogo_brasil, ensure_ascii=False)
    provas_json = json.dumps(catalogo_provas_banca_cargo, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#006b2d">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Concursos">
<meta name="description" content="Concursos — Painel diário de editais para Fisioterapia, Nível Médio/Técnico, Comparador de Concursos, Provas Anteriores por Banca e Cargo, e Busca no Brasil.">
<link rel="manifest" href="./manifest.webmanifest">
<link rel="icon" type="image/png" sizes="192x192" href="./icon-192.png">
<link rel="apple-touch-icon" href="./icon-192.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&amp;family=Plus+Jakarta+Sans:wght@400;500;600;700;800&amp;display=swap" rel="stylesheet">
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

  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--txt);
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }}
  .container {{ max-width: 1340px; margin: 0 auto; padding: 0 20px; }}

  header.app-bar {{
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
  .tabs-wrap {{ margin: 22px 0 18px; }}
  nav.tabs {{
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

  /* Barra de Ferramentas: Função Comparar + Recolher Filtros */
  .filtros-panel {{
    background: var(--surface);
    border: 2px solid var(--border);
    border-top: 5px solid var(--br-green);
    border-radius: var(--radius-lg);
    padding: 18px 22px;
    margin-bottom: 24px;
    box-shadow: var(--shadow-sm);
  }}
  .filtros-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }}
  .filtros-panel:not(.recolhido) .filtros-head {{
    padding-bottom: 14px;
    margin-bottom: 16px;
    border-bottom: 1.5px solid var(--border);
  }}
  .filtros-panel.recolhido .filter-groups,
  .filtros-panel.recolhido .filtros-foot {{
    display: none;
  }}
  .filtros-head-title {{
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 1.02rem;
    font-weight: 800;
    color: var(--br-blue);
    flex-wrap: wrap;
  }}
  .filtros-actions {{
    display: flex;
    align-items: center;
    gap: 9px;
    flex-wrap: wrap;
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
    grid-template-columns: repeat(auto-fill, minmax(410px, 1fr));
    gap: 20px;
    align-items: stretch;
  }}
  @media (max-width: 500px) {{ .grid {{ grid-template-columns: 1fr; }} }}

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

  .head-top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }}
  .badges-col {{ display: flex; flex-direction: column; align-items: flex-end; gap: 5px; flex-shrink: 0; }}
  .card h3 {{ margin: 0; font-size: 1.14rem; line-height: 1.32; font-weight: 800; }}
  .card h3 a {{ color: var(--br-blue); text-decoration: none; }}
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
</style>
</head>
<body>
  <header class="app-bar">
    <div class="container">
      <div class="bar-row">
        <div>
          <div class="brand-badge">🇧🇷 Monitoramento Diário de Editais · SP &amp; Brasil</div>
          <h1>Concursos</h1>
          <div class="meta">
            Atualizado em <b>{gerado_em}</b> (Brasília) · <b>{total_sp}</b> editais vigentes em SP e <b>{len(catalogo_brasil)}</b> no Brasil · Fonte:
            <a href="{listing_url}" target="_blank" rel="noopener">PCI Concursos</a>
          </div>
        </div>
        <div class="header-actions-col">
          <button id="btnInstall" class="btn-app-install" type="button">📲 Baixar Aplicativo</button>
          <button id="btnHeaderPix" class="btn-header-pix" type="button">💚 Me faça um Pix</button>
        </div>
      </div>
    </div>
  </header>

  <div class="container">
    <!-- Abas com Caixinha Separada para o Número de Concursos Vigentes -->
    <div class="tabs-wrap">
      <nav class="tabs" aria-label="Categorias de Concursos">
        <div class="tab-item ativo" data-tab="fisio">
          <button type="button" class="tab-btn">🩺 Fisioterapia</button>
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
          <button type="button" class="tab-btn">📊 Nível Médio (Faixas)</button>
          <div class="tab-count-box" title="Concursos vigentes de Nível Médio e Técnico em SP em todas as faixas salariais">
            <b class="cnt" data-cnt-for="medio_todos">{len(medio_todos)}</b>
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

        <div class="tab-item" data-tab="busca_cargo">
          <button type="button" class="tab-btn">🔎 Buscar Outro Cargo</button>
          <div class="tab-count-box" title="Concursos vigentes em todos os estados do Brasil">
            <b class="cnt" data-cnt-for="busca_cargo">{len(catalogo_brasil)}</b>
            <small>vigentes</small>
          </div>
        </div>
      </nav>
    </div>

    <!-- Painel Unificado de Filtros + Botão "Função comparar" + Botão "Recolher Filtros" -->
    <section id="painelFiltrosSp" class="filtros-panel" aria-label="Filtros e Função Comparar">
      <div class="filtros-head">
        <div class="filtros-head-title">
          <span>🎛️ Filtros Rápidos</span>
          <button type="button" id="btnToggleComparar" class="btn-comparar-toggle">⚖️ Função comparar</button>
        </div>
        <div class="filtros-actions">
          <span id="msgFiltroAplicado" class="feedback-filtro">✓ Filtros aplicados!</span>
          <button type="button" id="btnAplicarTopo" class="btn-aplicar">✅ Aplicar Filtros</button>
          <button type="button" id="btnLimpar" class="btn-limpar">🔄 Limpar Filtros</button>
          <button type="button" id="btnToggleFiltros" class="btn-recolher">🔼 Recolher Filtros</button>
        </div>
      </div>

      <div class="filter-groups">
        <div class="f-group">
          <div class="f-label">⏳ Prazo &amp; Destaques</div>
          <div class="pill-row">
            <button type="button" class="pill-btn ativo" data-filter="encerrando" data-val="">Todos os Prazos</button>
            <button type="button" class="pill-btn pill-urgente" data-filter="encerrando" data-val="1">
              ⏳ Inscrições Encerrando (Próximos dias) <span class="mini-cnt" id="cntEncerrandoBtn">{encerrando_count}</span>
            </button>
            <button type="button" class="pill-btn" data-filter="novo" data-val="1">
              ✨ Concursos Novos · 24h <span class="mini-cnt">{novos_count}</span>
            </button>
          </div>
        </div>

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
          <div class="f-label">🏙️ Cidade (SP)</div>
          <div class="pill-row">{botoes_cidades}</div>
        </div>

        <div class="f-group">
          <div class="f-label">↕️ Ordenar Resultados</div>
          <div class="pill-row">
            <button type="button" class="pill-btn ativo" data-filter="ordem" data-val="padrao">Ordenação Padrão</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="inscricao">Inscrição encerrando primeiro</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="salario">Maior Salário Bruto</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="rp">Mais perto de Rib. Preto</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="jarinu">Mais perto de Jarinu</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="vagas">Mais Vagas Imediatas</button>
            <button type="button" class="pill-btn" data-filter="ordem" data-val="prova">Prova mais próxima</button>
          </div>
        </div>
      </div>

      <div class="filtros-foot">
        <button type="button" id="btnLimparRodape" class="btn-limpar">🔄 Limpar Filtros</button>
        <button type="button" id="btnAplicarRodape" class="btn-aplicar">✅ Aplicar Filtros</button>
      </div>
    </section>

    <main>
      {render_secao(
          "fisio",
          "🩺",
          "Fisioterapia — Estado de São Paulo",
          "Salário bruto separado em destaque e soma com auxílios menor abaixo, benefícios (VA/VR/VT), isenção da taxa, regime, carga horária e conteúdo programático.",
          fisio,
          "fisio",
          ativo=True,
      )}
      {render_secao(
          "medio5k",
          "💰",
          "Nível Médio com Remuneração Acima de R$ 5.000,00 (SP)",
          "Cargos que exigem apenas Ensino Médio completo com ganhos iniciais acima de R$ 5.000,00, salário bruto separado + soma com auxílios, isenção da taxa e especificações técnicas.",
          medio_ok,
          "medio5k",
      )}
      {render_secao(
          "medio_todos",
          "📊",
          "Nível Médio &amp; Técnico — Escolha a Faixa de Remuneração (SP)",
          "Todos os cargos identificados de Nível Médio e Técnico nos editais de São Paulo, com salário bruto separado e soma com auxílios menor, isenção da taxa e requisitos do edital.",
          medio_todos,
          "medio_todos",
          barra_extra=barra_faixas_aba3,
      )}

      <!-- ABA 4: Provas Anteriores (Pesquisa por BANCA e CARGO, Nunca por Cidade) -->
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

      <!-- ABA 5: Busca por Cargo Específico (SP / Outros Estados / Brasil Todo) -->
      <section id="busca_cargo" class="tab-panel">
        <div class="sec-head">
          <div class="sec-title-row">
            <h2>🔎 Buscar Outro Cargo — SP, Estados ou Brasil Todo</h2>
            <div class="count-box-lg">
              <b id="countBuscaCargo">{len(catalogo_brasil)}</b>
              <span>vigentes</span>
            </div>
          </div>
          <p class="desc">
            Digite qualquer cargo, escolha um dos <b>{len(CARGOS_RAPIDOS_MAX)} Cargos Rápidos</b> abaixo e combine com os filtros acima (Fundamental, Médio, Técnico, Superior, Salário, Distância, Regime, Jornada e Vagas).
          </p>
        </div>

        <div class="busca-cargo-panel">
          <div>
            <div class="f-label" style="margin-bottom:8px;">1️⃣ Digite o Nome do Cargo Desejado (ou clique em um cargo rápido abaixo):</div>
            <div class="cargo-input-row">
              <div class="cargo-input-wrap">
                <input id="inputCargoEspecifico" type="search" autocomplete="off" placeholder="Digite o cargo... Ex.: Fisioterapeuta, Enfermeiro, Agente Administrativo, Psicólogo">
              </div>
              <button type="button" id="btnAplicarBuscaCargo" class="btn-aplicar">✅ Aplicar Filtro</button>
              <button type="button" id="btnLimparCargo" class="btn-limpar">🔄 Limpar Busca</button>
            </div>
          </div>

          <div>
            <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:8px;flex-wrap:wrap;">
              <div class="f-label">⚡ {len(CARGOS_RAPIDOS_MAX)} Cargos Rápidos (1 clique):</div>
              <button type="button" id="btnToggleCargosRapidos" class="btn-recolher" style="min-height:30px;padding:4px 12px;font-size:.77rem;">🔼 Recolher Cargos Rápidos</button>
            </div>
            <div class="pill-row" id="rowCargosRapidos">{botoes_cargos_rapidos}</div>
          </div>

          <div>
            <div class="f-label" style="margin-bottom:8px;">2️⃣ Escolha o Estado (UF) ou Brasil Todo:</div>
            <div class="pill-row" id="rowUfsBrasil">{botoes_ufs}</div>
          </div>
        </div>

        <div id="gridBuscaCargo" class="grid"></div>
        <p id="vazioBuscaCargo" class="vazio" style="display:none;">
          Nenhum concurso encontrado com os filtros atuais. Clique em "Limpar Filtros" ou selecione "🇧🇷 Brasil Todo".
        </p>
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
        <button type="button" id="btnCompartilharComparacaoZap" class="btn-share-opt btn-zap">🟢 Compartilhar Comparativo no WhatsApp</button>
        <button type="button" id="btnFecharCompRodape" class="btn-limpar">Fechar</button>
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
        <a id="linkShareZap" class="btn-share-opt btn-zap" href="#" target="_blank" rel="noopener">🟢 WhatsApp</a>
        <a id="linkShareTelegram" class="btn-share-opt btn-tg" href="#" target="_blank" rel="noopener">✈️ Telegram</a>
        <button type="button" id="btnShareNativo" class="btn-share-opt btn-native">📱 Outros Apps</button>
        <button type="button" id="btnCopiarShare" class="btn-share-opt btn-copy-share">🔗 Copiar Texto e Link</button>
      </div>
    </div>
  </div>

  <!-- Rodapé com botão "☕ Me pague um café" -->
  <footer class="app-footer">
    <div class="container footer-coffee-wrap">
      <button type="button" id="btnAbrirPix" class="btn-coffee">☕ Me pague um café</button>
      <p class="footer-note">Painel gratuito atualizado diariamente · Feito com carinho em São Paulo 🇧🇷</p>
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
  const PIX_PAYLOAD = {json.dumps(pix_key)};
  const DIAS_ALERTA = {DIAS_ALERTA_ENCERRAMENTO};
  const APP_PUBLIC_URL = window.location.href.split('#')[0];

  function normStr(s) {{
    return (s || '').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
  }}
  function normSlug(s) {{
    return normStr(s).replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  }}
  function escHtml(s) {{
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }}
  function fmtBrl(n) {{
    if (!n || isNaN(n) || n <= 0) return 'Consultar edital';
    return 'R$ ' + Number(n).toLocaleString('pt-BR', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
  }}

  // Distância rodoviária estimada entre duas coordenadas GPS (Haversine * 1.22)
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

  // 2) Botão de Recolher / Expandir Filtros
  const painelFiltrosSp = document.getElementById('painelFiltrosSp');
  const btnToggleFiltros = document.getElementById('btnToggleFiltros');
  btnToggleFiltros.addEventListener('click', () => {{
    const recolhido = painelFiltrosSp.classList.toggle('recolhido');
    btnToggleFiltros.innerHTML = recolhido ? '🔽 Mostrar Filtros' : '🔼 Recolher Filtros';
  }});

  // Botão de Recolher / Expandir Cargos Rápidos na Aba 5
  const btnToggleCargosRapidos = document.getElementById('btnToggleCargosRapidos');
  const rowCargosRapidos = document.getElementById('rowCargosRapidos');
  btnToggleCargosRapidos.addEventListener('click', () => {{
    const oculto = rowCargosRapidos.style.display === 'none';
    rowCargosRapidos.style.display = oculto ? 'flex' : 'none';
    btnToggleCargosRapidos.innerHTML = oculto ? '🔼 Recolher Cargos Rápidos' : '🔽 Mostrar {len(CARGOS_RAPIDOS_MAX)} Cargos Rápidos';
  }});

  // 3) Navegação entre as 5 Abas (Filtros visíveis em Fisioterapia, Médio 5k, Médio Faixas e Buscar Outro Cargo!)
  const tabItems = document.querySelectorAll('.tab-item');
  function abrirTab(tab) {{
    tabItems.forEach(item => item.classList.toggle('ativo', item.dataset.tab === tab));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('ativo', p.id === tab));
    painelFiltrosSp.style.display = (tab === 'provas_anteriores') ? 'none' : 'block';
    history.replaceState(null, '', '#' + tab);
    if (tab === 'busca_cargo') renderizarBuscaCargo();
    if (tab === 'provas_anteriores') renderizarProvasAnteriores();
  }}
  tabItems.forEach(item => item.addEventListener('click', () => abrirTab(item.dataset.tab)));
  const hashInicial = location.hash.slice(1);
  if (['fisio', 'medio5k', 'medio_todos', 'provas_anteriores', 'busca_cargo'].includes(hashInicial)) {{
    abrirTab(hashInicial);
  }}

  // 4) Filtros Unificados (Funcionam tanto nas abas de SP quanto na aba "Buscar Outro Cargo")
  const estadoFiltros = {{
    encerrando: '',
    novo: '',
    kmRp: '',
    kmJa: '',
    faixa: '',
    escolaridade: '',
    vagas: 'todas',
    regime: '',
    horas: '',
    cidade: '',
    ordem: 'padrao'
  }};

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
    const maxRp = estadoFiltros.kmRp ? Number(estadoFiltros.kmRp) : null;
    const maxJa = estadoFiltros.kmJa ? Number(estadoFiltros.kmJa) : null;
    const faixa = estadoFiltros.faixa;
    const esc = estadoFiltros.escolaridade;
    const vagasMode = estadoFiltros.vagas;
    const regime = estadoFiltros.regime;
    const maxHoras = estadoFiltros.horas ? Number(estadoFiltros.horas) : null;
    const cid = estadoFiltros.cidade;

    if (soEncerrando && c.dataset.encerrando !== '1') return false;
    if (soNovos && c.dataset.novo !== '1') return false;
    if (cid && c.dataset.cidade !== cid) return false;
    if (maxRp !== null && Number(c.dataset.kmRp) > maxRp) return false;
    if (maxJa !== null && Number(c.dataset.kmJarinu) > maxJa) return false;
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

    ['fisio', 'medio5k', 'medio_todos'].forEach(panelId => {{
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

    renderizarBuscaCargo();
    if (comFeedback) mostrarFeedbackFiltro();
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
    estadoFiltros.kmRp = '';
    estadoFiltros.kmJa = '';
    estadoFiltros.faixa = '';
    estadoFiltros.escolaridade = '';
    estadoFiltros.vagas = 'todas';
    estadoFiltros.regime = '';
    estadoFiltros.horas = '';
    estadoFiltros.cidade = '';
    estadoFiltros.ordem = 'padrao';
    sincronizarBotoesFiltro();
    aplicarFiltrosSp(true);
  }}

  document.getElementById('btnAplicarTopo').addEventListener('click', () => aplicarFiltrosSp(true));
  document.getElementById('btnAplicarRodape').addEventListener('click', () => {{
    aplicarFiltrosSp(true);
    const abaAtiva = document.querySelector('.tab-panel.ativo');
    if (abaAtiva) abaAtiva.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
  }});
  document.getElementById('btnLimpar').addEventListener('click', limparTodosFiltros);
  document.getElementById('btnLimparRodape').addEventListener('click', limparTodosFiltros);

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
        ? `<a class="btn-link" href="${{escHtml(p.url_banca)}}" target="_blank" rel="noopener">🏛️ Todas da Banca (${{escHtml(p.banca)}})</a>`
        : '';
      return `
        <article class="card">
          <header class="card-head">
            <div class="head-top">
              <h3><a href="${{escHtml(p.url_combo)}}" target="_blank" rel="noopener">📝 ${{escHtml(p.cargo)}} — Banca ${{escHtml(p.banca)}}</a></h3>
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
            <a class="btn-link primario" href="${{escHtml(p.url_combo)}}" target="_blank" rel="noopener">
              📥 Provas: ${{escHtml(p.cargo)}} + ${{escHtml(p.banca)}}
            </a>
            <a class="btn-link" href="${{escHtml(p.url_cargo)}}" target="_blank" rel="noopener">
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
  inputProvaCargo.addEventListener('input', () => renderizarProvasAnteriores());
  inputProvaBanca.addEventListener('input', () => renderizarProvasAnteriores());
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
    if (estadoFiltros.kmRp && (item.km_rp == null || item.km_rp > Number(estadoFiltros.kmRp))) return false;
    if (estadoFiltros.kmJa && (item.km_ja == null || item.km_ja > Number(estadoFiltros.kmJa))) return false;
    if (estadoFiltros.faixa && item.faixa !== estadoFiltros.faixa) return false;
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
        if (ordem === 'rp') return (ia.km_rp ?? 9999) - (ib.km_rp ?? 9999);
        if (ordem === 'jarinu') return (ia.km_ja ?? 9999) - (ib.km_ja ?? 9999);
        if (ordem === 'salario') return (ib.salario_max ?? 0) - (ia.salario_max ?? 0);
        if (ordem === 'vagas') return (ib.vagas_im ?? 0) - (ia.vagas_im ?? 0);
        if (ordem === 'prova') return (ia.prova_iso || '9999-12-31').localeCompare(ib.prova_iso || '9999-12-31');
        if (ordem === 'inscricao') return (ia.inscricao_iso || '9999-12-31').localeCompare(ib.inscricao_iso || '9999-12-31');
        return 0;
      }});
    }}

    countBuscaCargo.textContent = filtrados.length;
    if (tabCntBusca) tabCntBusca.textContent = filtrados.length;
    vazioBusca.style.display = filtrados.length === 0 ? 'block' : 'none';

    const fatia = filtrados.slice(0, 120);
    gridBusca.innerHTML = fatia.map(({{ item, cargosCasados, idx }}) => {{
      const uid = `br-${{idx}}`;
      const cargoDestaque = cargosCasados.length > 0
        ? cargosCasados.slice(0, 3).join(' · ') + (cargosCasados.length > 3 ? ` (+${{cargosCasados.length - 3}})` : '')
        : (item.cargos_resumo || 'Conferir cargos no edital');

      let chips = `<span class="chip-loc">📍 ${{escHtml(item.cidade)}} (${{escHtml(item.uf)}})</span>`;
      if (item.km_rp != null) chips += `<span class="chip-dist">🧭 ${{item.km_rp}} km de Rib. Preto</span>`;
      if (item.km_ja != null) chips += `<span class="chip-dist">🧭 ${{item.km_ja}} km de Jarinu</span>`;

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
          data-url="${{escHtml(item.url)}}"
          data-link-edital="${{escHtml(item.url)}}#links"
          data-cargo="${{escHtml(cargoDestaque)}}"
          data-vagas-txt="${{escHtml(item.vagas_txt || item.vagas_salario || 'Ver edital')}}"
          data-cidade="${{escHtml(item.cidade)}}"
          data-uf="${{escHtml(item.uf)}}"
          data-lat="${{item.lat}}"
          data-lon="${{item.lon}}"
          data-km-rp="${{item.km_rp ?? 9999}}"
          data-km-jarinu="${{item.km_ja ?? 9999}}"
          data-salario="${{item.salario_max || 0}}"
          data-salario-total="${{item.salario_total || item.salario_max || 0}}"
          data-salario-exib="${{escHtml(item.salario_exib)}}"
          data-salario-det="${{escHtml(item.salario_det)}}"
          data-beneficios="${{escHtml(item.beneficios)}}"
          data-regime-txt="${{escHtml(item.regime)}}"
          data-carreira="${{escHtml(item.carreira)}}"
          data-jornada-txt="${{escHtml(item.jornada)}}"
          data-data-prova-txt="${{escHtml(item.data_prova)}}"
          data-banca-txt="${{escHtml(item.banca)}}"
          data-inscricao-txt="${{escHtml(item.inscricao_ate)}}"
          data-isencao-txt="${{escHtml(item.isencao)}}"
          data-requisitos-txt="Escolaridade exigida no edital: ${{escHtml(item.niveis || 'Consultar Anexo I')}}"
          data-horas="${{item.horas_num || 40}}"
          data-vagas="${{item.vagas_im || 0}}">
          <header class="card-head">
            <div class="head-top">
              <h3><a href="${{escHtml(item.url)}}" target="_blank" rel="noopener">${{escHtml(item.orgao)}}</a></h3>
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

          <div class="info-grid">
            <div class="info-box destaque-sal">
              <span class="lbl">💰 Remuneração do Cargo (Bruto)</span>
              <strong class="val">${{escHtml(item.salario_exib)}}</strong>
              <small class="sub">${{escHtml(item.salario_det)}}</small>
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
            <a class="btn-link primario" href="${{escHtml(item.url)}}#links" target="_blank" rel="noopener">📄 Edital &amp; Anexos</a>
            <a class="btn-link" href="${{escHtml(urlProvaDinamica)}}" target="_blank" rel="noopener">📝 Provas (Cargo + Banca)</a>
            <button type="button" class="btn-link btn-share-card" data-share-uid="${{uid}}">📤 Compartilhar</button>
            <button type="button" class="btn-add-compare" data-compare-uid="${{uid}}">${{selClass ? '✅ Selecionado' : '➕ Adicionar para comparar'}}</button>
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
  document.getElementById('btnAplicarBuscaCargo').addEventListener('click', () => renderizarBuscaCargo());
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
      kmRp: Number(d.kmRp),
      kmJarinu: Number(d.kmJarinu),
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

    // 1. Diferença Salarial Bruta e Total com Auxílios
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

    // 2. Valor da Hora Trabalhada
    const valorHoraA = (A.salarioBruto > 0 && A.horasNum > 0) ? (A.salarioBruto / (A.horasNum * 4.5)) : null;
    const valorHoraB = (B.salarioBruto > 0 && B.horasNum > 0) ? (B.salarioBruto / (B.horasNum * 4.5)) : null;

    // 3. Distância entre as duas cidades
    const distEntreCidades = calcularDistanciaCidadesKm(A.lat, A.lon, B.lat, B.lon);
    const txtDistCidades = distEntreCidades === 0
      ? `Mesma cidade (${{A.cidade}}/${{A.uf}})`
      : (distEntreCidades != null ? `~${{distEntreCidades}} km entre ${{A.cidade}}/${{A.uf}} e ${{B.cidade}}/${{B.uf}}` : 'Cidades em estados distintos');

    // 4. Diferença de Benefícios (VA/VR/VT)
    const benValA = extrairValoresBeneficios(A.beneficios);
    const benValB = extrairValoresBeneficios(B.beneficios);
    const diffBen = Math.abs(benValA - benValB);
    const txtDiffBen = (benValA > 0 || benValB > 0)
      ? `A: ${{benValA > 0 ? fmtBrl(benValA) : 'Ver edital'}} vs B: ${{benValB > 0 ? fmtBrl(benValB) : 'Ver edital'}} (Diferença quantificada: ${{fmtBrl(diffBen)}}/mês)`
      : 'Ambos conforme estatuto/edital (sem valor fixo detalhado no resumo)';

    // 5. Conflito de Data de Prova
    const conflitoProva = (A.dataProvaTxt !== 'Consultar edital' && A.dataProvaTxt === B.dataProvaTxt)
      ? `⚠️ ATENÇÃO: Ambos têm prova marcada na MESMA DATA (${{A.dataProvaTxt}})!`
      : `✅ Datas diferentes (${{A.dataProvaTxt}} vs ${{B.dataProvaTxt}}) — você pode prestar os dois!`;

    corpoModalComparar.innerHTML = `
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
            <td class="cmp-crit">📍 Distância das Cidades</td>
            <td class="${{A.kmRp < B.kmRp ? 'cmp-win' : ''}}">
              <b>${{escHtml(A.cidade)}}/${{escHtml(A.uf)}}</b><br>
              ${{A.kmRp < 9000 ? `🧭 ${{A.kmRp}} km de Ribeirão Preto · ${{A.kmJarinu}} km de Jarinu` : 'Fora de SP'}}
            </td>
            <td class="${{B.kmRp < A.kmRp ? 'cmp-win' : ''}}">
              <b>${{escHtml(B.cidade)}}/${{escHtml(B.uf)}}</b><br>
              ${{B.kmRp < 9000 ? `🧭 ${{B.kmRp}} km de Ribeirão Preto · ${{B.kmJarinu}} km de Jarinu` : 'Fora de SP'}}
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
  document.getElementById('btnCompartilharComparacaoZap').addEventListener('click', () => {{
    window.open(`https://api.whatsapp.com/send?text=${{encodeURIComponent(ultimoResumoComparacao)}}`, '_blank', 'noopener');
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

  // 9) Modal Pix (Topo "💚 Me faça um Pix" + Rodapé "☕ Me pague um café")
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
</script>
</body>
</html>"""
