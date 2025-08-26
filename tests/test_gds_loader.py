"""
Tests for the gds_loader module to validate entrada processing changes.

These tests focus on the specific modifications:
1. Adding the "produto" field from Excel columns
2. Removing the "responsavel" field from results
3. Ensuring database compatibility
"""

import pytest
import pandas as pd
import tempfile
from pathlib import Path

from estoque.adapters.gds_loader import load_entradas_from_xlsx, _normalize_columns


def test_normalize_columns_produto_field():
    """Test that produto field mappings work correctly."""
    # Create a test DataFrame with various produto column names
    df = pd.DataFrame({
        'Produto': ['Test Product 1'],
        'Nome': ['Test Product 2'], 
        'Nome do Produto': ['Test Product 3'],
        'Código': ['123'],
        'Quantidade': ['5 FR']
    })
    
    result_df = _normalize_columns(df)
    
    # Check that all produto variations are mapped to "produto"
    assert 'produto' in result_df.columns
    # Original columns should be renamed
    column_mapping = dict(zip(df.columns, result_df.columns))
    assert column_mapping['Produto'] == 'produto'


def test_load_entradas_includes_produto_excludes_responsavel():
    """Test that load_entradas_from_xlsx includes produto field and excludes responsavel."""
    # Create a temporary Excel file with sample data
    test_data = {
        'Produto': ['Test Product A', 'Test Product B'],
        'Código': ['P001', 'P002'],
        'Quantidade': ['5 FR - Frascos', '3 AMP - Ampolas'],
        'Data de entrada': ['2025-01-01', '2025-01-02'],
        'Responsável': ['John Doe', 'Jane Smith'],
        'Pago': ['Sim', 'Não']
    }
    
    df = pd.DataFrame(test_data)
    
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
        df.to_excel(tmp_file.name, index=False)
        tmp_path = tmp_file.name
    
    try:
        # Load the data using our function
        results = load_entradas_from_xlsx(tmp_path)
        
        # Verify we got the expected number of records
        assert len(results) == 2
        
        # Check first record structure
        first_record = results[0]
        
        # Verify produto field is present and populated
        assert 'produto' in first_record
        assert first_record['produto'] == 'Test Product A'
        
        # Verify responsavel field is NOT present
        assert 'responsavel' not in first_record
        
        # Verify other expected fields are present
        expected_fields = {
            'produto', 'data_entrada', 'codigo', 'quantidade_raw', 
            'lote', 'data_validade', 'valor_unitario', 'nota_fiscal', 
            'representante', 'pago'
        }
        
        assert set(first_record.keys()) == expected_fields
        
        # Check second record has different product
        second_record = results[1]
        assert second_record['produto'] == 'Test Product B'
        
    finally:
        # Clean up temporary file
        Path(tmp_path).unlink()


def test_load_entradas_produto_field_variations():
    """Test that different produto column names are recognized."""
    variations = [
        ('Produto', 'Product via Produto'),
        ('Nome', 'Product via Nome'),
        ('Nome do Produto', 'Product via Nome do Produto')
    ]
    
    for column_name, expected_value in variations:
        test_data = {
            column_name: [expected_value],
            'Código': ['TEST001'],
            'Data de entrada': ['2025-01-01']
        }
        
        df = pd.DataFrame(test_data)
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            df.to_excel(tmp_file.name, index=False)
            tmp_path = tmp_file.name
        
        try:
            results = load_entradas_from_xlsx(tmp_path)
            assert len(results) == 1
            assert results[0]['produto'] == expected_value
            
        finally:
            Path(tmp_path).unlink()


def test_load_entradas_handles_missing_produto():
    """Test that function handles missing produto field gracefully."""
    # Create data without produto field
    test_data = {
        'Código': ['TEST001'],
        'Quantidade': ['1 FR'],
        'Data de entrada': ['2025-01-01']
    }
    
    df = pd.DataFrame(test_data)
    
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
        df.to_excel(tmp_file.name, index=False)
        tmp_path = tmp_file.name
    
    try:
        results = load_entradas_from_xlsx(tmp_path)
        assert len(results) == 1
        # Should still have produto field, but with None value
        assert 'produto' in results[0]
        assert results[0]['produto'] is None
        
    finally:
        Path(tmp_path).unlink()


def test_repository_compatibility():
    """Test that EntradaRepo handles missing responsavel field correctly."""
    from estoque.infra.repositories import EntradaRepo, ProdutoRepo
    from estoque.infra.migrations import apply_migrations
    from estoque.infra.views import create_views
    import sqlite3
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db = f.name
    
    try:
        # Setup database
        apply_migrations(test_db)
        create_views(test_db)
        
        # First create the product (required for foreign key constraint)
        produto_repo = ProdutoRepo(test_db)
        produto_repo.upsert([{
            'codigo': 'TEST001',
            'nome': 'Test Product',
            'categoria': 'TEST',
            'controle_lotes': 1,
            'controle_validade': 1,
            'lote_min': 1,
            'lote_mult': 1,
            'quantidade_minima': 0
        }])
        
        repo = EntradaRepo(test_db)
        
        # Test data without responsavel field (as produced by our updated gds_loader)
        test_record = {
            'produto': 'Test Product',
            'data_entrada': '2025-01-01',
            'codigo': 'TEST001',
            'quantidade_raw': '1 FR',
            'lote': None,
            'data_validade': None,
            'valor_unitario': None,
            'nota_fiscal': None,
            'representante': None,
            'pago': None
        }
        
        # This should work without error
        repo.insert(test_record)
        
        # Verify data was inserted
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM entrada WHERE codigo = ?', ('TEST001',))
        row = cursor.fetchone()
        assert row is not None
        
        # Verify responsavel was set to NULL
        cursor.execute('SELECT responsavel FROM entrada WHERE codigo = ?', ('TEST001',))
        responsavel_value = cursor.fetchone()[0]
        assert responsavel_value is None
        
        conn.close()
        
    finally:
        Path(test_db).unlink()