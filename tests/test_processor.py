"""
Testes para step2_llm/processor.py
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from step2_llm.processor import (
    NotaFiscalProcessada,
    limpar_valor_monetario,
    parse_json,
    chamar_llm_vision,
    chamar_llm_texto,
    montar_nota,
    processar_nota_fiscal,
    PROMPT_TEXTO,
)


class TestLimparValorMonetarioProcessor:
    """Testes da função limpar_valor_monetario (versão do processor)."""

    def test_formato_brasileiro(self):
        assert limpar_valor_monetario("1.234,56") == 1234.56

    def test_formato_erro_ocr_pontos(self):
        assert limpar_valor_monetario("1.234.56") == 1234.56

    def test_apenas_virgula(self):
        assert limpar_valor_monetario("123,45") == 123.45

    def test_com_rs(self):
        assert limpar_valor_monetario("R$ 1.234,56") == 1234.56

    def test_none_retorna_zero(self):
        assert limpar_valor_monetario(None) == 0.0

    def test_ja_e_float(self):
        assert limpar_valor_monetario(100.50) == 100.50

    def test_int(self):
        assert limpar_valor_monetario(100) == 100.0


class TestParseJson:
    """Testes para parse_json (tolerante a JSON incompleto/corrompido)."""

    def test_json_valido(self):
        json_str = '{"numero": "123", "valor_total": 100.50}'
        result = parse_json(json_str)
        assert result["numero"] == "123"
        assert result["valor_total"] == 100.50

    def test_json_com_markdown(self):
        json_str = '''```json
{"numero": "123", "valor_total": 100.50}
```'''
        result = parse_json(json_str)
        assert result["numero"] == "123"

    def test_json_incompleto_faltando_chaves(self):
        json_str = '{"numero": "123", "valor_total": 100.50'
        result = parse_json(json_str)
        assert result["numero"] == "123"
        assert result["valor_total"] == 100.50

    def test_json_incompleto_faltando_colchetes(self):
        json_str = '{"itens": [{"descricao": "A", "valor": 10.0}'
        result = parse_json(json_str)
        assert result["itens"] == [{"descricao": "A", "valor": 10.0}]

    def test_json_com_virgula_final(self):
        json_str = '{"numero": "123",}'
        result = parse_json(json_str)
        assert result["numero"] == "123"

    def test_json_totalmente_corrompido_fallback_regex(self):
        json_str = 'numero: "456" valor_total: 200.00'
        result = parse_json(json_str)
        assert result["numero"] == "456"
        assert result["valor_total"] == 200.00


class TestMontarNota:
    """Testes para montar_nota."""

    def test_monta_nota_completa(self):
        dados = {
            "numero": "12345",
            "data_emissao": "15/01/2024",
            "cnpj_emitente": "12.345.678/0001-90",
            "nome_emitente": "EMPRESA LTDA",
            "valor_total": "196,00",
            "impostos": "19,60",
            "itens": [{"descricao": "PRODUTO A", "valor": "51,00"}],
            "confianca": "alta",
        }
        nota = montar_nota(dados, rota="vision")

        assert nota.numero == "12345"
        assert nota.data_emissao == "15/01/2024"
        assert nota.cnpj_emitente == "12.345.678/0001-90"
        assert nota.nome_emitente == "EMPRESA LTDA"
        assert nota.valor_total == 196.00
        assert nota.impostos == 19.60
        assert len(nota.itens) == 1
        assert nota.itens[0]["descricao"] == "PRODUTO A"
        assert nota.rota == "vision"
        assert nota.confianca == "alta"

    def test_monta_nota_com_campos_none(self):
        dados = {
            "numero": None,
            "data_emissao": None,
            "cnpj_emitente": None,
            "nome_emitente": None,
            "valor_total": None,
            "impostos": None,
            "itens": [],
            "confianca": "media",
        }
        nota = montar_nota(dados, rota="vision+tesseract")

        assert nota.numero is None
        assert nota.valor_total == 0.0
        assert nota.impostos == 0.0
        assert nota.rota == "vision+tesseract"


class TestChamarLLMVision:
    """Testes para chamar_llm_vision (mockado)."""

    @patch('step2_llm.processor.requests.post')
    @patch('step2_llm.processor.imagem_para_base64')
    def test_chama_vision_retorna_json(self, mock_img_base64, mock_post, sample_image_path):
        # Setup mocks
        mock_img_base64.return_value = ("base64string", "image/png")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"numero": "12345", "valor_total": 100.0, "confianca": "alta"}'
                }
            }]
        }
        mock_post.return_value = mock_response

        # Test
        from step2_llm.processor import chamar_llm_vision
        result = chamar_llm_vision(sample_image_path)

        assert result["numero"] == "12345"
        assert result["valor_total"] == 100.0
        mock_post.assert_called_once()


class TestChamarLLMTexto:
    """Testes para chamar_llm_texto (mockado)."""

    @patch('step2_llm.processor.requests.post')
    def test_chama_texto_com_ocr(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"numero": "99999", "valor_total": 50.0, "confianca": "media"}'
                }
            }]
        }
        mock_post.return_value = mock_response

        from step2_llm.processor import chamar_llm_texto
        texto_ocr = "NFC-e no 99999\nValor Total R$ 50,00"
        result = chamar_llm_texto(texto_ocr)

        assert result["numero"] == "99999"
        assert result["valor_total"] == 50.0
        mock_post.assert_called_once()


class TestProcessarNotaFiscal:
    """Testes de integração do fluxo principal (mockados)."""

    @patch('step2_llm.processor.verificar_servidor')
    @patch('step2_llm.processor.chamar_llm_vision')
    @patch('step2_llm.processor.extrair_com_tesseract')
    def test_fluxo_vision_sucesso(self, mock_tesseract, mock_vision, mock_servidor, sample_image_path):
        """Vision extrai tudo, não precisa fallback."""
        mock_servidor.return_value = True

        mock_vision.return_value = {
            "numero": "12345",
            "data_emissao": "15/01/2024",
            "cnpj_emitente": "12.345.678/0001-90",
            "nome_emitente": "EMPRESA LTDA",
            "valor_total": 196.00,
            "impostos": 19.60,
            "itens": [{"descricao": "PRODUTO A", "valor": 51.00}],
            "confianca": "alta",
        }

        nota = processar_nota_fiscal(sample_image_path)

        assert nota.numero == "12345"
        assert nota.rota == "vision"
        assert nota.confianca == "alta"
        assert len(nota.itens) == 1
        mock_tesseract.assert_not_called()

    @patch('step2_llm.processor.verificar_servidor')
    @patch('step2_llm.processor.chamar_llm_vision')
    @patch('step2_llm.processor.extrair_com_tesseract')
    def test_fluxo_com_fallback_tesseract(self, mock_tesseract, mock_vision, mock_servidor, sample_image_path):
        """Vision falha em alguns campos, Tesseract complementa."""
        mock_servidor.return_value = True

        # Vision retorna sem número e sem impostos
        mock_vision.return_value = {
            "numero": None,
            "data_emissao": "15/01/2024",
            "cnpj_emitente": "12.345.678/0001-90",
            "nome_emitente": "EMPRESA LTDA",
            "valor_total": 196.00,
            "impostos": None,
            "itens": [],
            "confianca": "media",
        }

        # Tesseract retorna texto com número e impostos
        mock_tesseract.return_value = """
        NFC-e no 12345
        Tributos Totais R$ 19,60
        """

        nota = processar_nota_fiscal(sample_image_path)

        assert nota.numero == "12345"  # Preenchido pelo Tesseract
        assert nota.impostos == 19.60  # Preenchido pelo Tesseract
        assert nota.rota == "vision+tesseract"
        mock_tesseract.assert_called_once()

    @patch('step2_llm.processor.verificar_servidor')
    def test_servidor_indisponivel(self, mock_servidor, sample_image_path):
        mock_servidor.return_value = False

        with pytest.raises(ConnectionError):
            processar_nota_fiscal(sample_image_path)


class TestNotaFiscalProcessadaDataclass:
    """Testes do dataclass NotaFiscalProcessada."""

    def test_criacao_padrao(self):
        nota = NotaFiscalProcessada()
        assert nota.rota == "vision"
        assert nota.confianca == "alta"
        assert nota.itens == []

    def test_criacao_com_dados(self, nota_processada_dados, assert_nota_processada_valida):
        assert_nota_processada_valida(nota_processada_dados)
        assert nota_processada_dados.numero == "12345"
        assert len(nota_processada_dados.itens) == 3