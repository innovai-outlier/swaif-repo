from __future__ import annotations

import os
import subprocess
from typing import Optional, Dict
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Button, Header, Footer, Static, Tree, Input, DataTable, Label,
    Checkbox
)
from textual.screen import ModalScreen, Screen


from estoque.config import DB_PATH
from estoque.infra.db import connect
from estoque.infra.logger import LOGS_DIR, ENABLE_OUTPUT, ENABLE_LOGGING, log_system_event, get_log_summary
from estoque.infra.repositories import ProdutoRepo, EntradaRepo, SaidaRepo, DimConsumoRepo, DemandaRepo, SnapshotRepo
from estoque.usecases.relatorios import relatorio_reposicao, relatorio_alerta_ruptura, relatorio_produtos_a_vencer, relatorio_mais_consumidos
from estoque.usecases.registrar_entrada import run_entrada_unica, run_entrada_lote
from estoque.usecases.registrar_saida import run_saida_unica, run_saida_lote


class OutputDataTableScreen(Screen):
    """Screen to display a DataTable with database/query results."""
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("q", "app.pop_screen", "Back"),
    ]

    def __init__(self, title: str, columns: list, rows: list) -> None:
        super().__init__()
        self.title = title
        self.columns = columns
        self.rows = rows

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer():
            yield Static(f"📋 {self.title}", classes="output-title")
            dt = DataTable(zebra_stripes=True)
            dt.add_columns(*self.columns)
            for row in self.rows:
                dt.add_row(*[str(cell) if cell is not None else "" for cell in row])
            yield dt
        yield Footer()

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
        
        # Logging & Printing
        if ENABLE_LOGGING:
            status_info.append("✅ Logging: Ativo")
        else:
            status_info.append("❌ Logging: Desativado")
            
        if ENABLE_OUTPUT:
            status_info.append("✅ Output: Ativo")
        else:
            status_info.append("❌ Output: Desativado")

        status_text = "\n".join(status_info)
        self.update(status_text)


class MenuTreeWidget(Tree):
    """Main navigation tree widget."""
    
    def __init__(self) -> None:
        super().__init__("🏥 Estoque Clínica - Menu Principal")
        self.setup_menu_tree()
    
    def setup_menu_tree(self) -> None:
        """Setup the menu tree structure, expandido conforme tui.py."""
        # Menu principal expandido
        # Movimentação
        mov_node = self.root.add("� Movimentação (Entrada/Saída)", data="movimentacao")
        mov_node.add_leaf("⬇️ Carregar Entradas (XLSX)", data="entrada-lotes")
        mov_node.add_leaf("⬆️ Carregar Saídas (XLSX)", data="saida-lotes")
        mov_node.add_leaf("✍️ Entrada Manual", data="entrada-unica")
        mov_node.add_leaf("✍️ Saída Manual", data="saida-unica")

        # Banco de Dados
        db_node = self.root.add("🗃️ Banco de Dados", data="database")
        db_node.add_leaf("� Ver Produtos", data="ver-produtos")
        db_node.add_leaf("📥 Ver Entradas", data="ver-entradas")
        db_node.add_leaf("📤 Ver Saídas", data="ver-saidas")
        db_node.add_leaf("� Ver Estoque Atual", data="ver-estoque-atual")
        db_node.add_leaf("📑 Ver Lotes", data="ver-lotes")
    
        # Relatórios
        reports_node = self.root.add("� Relatórios", data="reports")
        reports_node.add_leaf("⚠️ Relatório de Ruptura", data="rel-ruptura")
        reports_node.add_leaf("📅 Produtos a Vencer", data="rel-vencimentos")
        reports_node.add_leaf("🔝 Top Consumo", data="rel-top")
        reports_node.add_leaf("🔄 Relatório de Reposição", data="rel-reposicao")

        # Sistema
        sys_node = self.root.add("⚙️ Sistema", data="sistema")
        sys_node.add_leaf("🔄 Aplicar Migrações", data="migrate")
        sys_node.add_leaf("✅ Verificar Estoque", data="verificar")
        sys_node.add_leaf("⚙️ Configurar Parâmetros", data="params-set")
        sys_node.add_leaf("�️ Exibir Parâmetros", data="params-show")

        # Qualidade & Testes
        quality_node = self.root.add("🧪 Qualidade", data="quality")
        quality_node.add_leaf("🧪 Executar Testes", data="test")
        quality_node.add_leaf("🔍 Lint (Verificar Código)", data="lint")
        quality_node.add_leaf("🩺 Doctor (Verificação Completa)", data="doctor")
        quality_node.add_leaf("🚀 CI (Pipeline Completa)", data="ci")


        # Limpeza de dados
        db_clean_node = self.root.add("🗑️ Limpeza de dados", data="db-clean")
        db_clean_node.add_leaf("🗑️ Limpar Dados Fictícios", data="clean-auto-products")
        db_clean_node.add_leaf("🗑️ Limpar Todos os Dados", data="clean-all-data")
        
        # Manutenção
        maintenance_node = self.root.add("🧹 Manutenção", data="maintenance")
        maintenance_node.add_leaf("🧹 Limpeza de cache", data="clean")
        maintenance_node.add_leaf("🗑️ Remover artefatos gerados", data="distclean")
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
                self.file_input = Input(placeholder="entradas.xlsx", id="file-input")
                yield self.file_input
                
                with Horizontal():
                    yield Button("Executar", variant="primary", id="execute-btn")
                    yield Button("Cancelar", id="cancel-btn")
    
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
            # Usa Static para renderizar ANSI/estilo Rich corretamente
            yield Static(self.content, markup=False)
        
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
        width: 60;
        height: 15;
        margin: 2;
    }
    
    Container#report-params-modal {
        background: #112233;
        border: solid #00aaff;
        width: 60;
        height: 25;
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
        """Executa a ação selecionada, agora com relatórios e sistema integrados."""
        log_system_event("tui_action_start", {"action": action})
        
        try:
            # Movimentação
            if action == "entrada-lotes":
                self.push_screen(FileInputForm(action, "Carregar Entradas (XLSX)"), self.on_file_input_result)
            elif action == "saida-lotes":
                self.push_screen(FileInputForm(action, "Carregar Saídas (XLSX)"), self.on_file_input_result)
            elif action == "entrada-unica":
                self.run_manual_entry("entrada")
            elif action == "saida-unica":
                self.run_manual_entry("saida")

            # Banco de Dados
            elif action == "ver-produtos":
                self.show_db_table("Produtos Cadastrados", "SELECT codigo, nome, categoria, lote_min, quantidade_minima FROM produto ORDER BY codigo", ["Código", "Nome", "Categoria", "Lote Min", "Qtd Min"])
            elif action == "ver-entradas":
                self.show_db_table("Entradas Recentes", "SELECT data_entrada, codigo, quantidade_raw, lote, representante FROM entrada ORDER BY id DESC", ["Data", "Código", "Quantidade", "Lote", "Representante"])
            elif action == "ver-saidas":
                self.show_db_table("Saídas Recentes", "SELECT data_saida, codigo, quantidade_raw, lote, paciente FROM saida ORDER BY id DESC", ["Data", "Código", "Quantidade", "Lote", "Paciente"])
            elif action == "ver-estoque-atual":
                self.show_db_table("Estoque Atual", "SELECT codigo, estoque_total_apres, unidade_apresentacao, estoque_total_unid, unidade_unidade FROM vw_estoque_consolidado ORDER BY codigo", ["Código", "Estoque Apres", "Un. Apres", "Estoque Unid", "Un. Unid"])
            elif action == "ver-lotes":
                self.show_db_table("Lotes Detalhados", "SELECT codigo, lote, qtd_apres_num, qtd_apres_un, data_entrada, data_validade FROM vw_lotes_detalhe ORDER BY codigo, lote", ["Código", "Lote", "Qtd Num", "Unidade", "Data Entrada", "Data Validade"])

            # Relatórios
            elif action == "rel-ruptura":
                self.push_screen(ReportParametersForm(action), self.on_report_params_result)
            elif action == "rel-vencimentos":
                self.push_screen(ReportParametersForm(action), self.on_report_params_result)
            elif action == "rel-top":
                self.push_screen(ReportParametersForm(action), self.on_report_params_result)
            elif action == "rel-reposicao":
                self.run_report("rel-reposicao")

            # Sistema
            elif action == "migrate":
                self.run_simple_command("migrate")
            elif action == "verificar":
                self.run_simple_command("verificar")
            elif action == "params-set":
                self.push_screen(ParametersForm(), self.on_params_result)
            elif action == "params-show":
                self.run_simple_command("params-show")
            elif action == "view-logs":
                self.show_logs_menu()
            elif action == "log-summary":
                self.show_log_summary()
                
            # Limpeza de dados
            elif action == "clean-auto-products":
                self.clean_auto_created_products()
            elif action == "clean-all-data":
                self.clean_all_data()

            # Qualidade & Testes
            elif action in ["venv", "install", "install-min", "test", "lint", "doctor", "ci", "clean", "distclean", "lock", "relock"]:
                self.run_simple_command(action)
                
        except Exception as e:
            self.notify(f"❌ Erro: {str(e)}", severity="error")

    def clean_auto_created_products(self) -> None:
        """Remove produtos fictícios (Auto-created) e registros relacionados do banco de dados."""
        log_system_event("cleanup_auto_products_start")
        
        try:
            with connect(DB_PATH) as c:
                # Seleciona códigos dos produtos fictícios
                codigos = [row[0] for row in c.execute("SELECT codigo FROM produto WHERE nome LIKE 'Auto-created%' ").fetchall()]
                total_prod = len(codigos)
                total_entradas = total_saidas = total_lotes = 0
                if codigos:
                    # Remove entradas
                    total_entradas = c.execute(f"DELETE FROM entrada WHERE codigo IN ({','.join(['?']*len(codigos))})", codigos).rowcount
                    # Remove saídas
                    total_saidas = c.execute(f"DELETE FROM saida WHERE codigo IN ({','.join(['?']*len(codigos))})", codigos).rowcount
                    # Remove lotes (se existir tabela lote)
                    try:
                        total_lotes = c.execute(f"DELETE FROM lote WHERE codigo IN ({','.join(['?']*len(codigos))})", codigos).rowcount
                    except Exception:
                        pass
                    # Remove produtos
                    deleted = c.execute(f"DELETE FROM produto WHERE codigo IN ({','.join(['?']*len(codigos))})", codigos).rowcount
                else:
                    deleted = 0
                c.commit()
            msg = (
                f"Produtos fictícios removidos: {deleted}\n"
                f"Entradas removidas: {total_entradas}\n"
                f"Saídas removidas: {total_saidas}\n"
                f"Lotes removidos: {total_lotes}"
            )
            
            log_system_event("cleanup_auto_products_success", {
                "products_deleted": deleted,
                "entries_deleted": total_entradas,
                "exits_deleted": total_saidas,
                "lots_deleted": total_lotes
            })
            
            self.push_screen(OutputScreen("Limpeza de Produtos Fictícios", msg))
            self.notify(f"✅ Limpeza concluída:\n{msg}")
            
        except Exception as e:
            error_msg = str(e)
            log_system_event("cleanup_auto_products_error", {"error": error_msg}, level="error")
            self.push_screen(OutputScreen("Erro na Limpeza", error_msg))
            self.notify(f"❌ Erro ao limpar produtos fictícios: {error_msg}", severity="error")

    # Limpar todas as tabelas
    def clean_all_data(self) -> None:
        try:
            # Limpar todas as tabelas
            DemandaRepo(DB_PATH).delete_all()
            EntradaRepo(DB_PATH).delete_all()
            SaidaRepo(DB_PATH).delete_all()
            SnapshotRepo(DB_PATH).delete_all()
            DimConsumoRepo(DB_PATH).delete_all()
            ProdutoRepo(DB_PATH).delete_all()

            msg = (
                f"O conteúdo das tabelas foi removido com sucesso.\n"
            )
            #self.push_screen(OutputScreen("Limpeza da Base de Dados", msg))
            self.notify(f"✅ Limpeza da Base de Dados:\n{msg}")
        except Exception as e:
            self.notify(f"❌ Erro ao limpar todas as tabelas: {str(e)}", severity="error")

    def run_report(self, report_type: str, params: Dict[str, str]) -> None:
        try:
            if report_type == "rel-reposicao":
                resultado = relatorio_reposicao(DB_PATH)
                titulo = "Relatório de Reposição"
                
            elif report_type == "rel-ruptura":
                horizonte_dias = 7
                for key, value in params.items():
                    if key == "H" and value:
                        horizonte_dias = int(value)
                resultado = relatorio_alerta_ruptura(db_path=DB_PATH, horizonte_dias=horizonte_dias)
                titulo = "Relatório de Ruptura"
                
            elif report_type == "rel-vencimentos":
                janela_dias = 30
                for key, value in params.items():
                    if key == "D" and value:
                        janela_dias = int(value)
                resultado = relatorio_produtos_a_vencer(db_path=DB_PATH, janela_dias=janela_dias)
                titulo = "Produtos a Vencer"
            
            elif report_type == "rel-top":
                ini = "2025-01"
                fim = "2025-06"
                top_n = 10
                for key, value in params.items():
                    if key == "I" and value:
                        ini = value
                    elif key == "F" and value:
                        fim = value
                    elif key == "N" and value:
                        top_n = int(value)
                # Parâmetros podem ser passados via self, mas aqui usa padrão
                resultado = relatorio_mais_consumidos(inicio_ano_mes=ini, fim_ano_mes=fim, top_n=top_n, db_path=DB_PATH)
                titulo = "Top Consumo"
            else:
                resultado = None
                titulo = "Relatório"
            if resultado:
                colunas = resultado[0]
                rows = resultado[1] 
                self.push_screen(OutputDataTableScreen(titulo, colunas, rows))
            else:
                self.push_screen(OutputScreen(titulo, "Nenhum dado encontrado."))
        except Exception as e:
            self.notify(f"❌ Erro ao gerar relatório: {str(e)}", severity="error")

    def run_manual_entry(self, tipo: str) -> None:
        """Executa entrada ou saída manual via prompt."""
        try:
            if tipo == "entrada":
                resultado = run_entrada_unica(DB_PATH)
                self.push_screen(OutputScreen("Entrada Registrada", str(resultado)))
            elif tipo == "saida":
                resultado = run_saida_unica(DB_PATH)
                self.push_screen(OutputScreen("Saída Registrada", str(resultado)))
        except Exception as e:
            self.notify(f"❌ Erro ao registrar {tipo}: {str(e)}", severity="error")

    def show_db_table(self, titulo: str, query: str, colunas: list, limite: int = 20) -> None:
        try:
            with connect(DB_PATH) as c:
                rows = c.execute(query).fetchmany(limite)
            if not rows:
                self.push_screen(OutputScreen(titulo, "Nenhum dado encontrado."))
                return
            self.push_screen(OutputDataTableScreen(titulo, colunas, rows))
        except Exception as e:
            self.notify(f"❌ Erro ao consultar {titulo}: {str(e)}", severity="error")

    def run_simple_command(self, command: str) -> None:
        """Execute a simple system command via build.bat/make."""
        try:
            if os.name == "nt":  # Windows
                cmd = f"build.bat {command}"
            else:
                cmd = f"make {command}"
            
            self.notify(f"🔄 Executando: {command}", timeout=3)
            
            result = subprocess.run(
                cmd.split(),
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            
            output = f"Comando: {cmd}\n"
            output += f"Return code: {result.returncode}\n\n"
            
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n\n"
            
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
            
            self.push_screen(OutputScreen(f"Execução: {command}", output))
            
            if result.returncode == 0:
                self.notify(f"✅ {command} executado com sucesso!")
            else:
                self.notify(f"❌ {command} falhou (code: {result.returncode})", severity="error")
                
        except Exception as e:
            self.notify(f"❌ Erro ao executar {command}: {str(e)}", severity="error")

    def on_params_result(self, params: Dict[str, str]) -> None:
        """Handle parameters form result."""
        if params:
            self.run_report(params)
    
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
            
            self.notify("🔄 Configurando parâmetros...", timeout=3)
            
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
            # Descobre a operação ativa pelo último action executado
            # Para garantir, pode-se usar um atributo self.last_file_action
            # Mas aqui, vamos tentar identificar pelo nome do arquivo ou contexto
            # Alternativamente, pode-se pedir para o usuário informar novamente, mas vamos assumir entrada-lotes ou saida-lotes
            # Para simplificar, verifica se o arquivo existe e tenta importar como entrada ou saída
            import os
            if not os.path.exists(file_path):
                self.push_screen(OutputScreen("Arquivo não encontrado", f"Arquivo '{file_path}' não existe."))
                return
            # Tenta importar como entrada ou saída
            try:
                resultado = None
                #Extrai do nome do arquivo se contém entrada ou saída na sua string:
                if "entrada" in  file_path.lower():
                    resultado = run_entrada_lote(file_path, DB_PATH)
                    titulo = "Entradas Importadas"
                elif "saida" in file_path.lower() or "saída" in file_path.lower():
                    resultado = run_saida_lote(file_path, DB_PATH)
                    titulo = "Saídas Importadas"
                else:
                    self.push_screen(OutputScreen("Erro ao importar arquivo", "O nome do arquivo precisa conter 'entrada' ou 'saída' para identificação."))
                if resultado:
                    # resultado é um dict simples: {"arquivo": path, "linhas_inseridas": count}
                    # Converte para formato de tabela
                    colunas = ["Campo", "Valor"]
                    rows = [[key, str(value)] for key, value in resultado.items()]
                    self.push_screen(OutputDataTableScreen(titulo, colunas, rows))
                else:
                    self.push_screen(OutputScreen("Importação", "Nenhum dado importado."))
            except Exception as e:
                self.push_screen(OutputScreen("Erro ao importar arquivo", str(e)))
    
    def on_report_params_result(self, params: Optional[Dict[str, str]]) -> None:
        """Handle report parameters form result."""
        if params:
            # Determine the report type from the params structure
            if "H" in params:
                self.run_report("rel-ruptura", params)
            elif "D" in params:
                self.run_report("rel-vencimentos", params)
            elif "INI" in params and "FIM" in params:
                self.run_report("rel-top", params)
    
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

    def show_logs_menu(self) -> None:
        """Show a submenu for different log types."""
        log_types = [
            ("Transações", "transactions"),
            ("Entradas", "entradas"),
            ("Saídas", "saidas"),
            ("Banco de Dados", "database"),
            ("Sistema", "system")
        ]
        
        menu_text = "📋 **VISUALIZAÇÃO DE LOGS**\n\n"
        menu_text += "Selecione o tipo de log:\n\n"
        
        for i, (nome, tipo) in enumerate(log_types, 1):
            menu_text += f"{i}. {nome}\n"
        
        menu_text += "\nPressione ESC para voltar"
        
        # Para simplificar, vou mostrar todos os logs de transação por padrão
        self.show_log_content("transactions")

    def show_log_content(self, log_type: str) -> None:
        """Show the content of a specific log type."""
        log_system_event("view_logs", {"log_type": log_type})
        
        try:
            content = get_log_summary(log_type, lines=500)
            
            title_map = {
                "transactions": "📋 Logs de Transações",
                "entradas": "📥 Logs de Entradas", 
                "saidas": "📤 Logs de Saídas",
                "database": "🗃️ Logs do Banco de Dados",
                "system": "⚙️ Logs do Sistema"
            }
            
            title = title_map.get(log_type, f"📋 Logs - {log_type}")
            self.push_screen(OutputScreen(title, content))
            
        except Exception as e:
            error_msg = str(e)
            log_system_event("view_logs_error", {"log_type": log_type, "error": error_msg}, level="error")
            self.push_screen(OutputScreen("Erro ao carregar logs", error_msg))

    def show_log_summary(self) -> None:
        """Show a summary of all log activity."""
        log_system_event("view_log_summary")
        
        try:
            summary_text = "📊 **RESUMO DOS LOGS DO SISTEMA**\n\n"
            
            log_files = {
                "Transações": "transactions.log",
                "Entradas": "entradas.log",
                "Saídas": "saidas.log",
                "Banco de Dados": "database.log",
                "Sistema": "system.log"
            }
            
            for name, filename in log_files.items():
                log_path = Path(LOGS_DIR) / filename
                if log_path.exists():
                    size_kb = log_path.stat().st_size / 1024
                    try:
                        with open(log_path, 'r', encoding='utf-8') as f:
                            lines = len(f.readlines())
                        summary_text += f"✅ {name}: {lines} linhas ({size_kb:.1f} KB)\n"
                    except Exception:
                        summary_text += f"⚠️ {name}: {size_kb:.1f} KB (erro ao contar linhas)\n"
                else:
                    summary_text += f"❌ {name}: Arquivo não encontrado\n"
            
            summary_text += f"\n📁 Diretório de logs: {LOGS_DIR}\n"
            
            self.push_screen(OutputScreen("Resumo dos Logs", summary_text))
            
        except Exception as e:
            error_msg = str(e)
            log_system_event("view_log_summary_error", {"error": error_msg}, level="error")
            self.push_screen(OutputScreen("Erro ao gerar resumo", error_msg))


def main() -> None:
    """Run the mainframe TUI application."""
    app = EstoqueMainframeApp()
    app.run()


if __name__ == "__main__":
    main()