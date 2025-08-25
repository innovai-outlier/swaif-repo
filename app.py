# app.py
"""
Entrypoint da aplicação.

Uso:
  python app.py migrate --db estoque.db
  python app.py params show
  python app.py verificar
  python app.py entrada-lotes entradas.xlsx
  python app.py saida-lotes saidas.xlsx
"""

from estoque.adapters.cli import main

if __name__ == "__main__":
    main()
