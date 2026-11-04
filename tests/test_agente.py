from pathlib import Path
import unittest
from datetime import date, timedelta
from agente import (
    parse_brl,
    salarios_no_texto,
    extrair_faixa_e_limites,
    extrair_data_final_br,
    calcular_status_inscricao,
    extrair_vagas_info,
    calcular_auxilios_efetivos,
    detectar_cidade,
    normalizar_cargo_slug,
    parse_taxa_inscricao,
    parse_etapas_prova,
    extrair_salarios_por_cargo,
)


class TestAgente(unittest.TestCase):
    def test_parse_brl(self):
        self.assertEqual(parse_brl("2.500,50"), 2500.5)
        self.assertEqual(parse_brl("800,00"), 800.0)
        self.assertIsNone(parse_brl("invalido"))

    def test_salarios_no_texto_upper_bound(self):
        # Valores normais devem ser mantidos
        self.assertEqual(salarios_no_texto("remuneração de R$ 3.500,00"), [3500.0])
        # Orçamentos milionários e valores acima de 65k devem ser excluídos
        self.assertEqual(salarios_no_texto("investimento de R$ 2.000.000,00"), [])
        # Valores abaixo de 500 devem ser excluídos
        self.assertEqual(salarios_no_texto("taxa de R$ 100,00"), [])

    def test_extrair_faixa_e_limites_accented_regex(self):
        # Testa correspondência de regex com acentuação 'salário' e 'até'
        s_min, s_max, faixa = extrair_faixa_e_limites("salário de R$ 3.000,00 até R$ 6.000,00")
        self.assertEqual(s_min, 3000.0)
        self.assertEqual(s_max, 6000.0)
        self.assertEqual(faixa, "R$ 3.000,00 a R$ 6.000,00")

    def test_extrair_data_final_br(self):
        self.assertEqual(
            extrair_data_final_br("Inscrições de 10/10 a 25/11/2026"),
            date(2026, 11, 25),
        )
        self.assertEqual(
            extrair_data_final_br("até 05/12/26"),
            date(2026, 12, 5),
        )
        self.assertIsNone(extrair_data_final_br(""))

    def test_extrair_data_final_br_sem_ano(self):
        # Testa data no formato DD/MM (sem ano explícito)
        hoje = date.today()
        # Se hoje for nov/dez e mês for jan/fev, é ano seguinte, senão é ano corrente
        esperado_ano = hoje.year + 1 if hoje.month >= 11 and 11 <= 2 else hoje.year
        self.assertEqual(
            extrair_data_final_br("inscrições até 25/11"),
            date(esperado_ano, 11, 25),
        )

    def test_calcular_status_inscricao(self):
        hoje = date.today()

        # Futuro (> 5 dias)
        d_futuro = hoje + timedelta(days=15)
        res_futuro = calcular_status_inscricao(f"até {d_futuro.strftime('%d/%m/%Y')}", hoje)
        self.assertFalse(res_futuro["encerrando"])
        self.assertFalse(res_futuro["encerrada"])
        self.assertEqual(res_futuro["dias_restantes"], 15)

        # Encerrando em breve (3 dias)
        d_3dias = hoje + timedelta(days=3)
        res_3dias = calcular_status_inscricao(f"até {d_3dias.strftime('%d/%m/%Y')}", hoje)
        self.assertTrue(res_3dias["encerrando"])
        self.assertFalse(res_3dias["encerrada"])
        self.assertEqual(res_3dias["dias_restantes"], 3)

        # Encerra hoje (0 dias)
        res_hoje = calcular_status_inscricao(f"até {hoje.strftime('%d/%m/%Y')}", hoje)
        self.assertTrue(res_hoje["encerrando"])
        self.assertFalse(res_hoje["encerrada"])
        self.assertEqual(res_hoje["dias_restantes"], 0)

        # Encerrada (-2 dias)
        d_passado = hoje - timedelta(days=2)
        res_passado = calcular_status_inscricao(f"até {d_passado.strftime('%d/%m/%Y')}", hoje)
        self.assertTrue(res_passado["encerrada"])
        self.assertFalse(res_passado["encerrando"])
        self.assertEqual(res_passado["dias_restantes"], -2)

    def test_extrair_vagas_info(self):
        self.assertEqual(
            extrair_vagas_info("5 vagas"),
            (5, False, "5 vagas imediatas"),
        )
        self.assertEqual(
            extrair_vagas_info("1 vaga + CR"),
            (1, True, "1 vaga imediata + CR"),
        )
        self.assertEqual(
            extrair_vagas_info("CR"),
            (0, True, "Cadastro de Reserva (CR)"),
        )

    def test_calcular_auxilios_efetivos(self):
        self.assertEqual(
            calcular_auxilios_efetivos("Vale alimentação de R$ 800,00 e vale transporte de R$ 300,00"),
            1100.0,
        )
        self.assertEqual(
            calcular_auxilios_efetivos("Auxílio diário de R$ 30,00"),
            660.0,
        )
        self.assertEqual(
            calcular_auxilios_efetivos("Não informado"),
            0.0,
        )

    def test_detectar_cidade(self):
        self.assertEqual(
            detectar_cidade("Prefeitura de Ribeirão Preto - SP", "Concurso Público", "http://exemplo"),
            "Ribeirão Preto",
        )
        self.assertEqual(
            detectar_cidade("Câmara de Campinas", "Concurso Público", "http://exemplo"),
            "Campinas",
        )

    def test_cargos_rapidos_ordem_alfabetica(self):
        import unicodedata
        from render_site import CARGOS_RAPIDOS_MAX

        self.assertGreater(len(CARGOS_RAPIDOS_MAX), 50)
        # Verifica se a lista está em ordem alfabética estrita em português (ignorando acentos para chave de ordenação)
        def chave_norm(s):
            return unicodedata.normalize('NFD', s.lower()).encode('ascii', 'ignore').decode('ascii')

        lista_ordenada = sorted(CARGOS_RAPIDOS_MAX, key=chave_norm)
        self.assertEqual(CARGOS_RAPIDOS_MAX, lista_ordenada)

    def test_datalist_autocomplete_cargos(self):
        from render_site import render_html
        html = render_html(
            fisio=[],
            medio_ok=[],
            medio_todos=[],
            catalogo_brasil=[],
            catalogo_provas_banca_cargo=[],
            total_sp=0,
            gerado_em="30/10/2026 às 12:00",
            listing_url="https://exemplo",
            pix_key="chave-pix-teste",
            superior_sp=[],
            municipios_sp={},
        )
        self.assertIn('id="listaCargosDisponiveis"', html)
        self.assertIn('list="listaCargosDisponiveis"', html)
        # Verifica que o primeiro cargo ordenado (Advogado) e outros estão presentes no datalist
        self.assertIn('<option value="Advogado"></option>', html)
        self.assertIn('<option value="Fisioterapeuta"></option>', html)

    def test_normalizar_cargo_slug(self):
        self.assertEqual(normalizar_cargo_slug("Médico Clínico Geral (40h)"), "medico clinico geral")
        self.assertEqual(normalizar_cargo_slug("Técnico - Enfermagem: PSF"), "tecnico enfermagem psf")
        self.assertEqual(normalizar_cargo_slug(""), "")

    def test_parse_taxa_inscricao(self):
        # Faixa com valores mínimo e máximo
        t1 = parse_taxa_inscricao("Taxa de inscrição de R$ 50,00 a R$ 120,00.")
        self.assertEqual(t1["taxa_min"], 50.0)
        self.assertEqual(t1["taxa_max"], 120.0)
        self.assertIn("50,00", t1["taxa_texto"])

        # Valor único
        t2 = parse_taxa_inscricao("Valor da taxa: R$ 85,00 com isenção prevista em lei.")
        self.assertEqual(t2["taxa_min"], 85.0)
        self.assertEqual(t2["taxa_max"], 85.0)

        # Gratuita
        t3 = parse_taxa_inscricao("Inscrições gratuitas sem taxa de participação.")
        self.assertEqual(t3["taxa_min"], 0.0)
        self.assertIn("Gratuita", t3["taxa_texto"])

        # Não informado
        t4 = parse_taxa_inscricao("")
        self.assertIsNone(t4["taxa_min"])
        self.assertEqual(t4["taxa_texto"], "Consultar edital")

    def test_parse_etapas_prova(self):
        txt1 = "O certame contará com prova objetiva, prova discursiva e avaliação de títulos."
        etapas1 = parse_etapas_prova(txt1)
        self.assertIn("Prova Objetiva", etapas1)
        self.assertIn("Prova Discursiva/Redação", etapas1)
        self.assertIn("Avaliação de Títulos", etapas1)

        txt2 = "Haverá teste de aptidão física (TAF) e prova prática para operadores."
        etapas2 = parse_etapas_prova(txt2)
        self.assertIn("Prova Prática", etapas2)
        self.assertIn("Teste de Aptidão Física (TAF)", etapas2)

    def test_extrair_salarios_por_cargo(self):
        cargos = ["Enfermeiro (40h)", "Técnico de Enfermagem", "Médico Plantonista"]
        txt = "O certame oferece para Enfermeiro: R$ 4.500,00; Técnico de Enfermagem - R$ 2.800,00; Médico Plantonista: R$ 12.000,00."
        res = extrair_salarios_por_cargo(cargos, txt, 2800.0, 12000.0)
        self.assertEqual(res.get("enfermeiro"), 4500.0)
        self.assertEqual(res.get("tecnico de enfermagem"), 2800.0)
        self.assertEqual(res.get("medico plantonista"), 12000.0)



    def test_novas_funcionalidades_render_site(self):
        render_path = Path(__file__).resolve().parent.parent / "render_site.py"
        self.assertTrue(render_path.exists())
        code = render_path.read_text(encoding="utf-8")

        # 1. Botão flutuante no canto inferior direito
        self.assertIn("bottom: 22px !important;", code)
        self.assertIn("right: 22px !important;", code)

        # 2. Correção de auxTotItem no template de renderizarBuscaCargo
        self.assertIn("const auxTotItem = (item.beneficios_total && item.beneficios_total > 0)", code)

        # 3. Suporte a fixar cargo personalizado
        self.assertIn('id="modalFixarCargo"', code)
        self.assertIn('id="pinnedRoleBanner"', code)
        self.assertIn('id="tabItemFisio"', code)
        self.assertIn("obterCargoFixado", code)
        self.assertIn("salvarCargoFixado", code)

        # 4. Busca rápida e interseção dinâmica de filtros
        self.assertIn("function itemCasaCargo(", code)
        self.assertIn("function passaItemFast(", code)
        self.assertIn("it._cargosJoined", code)

if __name__ == "__main__":
    unittest.main()

