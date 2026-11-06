"""
pytest configuration and shared fixtures for AI Fiscal Assistant tests.
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ─────────────────────────────────────────────
# Fixtures de dados sintéticos de NF
# ─────────────────────────────────────────────

@pytest.fixture
def nf_texto_completo():
    """Texto OCR simulado de uma NF-e completa."""
    return """
NFC-e nº 000012345
Data de Emissão: 15/01/2024
CNPJ: 12.345.678/0001-90
NOME DA EMPRESA LTDA
ENDEREÇO DA EMPRESA, 123 - CENTRO
CIDADE - UF

CÓDIGO    DESCRIÇÃO                    QTD    UN    VL.UNIT    VL.TOTAL
001       PRODUTO TESTE A               2     UN      25,50       51,00
002       PRODUTO TESTE B               1     UN     100,00      100,00
003       SERVIÇO TESTE C               3     UN      15,00       45,00

Valor Total R$ 196,00
Tributos Totais R$ 19,60
"""

@pytest.fixture
def nf_texto_minimo():
    """Texto OCR mínimo com apenas campos obrigatórios."""
    return """
NFC-e no 99999
Data: 01/02/2024
CNPJ: 98.765.432/0001-10
EMPRESA MINIMA LTDA
Valor Total R$ 50,00
"""

@pytest.fixture
def nf_texto_com_erros_ocr():
    """Texto com erros típicos de OCR para testar robustez."""
    return """
NKC-e no 77777
Data Emissao 10/03/2024
CNJ: 11.222.333/4444-55
EMPRESA COM ERROS DE OCR LTDA
Va1or Tota1 R$ 123,45
Tributos Totais R$ 12,34
"""

@pytest.fixture
def nota_fiscal_dados():
    """Dataclass NotaFiscal populada para testes."""
    from step1_ocr.extractor import NotaFiscal
    nf = NotaFiscal()
    nf.numero = "12345"
    nf.data_emissao = "15/01/2024"
    nf.cnpj_emitente = "12.345.678/0001-90"
    nf.nome_emitente = "NOME DA EMPRESA LTDA"
    nf.valor_total = 196.00
    nf.impostos = 19.60
    nf.fonte = "ocr"
    nf.confidence_score = {
        'numero': 1.0,
        'data_emissao': 1.0,
        'cnpj': 1.0,
        'valor_total': 1.0,
        'impostos': 1.0
    }
    return nf


@pytest.fixture
def nota_processada_dados():
    """Dataclass NotaFiscalProcessada populada para testes."""
    from step2_llm.processor import NotaFiscalProcessada
    nota = NotaFiscalProcessada()
    nota.numero = "12345"
    nota.data_emissao = "15/01/2024"
    nota.cnpj_emitente = "12.345.678/0001-90"
    nota.nome_emitente = "NOME DA EMPRESA LTDA"
    nota.valor_total = 196.00
    nota.impostos = 19.60
    nota.itens = [
        {"descricao": "PRODUTO TESTE A", "valor": 51.00},
        {"descricao": "PRODUTO TESTE B", "valor": 100.00},
        {"descricao": "SERVIÇO TESTE C", "valor": 45.00},
    ]
    nota.rota = "vision"
    nota.confianca = "alta"
    return nota


@pytest.fixture
def temp_db_path():
    """Cria banco SQLite temporário para testes isolados."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_notas_fiscais.db")
    yield db_path
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def init_test_db(temp_db_path):
    """Inicializa o banco de dados de teste (cria tabelas)."""
    from step3_database.crud import init_db
    init_db(temp_db_path)
    return temp_db_path


@pytest.fixture
def temp_excel_path():
    """Cria arquivo Excel temporário para testes."""
    temp_dir = tempfile.mkdtemp()
    excel_path = os.path.join(temp_dir, "test_notas_fiscais.xlsx")
    yield excel_path
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def mock_lm_studio():
    """Mock automático do servidor LM Studio para testes."""
    with patch('requests.post') as mock_post, \
         patch('requests.get') as mock_get:

        # Mock para /v1/models (verificação de servidor)
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": [{"id": "qwen2.5-vl-3b-instruct"}]}

        # Mock para /v1/chat/completions (Vision e Chat)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '''{
  "numero": "12345",
  "data_emissao": "15/01/2024",
  "cnpj_emitente": "12.345.678/0001-90",
  "nome_emitente": "NOME DA EMPRESA LTDA",
  "valor_total": 196.00,
  "impostos": 19.60,
  "itens": [
    {"descricao": "PRODUTO TESTE A", "valor": 51.00},
    {"descricao": "PRODUTO TESTE B", "valor": 100.00}
  ],
  "confianca": "alta"
}'''
                }
            }]
        }
        mock_post.return_value = mock_response

        yield mock_post


@pytest.fixture
def sample_image_path():
    """Cria uma imagem temporária simples para testes de OCR/Vision."""
    from PIL import Image
    import tempfile

    # Cria imagem simples 200x100 branca
    img = Image.new('RGB', (200, 100), color='white')
    temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    img.save(temp_file.name)
    temp_file.close()

    yield temp_file.name

    # Cleanup
    try:
        os.unlink(temp_file.name)
    except:
        pass


# ─────────────────────────────────────────────
# Configuração de banco de teste
# ─────────────────────────────────────────────

@pytest.fixture
def test_db_session(temp_db_path):
    """Fornece sessão de banco de teste isolada."""
    from step3_database.crud import init_db, get_session
    from step3_database.models import Base

    init_db(temp_db_path)
    # get_session é um context manager, usa-lo corretamente
    with get_session(temp_db_path) as session:
        yield session
    # session.close() é chamado automaticamente pelo context manager


# ─────────────────────────────────────────────
# Helpers de asserção
# ─────────────────────────────────────────────

def assert_nf_campos_obrigatorios(nf):
    """Verifica se NotaFiscal tem campos obrigatórios preenchidos."""
    assert nf.numero is not None, "Número da NF não deve ser None"
    assert nf.data_emissao is not None, "Data emissão não deve ser None"
    assert nf.cnpj_emitente is not None, "CNPJ não deve ser None"
    assert nf.valor_total is not None, "Valor total não deve ser None"
    assert isinstance(nf.valor_total, float), "Valor total deve ser float"


@pytest.fixture
def assert_nota_processada_valida():
    """Fixture que retorna função de validação para NotaFiscalProcessada."""
    def _validar(nota):
        assert nota.numero is not None
        assert nota.data_emissao is not None
        assert nota.cnpj_emitente is not None
        assert nota.valor_total is not None
        assert isinstance(nota.valor_total, float)
        assert nota.rota in ("vision", "vision+tesseract")
        assert nota.confianca in ("alta", "media", "baixa")
    return _validar


@pytest.fixture
def assert_nf_campos_obrigatorios():
    """Fixture que retorna função de validação para NotaFiscal (step1_ocr)."""
    def _validar(nf):
        assert nf.numero is not None, "Número da NF não deve ser None"
        assert nf.data_emissao is not None, "Data emissão não deve ser None"
        assert nf.cnpj_emitente is not None, "CNPJ não deve ser None"
        assert nf.valor_total is not None, "Valor total não deve ser None"
        assert isinstance(nf.valor_total, float), "Valor total deve ser float"
    return _validar