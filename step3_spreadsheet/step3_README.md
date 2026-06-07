# Step 3 — Gravação automática em planilha Excel

## O que essa etapa faz

Recebe os dados estruturados da Etapa 2 e os grava em uma planilha Excel acumulativa — cada nova nota processada adiciona uma linha, sem sobrescrever as anteriores.

## Estrutura da planilha

### Aba "Resumo"
Uma linha por nota fiscal com os campos principais:

| Campo | Descrição |
|---|---|
| Data Processamento | Quando a nota foi processada |
| Número NF | Número da nota fiscal |
| Data Emissão | Data da nota |
| CNPJ Emitente | CNPJ do emitente |
| Nome Emitente | Nome da empresa |
| Valor Total (R$) | Valor total da nota |
| Impostos (R$) | Valor dos impostos |
| Qtd Itens | Quantidade de itens |
| Confiança | Nível de confiança da leitura |
| Rota | Como foi processada (vision / vision+tesseract) |

### Aba "Itens"
Todos os produtos de todas as notas, com referência ao número da NF.

## Funcionalidades

- **Acumulativo** — novas notas são sempre adicionadas, nunca sobrescritas
- **Anti-duplicata** — verifica se o número da NF já existe antes de gravar
- **Multi-arquivo** — processa várias notas de uma vez na mesma execução
- **Fórmula de total** — soma automática dos valores na aba Resumo
- **Formatação** — cabeçalhos coloridos e zebra stripes para legibilidade

## Instalação

```bash
pip install pandas openpyxl
```

## Como usar

```bash
# Na raiz do projeto, com venv ativo e servidor LM Studio rodando:
python step3_spreadsheet/writer.py
```

Uma janela de seleção permite escolher **uma ou mais notas de uma vez**.
A planilha `notas_fiscais.xlsx` é criada automaticamente na pasta `step3_spreadsheet/`.

## Próxima etapa

Os dados gravados aqui alimentam o **Dashboard da Etapa 5** com gráficos e análises automáticas.
