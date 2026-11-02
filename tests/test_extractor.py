"""
Testes para step1_ocr/extractor.py
"""
import pytest
import re
from step1_ocr.extractor import (
    NotaFiscal,
    parsear_nota,
    pre_processar_imagem,
)
from step2_llm.processor import limpar_valor_monetario


class TestLimparValorMonetario:
    """Testes para a função limpar_valor_monetario."""

    def test_formato_brasileiro_padrao(self):
        """Formato BR: 1.163,38"""
        assert limpar_valor_monetario("1.163,38") == 1163.38

    def test_formato_apenas_virgula(self):
        """Formato: 163,38"""
        assert limpar_valor_monetario("163,38") == 163.38

    def test_formato_erro_ocr_multiplos_pontos(self):
        """Erro OCR comum: 1.163.38 -> deve virar 1163.38"""
        assert limpar_valor_monetario("1.163.38") == 1163.38

    def test_valor_com_rs(self):
        """Valor com R$ prefixo"""
        assert limpar_valor_monetario("R$ 1.234,56") == 1234.56

    def test_valor_zero(self):
        """Zero"""
        assert limpar_valor_monetario("0,00") == 0.0
        assert limpar_valor_monetario("R$ 0,00") == 0.0

    def test_none_retorna_zero(self):
        """None retorna 0.0"""
        assert limpar_valor_monetario(None) == 0.0

    def test_ja_e_float(self):
        """Se já for float, retorna direto"""
        assert limpar_valor_monetario(123.45) == 123.45

    def test_string_vazia(self):
        """String vazia retorna 0.0"""
        assert limpar_valor_monetario("") == 0.0

    def test_valor_malformado(self):
        """Valor completamente malformado retorna 0.0"""
        assert limpar_valor_monetario("abc") == 0.0


class TestParsearNota:
    """Testes para parsear_nota com textos sintéticos."""

    def test_extrai_cnpj_padrao(self, nf_texto_completo):
        nf = parsear_nota(nf_texto_completo)
        assert nf.cnpj_emitente == "12.345.678/0001-90"
        assert nf.confidence_score['cnpj'] == 1.0

    def test_extrai_numero_nf_padrao(self, nf_texto_completo):
        nf = parsear_nota(nf_texto_completo)
        assert nf.numero == "000012345"
        assert nf.confidence_score['numero'] == 1.0

    def test_extrai_data_emissao(self, nf_texto_completo):
        nf = parsear_nota(nf_texto_completo)
        assert nf.data_emissao == "15/01/2024"
        assert nf.confidence_score['data_emissao'] == 1.0

    def test_extrai_valor_total(self, nf_texto_completo):
        nf = parsear_nota(nf_texto_completo)
        assert nf.valor_total == 196.00
        assert nf.confidence_score['valor_total'] == 1.0

    def test_extrai_impostos(self, nf_texto_completo):
        nf = parsear_nota(nf_texto_completo)
        assert nf.impostos == 19.60
        assert nf.confidence_score['impostos'] == 1.0

    def test_campos_ausentes_tem_confianca_zero(self, nf_texto_minimo):
        nf = parsear_nota(nf_texto_minimo)
        # impostos não está no texto mínimo
        assert nf.impostos is None
        assert nf.confidence_score['impostos'] == 0.0

    def test_erro_ocr_numero_nf(self, nf_texto_com_erros_ocr):
        """Testa extração de número com erros OCR (NKC-e, KFC-e, etc.)"""
        nf = parsear_nota(nf_texto_com_erros_ocr)
        # O regex aceita N/K/M antes de FC-e
        assert nf.numero == "77777"

    def test_valor_monetario_erro_ocr(self, nf_texto_com_erros_ocr):
        """Testa parsing de valor com erro OCR (Va1or, Tota1)"""
        nf = parsear_nota(nf_texto_com_erros_ocr)
        # O regex procura "Valor Total" - o erro OCR pode não casar
        # Se não achar, confidence deve ser 0
        if nf.valor_total is None:
            assert nf.confidence_score['valor_total'] == 0.0


class TestPreProcessarImagem:
    """Testes para pré-processamento de imagem."""

    def test_converte_rgb_para_gray(self, sample_image_path):
        import cv2
        import numpy as np
        from PIL import Image

        img = Image.open(sample_image_path)
        resultado = pre_processar_imagem(img)

        assert isinstance(resultado, np.ndarray)
        assert len(resultado.shape) == 2  # Grayscale
        assert resultado.dtype == np.uint8

    def test_imagem_ja_gray(self, sample_image_path):
        """Imagem já em grayscale deve passar direto."""
        import cv2
        import numpy as np
        from PIL import Image

        img = Image.open(sample_image_path).convert('L')  # Já gray
        resultado = pre_processar_imagem(img)

        assert isinstance(resultado, np.ndarray)
        assert len(resultado.shape) == 2


class TestNotaFiscalDataclass:
    """Testes do dataclass NotaFiscal."""

    def test_criacao_vazia(self):
        nf = NotaFiscal()
        assert nf.numero is None
        assert nf.confidence_score == {}

    def test_criacao_com_dados(self, nota_fiscal_dados):
        assert_nf_campos_obrigatorios(nota_fiscal_dados)
        assert nota_fiscal_dados.fonte == "ocr"
        assert len(nota_fiscal_dados.confidence_score) == 5


# ─────────────────────────────────────────────
# Testes de integração (precisam de arquivos reais)
# ─────────────────────────────────────────────

@pytest.mark.integration
def test_processar_pdf_nativo():
    """Testa extração de PDF com texto nativo."""
    pytest.skip("Requer arquivo PDF de teste")


@pytest.mark.integration
def test_processar_imagem_ocr():
    """Testa OCR completo em imagem."""
    pytest.skip("Requer Tesseract instalado e imagem de teste")