# ====== CONFIG ======
PY?=python3
VENV?=.venv
PIP=$(VENV)/bin/pip
PYTHON=$(VENV)/bin/python
PYTEST=$(VENV)/bin/pytest
RUFF=$(VENV)/bin/ruff

DB?=estoque.db

# ====== HELP ======
.PHONY: help
help:
	@echo "Alvos principais:"
	@echo "  make venv           -> cria venv local em $(VENV)"
	@echo "  make install        -> instala dependências (app + dev)"
	@echo "  make install-min    -> instala dependências mínimas (sem dev)"
	@echo "  make migrate        -> aplica migrações e cria views (DB=$(DB))"
	@echo "  make verificar      -> executa cálculo completo (DB=$(DB))"
	@echo "  make params-show    -> exibe parâmetros globais (DB=$(DB))"
	@echo "  make params-set NS=0.95 MU=6 ST=1 -> grava parâmetros"
	@echo "  make entrada-lotes FILE=entradas.xlsx (DB=$(DB))"
	@echo "  make saida-lotes  FILE=saidas.xlsx   (DB=$(DB))"
	@echo "  make rel-ruptura H=3 DB=$(DB)       -> relatório de ruptura"
	@echo "  make rel-vencimentos D=60 DB=$(DB) -> relatório de vencimentos"
	@echo "  make rel-top INI=2025-01 FIM=2025-06 N=10 DB=$(DB) -> top consumo"
	@echo "  make rel-reposicao DB=$(DB)        -> relatório de reposição"
	@echo "  make test          -> pytest"
	@echo "  make lint          -> ruff check"
	@echo "  make doctor        -> lint + tests + lock-verify"
	@echo "  make ci            -> pipeline local completa"
	@echo "  make clean/distclean -> limpeza"

# ====== VENV / INSTALL ======
$(VENV):
	$(PY) -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel

.PHONY: venv
venv: $(VENV)

.PHONY: install
install: venv
	$(PIP) install -e .
	$(PIP) install pandas openpyxl scipy typer tabulate
	$(PIP) install pytest pytest-cov ruff

.PHONY: install-min
install-min: venv
	$(PIP) install -e .
	$(PIP) install pandas openpyxl scipy typer tabulate

# ====== MIGRAÇÃO / OPERAÇÃO ======
.PHONY: migrate
migrate:
	$(PYTHON) app.py migrate --db $(DB)

.PHONY: verificar
verificar:
	$(PYTHON) app.py verificar --db $(DB)

.PHONY: params-show
params-show:
	$(PYTHON) app.py params show --db $(DB)

.PHONY: params-set
params-set:
	@if [ -z "$(NS)" ] && [ -z "$(MU)" ] && [ -z "$(ST)" ]; then \
	  echo "Uso: make params-set NS=<nivel_servico> MU=<mu_t> ST=<sigma_t>"; \
	  exit 1; \
	fi
	$(PYTHON) app.py params set --db $(DB) \
		$(if $(NS),--nivel-servico $(NS),) \
		$(if $(MU),--mu-t-dias-uteis $(MU),) \
		$(if $(ST),--sigma-t-dias-uteis $(ST),)

# ====== MOVIMENTAÇÃO (LOTE) ======
.PHONY: entrada-lotes
entrada-lotes:
	@if [ -z "$(FILE)" ]; then echo "Informe FILE=<planilha.xlsx>"; exit 1; fi
	$(PYTHON) app.py entrada-lotes "$(FILE)" --db $(DB)

.PHONY: saida-lotes
saida-lotes:
	@if [ -z "$(FILE)" ]; then echo "Informe FILE=<planilha.xlsx>"; exit 1; fi
	$(PYTHON) app.py saida-lotes "$(FILE)" --db $(DB)

# ====== RELATÓRIOS ======
.PHONY: rel-ruptura
rel-ruptura:
	@if [ -z "$(H)" ]; then echo "Uso: make rel-ruptura H=<horizonte_dias>"; exit 1; fi
	$(PYTHON) app.py rel ruptura --horizonte-dias $(H) --db $(DB)

.PHONY: rel-vencimentos
rel-vencimentos:
	@if [ -z "$(D)" ]; then echo "Uso: make rel-vencimentos D=<janela_dias>"; exit 1; fi
	$(PYTHON) app.py rel vencimentos --janela-dias $(D) \
		$$( [ "$(DETALHE)" = "0" ] && echo "--no-detalhar-por-lote" || echo "" ) \
		--db $(DB)

.PHONY: rel-top
rel-top:
	@if [ -z "$(INI)" ] || [ -z "$(FIM)" ]; then echo "Uso: make rel-top INI=YYYY-MM FIM=YYYY-MM [N=20]"; exit 1; fi
	$(PYTHON) app.py rel top-consumo --inicio-ano-mes $(INI) --fim-ano-mes $(FIM) \
		$$( [ -n "$(N)" ] && echo "--top-n $(N)" || echo "" ) \
		--db $(DB)

.PHONY: rel-reposicao
rel-reposicao:
	$(PYTHON) app.py rel reposicao --db $(DB)

# ====== TESTES / LINT ======
.PHONY: test
test:
	$(PYTEST) -q --maxfail=1 --disable-warnings --cov=estoque --cov-report=term-missing

.PHONY: lint
lint:
	$(RUFF) check .

# ====== LOCK ======
.PHONY: lock
lock: install
	@echo ">> Gerando constraints.txt ..."
	@$(PYTHON) -m pip freeze | grep -v "^-e " > constraints.txt
	@echo ">> constraints.txt atualizado."

.PHONY: relock
relock: distclean venv install lock
	@echo ">> Relock concluído."

.PHONY: lock-verify
lock-verify: distclean venv
	@$(PIP) install -r requirements.txt -c constraints.txt

# ====== HEALTHCHECK ======
.PHONY: doctor
doctor: lint test lock-verify
	@echo ">> Tudo certo: lint + tests + lock verificados."

.PHONY: ci
ci: install migrate doctor
	@echo ">> Rodando relatório de ruptura (horizonte=5) como sanity-check..."
	$(PYTHON) app.py rel ruptura --horizonte-dias 5 --db $(DB)

# ====== CLEAN ======
.PHONY: clean
clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info

.PHONY: distclean
distclean: clean
	@rm -rf $(VENV)
