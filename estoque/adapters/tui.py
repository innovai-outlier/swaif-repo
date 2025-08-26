# estoque/adapters/tui.py
"""
TUI (Text User Interface) do sistema de estoque usando Rich.

Interface interativa baseada em menus para operações do sistema:
- Carregamento de arquivos de entrada e saída
- Visualização de dados do banco
- Relatórios
- Operações administrativas
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

from rich.console import Console
from rich.panel import Panel  
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.layout import Layout
from rich.text import Text
from rich.align import Align

from estoque.config import DB_PATH, DEFAULTS
from estoque.infra.migrations import apply_migrations
from estoque.infra.views import create_views
from estoque.infra.db import connect
from estoque.usecases.registrar_entrada import run_entrada_lote
from estoque.usecases.registrar_saida import run_saida_lote
from estoque.usecases.verificar_estoque import run_verificar
from estoque.usecases.relatorios import (
    relatorio_alerta_ruptura,
    relatorio_produtos_a_vencer,
    relatorio_mais_consumidos,
    relatorio_reposicao,
)


class EstoqueTUI:
    """Text User Interface para o sistema de estoque."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.console = Console()
        self.db_path = db_path
        
    def run(self) -> None:
        """Inicia a interface principal."""
        self.show_banner()
        
        while True:
            try:
                choice = self.show_main_menu()
                if choice == "1":
                    self.menu_movimentacao()
                elif choice == "2":
                    self.menu_banco_dados()
                elif choice == "3":
                    self.menu_relatorios()
                elif choice == "4":
                    self.menu_sistema()
                elif choice == "0":
                    self.console.print("\n[green]Saindo do sistema...[/green]")
                    break
                else:
                    self.console.print("[red]Opção inválida![/red]")
            except KeyboardInterrupt:
                self.console.print("\n[red]Saindo...[/red]")
                break
            except Exception as e:
                self.console.print(f"[red]Erro: {e}[/red]")
    
    def show_banner(self) -> None:
        """Exibe banner do sistema."""
        banner = Panel.fit(
            "[bold blue]SISTEMA DE ESTOQUE CLÍNICA[/bold blue]\n"
            "[cyan]Interface Terminal Interativa (TUI)[/cyan]",
            border_style="blue"
        )
        self.console.print("\n")
        self.console.print(Align.center(banner))
        self.console.print("\n")
    
    def show_main_menu(self) -> str:
        """Exibe menu principal e retorna escolha do usuário."""
        menu = Panel(
            "[bold]MENU PRINCIPAL[/bold]\n\n"
            "[yellow]1.[/yellow] Movimentação (Entrada/Saída)\n"
            "[yellow]2.[/yellow] Banco de Dados\n"
            "[yellow]3.[/yellow] Relatórios\n"
            "[yellow]4.[/yellow] Sistema\n"
            "[yellow]0.[/yellow] Sair\n",
            title="Opções",
            border_style="green"
        )
        self.console.print(menu)
        return Prompt.ask("Escolha uma opção", choices=["0", "1", "2", "3", "4"])
    
    def menu_movimentacao(self) -> None:
        """Menu de movimentação."""
        while True:
            menu = Panel(
                "[bold]MOVIMENTAÇÃO[/bold]\n\n"
                "[yellow]1.[/yellow] Carregar Entradas (XLSX)\n"
                "[yellow]2.[/yellow] Carregar Saídas (XLSX)\n"
                "[yellow]3.[/yellow] Entrada Manual\n"
                "[yellow]4.[/yellow] Saída Manual\n"
                "[yellow]0.[/yellow] Voltar\n",
                title="Movimentação",
                border_style="cyan"
            )
            self.console.print(menu)
            choice = Prompt.ask("Escolha uma opção", choices=["0", "1", "2", "3", "4"])
            
            if choice == "0":
                break
            elif choice == "1":
                self.carregar_entradas()
            elif choice == "2":
                self.carregar_saidas()
            elif choice == "3":
                self.entrada_manual()
            elif choice == "4":
                self.saida_manual()
    
    def menu_banco_dados(self) -> None:
        """Menu de banco de dados."""
        while True:
            menu = Panel(
                "[bold]BANCO DE DADOS[/bold]\n\n"
                "[yellow]1.[/yellow] Ver Produtos\n"
                "[yellow]2.[/yellow] Ver Entradas\n"
                "[yellow]3.[/yellow] Ver Saídas\n"
                "[yellow]4.[/yellow] Ver Estoque Atual\n"
                "[yellow]5.[/yellow] Ver Lotes\n"
                "[yellow]0.[/yellow] Voltar\n",
                title="Banco de Dados",
                border_style="magenta"
            )
            self.console.print(menu)
            choice = Prompt.ask("Escolha uma opção", choices=["0", "1", "2", "3", "4", "5"])
            
            if choice == "0":
                break
            elif choice == "1":
                self.mostrar_produtos()
            elif choice == "2":
                self.mostrar_entradas()
            elif choice == "3":
                self.mostrar_saidas()
            elif choice == "4":
                self.mostrar_estoque_atual()
            elif choice == "5":
                self.mostrar_lotes()
    
    def menu_relatorios(self) -> None:
        """Menu de relatórios."""
        while True:
            menu = Panel(
                "[bold]RELATÓRIOS[/bold]\n\n"
                "[yellow]1.[/yellow] Relatório de Ruptura\n"
                "[yellow]2.[/yellow] Produtos a Vencer\n"
                "[yellow]3.[/yellow] Top Consumo\n"
                "[yellow]4.[/yellow] Relatório de Reposição\n"
                "[yellow]0.[/yellow] Voltar\n",
                title="Relatórios",
                border_style="red"
            )
            self.console.print(menu)
            choice = Prompt.ask("Escolha uma opção", choices=["0", "1", "2", "3", "4"])
            
            if choice == "0":
                break
            elif choice == "1":
                self.relatorio_ruptura()
            elif choice == "2":
                self.relatorio_vencimentos()
            elif choice == "3":
                self.relatorio_top_consumo()
            elif choice == "4":
                self.relatorio_reposicao()
    
    def menu_sistema(self) -> None:
        """Menu de sistema."""
        while True:
            menu = Panel(
                "[bold]SISTEMA[/bold]\n\n"
                "[yellow]1.[/yellow] Aplicar Migrações\n"
                "[yellow]2.[/yellow] Verificar Estoque\n"
                "[yellow]3.[/yellow] Configurar Parâmetros\n"
                "[yellow]0.[/yellow] Voltar\n",
                title="Sistema",
                border_style="yellow"
            )
            self.console.print(menu)
            choice = Prompt.ask("Escolha uma opção", choices=["0", "1", "2", "3"])
            
            if choice == "0":
                break
            elif choice == "1":
                self.aplicar_migracoes()
            elif choice == "2":
                self.verificar_estoque()
            elif choice == "3":
                self.configurar_parametros()
    
    def carregar_entradas(self) -> None:
        """Carrega entradas de arquivo XLSX."""
        arquivo = Prompt.ask("Caminho do arquivo XLSX de entradas")
        
        if not os.path.exists(arquivo):
            self.console.print(f"[red]Arquivo não encontrado: {arquivo}[/red]")
            return
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console
            ) as progress:
                task = progress.add_task("Carregando entradas...", total=100)
                progress.update(task, advance=20)
                
                resultado = run_entrada_lote(arquivo, self.db_path)
                progress.update(task, advance=80)
                
                self.console.print(f"\n[green]✓ Entradas carregadas com sucesso![/green]")
                self.console.print(f"Arquivo: {resultado['arquivo']}")
                self.console.print(f"Linhas inseridas: {resultado['linhas_inseridas']}")
                
        except Exception as e:
            self.console.print(f"[red]Erro ao carregar entradas: {e}[/red]")
    
    def carregar_saidas(self) -> None:
        """Carrega saídas de arquivo XLSX."""
        arquivo = Prompt.ask("Caminho do arquivo XLSX de saídas")
        
        if not os.path.exists(arquivo):
            self.console.print(f"[red]Arquivo não encontrado: {arquivo}[/red]")
            return
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(), 
                TaskProgressColumn(),
                console=self.console
            ) as progress:
                task = progress.add_task("Carregando saídas...", total=100)
                progress.update(task, advance=20)
                
                resultado = run_saida_lote(arquivo, self.db_path)
                progress.update(task, advance=80)
                
                self.console.print(f"\n[green]✓ Saídas carregadas com sucesso![/green]")
                self.console.print(f"Arquivo: {resultado['arquivo']}")
                self.console.print(f"Linhas inseridas: {resultado['linhas_inseridas']}")
                
        except Exception as e:
            self.console.print(f"[red]Erro ao carregar saídas: {e}[/red]")
    
    def entrada_manual(self) -> None:
        """Entrada manual via prompts."""
        self.console.print("[bold]Entrada Manual[/bold]")
        from estoque.usecases.registrar_entrada import run_entrada_unica
        try:
            resultado = run_entrada_unica(self.db_path)
            self.console.print("[green]✓ Entrada registrada com sucesso![/green]")
        except Exception as e:
            self.console.print(f"[red]Erro ao registrar entrada: {e}[/red]")
    
    def saida_manual(self) -> None:
        """Saída manual via prompts."""
        self.console.print("[bold]Saída Manual[/bold]")
        from estoque.usecases.registrar_saida import run_saida_unica
        try:
            resultado = run_saida_unica(self.db_path)
            self.console.print("[green]✓ Saída registrada com sucesso![/green]")
        except Exception as e:
            self.console.print(f"[red]Erro ao registrar saída: {e}[/red]")
    
    def mostrar_tabela_db(self, titulo: str, query: str, colunas: List[str], limite: int = 20) -> None:
        """Mostra dados do banco em formato de tabela."""
        try:
            with connect(self.db_path) as c:
                rows = c.execute(query).fetchmany(limite)
            
            if not rows:
                self.console.print(f"[yellow]Nenhum dado encontrado em {titulo}[/yellow]")
                return
            
            table = Table(title=titulo, show_header=True, header_style="bold magenta")
            
            for coluna in colunas:
                table.add_column(coluna, style="cyan")
            
            for row in rows:
                table.add_row(*[str(cell) if cell is not None else "" for cell in row])
            
            self.console.print(table)
            
            if len(rows) == limite:
                self.console.print(f"[yellow]Mostrando apenas {limite} registros...[/yellow]")
                
        except Exception as e:
            self.console.print(f"[red]Erro ao consultar {titulo}: {e}[/red]")
    
    def mostrar_produtos(self) -> None:
        """Mostra produtos cadastrados."""
        self.mostrar_tabela_db(
            "Produtos Cadastrados",
            "SELECT codigo, nome, categoria, lote_min, quantidade_minima FROM produto ORDER BY codigo",
            ["Código", "Nome", "Categoria", "Lote Min", "Qtd Min"]
        )
    
    def mostrar_entradas(self) -> None:
        """Mostra entradas registradas."""
        self.mostrar_tabela_db(
            "Entradas Recentes",
            "SELECT data_entrada, codigo, quantidade_raw, lote, representante FROM entrada ORDER BY id DESC",
            ["Data", "Código", "Quantidade", "Lote", "Representante"]
        )
    
    def mostrar_saidas(self) -> None:
        """Mostra saídas registradas."""
        self.mostrar_tabela_db(
            "Saídas Recentes", 
            "SELECT data_saida, codigo, quantidade_raw, lote, paciente FROM saida ORDER BY id DESC",
            ["Data", "Código", "Quantidade", "Lote", "Paciente"]
        )
    
    def mostrar_estoque_atual(self) -> None:
        """Mostra estoque atual consolidado."""
        self.mostrar_tabela_db(
            "Estoque Atual",
            "SELECT codigo, estoque_total_apres, unidade_apresentacao, estoque_total_unid, unidade_unidade FROM vw_estoque_consolidado ORDER BY codigo",
            ["Código", "Estoque Apres", "Un. Apres", "Estoque Unid", "Un. Unid"]
        )
    
    def mostrar_lotes(self) -> None:
        """Mostra lotes detalhados."""
        self.mostrar_tabela_db(
            "Lotes Detalhados",
            "SELECT codigo, lote, qtd_apres_num, qtd_apres_un, data_entrada, data_validade FROM vw_lotes_detalhe ORDER BY codigo, lote",
            ["Código", "Lote", "Qtd Num", "Unidade", "Data Entrada", "Data Validade"]
        )
    
    def aplicar_migracoes(self) -> None:
        """Aplica migrações do banco."""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                progress.add_task("Aplicando migrações...", total=None)
                apply_migrations(self.db_path)
                create_views(self.db_path)
            
            self.console.print("[green]✓ Migrações aplicadas com sucesso![/green]")
        except Exception as e:
            self.console.print(f"[red]Erro ao aplicar migrações: {e}[/red]")
    
    def verificar_estoque(self) -> None:
        """Executa verificação completa do estoque."""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                progress.add_task("Verificando estoque...", total=None)
                resultado = run_verificar(self.db_path)
            
            self.console.print("[green]✓ Verificação concluída![/green]")
            self.console.print(f"Produtos processados: {len(resultado.get('produtos', []))}")
            
        except Exception as e:
            self.console.print(f"[red]Erro na verificação: {e}[/red]")
    
    def configurar_parametros(self) -> None:
        """Configura parâmetros do sistema."""
        self.console.print("[bold]Configuração de Parâmetros[/bold]")
        # Implementar configuração de parâmetros se necessário
        self.console.print("[yellow]Funcionalidade em desenvolvimento...[/yellow]")
    
    def relatorio_ruptura(self) -> None:
        """Gera relatório de ruptura."""
        horizonte = Prompt.ask("Horizonte em dias", default="7")
        try:
            horizonte_int = int(horizonte)
            resultado = relatorio_alerta_ruptura(horizonte_dias=horizonte_int, db_path=self.db_path)
            self.console.print(f"[green]✓ Relatório de ruptura gerado![/green]")
            self.console.print(f"Produtos em risco: {len(resultado.get('produtos', []))}")
        except Exception as e:
            self.console.print(f"[red]Erro no relatório: {e}[/red]")
    
    def relatorio_vencimentos(self) -> None:
        """Gera relatório de vencimentos."""
        janela = Prompt.ask("Janela em dias", default="60")
        try:
            janela_int = int(janela)
            resultado = relatorio_produtos_a_vencer(janela_dias=janela_int, db_path=self.db_path)
            self.console.print(f"[green]✓ Relatório de vencimentos gerado![/green]")
            self.console.print(f"Produtos próximos ao vencimento: {len(resultado.get('produtos', []))}")
        except Exception as e:
            self.console.print(f"[red]Erro no relatório: {e}[/red]")
    
    def relatorio_top_consumo(self) -> None:
        """Gera relatório de top consumo."""
        inicio = Prompt.ask("Início (YYYY-MM)", default="2025-01")
        fim = Prompt.ask("Fim (YYYY-MM)", default="2025-06")
        n = Prompt.ask("Top N produtos", default="10")
        try:
            n_int = int(n)
            resultado = relatorio_mais_consumidos(inicio_ano_mes=inicio, fim_ano_mes=fim, top_n=n_int, db_path=self.db_path)
            self.console.print(f"[green]✓ Relatório de top consumo gerado![/green]")
            self.console.print(f"Top {n_int} produtos identificados")
        except Exception as e:
            self.console.print(f"[red]Erro no relatório: {e}[/red]")
    
    def relatorio_reposicao(self) -> None:
        """Gera relatório de reposição."""
        try:
            resultado = relatorio_reposicao(db_path=self.db_path)
            self.console.print(f"[green]✓ Relatório de reposição gerado![/green]")
            self.console.print(f"Produtos analisados: {len(resultado.get('produtos', []))}")
        except Exception as e:
            self.console.print(f"[red]Erro no relatório: {e}[/red]")


def main_tui():
    """Ponto de entrada principal da TUI."""
    tui = EstoqueTUI()
    tui.run()


if __name__ == "__main__":
    main_tui()