# Step 1 — Extração de dados de notas fiscais (OCR)

## O que essa etapa faz

Recebe um arquivo de nota fiscal (PDF ou imagem) e devolve um dicionário estruturado com os campos extraídos e um `confidence_score` por campo.

### Fluxo de decisão

```
Arquivo (PDF / imagem)
        │
        ▼
Tem texto nativo?
   ├── sim → pdfplumber  (rápido, preciso)
   └── não → OpenCV + pytesseract  (OCR)
        │
        ▼
Parsing com regex
        │
        ▼
NotaFiscal { numero, data, cnpj, valor, impostos, confidence_score }
```

## Campos extraídos

| Campo | Descrição |
|---|---|
| `numero` | Número da nota fiscal |
| `data_emissao` | Data no formato DD/MM/AAAA |
| `cnpj_emitente` | CNPJ no formato XX.XXX.XXX/XXXX-XX |
| `valor_total` | Valor total em float (R$) |
| `impostos` | ICMS ou ISS em float (R$) |
| `confidence_score` | Score 0.0–1.0 por campo (0.0 = não encontrado) |

## Instalação

```bash
# Ative o ambiente virtual (na raiz do projeto)
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Instale as dependências
pip install -r requirements.txt
```

### Dependência extra — Tesseract OCR

O `pytesseract` é só um wrapper Python. O Tesseract precisa ser instalado separadamente:

- **Windows:** baixe o instalador em [github.com/UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) e marque o pacote de idioma **Português** durante a instalação.
- **Linux:** `sudo apt install tesseract-ocr tesseract-ocr-por`
- **Mac:** `brew install tesseract tesseract-lang`

## Como usar

```bash
# Na pasta raiz do projeto, com venv ativo:
python step1_ocr/extractor.py step1_ocr/samples/nota_teste.pdf
```

### Uso no código

```python
from step1_ocr.extractor import processar_nota_fiscal

nota = processar_nota_fiscal("samples/nota_teste.pdf")

print(nota.cnpj_emitente)          # "12.345.678/0001-99"
print(nota.valor_total)            # 1250.00
print(nota.confidence_score)       # {'cnpj': 1.0, 'valor_total': 1.0, ...}
```

Campos com `confidence_score` igual a `0.0` ficam marcados para revisão humana na planilha (Etapa 3).

## Decisões técnicas

- **`dpi=300`** no `convert_from_path`: abaixo de 200 DPI o Tesseract erra muito em fontes pequenas típicas de NF.
- **Binarização adaptativa** em vez de global: lida melhor com iluminação irregular em fotos tiradas com celular.
- **`confidence_score` por campo**: o sistema sabe quando não tem certeza — isso é mais confiável do que silenciosamente retornar `None`.

## Próxima etapa

Os dados extraídos aqui são passados para a **Etapa 2 (LLM)**, que interpreta e classifica os campos com muito mais inteligência do que regex.
