# Contador de acessos com Google Sheets

Este é o passo a passo para o app gravar **todos os acessos e logins** numa planilha sua e o
painel do desenvolvedor mostrar os totais de verdade.

São 4 partes: **planilha → Apps Script → GitHub → painel**. Leva ~10 minutos e não custa nada
(a cota gratuita do Apps Script é de ~20 mil requisições por dia, muito acima do necessário).

```
Usuário abre o app
      │  POST (text/plain, token ?k= público)
      ▼
Apps Script  ──grava──►  Google Sheets (aba "Acessos")
      ▲
      │  GET ?action=stats&admin=CHAVE (só o seu navegador tem a chave)
Painel do dev (no app)
```

---

## Parte 1 — Criar a planilha

1. Abra <https://sheets.new> e dê um nome (ex.: `Concursos — Acessos`).
2. Não precisa criar aba nem cabeçalho: o script cria a aba **Acessos** sozinho.

---

## Parte 2 — Instalar o Apps Script

1. Na planilha: **Extensões → Apps Script**. Abre um editor com `function myFunction() {}`.
2. Apague tudo e cole o conteúdo de [`Code.gs`](Code.gs) deste repositório.
3. Clique em **Salvar** (💾).
4. No seletor de funções (topo), escolha **`gerarChaves`** e clique em **Executar** (▶).
   - Na primeira vez o Google pede autorização: **Revisar permissões → escolha sua conta →
     Avançado → Acessar (não seguro) → Permitir**. É o seu próprio script, acessando a sua
     própria planilha.
   - **Copie as duas chaves** que aparecem no log (parte de baixo):
     ```
     TOKEN_ESCRITA = 8f3c... (32 caracteres)
     CHAVE_ADMIN   = 91ab... (64 caracteres)
     ```
5. Cole os valores nas duas primeiras constantes do script:
   ```js
   const TOKEN_ESCRITA = '8f3c...';   // vai na URL pública
   const CHAVE_ADMIN   = '91ab...';   // NUNCA vai para o app
   ```
6. Salve e rode **`verificarInstalacao`**. O log deve dizer `✅ Tudo certo.`

> ⚠️ **As duas chaves são diferentes de propósito.**
> `TOKEN_ESCRITA` fica visível no HTML (qualquer pessoa pode ver) e só permite **gravar**.
> `CHAVE_ADMIN` só permite **ler** — ela nunca entra no app, você digita no painel e ela fica
> guardada apenas no seu navegador. Sem isso, qualquer curioso abriria a lista de e-mails.

### Publicar como App da Web

1. **Implantar → Nova implantação**.
2. Engrenagem ⚙️ → **App da Web**.
3. Preencha:
   - **Descrição**: `Contador de acessos — Concursos`
   - **Executar como**: **Eu** (sua conta)
   - **Quem tem acesso**: **Qualquer pessoa**  ← tem que ser "Qualquer pessoa", não
     "Qualquer pessoa com conta Google"
4. **Implantar** e copie a URL que termina em `/exec`:
   ```
   https://script.google.com/macros/s/AKfy.../exec
   ```
5. Monte a URL do app, adicionando o token:
   ```
   https://script.google.com/macros/s/AKfy.../exec?k=8f3c...
   ```

### Testar antes de ir para o app

Cole no navegador (trocando `CHAVE_ADMIN`):

```
https://script.google.com/macros/s/AKfy.../exec?k=8f3c...&action=stats&admin=91ab...
```

O esperado é um JSON parecido com:

```json
{ "ok": true, "totalAcessos": 0, "totalLogins": 0, "usuariosUnicos": 0,
  "visitantesUnicos": 0, "logs": [], "geradoEm": "2026-11-17T..." }
```

Se aparecer uma página de login do Google, o "Quem tem acesso" está errado (volte ao passo 3).
Se aparecer `{"ok":false,"erro":"sem permissao..."}`, a `CHAVE_ADMIN` não confere.

---

## Parte 3 — Ligar no app (GitHub)

O app só envia dados para quem estiver embutido no HTML no momento do build. Então:

1. GitHub → repositório `concursos-sp-agente` → **Settings → Secrets and variables → Actions**.
2. **New repository secret**:
   - Nome: `AUDIT_WEBHOOK_URL`
   - Valor: a URL completa **com** `?k=...` do passo anterior.
3. **Actions → "Buscar concursos (diário)" → Run workflow** (branch `main`).
   - O workflow roda o agente, o `render_site.py` lê o secret, embute a URL em `docs/index.html`
     e commita. Leva alguns minutos.
4. Quando o workflow terminar, abra o site e confira no código-fonte da página que a URL
   aparece (`script.google.com/macros/...`).

> Não quer esperar o workflow? Rode localmente:
> ```powershell
> $env:AUDIT_WEBHOOK_URL = "https://script.google.com/macros/s/.../exec?k=..."
> python tools/render_from_json.py
> ```
> Isso reescreve `docs/index.html` com a URL — depois commite.

---

## Parte 4 — Ver os números no painel

1. Abra o site com o seu link de dev (o mesmo de antes):
   `https://matheusdochapeu-hub.github.io/concursos-sp-agente/?dev=SEU_TOKEN_DEV`
2. Clique em **🔐 Contador de Acessos (Dev)**.
3. Abra a seção **📊 Webhook da Planilha Google** e cole a `CHAVE_ADMIN` em
   **"Chave de admin"** → **Salvar chave** → **🔌 Testar conexão**.
4. O banner deve mudar para **📊 Planilha Google conectada** e os cartões mostrar:
   - **Acessos na Nuvem** — total de eventos gravados
   - **Logins Registrados** — eventos com "Login"
   - **Acessos Neste Dispositivo** — só o seu navegador
   - **Contas Únicas** — e-mails distintos que entraram

Para conferir se está gravando: recarregue o app duas vezes e olhe a aba **Acessos** da planilha
(uma linha por carregamento, com data, nome, e-mail, evento e o id anônimo do visitante).

---

## O que fica guardado

| Coluna | Conteúdo |
|---|---|
| A — Data/Hora | momento do evento (fuso da planilha) |
| B — Nome | nome informado no login ou `Visitante` |
| C — E-mail | só quando a pessoa entrou; vazio em visita anônima |
| D — Evento | `Acesso à página`, `Acesso (sessão ativa)`, `Login (Google One-Tap)`, `Login (Manual)`, `Logout` |
| E — Visitante ID | id aleatório salvo no navegador (não é identificador de publicidade) |

- **Acessos** contam carregamentos de página, então incluem recarregamentos e robôs. Para uma
  leitura de "pessoas", use **Visitantes únicos** (coluna E) — o script já devolve esse número
  em `visitantesUnicos`.
- A planilha é sua e **não** é publicada. Só quem tem a `CHAVE_ADMIN` consegue ler pelo app;
  quem tem acesso ao seu Google Drive também (normal).
- Se um dia remover a coleta, apague o secret `AUDIT_WEBHOOK_URL` e rode o workflow: o app volta
  ao modo local e a [política de privacidade](../docs/privacidade.html) continua verdadeira.

### Limpeza / arquivamento

Uma linha por acesso não cresce tanto (mil acessos = mil linhas), mas se quiser manter enxuto:

- Selecione as linhas antigas → **Arquivo → Fazer uma cópia** (ou exporte para CSV) e apague.
- Não apague o cabeçalho (linha 1) nem mude a ordem das colunas A:E — o script lê por posição.
- O `estatisticas()` lê a aba inteira a cada consulta. Acima de ~100 mil linhas a consulta fica
  lenta; arquivar de tempos em tempos resolve.

---

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| Painel diz **"Sem planilha conectada"** | `AUDIT_WEBHOOK_URL` não está no build | Configure o secret e rode o workflow (Parte 3) |
| Painel diz **"faltam a chave de admin"** | Chave não salva neste navegador | Cole a `CHAVE_ADMIN` no painel → Salvar chave |
| Painel diz **"não respondeu agora"** | URL, deploy ou chave | Teste a URL no navegador; confira `/exec` (não `/dev`), "Qualquer pessoa" e a chave |
| JSON `chave de escrita invalida` | URL sem `?k=` ou token trocado | Recopie `TOKEN_ESCRITA` e refaça a URL |
| Abre tela de login do Google | "Quem tem acesso" = "Qualquer pessoa com conta Google" | Editar implantação → **Qualquer pessoa** |
| Mudei o código e nada mudou | O `/exec` serve a **última versão implantada** | **Implantar → Gerenciar implantações → ✏️ → Versão: Nova versão → Implantar** |
| Planilha com 0 linhas | O app não está enviando | Confira no DevTools (F12 → Network) se há POST para `script.google.com` |
| Contagem inflada | Recarregamentos e robôs | Use `visitantesUnicos`; filtre por data na planilha |

---

## Referência do protocolo (para debug)

**Escrita** (o app faz `sendBeacon`, `text/plain`, sem CORS):

```
POST .../exec?k=TOKEN_ESCRITA
body: {"nome":"Fulano","email":"f@x.com","evento":"Login (Google One-Tap)","visitante_id":"uuid"}
```

**Leitura** (o painel faz `fetch` e espera JSON):

```
GET .../exec?k=TOKEN_ESCRITA&action=stats&admin=CHAVE_ADMIN
```

Resposta: `{ ok, totalAcessos, totalLogins, usuariosUnicos, visitantesUnicos, logs[], geradoEm }`
— `logs` traz até 100 itens `{ ts, usuario, evento }`, do mais recente para o mais antigo.
