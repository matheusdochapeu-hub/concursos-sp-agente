"""Testes do HTML gerado por render_html (login opcional, contador e busca compartilhável).

Não abrem navegador: garantem invariantes do template e, quando há Node.js,
validam a sintaxe de todo o JavaScript embutido (o site é um HTML montado por
f-strings — um `{{` esquecido quebra o JS sem quebrar o Python).
"""
from __future__ import annotations

import unittest
from pathlib import Path

from render_site import CARGOS_RAPIDOS_MAX, render_html


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


class TestRenderSite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = _render()

    def test_sem_placeholders_python_esquecidos(self):
        for resto in ("{opcoes_", "{botoes_", "{len(", "{gerado_em}", "{total_sp}"):
            self.assertNotIn(resto, self.html, f"placeholder não interpolado: {resto}")

    def test_login_e_opcional_e_nao_bloqueia(self):
        # O app abre livre: nada de blur/bloqueio no body.
        self.assertNotIn('<body class="bloqueado-login"', self.html)
        self.assertNotIn("bloqueado-login", self.html)
        # O cartão de conta começa fechado e pode ser dispensado.
        self.assertIn('id="loginGateOverlay" class="login-gate-bg oculto"', self.html)
        self.assertIn('id="btnFecharLogin"', self.html)
        self.assertIn('id="btnContinuarSemLogin"', self.html)
        self.assertIn('id="btnEntrarTopo"', self.html)
        # Sem login obrigatório, mas com link para a política de privacidade.
        self.assertIn("./privacidade.html", self.html)
        # Nenhuma chamada com variável fora de escopo que quebrava o botão Google.
        self.assertNotIn("opcManual", self.html)

    def test_contador_de_acessos_e_honesto(self):
        # Não inventa número mínimo nem chama número local de "global".
        self.assertNotIn("Math.max(1, contasUnicasLocais.size)", self.html)
        self.assertIn('id="avisoModoLocal"', self.html)
        self.assertIn('id="bannerNuvem"', self.html)
        self.assertIn("contagemNuvemAtiva()", self.html)
        # Webhook nunca vem embutido por padrão: só de variável de ambiente/painel.
        self.assertNotIn("script.google.com/macros/s/AKfy", self.html)

    def test_busca_compartilhavel(self):
        self.assertIn('id="btnCompartilharBusca"', self.html)
        self.assertIn("function estadoDaBuscaParaParams", self.html)
        self.assertIn("function aplicarEstadoDaURL", self.html)
        self.assertIn("function sincronizarURLBusca", self.html)
        # O catálogo nacional é carregado uma vez e sempre devolve Promise.
        self.assertIn("catalogoBrasilPromise", self.html)
        self.assertNotIn("aplicarFiltrosBuscaCargo", self.html)
        # A lista de 85 cargos agora existe também no JavaScript.
        self.assertIn(f"const CARGOS_RAPIDOS_LISTA = {CARGOS_RAPIDOS_MAX!r}".replace("'", '"'), self.html)

    def test_js_inline_tem_sintaxe_valida(self):
        import importlib.util
        import shutil
        import subprocess
        import sys
        import tempfile

        if not shutil.which("node") and not (Path.home() / ".dsh/dsh-runtimes/dsh-primary-runtime/dependencies/node/bin/node.exe").exists():
            self.skipTest("Node.js indisponível para checar o JS")

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        spec = importlib.util.spec_from_file_location(
            "check_inline_js", Path(__file__).resolve().parent.parent / "tools" / "check_inline_js.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        node = mod.achar_node(None)
        blocos = mod.extrair_blocos(self.html)
        self.assertTrue(blocos, "esperava ao menos um <script> inline")
        for linha, corpo in blocos:
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
                fh.write(corpo)
                temp = fh.name
            try:
                proc = subprocess.run(
                    [node, "--check", temp], capture_output=True, text=True, encoding="utf-8", errors="replace"
                )
            finally:
                Path(temp).unlink(missing_ok=True)
            self.assertEqual(proc.returncode, 0, f"JS inválido no bloco da linha {linha}:\n{proc.stderr}")


if __name__ == "__main__":
    unittest.main()
