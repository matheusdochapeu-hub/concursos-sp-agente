# 🔎 Agente de Concursos SP — Fisioterapia & Nível Médio (PWA)

Agente que, **todo dia às 07:00 (horário de Brasília)**, faz scraping do [PCI Concursos — Sudeste](https://www.pciconcursos.com.br/concursos/sudeste/), filtra **exclusivamente concursos do Estado de São Paulo (SP)** e apresenta em um **Progressive Web App (PWA)** instalável:

1. 🩺 **Cargos de Fisioterapeuta / Fisioterapia**
2. 💰 **Cargos de Nível Médio com remuneração acima de R$ 5.000,00**

🌐 **Acesso direto (online e instalável como App):**
👉 **<https://matheusdochapeu-hub.github.io/concursos-sp-agente/>**

---

## ✨ O que é exibido na tela inicial de cada concurso

- **💰 Salário Bruto Exato do Cargo** (vencimento base e/ou remuneração somada aos benefícios fixos)
- **🎁 Benefícios (VA, VR, VT, Saúde, Prêmio de Produtividade)** com valores quando divulgados
- **🏛️ Regime de Contratação** (`Estatutário`, `CLT (Celetista)`, `Residência (Bolsa)`, `Militar Temporário (RM2)`, `Processo Seletivo`)
- **⏱️ Carga Horária Semanal** (`20h`, `30h`, `36h`, `40h`, `60h semanais`)
- **📅 Data da Prova Objetiva**, **⏰ Prazo de Inscrição** e **🏢 Banca Organizadora**
- **📍 Cidade/SP** + **🧭 Distância em km até Ribeirão Preto/SP** e **🧭 Distância em km até Jarinu/SP** (calculadas com base nas coordenadas dos 645 municípios de SP)
- **✨ Plaquinha "CONCURSO NOVO · 24h"** apenas para concursos que apareceram nas últimas 24 horas e não estavam no período anterior
- **🔗 Links Clicáveis**:
  - **📄 Edital & Conteúdo Programático** (leva direto aos PDFs do edital e anexos da notícia)
  - **🌐 Site da Banca Organizadora**
  - **📝 Provas Anteriores Relacionadas**
- **📚 Resumo do Conteúdo Programático** expansível diretamente no card (voltado para Fisioterapeuta nos cards de Fisioterapia, e para o cargo específico nos cards de Nível Médio)

---

## 🎛️ Filtros e Ordenação

- **Busca textual**: Cidade, órgão, cargo ou banca
- **Seletor de Cidade (SP)** com distâncias ao lado
- **Proximidade com Ribeirão Preto/SP** (até 50 km, 100 km, 150 km, 220 km, 300 km, 400 km)
- **Proximidade com Jarinu/SP** (até 50 km, 100 km, 150 km, 250 km, 350 km)
- **Salário Bruto Mínimo** (≥ R$ 2.500 até ≥ R$ 8.000)
- **Número de Vagas** (com vagas imediatas ≥ 1, ≥ 2, ≥ 3 ou somente CR)
- **Regime de Contratação** (Estatutário, CLT, Residência/Militar/Seletivo)
- **Carga Horária Semanal Máxima** (até 20h, 30h, 36h, 40h)
- **Checkbox "Apenas novos (últimas 24h)"**
- **Ordenação**: mais próximos de Ribeirão Preto, mais próximos de Jarinu, maior salário bruto, maior nº de vagas, data da prova mais próxima, inscrições encerrando primeiro ou novos primeiro.

---

## 📲 Como baixar o App (PWA)

1. Acesse **<https://matheusdochapeu-hub.github.io/concursos-sp-agente/>**
2. Clique no botão **"📲 Baixar App (PWA)"** no topo da página (ou no ícone de instalação da barra de endereços do Chrome/Edge, ou em *Compartilhar → Adicionar à Tela de Início* no iPhone/Safari).

---

## 💻 Rodar localmente no computador

```powershell
pip install -r requirements.txt
$env:GEMINI_API_KEY = "sua_chave"   # opcional
python agente.py
```

Ou dê dois cliques em `rodar_local.bat`.
