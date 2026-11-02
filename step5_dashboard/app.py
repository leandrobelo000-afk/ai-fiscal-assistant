"""
step5_dashboard/app.py
----------------------
Ponto de entrada da Etapa 5: junta a tela de processamento (Etapa 4) e as
páginas do dashboard financeiro em um único app Streamlit.

    streamlit run step5_dashboard/app.py
"""

import os
import sys

import streamlit as st

caminho_raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if caminho_raiz not in sys.path:
    sys.path.append(caminho_raiz)

st.set_page_config(page_title="AI Fiscal Assistant", page_icon="🧾", layout="wide")

pasta = os.path.dirname(os.path.abspath(__file__))
navegacao = st.navigation({
    "Operação": [
        st.Page(os.path.join(caminho_raiz, "step4_interface", "app.py"),
                title="Processar Nota", icon="📤", url_path="processar"),
    ],
    "Dashboard": [
        st.Page(os.path.join(pasta, "paginas", "visao_geral.py"), title="Visão Geral", icon="📊", default=True),
        st.Page(os.path.join(pasta, "paginas", "fornecedores.py"), title="Fornecedores", icon="🏢"),
        st.Page(os.path.join(pasta, "paginas", "itens.py"), title="Itens", icon="🧺"),
    ],
    "Configurações": [
        st.Page(os.path.join(pasta, "paginas", "google_sheets.py"), title="Google Sheets", icon="☁️",
                url_path="google-sheets"),
    ],
})
navegacao.run()
