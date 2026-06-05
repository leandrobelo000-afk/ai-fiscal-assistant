# 🧾 AI Fiscal Assistant

> Assistente financeiro com IA que realiza a leitura automática de notas fiscais e organiza todas as informações em planilhas. 

O projeto é desenvolvido em etapas progressivas, cada uma construindo sobre a anterior, com o objetivo de demonstrar a aplicação prática de técnicas de Engenharia de IA e Automação de Dados em um problema corporativo real.

## 🚀 Etapas do Projeto

| # | Etapa | Status | Descrição |
|---|---|:---:|---|
| 1 | `step1_ocr/` | ✅ Concluída | Extração de dados via OCR |
| 2 | `step2_llm/` | ✅ Concluída | Processamento Vision + Tesseract com LLM local |
| 3 | `step3_spreadsheet/` | 🔜 Em breve | Gravação automática em planilha |
| 4 | `step4_interface/` | 🔜 Em breve | Interface de upload e chat |
| 5 | `step5_dashboard/` | 🔜 Em breve | Dashboard financeiro e analytics |

---

## 🏗️ Arquitetura Atual (Etapas 1 e 2)

O pipeline de processamento foi desenhado para maximizar a precisão. O modelo de visão atua como processador principal, enquanto o OCR clássico funciona como um *fallback* (plano B) seguro para quando o LLM demonstra baixa confiança na leitura.

```mermaid
flowchart TD
    A[📄 Imagem / PDF da Nota Fiscal] --> B(🧠 Qwen2.5-VL Vision<br/>rodando local via LM Studio)
    B -- Lê a imagem diretamente --> C{Confiança da leitura é baixa?}
    C -- Não --> D[JSON Estruturado]
    C -- Sim --> E[🔍 Tesseract OCR <br/>Fallback Automático]
    E -- Extrai o texto bruto --> F(🤖 LLM processa o texto bruto)
    F --> D
    D --> G[\Objeto: NotaFiscalProcessada<br/>numero, data, cnpj, valor, impostos, itens...\]
