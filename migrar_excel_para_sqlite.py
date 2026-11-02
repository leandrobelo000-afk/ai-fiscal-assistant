#!/usr/bin/env python
"""
migrar_excel_para_sqlite.py
---------------------------
Script de migração para importar dados de planilhas Excel (.xlsx)
para o banco de dados SQLite (notas_fiscais.db).

Uso:
    python migrar_excel_para_sqlite.py [caminho_excel] [caminho_db]

Se não informados, usa:
- Excel: notas_fiscais.xlsx (ou Nota.xlsx se existir)
- DB: notas_fiscais.db
"""

import os
import sys
import glob

# Adiciona o diretório do projeto ao path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

from step3_database import migrar_excel_para_sqlite, init_db, get_estatisticas


def encontrar_arquivos_excel():
    """Encontra arquivos Excel no diretório do projeto."""
    excel_files = glob.glob(os.path.join(project_root, "*.xlsx"))
    return excel_files


def main():
    print("=" * 60)
    print("MIGRACAO EXCEL -> SQLITE")
    print("=" * 60)

    # Determina arquivos de entrada/saída
    if len(sys.argv) > 1:
        excel_path = sys.argv[1]
    else:
        # Procura arquivos Excel existentes
        excel_files = encontrar_arquivos_excel()
        if not excel_files:
            print("[ERRO] Nenhum arquivo Excel encontrado no diretório do projeto.")
            print("   Uso: python migrar_excel_para_sqlite.py <arquivo.xlsx> [arquivo.db]")
            sys.exit(1)

        # Prioriza notas_fiscais.xlsx ou Nota.xlsx
        preferred = ["notas_fiscais.xlsx", "Nota.xlsx"]
        excel_path = None
        for pref in preferred:
            for f in excel_files:
                if os.path.basename(f) == pref:
                    excel_path = f
                    break
            if excel_path:
                break

        if not excel_path:
            excel_path = excel_files[0]

        print(f"[INFO] Arquivo Excel detectado: {os.path.basename(excel_path)}")

    if len(sys.argv) > 2:
        db_path = sys.argv[2]
    else:
        # Usa mesmo nome do Excel mas com .db
        db_path = os.path.splitext(excel_path)[0] + ".db"
        print(f"[INFO] Banco de dados destino: {os.path.basename(db_path)}")

    # Verifica se o arquivo Excel existe
    if not os.path.exists(excel_path):
        print(f"[ERRO] Arquivo Excel não encontrado: {excel_path}")
        sys.exit(1)

    print("-" * 60)

    # Executa a migração
    stats = migrar_excel_para_sqlite(excel_path, db_path)

    print("-" * 60)
    print("RESUMO DA MIGRACAO:")
    print(f"   [OK] Notas migradas:      {stats['notas_migradas']}")
    print(f"   [AVISO] Notas ignoradas:    {stats['notas_ignoradas']} (duplicatas)")
    print(f"   [OK] Itens migrados:     {stats['itens_migrados']}")

    if stats['erros']:
        print(f"   [ERRO] Erros:             {len(stats['erros'])}")
        for erro in stats['erros'][:5]:  # Mostra apenas os primeiros 5
            print(f"      - {erro}")
        if len(stats['erros']) > 5:
            print(f"      ... e mais {len(stats['erros']) - 5} erro(s)")

    # Mostra estatísticas do banco após migração
    print("-" * 60)
    print("ESTATISTICAS DO BANCO APOS MIGRACAO:")
    db_stats = get_estatisticas(db_path)
    print(f"   Total de notas:    {db_stats['total_notas']}")
    print(f"   Total de itens:    {db_stats['total_itens']}")
    print(f"   Faturamento total: R$ {db_stats['faturamento_total']:,.2f}")
    print(f"   Impostos totais:   R$ {db_stats['impostos_totais']:,.2f}")
    print(f"   Ticket médio:      R$ {db_stats['ticket_medio']:,.2f}")

    print("=" * 60)
    print("[OK] Migração concluída com sucesso!")
    print(f"   Banco de dados: {db_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()