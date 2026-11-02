# tests package
# Testes automatizados do AI Fiscal Assistant
#
# Execução:
#   pytest                          # Todos os testes unitários
#   pytest -m integration           # Testes de integração (requer recursos externos)
#   pytest -m "not integration"     # Apenas testes unitários rápidos
#   pytest --cov=step1_ocr --cov=step2_llm --cov=step3_database --cov=step3_spreadsheet  # Com coverage