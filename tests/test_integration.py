"""
Testes de integração end-to-end (requerem recursos externos).
Execute com: pytest -m integration
"""
import pytest
import tempfile
import os
from step1_ocr.extractor import processar_nota_fiscal as ocr_processar
from step2_llm.processor import processar_nota_fiscal as llm_processar
from step3_spreadsheet.writer import gravar_nota
from step3_database.crud import get_estatisticas


@pytest.mark.integration
class TestIntegracaoOCR:
    """Testes de integração do OCR (requer Tesseract instalado)."""

    def test_ocr_imagem_simples(self):
        """Testa OCR em imagem sintética simples."""
        pytest.skip("Requer imagem de teste real e Tesseract configurado")

    def test_ocr_pdf_nativo(self):
        """Testa extração de PDF com texto nativo."""
        pytest.skip("Requer PDF de teste com texto nativo")

    def test_ocr_pdf_escaneado(self):
        """Testa OCR em PDF escaneado (requer poppler)."""
        pytest.skip("Requer PDF escaneado e poppler instalado")


@pytest.mark.integration
class TestIntegracaoLLM:
    """Testes de integração com LLM local (requer LM Studio rodando)."""

    def test_vision_com_modelo_real(self, sample_image_path):
        """Testa Vision com modelo real no LM Studio."""
        pytest.skip("Requer LM Studio rodando na porta 1234 com modelo carregado")

    def test_fallback_tesseract_real(self, sample_image_path):
        """Testa fallback Tesseract real."""
        pytest.skip("Requer LM Studio + Tesseract configurado")


@pytest.mark.integration
class TestIntegracaoPipelineCompleto:
    """Teste do pipeline completo OCR → LLM → SQLite."""

    def test_pipeline_completo_com_arquivo_real(self):
        """Processa NF real → salva no SQLite → verifica dashboard."""
        pytest.skip("Requer NF real, LM Studio, Tesseract, SQLite")


@pytest.mark.slow
class TestPerformance:
    """Testes de performance/bateria."""

    def test_processamento_multiplas_notas(self):
        """Processa múltiplas notas em sequência."""
        pytest.skip("Teste de carga - requer múltiplas NFs de teste")

    def test_migracao_excel_grande(self):
        """Migra planilha grande (>1000 notas)."""
        pytest.skip("Requer planilha grande de teste")


# ─────────────────────────────────────────────
# Testes manuais auxiliares (não automatizados)
# ─────────────────────────────────────────────

def test_manual_criar_fixtures_reais():
    """
    Helper para criar fixtures reais a partir de NFs reais.
    Execute manualmente: python -m tests.test_integration::test_manual_criar_fixtures_reais
    """
    print("Para criar fixtures reais:")
    print("1. Coloque NFs reais em tests/fixtures/real/")
    print("2. Rode este teste com -s para ver output")
    print("3. Copie os dados extraídos para fixtures sintéticos")
    pass


if __name__ == "__main__":
    # Permite rodar direto para debug
    pytest.main([__file__, "-v", "-m", "integration"])