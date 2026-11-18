# Publicar o Concursos na Google Play Store

Guia da via **recomendada** (e a única que o Google aceita sem "app de site embrulhado"):
transformar o PWA em **TWA (Trusted Web Activity)** com o [PWABuilder](https://www.pwabuilder.com/).
O app continua sendo o mesmo HTML publicado no GitHub Pages — nada de código nativo para manter.

> O que **não** dá certo: WebView "caseiro" apontando para o site. O Google reprova (política
> *Spam e experiência mínima*) e o app quebra o login do Google (o Google bloqueia OAuth em WebView).

---

## 0. Pré-requisitos

| Item | Situação |
|---|---|
| App publicado em HTTPS | ✅ GitHub Pages: <https://matheusdochapeu-hub.github.io/concursos-sp-agente/> |
| Manifest completo (nome, ícones 192/512 + maskable, `start_url`, `display`) | ✅ `docs/manifest.webmanifest` |
| Service Worker registrado | ✅ `docs/sw.js` |
| Política de privacidade pública | ✅ <https://matheusdochapeu-hub.github.io/concursos-sp-agente/privacidade.html> |
| Conta Google Play Console | ❌ criar (taxa única de US$ 25) |
| `assetlinks.json` no **domínio raiz** | ❌ falta (passo 2) |

---

## 1. Gerar o pacote Android (AAB)

1. Abra <https://www.pwabuilder.com/> e informe a URL do app.
2. Em **Package for stores → Android**, escolha:
   - **Package ID**: `br.com.matheus.concursos` (definitivo — não muda depois).
   - **App name**: `Concursos`.
   - **Short name**: `Concursos`.
   - Marque *Include signing key* e **guarde o arquivo `.keystore` e as senhas** (sem eles não há
     atualização futura do app). Guarde fora do repositório.
3. Baixe o `.zip`: contém `app-release-bundle.aab`, `assetlinks.json` e o `.keystore`.
4. (Alternativa por linha de comando: `npx @bubblewrap/cli init --manifest https://matheusdochapeu-hub.github.io/concursos-sp-agente/manifest.webmanifest`.)

Os assets de loja já estão prontos em [`play-store/assets/`](assets):

| Arquivo | Uso na Play Console |
|---|---|
| `icon-play-512.png` | Ícone do app (512×512, 32 bits) |
| `feature-graphic-1024x500.png` | Gráfico de destaque (obrigatório) |

Screenshots (mínimo 2, telefone) precisam ser capturados do app rodando — veja o passo 6.

---

## 2. `assetlinks.json` no domínio raiz (o passo que mais falha)

O TWA só abre sem barra de endereço se o Google confirmar que o app pertence ao domínio.
O arquivo **tem** que ficar em:

```
https://matheusdochapeu-hub.github.io/.well-known/assetlinks.json
```

…e **não** em `/concursos-sp-agente/.well-known/`. Como o app mora em um *project site*, isso exige
um segundo repositório:

1. Crie o repositório **`matheusdochapeu-hub.github.io`** (repositório de usuário do GitHub Pages).
2. Nele, crie a pasta `.well-known/` e o arquivo `assetlinks.json` com o conteúdo que o PWABuilder
   gerou. Modelo em [`assetlinks.json.example`](assetlinks.json.example):

   ```json
   [
     {
       "relation": ["delegate_permission/common.handle_all_urls"],
       "target": {
         "namespace": "android_app",
         "package_name": "br.com.matheus.concursos",
         "sha256_cert_fingerprints": ["COLE_AQUI_O_SHA256_DO_SEU_KEYSTORE"]
       }
     }
   ]
   ```

   O SHA-256 sai do próprio PWABuilder ou com:
   `keytool -list -v -keystore meu.keystore -alias androiddebugkey`
3. Ative o GitHub Pages nesse repositório (branch `main`, pasta raiz).
4. Confirme que responde 200 e com `Content-Type: application/json`:
   <https://matheusdochapeu-hub.github.io/.well-known/assetlinks.json>
5. Teste com o [Asset Links Tool](https://developers.google.com/digital-asset-links/tools/generator)
   ou `adb shell pm get-app-links br.com.matheus.concursos`.

> Atenção: se você usar o **Play App Signing** (padrão hoje), o Google reassina o app. Nesse caso
> adicione **também** o SHA-256 que aparece em *Play Console → Configuração → Integridade do app →
> Certificado de assinatura do app* — o `assetlinks.json` precisa listar os dois fingerprints.

---

## 3. Play Console — criar o app

1. <https://play.google.com/console> → **Criar app**.
2. Nome: `Concursos — editais SP e Brasil` · Idioma padrão: Português (Brasil) ·
   Tipo: **App** · Gratuito.
3. Preencha **Configuração do app**:
   - **Política de privacidade**: `https://matheusdochapeu-hub.github.io/concursos-sp-agente/privacidade.html`
   - **Acesso ao app**: o app é aberto, sem login obrigatório → marque *Todo o app fica disponível
     sem restrições*. (Se um dia o login voltar a ser obrigatório, é obrigatório fornecer
     credenciais de teste para o revisor.)
   - **Anúncios**: não contém anúncios.
   - **Classificação de conteúdo**: preencha o questionário (educação/notícias, sem violência,
     sem conteúdo adulto, sem compras).
   - **Público-alvo**: 18+ (concurso público) — evita exigências de app infantil.
   - **Segurança dos dados**: declare o que o app coleta de fato:
     - *Informações pessoais → Nome e e-mail*: **coletados** (somente se a pessoa entrar),
       **não compartilhados** com terceiros, **criptografados em trânsito**,
       finalidade “funcionalidade do app”, **exclusão disponível** (basta sair e limpar os dados;
       e pedir remoção por contato).
     - *Atividade no app → interações no app*: **coletado** (contador de acessos), anônimo.
     - *Localização*: **não**.
     - *Identificadores do dispositivo*: **não** (o app guarda um id aleatório local, não é
       identificador de publicidade).
4. **Conta de desenvolvedor pessoal nova?** O Google exige um teste fechado com **12 testadores
   por 14 dias** antes de liberar produção. Recrute os 12 e mantenha o app em *Teste fechado*
   nesse período.

---

## 4. Enviar o AAB

1. **Produção → Criar nova versão** → envie `app-release-bundle.aab`.
2. **Notas da versão** (exemplo):
   `Primeira versão: editais de SP e do Brasil, busca por cargo, cargo fixado, comparador e provas anteriores.`
3. Preencha **Presença na loja**:
   - Descrição curta (80 caracteres):
     `Editais de concursos em SP e no Brasil, atualizados todo dia. Busque por cargo.`
   - Descrição completa: fale do que existe hoje (Fisioterapia, Nível Médio/Técnico, Nível
     Superior, busca por cargo/UF, filtros de salário/distância, comparador, provas anteriores).
     **Não prometa** "todos os concursos do Brasil" nem "aprovação".
   - Ícone: `play-store/assets/icon-play-512.png`
   - Gráfico de destaque: `play-store/assets/feature-graphic-1024x500.png`
   - Screenshots: 2 a 8 imagens de telefone (mín. 320px, máx. 3840px).
4. **Revisão e lançamento** → revisão do Google (de horas a alguns dias).

---

## 5. Riscos que podem reprovar (leia antes)

| Risco | Por quê | O que fazer |
|---|---|---|
| **Direito autoral / conteúdo de terceiros** | O app exibe títulos, resumos e links de editais do PCI Concursos. O Google pode entender como republicação. | Manter o app como **índice que linka a fonte** (já é o caso), creditar o PCI na tela inicial e no rodapé, e remover qualquer trecho longo copiado. Se o PCI reclamar, atenda em 24h pelo e-mail de suporte da Play. |
| **Scraping** | Coleta automática diária de uma página pública. | Baixa frequência (1 vez/dia), 1 requisição por concurso, User-Agent identificável. Não aumentar. |
| **Login/coleta de e-mail** | Exige política de privacidade e declaração de dados corretas. | Já resolvido: login **opcional**, política publicada, declaração no passo 3. |
| **App "só um site"** | Reprovam apps que são apenas um site em WebView. | TWA com `assetlinks.json` correto + recursos offline (SW) + manifest completo. |
| **Nome/ícone de terceiros** | Não usar marca de banca/órgão no ícone. | O ícone atual é o mascote próprio ✅. |

---

## 6. Capturar screenshots

Com o app aberto no Chrome (celular ou DevTools em modo dispositivo):

1. Aba **Buscar Cargo** com um termo digitado (ex.: “Fisioterapeuta”).
2. Aba **Nível Médio** com filtros abertos.
3. Card com “Comprovante de salário” e distância.
4. Aba **Provas Anteriores**.
5. Tela de comparação (2 concursos).

Salve em PNG, 1080×1920 ou 1440×2560. Evite mostrar nome/e-mail reais.

---

## 7. Atualizações depois de publicado

- O conteúdo (editais) atualiza sozinho todo dia às 07:00 (GitHub Actions) — **não** precisa
  publicar versão nova na Play.
- Só gere novo AAB quando mudar algo no *envelope* (nome, ícone, versão, permissões).
- Aumente `versionCode` a cada envio (o PWABuilder faz isso; confira antes de subir).

---

## 8. Checklist final

- [ ] `assetlinks.json` respondendo no domínio raiz com os dois SHA-256 (build + Play App Signing)
- [ ] AAB assinado e keystore guardado fora do repositório
- [ ] Ícone 512×512 e gráfico 1024×500 enviados
- [ ] Ao menos 2 screenshots de telefone
- [ ] Política de privacidade acessível (link no app e na Play Console)
- [ ] Segurança dos dados preenchida conforme o passo 3
- [ ] Classificação de conteúdo e público-alvo preenchidos
- [ ] (Conta pessoal nova) 12 testadores por 14 dias no teste fechado
- [ ] Fluxo testado no aparelho: abrir sem login, buscar cargo, trocar aba, instalar pela Play
