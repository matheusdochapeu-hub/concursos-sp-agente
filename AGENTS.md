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
| `data/resultados.json` | Resultado consolidado da última execução |
| `tests/test_agente.py` | Testes de parsing e filtros |
| `docs/` | **Saída gerada** — não editar à mão |
| `plans/` | Planos de evolução |

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

## Vizinhança (ecossistema)

- Independente dos outros apps. O material de estudo em `../Conteudo Programático TJSP 2026`
  é insumo de estudo, não faz parte deste repositório.
