import sys
import os
import tempfile
import json
import requests
import streamlit as st
import glob
from dataclasses import asdict

caminho_raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if caminho_raiz not in sys.path:
    sys.path.append(caminho_raiz)

# ==========================================
# CONFIGURAÇÃO VIA .ENV
# ==========================================
from config import settings

# ==========================================
# IMPORTAÇÕES DAS ETAPAS ANTERIORES
# ==========================================

from step2_llm.processor import processar_nota_fiscal
from step3_spreadsheet.writer import gravar_nota
from step5_dashboard.database import salvar_nota
from step5_dashboard import sheets_sync
from step1_ocr.extractor import verificar_tesseract

# Importa funções de leitura do banco SQLite
try:
    from step3_database import (
        obter_todas_notas_para_dataframe,
        obter_todos_itens_para_dataframe,
        get_estatisticas,
        init_db
    )
    USAR_SQLITE = True
except ImportError:
    USAR_SQLITE = False

@st.cache_resource(show_spinner="Verificando o Tesseract...")
def _tesseract_disponivel() -> bool:
    # Uma vez por sessão do servidor: evita repetir a instalação (e o aviso do UAC) a cada clique
    return verificar_tesseract()

# 1. Configuração da Página
# Quando roda dentro do app da Etapa 5, a configuração já foi feita lá
try:
    st.set_page_config(page_title="AI Fiscal Assistant", page_icon="🧾", layout="wide")
except st.errors.StreamlitAPIException:
    pass

# ==========================================
# BARRA LATERAL (CONFIGURAÇÕES)
# ==========================================
with st.sidebar:
    st.header("⚙️ Configurações do Sistema")
    st.write("Escolha onde os dados serão salvos/lidos:")
    
    # Busca bancos de dados existentes (.db) e planilhas (.xlsx)
    bancos_encontrados = glob.glob("**/*.db", recursive=True)
    planilhas_encontradas = glob.glob("**/*.xlsx", recursive=True)
    todos_arquivos = bancos_encontrados + planilhas_encontradas

    # Exibe o SelectBox
    if todos_arquivos:
        arquivo_selecionado = st.selectbox("📁 Banco de Dados Atual:", todos_arquivos)
    else:
        arquivo_selecionado = "notas_fiscais.db"  # Nome padrão SQLite

    # Campo para criar novo
    novo_arquivo = st.text_input("✨ Ou crie um novo (ex: notas_maio.db):")

    # Regra de negócio
    if novo_arquivo:
        if not novo_arquivo.endswith((".db", ".xlsx")):
            novo_arquivo += ".db"  # Default para SQLite
        caminho_arquivo = novo_arquivo
    else:
        caminho_arquivo = arquivo_selecionado

    # Feedback visual
    st.success(f"📌 Usando banco: {caminho_arquivo}")

    # Inicializa o banco se for SQLite
    if USAR_SQLITE and caminho_arquivo.endswith(".db"):
        init_db(caminho_arquivo)

    # Status do Tesseract
    if not _tesseract_disponivel():
        st.warning(
            "⚠️ Tesseract não está instalado, então o OCR de apoio fica desligado. "
            "A leitura pelo modelo Vision continua funcionando. Para ativar, instale o "
            "[Tesseract para Windows](https://github.com/UB-Mannheim/tesseract/wiki) "
            "e reinicie o app."
        )

st.title("🧾 AI Fiscal Assistant - Central")
st.write("Faça o upload, extraia os dados, salve na planilha e converse com a nota!")

# ==========================================
# ÁREA PRINCIPAL: COLUNAS
# ==========================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("📤 1. Upload e Processamento")
    arquivo_enviado = st.file_uploader("Arraste seu PDF ou Imagem da NF aqui", type=["pdf", "png", "jpg", "jpeg"])

    if arquivo_enviado is not None:
        if st.button("Processar Nota Fiscal", type="primary"):

            with st.spinner("Analisando com IA (Qwen-VL)... Isso pode levar alguns segundos."):
                try:
                    # PASSO A: Salvar o arquivo do Streamlit temporariamente no HD
                    extensao = arquivo_enviado.name.split('.')[-1]
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extensao}") as tmp_file:
                        tmp_file.write(arquivo_enviado.getvalue())
                        caminho_temp = tmp_file.name

                    # PASSO B: Executar as Etapas 1 e 2 (OCR e LLM)
                    st.toast("Lendo o documento...")
                    nota_processada = processar_nota_fiscal(caminho_temp)

                    # Salva os dados na memória da sessão para o Chat poder usar depois
                    st.session_state['nota_atual'] = nota_processada

                    # PASSO C: Gravar na base SQLite (fonte única, Etapa 5) e na planilha (Etapa 3)
                    st.toast("Salvando na base de dados...")
                    salvar_nota(nota_processada)
                    st.toast("Salvando na planilha...")
                    gravar_nota(nota_processada, caminho_arquivo)

                    # PASSO D: Espelhar no Google Sheets, se configurado (Etapa 5.2)
                    if sheets_sync.configurado():
                        try:
                            sheets_sync.sincronizar()
                            st.toast("Google Sheets atualizado.")
                        except Exception as e:
                            st.warning(f"Nota salva, mas o Google Sheets não foi atualizado: {sheets_sync.mensagem_amigavel(e)}")
                    
                    st.success("✅ Nota processada e salva com sucesso!")

                    # Mostra os dados extraídos de forma bonita na tela
                    st.json(nota_processada.__dict__)

                except Exception as e:
                    st.error(f"Ocorreu um erro no processamento: {e}")
                finally:
                    # PASSO E: Limpeza - deleta o arquivo temporário para não lotar o PC
                    if 'caminho_temp' in locals() and os.path.exists(caminho_temp):
                        os.remove(caminho_temp)

with col2:
    st.subheader("💬 2. Chat com a Nota Fiscal")

    if "mensagens" not in st.session_state:
        st.session_state.mensagens = []

    for msg in st.session_state.mensagens:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    pergunta_usuario = st.chat_input("O que você quer saber sobre esta nota?")

    if pergunta_usuario:
        if 'nota_atual' not in st.session_state:
            st.warning("⚠️ Por favor, processe uma nota fiscal primeiro antes de fazer perguntas.")
        else:
            with st.chat_message("user"):
                st.write(pergunta_usuario)
            st.session_state.mensagens.append({"role": "user", "content": pergunta_usuario})

            with st.spinner("A IA está analisando a nota fiscal. Isso pode levar alguns segundos..."):
                try:
                    nota_atual = st.session_state['nota_atual']
                    dados_em_json = json.dumps(asdict(nota_atual), indent=2, ensure_ascii=False)

                    payload = {
                        "model": settings.MODELO_CHAT,
                        "temperature": settings.TEMPERATURA,
                        "messages": [
                            {
                                "role": "system",
                                "content": f"Você é um analista financeiro prestativo que fala português e realiza a análise de notas fiscais brasileiras.\nResponda APENAS com base nos dados fornecidos abaixo:\n\n{dados_em_json}"
                            },
                            {"role": "user", "content": pergunta_usuario}
                        ]
                    }

                    url_api = settings.LM_STUDIO_URL
                    resposta_requisicao = requests.post(url_api, json=payload)

                    texto_final = resposta_requisicao.json()["choices"][0]["message"]["content"]

                except Exception as e:
                    texto_final = f"❌ Erro ao comunicar com a IA local: {str(e)}"

            with st.chat_message("assistant"):
                st.write(texto_final)
            st.session_state.mensagens.append({"role": "assistant", "content": texto_final})

    # ==========================================
    # VISUALIZADOR DO BANCO DE DADOS NA TELA
    # ==========================================
    st.divider()
    st.subheader("📊 Banco de Dados (SQLite)")

    if USAR_SQLITE and caminho_arquivo.endswith(".db"):
        # Usa SQLite
        df = obter_todas_notas_para_dataframe(caminho_arquivo)

        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Mostra itens se houver
            df_itens = obter_todos_itens_para_dataframe(caminho_arquivo)
            if not df_itens.empty:
                with st.expander("📦 Ver Itens Detalhados"):
                    st.dataframe(df_itens, use_container_width=True, hide_index=True)
        else:
            st.info("Banco de dados vazio. Processe uma nota fiscal para ver os dados.")
    else:
        # Fallback para Excel
        if os.path.exists(caminho_arquivo):
            import pandas as pd
            try:
                df = pd.read_excel(caminho_arquivo, sheet_name="Resumo")
                st.dataframe(df, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Erro ao ler planilha: {e}")
        else:
            st.info("Nenhum banco de dados ou planilha encontrado.")


# ==========================================
# ETAPA 5: DASHBOARD E ANALYTICS
# ==========================================
st.divider()
st.header("📈 Painel Executivo (Dashboard)")

if USAR_SQLITE and caminho_arquivo.endswith(".db"):
    # Usa estatísticas do SQLite
    stats = get_estatisticas(caminho_arquivo)
    df = obter_todas_notas_para_dataframe(caminho_arquivo)

    if not df.empty:
        faturamento_total = stats["faturamento_total"]
        impostos_totais = stats["impostos_totais"]
        total_notas = stats["total_notas"]
        ticket_medio = stats["ticket_medio"]
    else:
        faturamento_total = 0.0
        impostos_totais = 0.0
        total_notas = 0
        ticket_medio = 0.0
else:
    # Fallback para Excel
    if os.path.exists(caminho_arquivo):
        import pandas as pd

        df = pd.read_excel(caminho_arquivo, sheet_name="Resumo")
        df.rename(columns={
            "Valor Total (R$)": "valor_total",
            "Impostos": "impostos"
        }, inplace=True)

        if not df.empty:
            if "valor_total" in df.columns:
                faturamento_total = df["valor_total"].sum()
            else:
                faturamento_total = 0.0

            if "impostos" in df.columns:
                impostos_totais = df["impostos"].sum()
            elif "Impostos" in df.columns:
                impostos_totais = df["Impostos"].sum()
            else:
                impostos_totais = 0.0

            total_notas = len(df)
            ticket_medio = faturamento_total / total_notas if total_notas > 0 else 0.0
        else:
            faturamento_total = 0.0
            impostos_totais = 0.0
            total_notas = 0
            ticket_medio = 0.0
    else:
        st.warning("Nenhum banco de dados ou planilha encontrado para gerar o dashboard. Por favor, faça o upload de uma nota fiscal primeiro.")
        faturamento_total = 0.0
        impostos_totais = 0.0
        total_notas = 0
        ticket_medio = 0.0

def formata_br(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.metric(label="💰 Faturamento", value=formata_br(faturamento_total))
with kpi2:
    st.metric(label="🏛️ Impostos", value=formata_br(impostos_totais))
with kpi3:
    st.metric(label="📊 Ticket Médio", value=formata_br(ticket_medio))
with kpi4:
    st.metric(label="🧾 Total Notas", value=total_notas)

# Gráfico de faturamento por dia
if 'df' in locals() and not df.empty:
    if USAR_SQLITE and caminho_arquivo.endswith(".db"):
        # Para SQLite, a coluna já vem renomeada
        coluna_data = "Data Emissão" if "Data Emissão" in df.columns else "data_emissao"
        coluna_valor = "Valor Total (R$)" if "Valor Total (R$)" in df.columns else "valor_total"
    else:
        coluna_data = "Data Emissao" if "Data Emissao" in df.columns else "Data Emissão"
        coluna_valor = "valor_total"

    if coluna_data in df.columns and coluna_valor in df.columns:
        faturamento_diario = df.groupby(coluna_data)[coluna_valor].sum()
        st.subheader("📈 Faturamento por Dia")
        st.line_chart(faturamento_diario)
    else:
        st.warning("⚠️ Não foi possível gerar o gráfico diário: as colunas de Data ou Valor não foram encontradas.")
