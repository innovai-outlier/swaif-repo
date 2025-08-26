# Build System - Multiplataforma

Este projeto agora suporta múltiplas plataformas com sistemas de build específicos:

## Para usuários Linux/Unix/MacOS

Use o Makefile Unix:
```bash
# Ver ajuda
make -f Makefile.unix help

# Ou usar os atalhos diretos
make help
make install
make test
make lint
```

## Para usuários Windows

Use o script de build em batch:
```cmd
# Ver ajuda
build.bat help

# Exemplos de uso
build.bat install
build.bat test
build.bat lint
```

## Comandos Disponíveis

### Ambiente e Instalação
- `venv` - Cria ambiente virtual
- `install` - Instala todas as dependências (app + dev)
- `install-min` - Instala dependências mínimas (só app)

### Migração e Operação
- `migrate` - Aplica migrações e cria views do banco
- `verificar` - Executa cálculo completo do estoque
- `params-show` - Exibe parâmetros globais
- `params-set` - Grava parâmetros (requer NS, MU, ST)

### Movimentação em Lote
- `entrada-lotes` - Processa planilha de entrada (requer FILE)
- `saida-lotes` - Processa planilha de saída (requer FILE)

### Relatórios
- `rel-ruptura` - Relatório de ruptura (requer H=horizonte)
- `rel-vencimentos` - Relatório de vencimentos (requer D=janela)
- `rel-top` - Top consumo (requer INI=início, FIM=fim, opcional N=top_n)
- `rel-reposicao` - Relatório de reposição

### Qualidade e Testes
- `test` - Executa testes com cobertura
- `lint` - Verifica código com ruff
- `doctor` - Executa lint + testes + verificação de deps
- `ci` - Pipeline completa (install + migrate + doctor)

### Limpeza
- `clean` - Remove arquivos de cache
- `distclean` - Remove cache e ambiente virtual

## Exemplos de Uso

### Linux/Unix/MacOS
```bash
# Setup completo
make install
make migrate

# Definir parâmetros
NS=0.95 MU=6 ST=1 make params-set

# Processar planilhas
FILE=entrada.xlsx make entrada-lotes
FILE=saida.xlsx make saida-lotes

# Gerar relatórios
H=5 make rel-ruptura
D=60 make rel-vencimentos
INI=2025-01 FIM=2025-06 N=10 make rel-top
```

### Windows
```cmd
REM Setup completo
build.bat install
build.bat migrate

REM Definir parâmetros
set NS=0.95 && set MU=6 && set ST=1 && build.bat params-set

REM Processar planilhas
set FILE=entrada.xlsx && build.bat entrada-lotes
set FILE=saida.xlsx && build.bat saida-lotes

REM Gerar relatórios
set H=5 && build.bat rel-ruptura
set D=60 && build.bat rel-vencimentos
set INI=2025-01 && set FIM=2025-06 && set N=10 && build.bat rel-top
```