# AGENTS.md — Concursos SP (Agente)

> Contexto para agentes de IA. Escopo: **esta pasta**.

## O que é

Agente que roda **todo dia às 07:00 (Brasília)** raspando o PCI Concursos (Sudeste),
filtrando apenas concursos de **São Paulo** e publicando um PWA com os cargos de
**Fisioterapia** e de **nível médio acima de R$ 5.000**. Inclui distância até
Ribeirão Preto e Jarinu, benefícios, banca, datas e resumo do conteúdo programático.

## Stack

- Robô em Python (`agente.py`, ~95 KB) + publicação de site estático (`render_site.py`).
- Saída estática em `docs/` (é isso que o GitHub Pages serve).
- Dados em `data/` (`resultados.json`, caches, municípios com coordenadas).
- Sem framework web: o site é gerado como HTML puro.

## Rodar localmente

```powershell
pip install -r requirements.txt
python agente.py        # executa a coleta (grava em data/ e docs/)
.\rodar_local.bat       # atalho para Windows
```

## Testes

```powershell
python -m unittest discover -s tests -v   # tests/test_agente.py
```
Os testes rodam **antes** da coleta no workflow diário — se falharem, o site não é publicado.

## Deploy

- Cron diário em `.github/workflows/diario.yml` (10:00 UTC = 07:00 BRT):
  instala deps → roda testes → executa o agente → commita `docs/` e `data/`.
- Site: <https://matheusdochapeu-hub.github.io/concursos-sp-agente/>
- A chave `GEMINI_API_KEY` vem de **GitHub Secrets**, nunca do código.

## Arquivos-chave

| Arquivo | Papel |
|---|---|
| `agente.py` | Scraping, enriquecimento e regras de filtro |
| `render_site.py` | Gera o HTML/CSS/JS do PWA em `docs/` |
| `tools/render_from_json.py` | Regera `docs/index.html` a partir dos JSON (sem raspar, sem IA) |
| `tools/check_inline_js.py` | Valida a sintaxe de todo `<script>` do HTML gerado (usa `node --check`) |
| `build_icons.py` | Ícones do PWA + ícone/gráfico da Play Store (caminhos relativos) |
| `data/resultados.json` | Resultado consolidado da última execução |
| `tests/test_agente.py` | Testes de parsing e filtros |
| `tests/test_render_site.py` | Invariantes do HTML gerado (login opcional, contador, busca, JS válido) |
| `tests/test_assets_pwa.py` | Manifest, ícones, service worker e política de privacidade |
| `docs/` | **Saída gerada** — não editar à mão (exceções: `sw.js`, `manifest.webmanifest`, `privacidade.html`) |
| `play-store/` | Guia de publicação na Play Store, `assetlinks.json.example` e assets de loja |
| `apps-script/` | Apps Script + guia do contador de acessos na planilha Google |
| `plans/` | Planos de evolução |

## Comandos úteis

```powershell
python tools/render_from_json.py            # regenera docs/index.html sem raspar
python tools/render_from_json.py --check    # só valida o template
python tools/check_inline_js.py             # valida o JS embutido no HTML publicado
python build_icons.py                       # ícones PWA + assets da Play Store
```

## Regras críticas

1. **`docs/` é artefato gerado.** Nunca editar manualmente: o próximo cron sobrescreve.
   Toda mudança visual vai em `render_site.py`.
2. **Respeitar o site de origem:** o scraping é diário e único; não aumentar frequência
   nem paralelizar sem necessidade.
3. **Filtro é a razão de existir do app:** só SP, só Fisioterapia ou nível médio
   acima do piso. Não "ampliar" o filtro sem pedido explícito.
4. **Nunca commitar chaves.** Use `GEMINI_API_KEY` via secret.
5. Se a coleta falhar, o workflow deve falhar de forma visível — não publicar resultado
   parcial silenciosamente.
6. **Login é opcional.** O app nunca pode bloquear o conteúdo atrás do cartão de conta
   (exigência de UX e de revisão da Play Store). O formulário manual de nome/e-mail
   **não autentica** ninguém — trate-o como preferência local, não como segurança.
7. **Contador de acessos não pode mentir.** Sem `AUDIT_WEBHOOK_URL` no build, os números
   são só do dispositivo e a interface precisa dizer isso. Nunca somar número local em
   rótulo de "global".
8. **O JS do app vive dentro de f-string.** Qualquer `{`/`}` do JavaScript precisa ser
   duplicado (`{{`/`}}`); rode `python tools/check_inline_js.py` antes de publicar.
9. **Política de privacidade é obrigatória** enquanto houver qualquer coleta de nome/e-mail
   (`docs/privacidade.html`), e precisa continuar verdadeira se o contador mudar.
10. **Planilha de acessos: duas chaves, papéis diferentes.** `TOKEN_ESCRITA` é público (vai na
    URL do app, embutido no HTML) e só grava. `CHAVE_ADMIN` só lê, nunca entra no build — é
    digitada no painel do dev e guardada no `localStorage`. Não juntar as duas.
    Passo a passo em [`apps-script/README.md`](apps-script/README.md).

## Vizinhança (ecossistema)

- Independente dos outros apps. O material de estudo em `../Conteudo Programático TJSP 2026`
  é insumo de estudo, não faz parte deste repositório.
