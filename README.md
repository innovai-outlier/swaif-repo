# Estoque Clínica - Sistema de Gestão de Estoque

Sistema de gestão de estoque para clínicas médicas com funcionalidades avançadas de controle de inventário, relatórios e análises.

## 🚀 Como Usar

Este projeto suporta múltiplas plataformas com sistemas de build específicos.

### Linux/Unix/MacOS
```bash
# Ver comandos disponíveis
make help
make -f Makefile.unix help

# Setup inicial
make install
make migrate

# Executar testes
make test
```

### Windows
```cmd
# Ver comandos disponíveis
build.bat help

# Setup inicial
build.bat install
build.bat migrate

# Executar testes
build.bat test
```

## 🖥️ Interface Terminal (TUI)

O sistema inclui uma interface terminal interativa moderna:

```bash
# Linux/Unix/MacOS
python mainframe.py

# Windows
python mainframe.py

# Ou através da CLI
python app.py tui
```

## 📖 Documentação

- **BUILD.md** - Instruções detalhadas de build para cada plataforma
- **Comandos disponíveis** - Setup, migração, relatórios, testes, linting

## ✨ Funcionalidades

- 🗃️ Gestão de banco de dados
- ⚙️ Configuração de parâmetros
- 📋 Movimentação em lote (entrada/saída)
- 📊 Relatórios (ruptura, vencimentos, top consumo, reposição)
- 🧪 Testes automatizados
- 🔍 Linting e qualidade de código
- 🖥️ Interface terminal interativa (TUI)