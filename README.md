# AI Fiscal Assistant

Assistente financeiro com IA que realiza leitura automática de notas fiscais
e organiza todas as informações em planilha.

Projeto desenvolvido em etapas para portfólio de engenharia de IA.

## Etapas

| # | Pasta | Status | Descrição |
|---|---|---|---|
| 1 | `step1_ocr/` | ✅ concluída | Extração de dados com OCR |
| 2 | `step2_llm/` | 🔜 em breve | Processamento e classificação com LLM |
| 3 | `step3_spreadsheet/` | 🔜 em breve | Gravação automática em planilha |
| 4 | `step4_interface/` | 🔜 em breve | Interface de upload e chat |
| 5 | `step5_dashboard/` | 🔜 em breve | Dashboard financeiro |

## Como rodar

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/ai-fiscal-assistant.git
cd ai-fiscal-assistant

# 2. Crie e ative o ambiente virtual
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Mac/Linux

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Rode a extração (Etapa 1)
python step1_ocr/extractor.py step1_ocr/samples/sua_nota.pdf
```

## Stack

- **OCR:** `pdfplumber`, `pytesseract`, `opencv-python`, `pdf2image`
- **LLM:** Claude API (Anthropic)
- **Planilha:** `openpyxl` / Google Sheets API
- **Interface:** Streamlit
