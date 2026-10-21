# 🔎 Agente de Concursos SP — Fisioterapia & Nível Médio

Agente que, **todo dia**, faz scraping do [PCI Concursos — Sudeste](https://www.pciconcursos.com.br/concursos/sudeste/),
filtra **apenas concursos do estado de São Paulo** e procura:

1. 🩺 **Cargos de Fisioterapeuta / Fisioterapia**
2. 💰 **Cargos que exigem apenas nível médio com salário acima de R$ 5.000,00**

Os resultados são publicados numa página HTML (`docs/index.html`), servida pelo **GitHub Pages**.

## Como funciona

```
Listagem PCI (Sudeste) ─► filtra UF = SP ─► abre cada notícia
      │                                        │
      │                 ┌──────────────────────┴─────────────────────┐
      │                 ▼                                            ▼
      │       busca "fisioterap" no texto         IA (Gemini) extrai cargos, escolaridade
      │                                           e salário → filtra médio > R$ 5.000
      ▼
 docs/index.html  +  data/resultados.json   (cache em data/cache.json)
```

- **Cache**: cada notícia é processada uma única vez; nos dias seguintes só os concursos novos são lidos (e marcados como **NOVO**).
- **IA é opcional**: sem `GEMINI_API_KEY`, a busca de fisioterapia funciona normalmente, e os concursos de nível médio
  com teto acima de R$ 5 mil aparecem na aba *"Possíveis — verificar edital"*.
- As notícias do PCI geralmente informam só a **faixa salarial geral**. Quando a IA não encontra o salário de um cargo
  específico, ele vai para *"Possíveis"*. Sempre confirme no edital.

## Publicar no GitHub (execução diária automática)

1. Crie um repositório novo em <https://github.com/new> (ex.: `concursos-sp-agente`, pode ser público).
2. Nesta pasta, rode:
   ```powershell
   git remote add origin https://github.com/matheusdochapeu-hub/concursos-sp-agente.git
   git push -u origin main
   ```
3. **(Opcional, recomendado) chave do Gemini** — gere grátis em <https://aistudio.google.com/apikey> e cadastre em
   *Settings → Secrets and variables → Actions → New repository secret* com o nome `GEMINI_API_KEY`.
4. **GitHub Pages**: *Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: `main` / pasta `/docs`*.
5. Teste já: aba *Actions → "Buscar concursos (diário)" → Run workflow*.

A página ficará em `https://matheusdochapeu-hub.github.io/concursos-sp-agente/` e é atualizada todo dia às **07:00 (Brasília)**.

## Rodar no computador

```powershell
pip install -r requirements.txt
$env:GEMINI_API_KEY = "sua_chave"   # opcional
python agente.py
```

Ou dê dois cliques em `rodar_local.bat` (instala, roda e abre a página).

## Configurações (variáveis de ambiente)

| Variável | Padrão | Descrição |
|---|---|---|
| `GEMINI_API_KEY` | — | Ativa a extração de cargos por IA |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Modelo usado |
| `MAX_AI_CALLS` | `200` | Limite de chamadas de IA por execução |
| `AI_DELAY_S` | `4` | Pausa entre chamadas de IA (free tier) |

Para mudar o valor mínimo ou o termo buscado, edite `SALARIO_MINIMO_MEDIO` e `FISIO_REGEX` no topo de `agente.py`.
