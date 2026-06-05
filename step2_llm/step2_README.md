# Step 2 — Processamento com LLM local (LM Studio)

## O que essa etapa faz

Recebe o texto bruto extraído pelo OCR da Etapa 1 — mesmo distorcido — e usa um modelo de linguagem rodando **localmente** para interpretar e estruturar os dados com inteligência.

### Por que LLM depois do OCR?

O OCR extrai texto, mas não entende contexto. A LLM consegue:
- Corrigir erros do OCR (`KFC-e` → `NFC-e`, `RS` → `R$`)
- Inferir campos que o regex não encontrou
- Extrair lista de itens da nota
- Avaliar a confiança da leitura

### Fluxo

```
Texto bruto (OCR)
      │
      ▼
Prompt estruturado
      │
      ▼
Modelo local (LM Studio)
      │
      ▼
JSON validado → NotaFiscalProcessada
```

## Stack

- **LM Studio** — roda o modelo localmente, sem custo de API
- **Modelo:** `Qwen2.5-VL-3B-Instruct` Q4_K_M
- **API:** compatível com OpenAI em `http://localhost:1234`

## Pré-requisitos

1. LM Studio instalado com o modelo `qwen2.5-v1-3b-instruct` baixado
2. Servidor iniciado:
```bash
lms server start
```

## Instalação

```bash
pip install requests
```

## Como usar

```bash
# Na raiz do projeto, com venv ativo:
python step2_llm/processor.py
```

### Uso no código

```python
from step2_llm.processor import processar_com_llm

nota = processar_com_llm(texto_extraido_pelo_ocr)

print(nota.cnpj_emitente)   # "50.457.085/0001-32"
print(nota.valor_total)     # 117.14
print(nota.confianca)       # "alta"
print(nota.itens)           # [{"descricao": "PAO FRANCES", "valor": 3.76}, ...]
```

## Decisões técnicas

- **`temperature: 0.1`** — valor baixo garante respostas consistentes e determinísticas
- **Servidor local** — dados da nota fiscal nunca saem do computador
- **JSON puro na resposta** — o prompt instrui o modelo a não adicionar texto extra, facilitando o parse
- **`confianca`** — campo avaliado pelo próprio modelo, indicando se o texto de entrada estava legível

## Próxima etapa

Os dados estruturados aqui são gravados automaticamente na planilha pela **Etapa 3**.
