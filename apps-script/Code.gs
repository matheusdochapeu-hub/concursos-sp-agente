/**
 * Concursos — contador de acessos (Google Sheets + Apps Script)
 * ---------------------------------------------------------------
 * Recebe os acessos/logins do PWA e devolve os totais para o painel do dev.
 *
 * COMO INSTALAR (resumo — passo a passo completo em README.md):
 *   1. Crie uma planilha no Google Sheets (nome livre).
 *   2. Extensões → Apps Script → apague o conteúdo e cole ESTE arquivo.
 *   3. Rode a função `gerarChaves` (▶). Ela salva as chaves nas Propriedades do
 *      script e mostra no log a URL pronta para colar no GitHub — você NÃO
 *      precisa colar chave nenhuma no código.
 *   4. Implantar → Nova implantação → Tipo "App da Web"
 *        Executar como: Eu
 *        Quem tem acesso: Qualquer pessoa
 *   5. Rode `mostrarChaves` para ver a URL de escrita (com ?k=) e a de teste.
 *      Salve a de escrita em GitHub: Settings → Secrets and variables → Actions →
 *      New repository secret → AUDIT_WEBHOOK_URL.
 *   6. Actions → "Buscar concursos (diário)" → Run workflow.
 *   7. No site, abra ?dev=SEU_TOKEN e cole a CHAVE_ADMIN no painel.
 *
 *   Rodou `gerarChaves` de novo? As chaves anteriores param de valer; refaça a
 *   URL do secret e o workflow, e cole a nova CHAVE_ADMIN no painel.
 *
 * SEGURANÇA (leia):
 *   - TOKEN_ESCRITA fica público dentro do HTML (todo mundo que abre o app vê).
 *     Ele só permite GRAVAR linhas. Não use o mesmo valor da chave admin.
 *   - CHAVE_ADMIN nunca vai para o app: só é digitada no painel do dev, e o
 *     painel a guarda no localStorage daquele navegador. Sem ela, ninguém
 *     consegue ler a lista de nomes/e-mails dos usuários.
 */

// --------------------------------------------------------------------------- //
// Configuração das chaves
// --------------------------------------------------------------------------- //
// (a configuração fica logo abaixo: as chaves vêm das Propriedades do script,
//  geradas por `gerarChaves` — não é preciso colar nada aqui)

// --------------------------------------------------------------------------- //
// Configuração das chaves
//
// As chaves NÃO precisam ser coladas no código: `gerarChaves` grava nas
// Propriedades do script (PropertiesService) e o código lê de lá.
// As constantes abaixo são só o fallback (se você preferir colar à mão).
// --------------------------------------------------------------------------- //
const PROP_TOKEN = 'TOKEN_ESCRITA';
const PROP_ADMIN = 'CHAVE_ADMIN';

function lerChave(nome, valorNoCodigo) {
  try {
    const salvo = PropertiesService.getScriptProperties().getProperty(nome);
    if (salvo && String(salvo).trim()) return String(salvo).trim();
  } catch (err) {
    // Propriedades indisponíveis: usa o valor do código
  }
  return valorNoCodigo;
}

const TOKEN_ESCRITA = lerChave(PROP_TOKEN, 'COLE_AQUI_O_TOKEN_PUBLICO');   // vai na URL do app (?k=...)
const CHAVE_ADMIN = lerChave(PROP_ADMIN, 'COLE_AQUI_A_CHAVE_ADMIN');       // só no seu navegador

const NOME_ABA = 'Acessos';
const MAX_LOGS_RESPOSTA = 100;      // itens devolvidos ao painel
const MAX_CARACTERES_CORPO = 2000;  // proteção contra payload gigante

// URL pública do App da Web (só existe depois da primeira implantação)
function urlDoApp() {
  try {
    return ScriptApp.getService().getUrl() || '';
  } catch (err) {
    return '';
  }
}

function origemDaChave(nome) {
  try {
    return PropertiesService.getScriptProperties().getProperty(nome) ? 'Propriedades do script' : 'código (fallback)';
  } catch (err) {
    return 'código (fallback)';
  }
}

// --------------------------------------------------------------------------- //
// Geração de chaves — rode UMA vez (ou quando quiser trocar as chaves)
// --------------------------------------------------------------------------- //
function gerarChaves() {
  const token = Utilities.getUuid().replace(/-/g, '');
  const admin = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '');

  PropertiesService.getScriptProperties().setProperties({
    [PROP_TOKEN]: token,
    [PROP_ADMIN]: admin
  });

  const url = urlDoApp();

  Logger.log('✅ Chaves novas salvas nas Propriedades do script (não precisa colar no código).');
  Logger.log('TOKEN_ESCRITA = %s', token);
  Logger.log('CHAVE_ADMIN   = %s', admin);
  Logger.log('URL de escrita (valor do secret AUDIT_WEBHOOK_URL) = %s',
    url ? url + '?k=' + token : '<implante como App da Web para ver a URL>');
  Logger.log('⚠️ As chaves ANTERIORES pararam de funcionar. Se o app já estava ligado, ' +
    'atualize o secret AUDIT_WEBHOOK_URL e rode o workflow de novo.');
}

// Mostra as chaves em uso e a URL para colar no GitHub
function mostrarChaves() {
  const url = urlDoApp();
  Logger.log('Fonte das chaves: %s', origemDaChave(PROP_TOKEN));
  Logger.log('TOKEN_ESCRITA = %s', TOKEN_ESCRITA);
  Logger.log('CHAVE_ADMIN   = %s', CHAVE_ADMIN);
  Logger.log('URL de escrita (secret AUDIT_WEBHOOK_URL) = %s',
    url ? url + '?k=' + TOKEN_ESCRITA : '<implante como App da Web para ver a URL>');
  Logger.log('URL de teste do painel = %s',
    url ? url + '?k=' + TOKEN_ESCRITA + '&action=stats&admin=' + CHAVE_ADMIN : '<implante primeiro>');
}

// Verifica se as chaves estão configuradas e se a planilha responde
function verificarInstalacao() {
  const problemas = [];
  if (String(TOKEN_ESCRITA).indexOf('COLE_AQUI') === 0) problemas.push('TOKEN_ESCRITA ainda é placeholder (rode gerarChaves)');
  if (String(CHAVE_ADMIN).indexOf('COLE_AQUI') === 0) problemas.push('CHAVE_ADMIN ainda é placeholder (rode gerarChaves)');
  if (TOKEN_ESCRITA === CHAVE_ADMIN) problemas.push('TOKEN_ESCRITA e CHAVE_ADMIN não podem ser iguais');

  const aba = getAba();
  Logger.log(problemas.length ? '⚠️ ' + problemas.join(' | ') : '✅ Tudo certo.');
  Logger.log('Fonte das chaves: %s', origemDaChave(PROP_TOKEN));
  Logger.log('Aba "%s" com %s linha(s) (incluindo cabeçalho).', NOME_ABA, aba.getLastRow());
  if (!urlDoApp()) Logger.log('ℹ️ Ainda não há implantação como App da Web (Implantar → Nova implantação).');
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
