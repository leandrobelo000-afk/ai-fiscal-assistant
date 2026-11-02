import json
from types import SimpleNamespace

import gspread
import pytest

from step5_dashboard import database, sheets_sync


def _popular(banco):
    for numero, data, valor in [("1", "10/07/2026", 700.0), ("2", "05/09/2026", 80.5)]:
        database.salvar_nota(SimpleNamespace(
            numero=numero, data_emissao=data, cnpj_emitente="11.111.111/0001-11", nome_emitente="Posto A",
            valor_total=valor, impostos=None, itens=[{"descricao": "Gasolina", "valor": valor}],
            rota="vision", confianca="alta"), banco)


def test_montar_tabelas(tmp_path):
    banco = tmp_path / "t.db"
    _popular(banco)
    tabelas = sheets_sync.montar_tabelas(database.carregar_notas(banco), database.carregar_itens(banco))
    assert list(tabelas) == ["Notas", "Itens", "Resumo Mensal"]
    notas = tabelas["Notas"]
    cab = notas[0]
    assert notas[1][cab.index("data_emissao")] == "2026-07-10"
    assert notas[1][cab.index("cnpj_emitente")] == "11.111.111/0001-11"
    assert notas[2][cab.index("valor_total")] == 80.5
    assert len(tabelas["Resumo Mensal"]) == 1 + 3  # julho, agosto (vazio) e setembro
    # Tudo precisa ser serializável em JSON (a API do Sheets rejeita numpy e NaN)
    json.dumps(tabelas, allow_nan=False)


class _AbaFalsa:
    def __init__(self):
        self.valores = None
    def clear(self):
        self.valores = None
    def update(self, values, range_name, value_input_option):
        assert range_name == "A1" and value_input_option == "RAW"
        self.valores = values
    def freeze(self, rows):
        pass


class _PlanilhaFalsa:
    def __init__(self):
        self.abas = {}
    def worksheet(self, nome):
        if nome not in self.abas:
            raise gspread.WorksheetNotFound(nome)
        return self.abas[nome]
    def add_worksheet(self, title, rows, cols):
        self.abas[title] = _AbaFalsa()
        return self.abas[title]


def test_sincronizar_reescreve_sem_duplicar(tmp_path, monkeypatch):
    banco = tmp_path / "t.db"
    _popular(banco)
    chave = tmp_path / "chave.json"
    chave.write_text("{}")
    planilha = _PlanilhaFalsa()
    monkeypatch.setattr(gspread, "service_account",
                        lambda filename: SimpleNamespace(open_by_key=lambda k: planilha))

    assert sheets_sync.sincronizar(banco, "ID", str(chave)) == {"Notas": 2, "Itens": 2, "Resumo Mensal": 3}
    sheets_sync.sincronizar(banco, "ID", str(chave))
    assert len(planilha.abas["Notas"].valores) == 3  # cabeçalho + 2, mesmo sincronizando duas vezes


def test_sem_configuracao(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
    assert not sheets_sync.configurado()
    with pytest.raises(ValueError):
        sheets_sync.sincronizar(tmp_path / "t.db")


CHAVE = json.dumps({"type": "service_account", "client_email": "robo@projeto.iam.gserviceaccount.com",
                    "project_id": "projeto"}).encode()


@pytest.mark.parametrize("texto, esperado", [
    ("https://docs.google.com/spreadsheets/d/1AbC-dEf_123456789012345/edit#gid=0", "1AbC-dEf_123456789012345"),
    ("  1AbC-dEf_123456789012345  ", "1AbC-dEf_123456789012345"),
    ("https://google.com", ""),
    ("", ""),
])
def test_extrair_id(texto, esperado):
    assert sheets_sync.extrair_id(texto) == esperado


def test_configuracao_pela_tela(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CREDENTIALS", raising=False)
    assert sheets_sync.salvar_chave(CHAVE) == "robo@projeto.iam.gserviceaccount.com"
    assert not sheets_sync.configurado()
    sheets_sync.salvar_planilha("https://docs.google.com/spreadsheets/d/1AbC-dEf_123456789012345/edit")
    assert sheets_sync.configurado()
    assert sheets_sync.configuracao()["sheet_id"] == "1AbC-dEf_123456789012345"
    assert sheets_sync.dados_chave()["project_id"] == "projeto"


def test_config_da_tela_vale_mais_que_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GOOGLE_SHEET_ID", "ID_ANTIGO_DO_ENV")
    assert sheets_sync.configuracao()["sheet_id"] == "ID_ANTIGO_DO_ENV"
    sheets_sync.salvar_planilha("1AbC-dEf_123456789012345")
    assert sheets_sync.configuracao()["sheet_id"] == "1AbC-dEf_123456789012345"


@pytest.mark.parametrize("conteudo", [b"nao e json", b'{"type": "authorized_user"}', b"[]"])
def test_chave_invalida(tmp_path, monkeypatch, conteudo):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        sheets_sync.salvar_chave(conteudo)
    assert not (tmp_path / sheets_sync.CREDENCIAIS_PADRAO).exists()


def test_mensagens_amigaveis(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sheets_sync.salvar_chave(CHAVE)
    try:
        raise PermissionError from Exception("The caller does not have permission")
    except PermissionError as e:
        assert "robo@projeto.iam.gserviceaccount.com" in sheets_sync.mensagem_amigavel(e)
    try:
        raise PermissionError from Exception("Google Sheets API has not been used in project 123 ... SERVICE_DISABLED")
    except PermissionError as e:
        assert "sheets.googleapis.com?project=projeto" in sheets_sync.mensagem_amigavel(e)
