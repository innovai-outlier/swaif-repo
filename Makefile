# ====== PLATAFORMA-ESPECÍFICA ======
# Este Makefile foi dividido em versões específicas para cada plataforma:
#
# Para usuários Linux/Unix/MacOS:
#   use: make -f Makefile.unix <target>
#   exemplo: make -f Makefile.unix install
#
# Para usuários Windows CMD:
#   use: build.bat <target>  
#   exemplo: build.bat install

# ====== HELP ======
.PHONY: help
help:
	@echo "=== SISTEMA DE BUILD MULTIPLATAFORMA ==="
	@echo ""
	@echo "Para usuários Linux/Unix/MacOS:"
	@echo "  make -f Makefile.unix <target>  -> uso direto do Makefile Unix"
	@echo ""
	@echo "Para usuários Windows:"
	@echo "  build.bat <target>              -> usa build.bat"
	@echo ""
	@echo "Exemplos de comandos disponíveis:"
	@echo "  venv, install, migrate, test, lint, doctor, ci, clean"
	@echo ""
	@echo "Para ver todos os comandos específicos da sua plataforma:"
	@echo "  Linux/Unix: make -f Makefile.unix help"
	@echo "  Windows:    build.bat help"

# ====== ATALHOS PARA LINUX/UNIX ======
.PHONY: venv install install-min migrate verificar params-show params-set
.PHONY: entrada-lotes saida-lotes rel-ruptura rel-vencimentos rel-top rel-reposicao
.PHONY: test lint lock relock lock-verify doctor ci clean distclean

venv install install-min migrate verificar params-show params-set:
	@$(MAKE) -f Makefile.unix $@

entrada-lotes saida-lotes rel-ruptura rel-vencimentos rel-top rel-reposicao:
	@$(MAKE) -f Makefile.unix $@

test lint lock relock lock-verify doctor ci clean distclean:
	@$(MAKE) -f Makefile.unix $@