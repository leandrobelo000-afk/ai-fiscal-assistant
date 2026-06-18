import sys
import os
import tempfile
import json
import streamlit as st
import glob

caminho_raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if caminho_raiz not in sys.path:
    sys.path.append(caminho_raiz)

# ==========================================
# IMPORTAÇÕES DAS ETAPAS ANTERIORES
# ==========================================

from step2_llm.processor import processar_nota_fiscal
from step3_spreadsheet.writer import gravar_nota
from step1_ocr.extractor import verificar_tesseract

verificar_tesseract()

# 1. Configuração da Página
st.set_page_config(page_title="AI Fiscal Assistant", page_icon="🧾", layout="wide")
# ==========================================
# BARRA LATERAL (CONFIGURAÇÕES)
# ==========================================
with st.sidebar:
    st.header("⚙️ Configurações do Sistema")
    st.write("Escolha onde os dados serão salvos/lidos:")
    
    # O glob varre toda a sua pasta do projeto procurando arquivos do Excel
    planilhas_encontradas = glob.glob("**/*.xlsx", recursive=True)
    
    if planilhas_encontradas:
        # Se encontrar, cria um menu (dropdown) para você selecionar
        caminho_planilha = st.selectbox("📁 Banco de Dados Atual:", planilhas_encontradas)
    else:
        # Se não encontrar nenhuma, abre um campo para você digitar o nome de uma nova
        caminho_planilha = st.text_input("📁 Nome do novo banco de dados:", value="notas_fiscais.xlsx")
        st.caption("O arquivo será criado automaticamente ao processar a próxima nota.")
st.title("🧾 AI Fiscal Assistant - Central")
st.write("Faça o upload, extraia os dados, salve na planilha e converse com a nota!")

# Layout em duas colunas (Esquerda: Upload/Resultados | Direita: Chat)
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📤 1. Upload e Processamento")
    arquivo_enviado = st.file_uploader("Arraste seu PDF ou Imagem da NF aqui", type=["pdf", "png", "jpg", "jpeg"])

    if arquivo_enviado is not None:
        # Botão para iniciar todo o fluxo
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
                    
                    # PASSO C: Executar a Etapa 3 (Gravar na Planilha)
                    st.toast("Salvando na planilha...")
                    gravar_nota(nota_processada)
                    st.toast("Salvando na planilha...")
                    gravar_nota(nota_processada, caminho_planilha)
                    
                    st.success("✅ Nota processada e salva na planilha com sucesso!")
                    
                    # Mostra os dados extraídos de forma bonita na tela
                    st.json(nota_processada.__dict__)

                except Exception as e:
                    st.error(f"Ocorreu um erro no processamento: {e}")
                finally:
                    # PASSO D: Limpeza - deleta o arquivo temporário para não lotar o PC
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
        # Verifica se alguma nota já foi processada antes de responder
        if 'nota_atual' not in st.session_state:
            st.warning("Por favor, processe uma nota fiscal primeiro antes de fazer perguntas.")
        else:
            with st.chat_message("user"):
                st.write(pergunta_usuario)
            st.session_state.mensagens.append({"role": "user", "content": pergunta_usuario})
            
            # TODO: No futuro, enviaremos a pergunta + st.session_state['nota_atual'] para o LLM responder
            resposta_ia = f"Você perguntou: '{pergunta_usuario}'. Em breve, a IA buscará a resposta nos dados da nota extraída!"
            
            with st.chat_message("assistant"):
                st.write(resposta_ia)
            st.session_state.mensagens.append({"role": "assistant", "content": resposta_ia})

    # ==========================================
    # NOVO: VISUALIZADOR DA PLANILHA NA TELA
    # ==========================================
    st.divider()
    st.subheader("📊 Banco de Dados (Excel)")
    
    if os.path.exists(caminho_planilha):
        import pandas as pd
        
        # Cria duas abas na interface para simular as abas do Excel
        aba1, aba2 = st.tabs(["Resumo das Notas", "Itens Detalhados"])
        
        with aba1:
            df_resumo = pd.read_excel(caminho_planilha, sheet_name="Resumo")
            st.dataframe(df_resumo, use_container_width=True, hide_index=True)
            
        with aba2:
            try:
                df_itens = pd.read_excel(caminho_planilha, sheet_name="Itens")
                st.dataframe(df_itens, use_container_width=True, hide_index=True)
            except:
                st.info("A aba de itens ainda não foi criada ou está vazia.")
    else:
        st.info("Nenhuma planilha encontrada ainda. Processe uma nota para criar!")