# Makefile — Estoque Clínica
# Uso rápido:
#   make scaffold   # cria toda a árvore de diretórios e arquivos vazios
#   make clean      # remove caches

.PHONY: scaffold clean

scaffold:
	@echo ">> Criando estrutura de diretórios..."
	@mkdir -p estoque/{domain,adapters,infra,usecases} tests
	@touch README.md
	@test -f pyproject.toml || echo "[project]\nname = \"estoque-clinica\"\nversion = \"0.1.0\"\nrequires-python = \">=3.10\"\n" > pyproject.toml
	@touch app.py
	@touch estoque/__init__.py
	@touch estoque/config.py
	@touch estoque/domain/{__init__.py,models.py,formulas.py,policies.py}
	@touch estoque/adapters/{__init__.py,cli.py,parsers.py,gds_loader.py}
	@touch estoque/infra/{__init__.py,db.py,migrations.py,repositories.py,views.py}
	@touch estoque/usecases/{__init__.py,verificar_estoque.py,registrar_entrada.py,registrar_saida.py}
	@touch tests/{__init__.py,test_parsers.py,test_formulas.py,test_cli.py}
	@echo "✅ Estrutura criada (arquivos vazios + pyproject.toml mínimo)."

clean:
	rm -rf __pycache__ */__pycache__ .pytest_cache .mypy_cache build dist htmlcov *.egg-info
