# Makefile — Estoque Clínica
# Uso rápido:
#   make scaffold   # cria toda a árvore de diretórios e arquivos vazios
#   make validate   # valida se a estrutura de diretórios está completa
#   make clean      # remove caches

.PHONY: scaffold clean validate

scaffold:
	@echo ">> Criando estrutura de diretórios..."
	@mkdir -p estoque/domain estoque/adapters estoque/infra estoque/usecases tests
	@touch README.md
	@test -f pyproject.toml || echo "[project]\nname = \"estoque-clinica\"\nversion = \"0.1.0\"\nrequires-python = \">=3.10\"\n" > pyproject.toml
	@touch app.py
	@touch estoque/__init__.py
	@touch estoque/config.py
	@touch estoque/domain/__init__.py estoque/domain/models.py estoque/domain/formulas.py estoque/domain/policies.py
	@touch estoque/adapters/__init__.py estoque/adapters/cli.py estoque/adapters/parsers.py estoque/adapters/gds_loader.py
	@touch estoque/infra/__init__.py estoque/infra/db.py estoque/infra/migrations.py estoque/infra/repositories.py estoque/infra/views.py
	@touch estoque/usecases/__init__.py estoque/usecases/verificar_estoque.py estoque/usecases/registrar_entrada.py estoque/usecases/registrar_saida.py
	@touch tests/__init__.py tests/test_parsers.py tests/test_formulas.py tests/test_cli.py
	@echo "✅ Estrutura criada (arquivos vazios + pyproject.toml mínimo)."
	@$(MAKE) validate

validate:
	@echo ">> Validando estrutura de diretórios..."
	@echo "Verificando diretórios principais:"
	@test -d estoque && echo "  ✅ estoque/" || (echo "  ❌ estoque/" && exit 1)
	@test -d estoque/domain && echo "  ✅ estoque/domain/" || (echo "  ❌ estoque/domain/" && exit 1)
	@test -d estoque/adapters && echo "  ✅ estoque/adapters/" || (echo "  ❌ estoque/adapters/" && exit 1)
	@test -d estoque/infra && echo "  ✅ estoque/infra/" || (echo "  ❌ estoque/infra/" && exit 1)
	@test -d estoque/usecases && echo "  ✅ estoque/usecases/" || (echo "  ❌ estoque/usecases/" && exit 1)
	@test -d tests && echo "  ✅ tests/" || (echo "  ❌ tests/" && exit 1)
	@echo "Verificando arquivos principais:"
	@test -f README.md && echo "  ✅ README.md" || (echo "  ❌ README.md" && exit 1)
	@test -f pyproject.toml && echo "  ✅ pyproject.toml" || (echo "  ❌ pyproject.toml" && exit 1)
	@test -f app.py && echo "  ✅ app.py" || (echo "  ❌ app.py" && exit 1)
	@test -f estoque/__init__.py && echo "  ✅ estoque/__init__.py" || (echo "  ❌ estoque/__init__.py" && exit 1)
	@test -f estoque/config.py && echo "  ✅ estoque/config.py" || (echo "  ❌ estoque/config.py" && exit 1)
	@echo "Verificando arquivos do domínio:"
	@test -f estoque/domain/__init__.py && echo "  ✅ estoque/domain/__init__.py" || (echo "  ❌ estoque/domain/__init__.py" && exit 1)
	@test -f estoque/domain/models.py && echo "  ✅ estoque/domain/models.py" || (echo "  ❌ estoque/domain/models.py" && exit 1)
	@test -f estoque/domain/formulas.py && echo "  ✅ estoque/domain/formulas.py" || (echo "  ❌ estoque/domain/formulas.py" && exit 1)
	@test -f estoque/domain/policies.py && echo "  ✅ estoque/domain/policies.py" || (echo "  ❌ estoque/domain/policies.py" && exit 1)
	@echo "Verificando arquivos dos adaptadores:"
	@test -f estoque/adapters/__init__.py && echo "  ✅ estoque/adapters/__init__.py" || (echo "  ❌ estoque/adapters/__init__.py" && exit 1)
	@test -f estoque/adapters/cli.py && echo "  ✅ estoque/adapters/cli.py" || (echo "  ❌ estoque/adapters/cli.py" && exit 1)
	@test -f estoque/adapters/parsers.py && echo "  ✅ estoque/adapters/parsers.py" || (echo "  ❌ estoque/adapters/parsers.py" && exit 1)
	@test -f estoque/adapters/gds_loader.py && echo "  ✅ estoque/adapters/gds_loader.py" || (echo "  ❌ estoque/adapters/gds_loader.py" && exit 1)
	@echo "Verificando arquivos da infraestrutura:"
	@test -f estoque/infra/__init__.py && echo "  ✅ estoque/infra/__init__.py" || (echo "  ❌ estoque/infra/__init__.py" && exit 1)
	@test -f estoque/infra/db.py && echo "  ✅ estoque/infra/db.py" || (echo "  ❌ estoque/infra/db.py" && exit 1)
	@test -f estoque/infra/migrations.py && echo "  ✅ estoque/infra/migrations.py" || (echo "  ❌ estoque/infra/migrations.py" && exit 1)
	@test -f estoque/infra/repositories.py && echo "  ✅ estoque/infra/repositories.py" || (echo "  ❌ estoque/infra/repositories.py" && exit 1)
	@test -f estoque/infra/views.py && echo "  ✅ estoque/infra/views.py" || (echo "  ❌ estoque/infra/views.py" && exit 1)
	@echo "Verificando arquivos dos casos de uso:"
	@test -f estoque/usecases/__init__.py && echo "  ✅ estoque/usecases/__init__.py" || (echo "  ❌ estoque/usecases/__init__.py" && exit 1)
	@test -f estoque/usecases/verificar_estoque.py && echo "  ✅ estoque/usecases/verificar_estoque.py" || (echo "  ❌ estoque/usecases/verificar_estoque.py" && exit 1)
	@test -f estoque/usecases/registrar_entrada.py && echo "  ✅ estoque/usecases/registrar_entrada.py" || (echo "  ❌ estoque/usecases/registrar_entrada.py" && exit 1)
	@test -f estoque/usecases/registrar_saida.py && echo "  ✅ estoque/usecases/registrar_saida.py" || (echo "  ❌ estoque/usecases/registrar_saida.py" && exit 1)
	@echo "Verificando arquivos de teste:"
	@test -f tests/__init__.py && echo "  ✅ tests/__init__.py" || (echo "  ❌ tests/__init__.py" && exit 1)
	@test -f tests/test_parsers.py && echo "  ✅ tests/test_parsers.py" || (echo "  ❌ tests/test_parsers.py" && exit 1)
	@test -f tests/test_formulas.py && echo "  ✅ tests/test_formulas.py" || (echo "  ❌ tests/test_formulas.py" && exit 1)
	@test -f tests/test_cli.py && echo "  ✅ tests/test_cli.py" || (echo "  ❌ tests/test_cli.py" && exit 1)
	@echo "🎉 Estrutura de diretórios válida!"

clean:
	rm -rf __pycache__ */__pycache__ .pytest_cache .mypy_cache build dist htmlcov *.egg-info
