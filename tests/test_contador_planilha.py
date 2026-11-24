"""Testes do contador de acessos com Google Sheets (Apps Script + painel do dev).

Garantem que:
  - o script da planilha continua com as proteções de chave (escrita x admin);
  - nenhuma chave real vaza para o HTML publicado;
  - o painel tem os campos para configurar e testar a planilha.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from render_site import render_html

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
SCRIPT = REPO / "apps-script" / "Code.gs"


def _render() -> str:
    return render_html(
        fisio=[],
        medio_ok=[],
        medio_todos=[],
        catalogo_brasil=[],
        catalogo_provas_banca_cargo=[],
        total_sp=0,
        gerado_em="17/11/2026 às 16:03",
        listing_url="https://exemplo.test/concursos",
        pix_key="chave-pix-teste",
        superior_sp=[],
        municipios_sp={},
    )


class TestAppsScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codigo = SCRIPT.read_text(encoding="utf-8")

    def test_arquivo_existe_com_funcoes_do_protocolo(self):
        for funcao in ("function doPost", "function doGet", "function estatisticas",
                       "function getAba", "function gerarChaves", "function verificarInstalacao",
                       "function mostrarChaves", "function urlDoApp"):
            self.assertIn(funcao, self.codigo, f"falta {funcao}")

    def test_chaves_vem_das_propriedades_do_script(self):
        # O fluxo não depende de copiar/colar chave no código (que já gerou confusão:
        # o log gerava uma chave e o código tinha outra).
        self.assertIn("PropertiesService.getScriptProperties()", self.codigo)
        self.assertIn("setProperties", self.codigo)
        self.assertIn("lerChave(PROP_TOKEN, 'COLE_AQUI_O_TOKEN_PUBLICO')", self.codigo)
        self.assertIn("lerChave(PROP_ADMIN, 'COLE_AQUI_A_CHAVE_ADMIN')", self.codigo)
        # A URL pronta para o secret é impressa pelo próprio script
        self.assertIn("ScriptApp.getService().getUrl()", self.codigo)

    def test_post_exige_token_de_escrita(self):
        # O POST precisa comparar o ?k= com TOKEN_ESCRITA antes de gravar
        self.assertIn("p.k !== TOKEN_ESCRITA", self.codigo)
        self.assertIn("appendRow", self.codigo)
        self.assertIn("LockService", self.codigo, "append sem lock pode perder linhas concorrentes")

    def test_get_exige_chave_de_admin(self):
        self.assertIn("p.admin !== CHAVE_ADMIN", self.codigo)
        # A listagem de nomes/e-mails nunca pode sair sem a chave
        self.assertLess(
            self.codigo.index("p.admin !== CHAVE_ADMIN"),
            self.codigo.index("estatisticas()"),
            "a checagem de admin tem que vir antes de devolver as estatísticas",
        )

    def test_resposta_tem_os_campos_que_o_painel_le(self):
        for campo in ("totalAcessos", "totalLogins", "usuariosUnicos", "visitantesUnicos", "logs"):
            self.assertIn(campo, self.codigo)
        self.assertIn("ContentService.MimeType.JSON", self.codigo)

    def test_chaves_nao_vazaram_para_o_repositorio(self):
        import re

        # Nenhuma chave real pode estar versionada: só os placeholders de fallback
        self.assertIn("COLE_AQUI_O_TOKEN_PUBLICO", self.codigo)
        self.assertIn("COLE_AQUI_A_CHAVE_ADMIN", self.codigo)
        self.assertIsNone(
            re.search(r"'[0-9a-f]{32,}'", self.codigo),
            "parece haver uma chave real no Code.gs",
        )
        # O script avisa se as duas chaves forem iguais
        self.assertIn("TOKEN_ESCRITA === CHAVE_ADMIN", self.codigo)

    def test_url_de_teste_do_apps_script_e_corrigida(self):
        from render_site import normalizar_webhook_url

        # /exec (produção) passa intacta
        self.assertEqual(
            normalizar_webhook_url("https://script.google.com/macros/s/AK1/exec?k=abc"),
            "https://script.google.com/macros/s/AK1/exec?k=abc",
        )
        # /dev só funciona para o dono logado: precisa virar /exec
        self.assertEqual(
            normalizar_webhook_url("https://script.google.com/macros/s/AK1/dev?k=abc"),
            "https://script.google.com/macros/s/AK1/exec?k=abc",
        )
        self.assertEqual(
            normalizar_webhook_url("https://script.google.com/macros/s/AK1/dev"),
            "https://script.google.com/macros/s/AK1/exec",
        )
        self.assertEqual(
            normalizar_webhook_url("(secret AUDIT_WEBHOOK_URL) = https://script.google.com/macros/s/AK1/dev?k=abc"),
            "https://script.google.com/macros/s/AK1/exec?k=abc",
        )
        self.assertEqual(normalizar_webhook_url(""), "")

    def test_apps_script_tambem_normaliza_dev_para_exec(self):
        self.assertIn("/dev(\\?|$)", self.codigo)
        self.assertIn("'/exec$1'", self.codigo)

    def test_js_do_apps_script_tem_sintaxe_valida(self):
        node = shutil.which("node") or str(
            Path.home() / ".dsh/dsh-runtimes/dsh-primary-runtime/dependencies/node/bin/node.exe"
        )
        if not shutil.which("node") and not Path(node).exists():
            self.skipTest("Node.js indisponível")
        # Apps Script é V8; .gs não é aceito pelo node --check, então copia como .js
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write(self.codigo)
            temp = fh.name
        try:
            proc = subprocess.run([node, "--check", temp], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
        finally:
            Path(temp).unlink(missing_ok=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


class TestPainelPlanilha(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = _render()

    def test_le_a_url_do_arquivo_contador_json(self):
        """Sem secret e sem rebuild: a URL pode vir de docs/contador.json."""
        cfg = json.loads((DOCS / "contador.json").read_text(encoding="utf-8"))
        self.assertIn("webhook", cfg)
        self.assertIsInstance(cfg["webhook"], str)
        if cfg["webhook"]:
            self.assertTrue(cfg["webhook"].startswith("https://"), "webhook precisa ser https")
            self.assertRegex(cfg["webhook"], r"/exec(\?|$)", "webhook precisa ser a URL /exec")
        self.assertIn("fetch('./contador.json", self.html)
        self.assertIn("function carregarConfigContador", self.html)
        self.assertIn("function normalizarUrlWebhook", self.html)

    def test_precedencia_build_arquivo_painel(self):
        import re

        trecho = re.search(r"function obterAuditWebhookUrl\(\) \{(.*?)\n  \}", self.html, re.S)
        self.assertIsNotNone(trecho)
        corpo = trecho.group(1)
        # A ordem do retorno é o que vale: secret do build → contador.json → painel
        self.assertIn("return fixo || webhookDoArquivo || salvo;", corpo)

    def test_testar_tudo_no_apps_script(self):
        codigo = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("function testarTudo", codigo)
        self.assertIn("Teste de instalação", codigo)

    def test_campos_de_configuracao_existem(self):
        for ident in ("inputDevWebhookUrl", "inputDevAdminKey", "btnSalvarAdminKey",
                      "btnLimparAdminKey", "btnTestarWebhook", "statusAdminKey", "bannerNuvem"):
            self.assertIn(f'id="{ident}"', self.html, f"faltando #{ident}")

    def test_busca_de_stats_exige_chave_e_devolve_status(self):
        self.assertIn("function obterAdminKey", self.html)
        self.assertIn("AUDIT_ADMIN_KEY_STORAGE", self.html)
        self.assertIn("'sem_chave'", self.html)
        self.assertIn("&admin=", self.html)

    def test_aviso_explica_como_ligar_a_planilha(self):
        self.assertIn("AUDIT_WEBHOOK_URL", self.html)
        self.assertIn("Apps Script", self.html)

    def test_webhook_url_publica_nao_esta_embutida_por_padrao(self):
        # Sem env var no build, nenhuma URL de planilha aparece no HTML
        self.assertNotIn("script.google.com/macros/s/AKfy", self.html)
        # A chave de admin só é lida do localStorage deste navegador
        self.assertIn("localStorage.getItem(AUDIT_ADMIN_KEY_STORAGE)", self.html)


if __name__ == "__main__":
    unittest.main()
