#!/usr/bin/env python3
"""
Launcher script for the Estoque Mainframe TUI.

This script provides an easy way to launch the terminal user interface
from the command line.
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from estoque.adapters.mainframe_tui import main
    
    if __name__ == "__main__":
        print("🚀 Iniciando Estoque Clínica - Mainframe Terminal UI...")
        main()
        
except ImportError as e:
    print(f"❌ Erro ao importar o TUI: {e}")
    print("📦 Certifique-se de que as dependências estão instaladas:")
    print("   pip install textual")
    sys.exit(1)
except KeyboardInterrupt:
    print("\n👋 Saindo do sistema...")
    sys.exit(0)
except Exception as e:
    print(f"❌ Erro inesperado: {e}")
    sys.exit(1)