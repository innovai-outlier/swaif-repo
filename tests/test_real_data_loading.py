"""
Testes específicos para o carregamento de dados reais dos arquivos Excel.

Testa o fluxo completo de carregamento das planilhas entradas.xlsx e saidas.xlsx
com criação automática de produtos.
"""

import os
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from estoque.usecases.registrar_entrada import run_entrada_lote
from estoque.usecases.registrar_saida import run_saida_lote
from estoque.infra.migrations import apply_migrations
from estoque.infra.views import create_views


@pytest.fixture
def test_db():
    """Cria um banco de dados temporário para os testes."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # Aplica migrações
    apply_migrations(db_path)
    create_views(db_path)
    
    yield db_path
    
    # Limpeza
    os.unlink(db_path)


@pytest.fixture
def sample_entradas_xlsx():
    """Cria um arquivo de teste de entradas."""
    data = {
        'Código': ['P1', 'P2', 'P3'],
        'Produto': ['Produto 1', 'Produto 2', 'Produto 3'],
        'Quantidade': ['5.00 UN - UNIDADES', '10.00 ML - MILILITROS', '2.00 AMP - AMPOLAS'],
        'Data de entrada': ['01/01/2025', '02/01/2025', '03/01/2025'],
        'Lote': ['L001', 'L002', 'L003'],
        'Data de validade': ['01/12/2025', '02/12/2025', '03/12/2025'],
        'Valor unitário': ['10.50', '25.00', '15.75'],
        'Representante': ['Rep A', 'Rep B', 'Rep C'],
        'Responsável': ['User1', 'User2', 'User3'],
        'Pago': ['Sim', 'Não', 'Sim']
    }
    
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        df = pd.DataFrame(data)
        df.to_excel(f.name, index=False)
        yield f.name
    
    os.unlink(f.name)


@pytest.fixture
def sample_saidas_xlsx():
    """Cria um arquivo de teste de saídas."""
    data = {
        'Código': ['P1', 'P2', 'P4'],
        'Produto': ['Produto 1', 'Produto 2', 'Produto 4'],
        'Quantidade': ['2.00 UN - UNIDADES', '5.00 ML - MILILITROS', '1.00 AMP - AMPOLAS'],
        'Data de saída': ['05/01/2025', '06/01/2025', '07/01/2025'],
        'Lote': ['L001', 'L002', 'L004'],
        'Data de validade': ['01/12/2025', '02/12/2025', '04/12/2025'],
        'Custo': ['21.00', '125.00', '15.75'],
        'Paciente': ['Paciente A', 'Paciente B', 'Paciente C'],
        'Responsável': ['User1', 'User2', 'User3'],
        'Descarte?': ['False', 'False', 'False']
    }
    
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        df = pd.DataFrame(data)
        df.to_excel(f.name, index=False)
        yield f.name
    
    os.unlink(f.name)


def test_entrada_lotes_with_auto_product_creation(test_db, sample_entradas_xlsx):
    """Testa carregamento de entradas com criação automática de produtos."""
    result = run_entrada_lote(sample_entradas_xlsx, db_path=test_db)
    
    # Verifica o resultado
    assert result["arquivo"] == sample_entradas_xlsx
    assert result["linhas_inseridas"] == 3
    assert result["produtos_criados"] == 3
    
    # Verifica se os produtos foram criados na base
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM produto")
    assert cursor.fetchone()[0] == 3
    
    cursor.execute("SELECT codigo FROM produto ORDER BY codigo")
    produtos = [row[0] for row in cursor.fetchall()]
    assert produtos == ['P1', 'P2', 'P3']
    
    # Verifica se as entradas foram inseridas
    cursor.execute("SELECT COUNT(*) FROM entrada")
    assert cursor.fetchone()[0] == 3
    
    conn.close()


def test_saida_lotes_with_auto_product_creation(test_db, sample_saidas_xlsx):
    """Testa carregamento de saídas com criação automática de produtos."""
    result = run_saida_lote(sample_saidas_xlsx, db_path=test_db)
    
    # Verifica o resultado
    assert result["arquivo"] == sample_saidas_xlsx
    assert result["linhas_inseridas"] == 3
    assert result["produtos_criados"] == 3  # P1, P2, P4
    
    # Verifica se os produtos foram criados na base
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM produto")
    assert cursor.fetchone()[0] == 3
    
    cursor.execute("SELECT codigo FROM produto ORDER BY codigo")
    produtos = [row[0] for row in cursor.fetchall()]
    assert produtos == ['P1', 'P2', 'P4']
    
    # Verifica se as saídas foram inseridas
    cursor.execute("SELECT COUNT(*) FROM saida")
    assert cursor.fetchone()[0] == 3
    
    conn.close()


def test_combined_entrada_saida_loading(test_db, sample_entradas_xlsx, sample_saidas_xlsx):
    """Testa carregamento combinado de entradas e saídas."""
    # Carrega entradas primeiro
    entrada_result = run_entrada_lote(sample_entradas_xlsx, db_path=test_db)
    assert entrada_result["produtos_criados"] == 3
    
    # Carrega saídas depois (P4 será novo, P1 e P2 já existem)
    # O sistema sempre reporta quantos produtos processou (upsert), não quantos criou
    saida_result = run_saida_lote(sample_saidas_xlsx, db_path=test_db)
    assert saida_result["produtos_criados"] == 3  # P1, P2, P4 processados
    
    # Verifica estado final da base
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    
    # Deve ter 4 produtos: P1, P2, P3, P4
    cursor.execute("SELECT COUNT(*) FROM produto")
    assert cursor.fetchone()[0] == 4
    
    cursor.execute("SELECT codigo FROM produto ORDER BY codigo")
    produtos = [row[0] for row in cursor.fetchall()]
    assert produtos == ['P1', 'P2', 'P3', 'P4']
    
    # Deve ter 3 entradas e 3 saídas
    cursor.execute("SELECT COUNT(*) FROM entrada")
    assert cursor.fetchone()[0] == 3
    
    cursor.execute("SELECT COUNT(*) FROM saida")
    assert cursor.fetchone()[0] == 3
    
    conn.close()


def test_real_excel_files_exist():
    """Verifica se os arquivos Excel reais existem no repositório."""
    repo_root = Path(__file__).parent.parent
    entradas_file = repo_root / "entradas.xlsx"
    saidas_file = repo_root / "saidas.xlsx"
    
    assert entradas_file.exists(), "Arquivo entradas.xlsx não encontrado"
    assert saidas_file.exists(), "Arquivo saidas.xlsx não encontrado"
    
    # Verifica se os arquivos têm conteúdo
    assert entradas_file.stat().st_size > 1000, "Arquivo entradas.xlsx parece vazio"
    assert saidas_file.stat().st_size > 1000, "Arquivo saidas.xlsx parece vazio"


def test_real_data_structure():
    """Verifica a estrutura dos arquivos Excel reais."""
    repo_root = Path(__file__).parent.parent
    entradas_file = repo_root / "entradas.xlsx"
    saidas_file = repo_root / "saidas.xlsx"
    
    # Testa estrutura do arquivo de entradas
    df_entradas = pd.read_excel(entradas_file, dtype='string')
    assert len(df_entradas) > 0, "Arquivo entradas.xlsx não tem dados"
    assert 'Código' in df_entradas.columns, "Coluna 'Código' ausente em entradas.xlsx"
    assert 'Quantidade' in df_entradas.columns, "Coluna 'Quantidade' ausente em entradas.xlsx"
    
    # Testa estrutura do arquivo de saídas
    df_saidas = pd.read_excel(saidas_file, dtype='string')
    assert len(df_saidas) > 0, "Arquivo saidas.xlsx não tem dados"
    assert 'Código' in df_saidas.columns, "Coluna 'Código' ausente em saidas.xlsx"
    assert 'Quantidade' in df_saidas.columns, "Coluna 'Quantidade' ausente em saidas.xlsx"


@pytest.mark.integration
def test_full_real_data_loading():
    """Teste de integração completo com os dados reais."""
    repo_root = Path(__file__).parent.parent
    entradas_file = str(repo_root / "entradas.xlsx")
    saidas_file = str(repo_root / "saidas.xlsx")
    
    # Cria banco temporário
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name
    
    try:
        # Aplica migrações
        apply_migrations(test_db_path)
        create_views(test_db_path)
        
        # Carrega dados reais
        entrada_result = run_entrada_lote(entradas_file, db_path=test_db_path)
        saida_result = run_saida_lote(saidas_file, db_path=test_db_path)
        
        # Verifica resultados
        assert entrada_result["linhas_inseridas"] > 0
        assert entrada_result["produtos_criados"] > 0
        assert saida_result["linhas_inseridas"] > 0
        
        # Verifica consistência da base
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM produto")
        produtos_count = cursor.fetchone()[0]
        assert produtos_count > 0
        
        cursor.execute("SELECT COUNT(*) FROM entrada")
        entradas_count = cursor.fetchone()[0]
        assert entradas_count > 0
        
        cursor.execute("SELECT COUNT(*) FROM saida")
        saidas_count = cursor.fetchone()[0]
        assert saidas_count > 0
        
        # Verifica integridade referencial
        cursor.execute("""
            SELECT COUNT(*) FROM entrada e 
            LEFT JOIN produto p ON e.codigo = p.codigo 
            WHERE p.codigo IS NULL
        """)
        assert cursor.fetchone()[0] == 0, "Entradas com códigos inválidos"
        
        cursor.execute("""
            SELECT COUNT(*) FROM saida s 
            LEFT JOIN produto p ON s.codigo = p.codigo 
            WHERE p.codigo IS NULL
        """)
        assert cursor.fetchone()[0] == 0, "Saídas com códigos inválidos"
        
        conn.close()
        
    finally:
        # Limpeza
        os.unlink(test_db_path)