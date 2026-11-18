/**
 * Concursos — contador de acessos (Google Sheets + Apps Script)
 * ---------------------------------------------------------------
 * Recebe os acessos/logins do PWA e devolve os totais para o painel do dev.
 *
 * COMO INSTALAR (resumo — passo a passo completo em README.md):
 *   1. Crie uma planilha no Google Sheets (nome livre).
 *   2. Extensões → Apps Script → apague o conteúdo e cole ESTE arquivo.
 *   3. Rode a função `gerarChaves` (▶) e copie as duas chaves do log.
 *   4. Cole as chaves nas constantes abaixo.
 *   5. Implantar → Nova implantação → Tipo "App da Web"
 *        Executar como: Eu
 *        Quem tem acesso: Qualquer pessoa
 *      Copie a URL que termina em /exec.
 *   6. Monte a URL do app:  URL_DO_EXEC + "?k=" + TOKEN_ESCRITA
 *      e salve no GitHub: Settings → Secrets and variables → Actions →
 *      New repository secret → AUDIT_WEBHOOK_URL.
 *   7. Actions → "Buscar concursos (diário)" → Run workflow.
 *   8. No site, abra ?dev=SEU_TOKEN e cole a CHAVE_ADMIN no painel.
 *
 * SEGURANÇA (leia):
 *   - TOKEN_ESCRITA fica público dentro do HTML (todo mundo que abre o app vê).
 *     Ele só permite GRAVAR linhas. Não use o mesmo valor da chave admin.
 *   - CHAVE_ADMIN nunca vai para o app: só é digitada no painel do dev, e o
 *     painel a guarda no localStorage daquele navegador. Sem ela, ninguém
 *     consegue ler a lista de nomes/e-mails dos usuários.
 */

// --------------------------------------------------------------------------- //
// Configuração — troque os dois valores depois de rodar gerarChaves()
// --------------------------------------------------------------------------- //
const TOKEN_ESCRITA = 'COLE_AQUI_O_TOKEN_PUBLICO';   // vai na URL do app (?k=...)
const CHAVE_ADMIN = 'COLE_AQUI_A_CHAVE_ADMIN';       // só no seu navegador

const NOME_ABA = 'Acessos';
const MAX_LOGS_RESPOSTA = 100;      // itens devolvidos ao painel
const MAX_CARACTERES_CORPO = 2000;  // proteção contra payload gigante

// --------------------------------------------------------------------------- //
// Geração de chaves (rode uma vez, copie do log)
// --------------------------------------------------------------------------- //
function gerarChaves() {
  const novoToken = Utilities.getUuid().replace(/-/g, '');
  const novaChave = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '');
  Logger.log('TOKEN_ESCRITA = ' + novoToken);
  Logger.log('CHAVE_ADMIN   = ' + novaChave);
  Logger.log('URL do app    = <URL_DO_EXEC>?k=' + novoToken);
  Logger.log('Painel do dev = <URL_DO_EXEC>?k=' + novoToken + '&action=stats&admin=' + novaChave);
}

// Verifica se as chaves ainda são os placeholders
function verificarInstalacao() {
  const problemas = [];
  if (TOKEN_ESCRITA.indexOf('COLE_AQUI') === 0) problemas.push('TOKEN_ESCRITA ainda é placeholder');
  if (CHAVE_ADMIN.indexOf('COLE_AQUI') === 0) problemas.push('CHAVE_ADMIN ainda é placeholder');
  if (TOKEN_ESCRITA === CHAVE_ADMIN) problemas.push('TOKEN_ESCRITA e CHAVE_ADMIN não podem ser iguais');
  const aba = getAba();
  Logger.log(problemas.length ? '⚠️ ' + problemas.join(' | ') : '✅ Tudo certo.');
  Logger.log('Aba "%s" com %s linha(s) (incluindo cabeçalho).', NOME_ABA, aba.getLastRow());
  return problemas;
}

// --------------------------------------------------------------------------- //
// POST — o app envia um acesso ou um login
// --------------------------------------------------------------------------- //
function doPost(e) {
  try {
    const p = (e && e.parameter) || {};
    if (p.k !== TOKEN_ESCRITA) {
      return json({ ok: false, erro: 'chave de escrita invalida' });
    }

    const bruto = (e && e.postData && e.postData.contents) || '';
    if (!bruto) return json({ ok: false, erro: 'corpo vazio' });
    if (bruto.length > MAX_CARACTERES_CORPO) return json({ ok: false, erro: 'payload grande demais' });

    let dados;
    try {
      dados = JSON.parse(bruto);
    } catch (err) {
      return json({ ok: false, erro: 'JSON invalido' });
    }
    if (!dados || typeof dados !== 'object') return json({ ok: false, erro: 'payload invalido' });

    const evento = limpar(dados.evento, 'Acesso', 120);
    const nome = limpar(dados.nome, 'Visitante', 120);
    const email = limpar(dados.email, '', 120);
    const visitante = limpar(dados.visitante_id, '', 64);

    // Append seguro mesmo com vários usuários abrindo o app ao mesmo tempo
    const lock = LockService.getScriptLock();
    if (!lock.tryLock(8000)) return json({ ok: false, erro: 'planilha ocupada, tente de novo' });
    try {
      getAba().appendRow([new Date(), nome, email, evento, visitante]);
    } finally {
      lock.releaseLock();
    }

    return json({ ok: true });
  } catch (err) {
    return json({ ok: false, erro: String(err) });
  }
}

// --------------------------------------------------------------------------- //
// GET — estatísticas para o painel do desenvolvedor (exige CHAVE_ADMIN)
// --------------------------------------------------------------------------- //
function doGet(e) {
  try {
    const p = (e && e.parameter) || {};
    if (p.admin !== CHAVE_ADMIN) {
      return json({ ok: false, erro: 'sem permissao: informe a chave de admin' });
    }
    if (p.action === 'stats') return json(estatisticas());
    if (p.action === 'health') {
      return json({ ok: true, aba: NOME_ABA, linhas: getAba().getLastRow(), agora: new Date().toISOString() });
    }
    return json({ ok: true, dica: 'use action=stats' });
  } catch (err) {
    return json({ ok: false, erro: String(err) });
  }
}

// --------------------------------------------------------------------------- //
// Agregação
// --------------------------------------------------------------------------- //
function estatisticas() {
  const aba = getAba();
  const ultima = aba.getLastRow();
  const vazio = {
    ok: true, totalAcessos: 0, totalLogins: 0,
    usuariosUnicos: 0, visitantesUnicos: 0, logs: [],
    geradoEm: new Date().toISOString()
  };
  if (ultima < 2) return vazio;

  // Lê só as colunas usadas (A:E) a partir da linha 2
  const dados = aba.getRange(2, 1, ultima - 1, 5).getValues();

  let totalAcessos = 0;
  let totalLogins = 0;
  const contas = new Set();
  const visitantes = new Set();
  const logs = [];

  // Do mais recente para o mais antigo
  for (let i = dados.length - 1; i >= 0; i--) {
    const linha = dados[i];
    const evento = String(linha[3] || '');
    if (!evento) continue;

    totalAcessos++;
    const ehLogin = evento.toLowerCase().indexOf('login') >= 0;
    if (ehLogin) totalLogins++;

    const email = String(linha[2] || '').trim().toLowerCase();
    if (email) contas.add(email);
    const visitante = String(linha[4] || '').trim();
    if (visitante) visitantes.add(visitante);

    if (logs.length < MAX_LOGS_RESPOSTA) {
      logs.push({
        ts: (linha[0] instanceof Date) ? linha[0].toISOString() : String(linha[0]),
        usuario: String(linha[1] || 'Visitante') + (email ? ' <' + email + '>' : ''),
        evento: evento
      });
    }
  }

  return {
    ok: true,
    totalAcessos: totalAcessos,
    totalLogins: totalLogins,
    usuariosUnicos: contas.size,
    visitantesUnicos: visitantes.size,
    logs: logs,
    geradoEm: new Date().toISOString()
  };
}

// --------------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------------- //
function getAba() {
  const planilha = SpreadsheetApp.getActiveSpreadsheet();
  let aba = planilha.getSheetByName(NOME_ABA);

  if (!aba) {
    aba = planilha.insertSheet(NOME_ABA);
  }
  if (aba.getLastRow() === 0) {
    aba.appendRow(['Data/Hora', 'Nome', 'E-mail', 'Evento', 'Visitante ID']);
    const cabecalho = aba.getRange(1, 1, 1, 5);
    cabecalho.setFontWeight('bold').setBackground('#e8f5ee');
    aba.setFrozenRows(1);
    aba.setColumnWidth(1, 150);
    aba.setColumnWidth(2, 200);
    aba.setColumnWidth(3, 220);
    aba.setColumnWidth(4, 200);
    aba.setColumnWidth(5, 320);
  }
  return aba;
}

function limpar(valor, padrao, max) {
  const s = (valor === null || valor === undefined) ? '' : String(valor).trim();
  return (s || padrao).slice(0, max);
}

function json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
