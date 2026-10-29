"""Configuração guiada do Google Sheets: chave, planilha e teste, tudo pela tela."""
import streamlit as st

from step5_dashboard import sheets_sync

st.title("☁️ Google Sheets")
st.write("Espelhe suas notas em uma planilha do Google (abas **Notas**, **Itens** e **Resumo Mensal**). "
         "Depois de configurado, cada nota processada atualiza a planilha sozinha.")

cfg = sheets_sync.configuracao()
chave = sheets_sync.dados_chave()

# ── Passo 1: chave da conta de serviço ───────
st.subheader(("✅ " if chave else "1️⃣ ") + "Chave de acesso do Google")


def _enviar_chave(arquivo):
    try:
        email = sheets_sync.salvar_chave(arquivo.getvalue())
        st.success(f"Chave salva. Conta de serviço: {email}")
        return True
    except ValueError as e:
        st.error(str(e))
        return False


if chave:
    st.write("Conta de serviço em uso (clique no ícone para copiar o e-mail):")
    st.code(chave["client_email"], language=None)
    with st.expander("Trocar a chave"):
        arquivo = st.file_uploader("Nova chave JSON", type="json", key="nova_chave")
        if arquivo and _enviar_chave(arquivo):
            st.rerun()
else:
    st.markdown(
        "É feito uma única vez, no Google Cloud (gratuito):\n"
        "1. Abra **Contas de serviço**, escolha ou crie um projeto e clique em **Criar conta de serviço** "
        "(só o nome basta; pule as permissões).\n"
        "2. Na conta criada, vá em **Chaves > Adicionar chave > Criar nova chave > JSON**. O arquivo é baixado.\n"
        "3. Ative a **Google Sheets API** no mesmo projeto.\n"
        "4. Arraste o arquivo baixado aqui embaixo."
    )
    c1, c2 = st.columns(2)
    c1.link_button("Abrir Contas de serviço", sheets_sync.LINK_CONTAS_SERVICO, use_container_width=True)
    c2.link_button("Ativar Google Sheets API", sheets_sync.LINK_API_SHEETS, use_container_width=True)
    arquivo = st.file_uploader("Chave JSON da conta de serviço", type="json")
    if arquivo and _enviar_chave(arquivo):
        st.rerun()
    st.stop()

# ── Passo 2: planilha ────────────────────────
st.subheader(("✅ " if cfg["sheet_id"] else "2️⃣ ") + "Planilha")
st.markdown(
    "1. Crie uma planilha em branco (o botão abaixo abre uma nova).\n"
    f"2. Clique em **Compartilhar** e adicione `{chave['client_email']}` como **Editor**.\n"
    "3. Copie o endereço da planilha na barra do navegador e cole aqui."
)
st.link_button("Criar planilha nova", "https://sheets.new")
with st.form("planilha"):
    link = st.text_input("Link da planilha", value=sheets_sync.link_planilha(cfg["sheet_id"]) if cfg["sheet_id"] else "",
                         placeholder="https://docs.google.com/spreadsheets/d/.../edit")
    if st.form_submit_button("Salvar e testar", type="primary"):
        try:
            sheets_sync.salvar_planilha(link)
            with st.spinner("Conectando ao Google Sheets..."):
                titulo = sheets_sync.testar_conexao()
            st.success(f"Conectado à planilha “{titulo}”.")
        except Exception as e:
            st.error(sheets_sync.mensagem_amigavel(e))
        cfg = sheets_sync.configuracao()

if not cfg["sheet_id"]:
    st.stop()

# ── Passo 3: sincronizar ─────────────────────
st.subheader("3️⃣ Enviar as notas")
c1, c2 = st.columns(2)
if c1.button("🔄 Sincronizar agora", type="primary", use_container_width=True):
    try:
        with st.spinner("Enviando para o Google Sheets..."):
            enviados = sheets_sync.sincronizar()
        st.success(f"Planilha atualizada: {enviados['Notas']} nota(s), {enviados['Itens']} item(ns).")
    except Exception as e:
        st.error(sheets_sync.mensagem_amigavel(e))
c2.link_button("Abrir a planilha", sheets_sync.link_planilha(cfg["sheet_id"]), use_container_width=True)
st.caption("A sincronização reescreve as abas inteiras, então nunca duplica linhas. "
           "Para usar no Looker Studio, veja o guia no README.")
