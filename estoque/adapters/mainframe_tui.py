"""
Fancy Mainframe Terminal UI for the Estoque System.

This module provides an interactive terminal user interface (TUI) that allows
users to navigate and execute all the system functions through a menu-driven
interface.
"""

from __future__ import annotations

import os
import subprocess
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Button, Header, Footer, Static, Tree, Input, TextArea, Label,
    Select, Checkbox, ProgressBar, Log, Markdown
)
from textual.screen import ModalScreen, Screen
from textual.binding import Binding
from rich.text import Text
from rich.console import Console
from rich import box
from rich.panel import Panel
from rich.table import Table

from estoque.config import DB_PATH


class StatusDisplay(Static):
    """Display current system status."""
    
    def __init__(self) -> None:
        super().__init__()
        self.refresh_status()
    
    def refresh_status(self) -> None:
        """Update the status display with current system info."""
        venv_path = Path(".venv")
        db_path = Path(DB_PATH)
        
        status_info = []
        
        # Virtual Environment Status
        if venv_path.exists():
            status_info.append("✅ Virtual Environment: Active")
        else:
            status_info.append("❌ Virtual Environment: Not Found")
        
        # Database Status
        if db_path.exists():
            size_mb = db_path.stat().st_size / (1024 * 1024)
            status_info.append(f"✅ Database: {DB_PATH} ({size_mb:.1f}MB)")
        else:
            status_info.append(f"❌ Database: {DB_PATH} (Not Found)")
        
        # Python Path
        python_exe = Path(".venv/bin/python" if venv_path.exists() else "python")
        status_info.append(f"🐍 Python: {python_exe}")
        
        status_text = "\n".join(status_info)
        self.update(status_text)


class MenuTreeWidget(Tree):
    """Main navigation tree widget."""
    
    def __init__(self) -> None:
        super().__init__("🏥 Estoque Clínica - Menu Principal")
        self.setup_menu_tree()
    
    def setup_menu_tree(self) -> None:
        """Setup the menu tree structure."""
        
        # Environment & Installation
        env_node = self.root.add("🔧 Ambiente & Instalação", data="env")
        env_node.add_leaf("🆕 Criar Virtual Environment", data="venv")
        env_node.add_leaf("📦 Instalar Dependências (Completo)", data="install")
        env_node.add_leaf("📦 Instalar Dependências (Mínimo)", data="install-min")
        
        # Database & Migration
        db_node = self.root.add("🗃️ Banco de Dados", data="db")
        db_node.add_leaf("🔄 Executar Migrações", data="migrate")
        db_node.add_leaf("✅ Verificar Estoque", data="verificar")
        
        # Parameters
        params_node = self.root.add("⚙️ Parâmetros", data="params")
        params_node.add_leaf("👁️ Exibir Parâmetros", data="params-show")
        params_node.add_leaf("✏️ Configurar Parâmetros", data="params-set")
        
        # Lote Operations
        lote_node = self.root.add("📋 Movimentação em Lote", data="lote")
        lote_node.add_leaf("⬇️ Entrada de Lotes", data="entrada-lotes")
        lote_node.add_leaf("⬆️ Saída de Lotes", data="saida-lotes")
        
        # Reports
        reports_node = self.root.add("📊 Relatórios", data="reports")
        reports_node.add_leaf("⚠️ Relatório de Ruptura", data="rel-ruptura")
        reports_node.add_leaf("📅 Relatório de Vencimentos", data="rel-vencimentos")
        reports_node.add_leaf("🔝 Top Consumo", data="rel-top")
        reports_node.add_leaf("🔄 Relatório de Reposição", data="rel-reposicao")
        
        # Quality & Testing
        quality_node = self.root.add("🧪 Qualidade", data="quality")
        quality_node.add_leaf("🧪 Executar Testes", data="test")
        quality_node.add_leaf("🔍 Lint (Verificar Código)", data="lint")
        quality_node.add_leaf("🩺 Doctor (Verificação Completa)", data="doctor")
        quality_node.add_leaf("🚀 CI (Pipeline Completa)", data="ci")
        
        # Maintenance
        maintenance_node = self.root.add("🧹 Manutenção", data="maintenance")
        maintenance_node.add_leaf("🧹 Limpeza de Cache", data="clean")
        maintenance_node.add_leaf("🗑️ Limpeza Completa", data="distclean")
        maintenance_node.add_leaf("🔒 Lock Dependencies", data="lock")
        maintenance_node.add_leaf("🔄 Relock Dependencies", data="relock")


class ParametersForm(ModalScreen):
    """Modal form for setting parameters."""
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Cancel"),
        ("ctrl+s", "save", "Save"),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.ns_input: Optional[Input] = None
        self.mu_input: Optional[Input] = None
        self.st_input: Optional[Input] = None
    
    def compose(self) -> ComposeResult:
        with Container(id="parameters-modal"):
            yield Static("⚙️ Configurar Parâmetros do Sistema", classes="modal-title")
            
            with Vertical():
                yield Label("Nível de Serviço (NS): (ex: 0.95)")
                self.ns_input = Input(placeholder="0.95", id="ns-input")
                yield self.ns_input
                
                yield Label("Mu T (dias úteis): (ex: 6)")
                self.mu_input = Input(placeholder="6", id="mu-input")
                yield self.mu_input
                
                yield Label("Sigma T (dias úteis): (ex: 1)")
                self.st_input = Input(placeholder="1", id="st-input")
                yield self.st_input
                
                with Horizontal():
                    yield Button("💾 Salvar", variant="primary", id="save-btn")
                    yield Button("❌ Cancelar", id="cancel-btn")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self.action_save()
        elif event.button.id == "cancel-btn":
            self.app.pop_screen()
    
    def action_save(self) -> None:
        """Save the parameters."""
        ns = self.ns_input.value.strip() if self.ns_input else ""
        mu = self.mu_input.value.strip() if self.mu_input else ""
        st = self.st_input.value.strip() if self.st_input else ""
        
        if not any([ns, mu, st]):
            self.notify("❌ Informe pelo menos um parâmetro!", severity="warning")
            return
        
        params = {"NS": ns, "MU": mu, "ST": st}
        self.dismiss(params)


class FileInputForm(ModalScreen):
    """Modal form for file input operations."""
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Cancel"),
    ]
    
    def __init__(self, operation: str, title: str) -> None:
        super().__init__()
        self.operation = operation
        self.title = title
        self.file_input: Optional[Input] = None
    
    def compose(self) -> ComposeResult:
        with Container(id="file-input-modal"):
            yield Static(f"📁 {self.title}", classes="modal-title")
            
            with Vertical():
                yield Label("Arquivo Excel (.xlsx):")
                self.file_input = Input(placeholder="exemplo.xlsx", id="file-input")
                yield self.file_input
                
                with Horizontal():
                    yield Button("▶️ Executar", variant="primary", id="execute-btn")
                    yield Button("❌ Cancelar", id="cancel-btn")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "execute-btn":
            file_path = self.file_input.value.strip() if self.file_input else ""
            if not file_path:
                self.notify("❌ Informe o arquivo!", severity="warning")
                return
            self.dismiss({"file": file_path})
        elif event.button.id == "cancel-btn":
            self.app.pop_screen()


class ReportParametersForm(ModalScreen):
    """Modal form for report parameters."""
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Cancel"),
    ]
    
    def __init__(self, report_type: str) -> None:
        super().__init__()
        self.report_type = report_type
        self.inputs: Dict[str, Input] = {}
    
    def compose(self) -> ComposeResult:
        with Container(id="report-params-modal"):
            title = {
                "rel-ruptura": "⚠️ Relatório de Ruptura",
                "rel-vencimentos": "📅 Relatório de Vencimentos", 
                "rel-top": "🔝 Top Consumo"
            }.get(self.report_type, "📊 Relatório")
            
            yield Static(title, classes="modal-title")
            
            with Vertical():
                if self.report_type == "rel-ruptura":
                    yield Label("Horizonte (dias):")
                    self.inputs["H"] = Input(placeholder="3", id="h-input")
                    yield self.inputs["H"]
                    
                elif self.report_type == "rel-vencimentos":
                    yield Label("Janela (dias):")
                    self.inputs["D"] = Input(placeholder="60", id="d-input")
                    yield self.inputs["D"]
                    
                    yield Checkbox("Detalhar por lote", id="detalhe-checkbox")
                    
                elif self.report_type == "rel-top":
                    yield Label("Início (YYYY-MM):")
                    self.inputs["INI"] = Input(placeholder="2025-01", id="ini-input")
                    yield self.inputs["INI"]
                    
                    yield Label("Fim (YYYY-MM):")
                    self.inputs["FIM"] = Input(placeholder="2025-06", id="fim-input")
                    yield self.inputs["FIM"]
                    
                    yield Label("Top N (opcional):")
                    self.inputs["N"] = Input(placeholder="20", id="n-input")
                    yield self.inputs["N"]
                
                with Horizontal():
                    yield Button("📊 Gerar", variant="primary", id="generate-btn")
                    yield Button("❌ Cancelar", id="cancel-btn")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "generate-btn":
            params = {}
            
            if self.report_type == "rel-ruptura":
                h_val = self.inputs["H"].value.strip()
                if not h_val:
                    self.notify("❌ Informe o horizonte!", severity="warning")
                    return
                params["H"] = h_val
                
            elif self.report_type == "rel-vencimentos":
                d_val = self.inputs["D"].value.strip()
                if not d_val:
                    self.notify("❌ Informe a janela!", severity="warning")
                    return
                params["D"] = d_val
                
                checkbox = self.query_one("#detalhe-checkbox", Checkbox)
                if not checkbox.value:
                    params["DETALHE"] = "0"
                    
            elif self.report_type == "rel-top":
                ini_val = self.inputs["INI"].value.strip()
                fim_val = self.inputs["FIM"].value.strip()
                
                if not ini_val or not fim_val:
                    self.notify("❌ Informe início e fim!", severity="warning")
                    return
                
                params["INI"] = ini_val
                params["FIM"] = fim_val
                
                n_val = self.inputs["N"].value.strip()
                if n_val:
                    params["N"] = n_val
            
            self.dismiss(params)
            
        elif event.button.id == "cancel-btn":
            self.app.pop_screen()


class OutputScreen(Screen):
    """Screen to display command output."""
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("q", "app.pop_screen", "Back"),
    ]
    
    def __init__(self, title: str, content: str) -> None:
        super().__init__()
        self.title = title
        self.content = content
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        with ScrollableContainer():
            yield Static(f"📋 {self.title}", classes="output-title")
            yield TextArea(self.content, read_only=True, show_line_numbers=False)
        
        yield Footer()


class EstoqueMainframeApp(App):
    """Main TUI Application for Estoque System."""
    
    CSS = """
    Screen {
        background: #001122;
    }
    
    .modal-title {
        background: #003366;
        color: #ffffff;
        text-align: center;
        padding: 1;
        margin-bottom: 1;
    }
    
    .output-title {
        background: #004488;
        color: #ffffff;
        text-align: center;
        padding: 1;
        margin-bottom: 1;
    }
    
    Container#parameters-modal {
        background: #112233;
        border: solid #00aaff;
        width: 60;
        height: 20;
        margin: 2;
    }
    
    Container#file-input-modal {
        background: #112233;
        border: solid #00aaff;
        width: 50;
        height: 12;
        margin: 2;
    }
    
    Container#report-params-modal {
        background: #112233;
        border: solid #00aaff;
        width: 60;
        height: 18;
        margin: 2;
    }
    
    Tree {
        background: #001a33;
        color: #ccddff;
    }
    
    StatusDisplay {
        background: #003366;
        color: #ffffff;
        padding: 1;
    }
    
    Button {
        margin: 1;
    }
    """
    
    TITLE = "🏥 Estoque Clínica - Mainframe Terminal UI"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
        ("r", "refresh", "Refresh Status"),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.menu_tree: Optional[MenuTreeWidget] = None
        self.status_display: Optional[StatusDisplay] = None
    
    def compose(self) -> ComposeResult:
        """Compose the main UI layout."""
        yield Header()
        
        with Horizontal():
            with Container(classes="left-panel"):
                self.menu_tree = MenuTreeWidget()
                yield self.menu_tree
            
            with Vertical(classes="right-panel"):
                self.status_display = StatusDisplay()
                yield self.status_display
                
                yield Static("""
🏥 **ESTOQUE CLÍNICA - SISTEMA MAINFRAME**

Bem-vindo ao Sistema de Gestão de Estoque!

**Como usar:**
- Use as setas ↑↓ para navegar no menu
- Pressione ENTER para executar uma ação
- Pressione 'r' para atualizar o status
- Pressione 'q' para sair

**Status das operações aparecerá aqui.**
                """, classes="info-panel")
        
        yield Footer()
    
    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle menu tree node selection."""
        if not event.node.data:
            return
        
        action = event.node.data
        self.execute_action(action)
    
    def execute_action(self, action: str) -> None:
        """Execute the selected action."""
        try:
            if action in ["venv", "install", "install-min", "migrate", "verificar", 
                         "params-show", "test", "lint", "doctor", "ci", "clean", 
                         "distclean", "lock", "relock", "rel-reposicao"]:
                self.run_simple_command(action)
                
            elif action == "params-set":
                self.push_screen(ParametersForm(), self.on_params_result)
                
            elif action in ["entrada-lotes", "saida-lotes"]:
                title = "Entrada de Lotes" if action == "entrada-lotes" else "Saída de Lotes"
                self.push_screen(FileInputForm(action, title), self.on_file_input_result)
                
            elif action in ["rel-ruptura", "rel-vencimentos", "rel-top"]:
                self.push_screen(ReportParametersForm(action), self.on_report_params_result)
                
        except Exception as e:
            self.notify(f"❌ Erro: {str(e)}", severity="error")
    
    def run_simple_command(self, action: str) -> None:
        """Run a simple command without parameters."""
        try:
            # Determine the command to run
            if os.name == "nt":  # Windows
                cmd = f"build.bat {action}"
            else:
                cmd = f"make {action}"
            
            self.notify(f"🔄 Executando: {cmd}", timeout=3)
            
            # Run the command
            result = subprocess.run(
                cmd.split(), 
                capture_output=True, 
                text=True, 
                cwd=Path.cwd()
            )
            
            output = f"Comando: {cmd}\n\n"
            output += f"Return code: {result.returncode}\n\n"
            
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n\n"
            
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
            
            self.push_screen(OutputScreen(f"Resultado: {action}", output))
            
            if result.returncode == 0:
                self.notify(f"✅ {action} executado com sucesso!")
            else:
                self.notify(f"❌ {action} falhou (code: {result.returncode})", severity="error")
                
        except Exception as e:
            self.notify(f"❌ Erro ao executar {action}: {str(e)}", severity="error")
    
    def on_params_result(self, params: Dict[str, str]) -> None:
        """Handle parameters form result."""
        if params:
            self.run_params_command(params)
    
    def run_params_command(self, params: Dict[str, str]) -> None:
        """Run the params-set command with given parameters."""
        try:
            # Set environment variables and run command
            env = os.environ.copy()
            for key, value in params.items():
                if value:  # Only set non-empty values
                    env[key] = value
            
            if os.name == "nt":  # Windows
                cmd = "build.bat params-set"
            else:
                cmd = "make params-set"
            
            self.notify(f"🔄 Configurando parâmetros...", timeout=3)
            
            result = subprocess.run(
                cmd.split(),
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
                env=env
            )
            
            output = f"Comando: {cmd}\n"
            output += f"Parâmetros: {params}\n\n"
            output += f"Return code: {result.returncode}\n\n"
            
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n\n"
            
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
            
            self.push_screen(OutputScreen("Configuração de Parâmetros", output))
            
            if result.returncode == 0:
                self.notify("✅ Parâmetros configurados com sucesso!")
            else:
                self.notify(f"❌ Erro ao configurar parâmetros (code: {result.returncode})", severity="error")
                
        except Exception as e:
            self.notify(f"❌ Erro: {str(e)}", severity="error")
    
    def on_file_input_result(self, result: Optional[Dict[str, str]]) -> None:
        """Handle file input form result."""
        if result and "file" in result:
            file_path = result["file"]
            # We need to determine which operation this was for
            # For now, we'll handle it in the action context
            pass
    
    def on_report_params_result(self, params: Optional[Dict[str, str]]) -> None:
        """Handle report parameters form result."""
        if params:
            # Determine the report type from the params structure
            if "H" in params:
                self.run_report_command("rel-ruptura", params)
            elif "D" in params:
                self.run_report_command("rel-vencimentos", params)
            elif "INI" in params and "FIM" in params:
                self.run_report_command("rel-top", params)
    
    def run_report_command(self, report_type: str, params: Dict[str, str]) -> None:
        """Run a report command with given parameters."""
        try:
            env = os.environ.copy()
            for key, value in params.items():
                env[key] = value
            
            if os.name == "nt":  # Windows
                cmd = f"build.bat {report_type}"
            else:
                cmd = f"make {report_type}"
            
            self.notify(f"🔄 Gerando relatório: {report_type}", timeout=3)
            
            result = subprocess.run(
                cmd.split(),
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
                env=env
            )
            
            output = f"Comando: {cmd}\n"
            output += f"Parâmetros: {params}\n\n"
            output += f"Return code: {result.returncode}\n\n"
            
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n\n"
            
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
            
            self.push_screen(OutputScreen(f"Relatório: {report_type}", output))
            
            if result.returncode == 0:
                self.notify(f"✅ Relatório {report_type} gerado com sucesso!")
            else:
                self.notify(f"❌ Erro ao gerar relatório (code: {result.returncode})", severity="error")
                
        except Exception as e:
            self.notify(f"❌ Erro: {str(e)}", severity="error")
    
    def action_refresh(self) -> None:
        """Refresh the status display."""
        if self.status_display:
            self.status_display.refresh_status()
        self.notify("🔄 Status atualizado!", timeout=2)
    
    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.dark = not self.dark
        self.notify(f"🌙 Dark mode: {'On' if self.dark else 'Off'}", timeout=2)


def main() -> None:
    """Run the mainframe TUI application."""
    app = EstoqueMainframeApp()
    app.run()


if __name__ == "__main__":
    main()