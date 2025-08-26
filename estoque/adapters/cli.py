# estoque/adapters/cli.py
"""
CLI do sistema de estoque (Typer).

Comandos principais:
- migrate                 -> aplica migrações e cria views
- params set/get/show     -> gerencia parâmetros globais
- verificar               -> executa o caso de uso de verificação do estoque
- entrada-unica           -> registra uma entrada via prompts no terminal
- entrada-lotes <xlsx>    -> registra entradas em lote a partir de um XLSX
- saida-unica             -> registra uma saída via prompts no terminal
- saida-lotes <xlsx>      -> registra saídas em lote a partir de um XLSX
"""

from __future__ import annotations

import json
from typing import Optional, List, Dict, Any
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from estoque.config import DB_PATH, DEFAULTS
from estoque.infra.migrations import apply_migrations
from estoque.infra.views import create_views
from estoque.infra.repositories import ParamsRepo
from estoque.usecases.verificar_estoque import run_verificar
from estoque.usecases.registrar_entrada import run_entrada_unica, run_entrada_lote
from estoque.usecases.registrar_saida import run_saida_unica, run_saida_lote
from estoque.usecases.relatorios import (
    relatorio_alerta_ruptura,
    relatorio_produtos_a_vencer,
    relatorio_mais_consumidos,
    relatorio_reposicao,
)


app = typer.Typer(help="Estoque Clínica — CLI")
console = Console()


# -----------------------
# TUI command
# -----------------------

@app.command("tui")
def cmd_tui():
    """Inicia a interface terminal interativa (TUI)."""
    from estoque.adapters.tui import main_tui
    main_tui()


# -----------------------
# util
# -----------------------

def _print_json(obj) -> None:
    """Fallback para impressão de JSON quando necessário."""
    typer.echo(json.dumps(obj, ensure_ascii=False, indent=2))


def _display_table(data: Dict[str, Any] | List[Dict[str, Any]], title: str = "Resultado") -> None:
    """Exibe os dados em tabelas formatadas usando Rich."""
    if not data:
        console.print(Panel("Nenhum dado encontrado", title=title, border_style="yellow"))
        return

    # Lista de itens - formato mais comum nos relatórios
    if isinstance(data, list) and data and isinstance(data[0], dict):
        table = Table(title=title, box=box.ROUNDED)
        
        # Determinar colunas com base nas chaves do primeiro item
        columns = data[0].keys()
        for column in columns:
            # Estilizar colunas específicas
            if column.lower() in ['quantidade', 'estoque', 'demanda', 'valor']:
                table.add_column(column, justify="right")
            elif column.lower() in ['data', 'vencimento']:
                table.add_column(column, justify="center")
            else:
                table.add_column(column)
        
        # Adicionar linhas
        for row in data:
            values = []
            for col in columns:
                val = row.get(col, "")
                # Formatar valores específicos
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    values.append(f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                elif isinstance(val, datetime):
                    values.append(val.strftime("%d/%m/%Y"))
                else:
                    values.append(str(val))
            table.add_row(*values)
        
        console.print(table)
        return

    # Caso específico para o relatório de verificação
    if isinstance(data, dict) and "produtos" in data and isinstance(data["produtos"], list):
        # Tabela para produtos
        produtos_table = Table(title="Produtos no Estoque", box=box.ROUNDED)
        
        if data["produtos"]:
            # Colunas para produtos
            produtos_cols = ["cod", "nome", "estoque", "demanda_dia", "ss", "rop", "status"]
            for col in produtos_cols:
                if col in ["estoque", "demanda_dia", "ss", "rop"]:
                    produtos_table.add_column(col, justify="right")
                else:
                    produtos_table.add_column(col)
            
            for prod in data["produtos"]:
                valores = []
                for col in produtos_cols:
                    val = prod.get(col, "")
                    if col == "status":
                        # Colorir status
                        status_val = str(val)
                        if "crítico" in status_val.lower():
                            valores.append(f"[bold red]{status_val}[/]")
                        elif "alerta" in status_val.lower():
                            valores.append(f"[bold yellow]{status_val}[/]")
                        elif "normal" in status_val.lower():
                            valores.append(f"[bold green]{status_val}[/]")
                        else:
                            valores.append(status_val)
                    elif isinstance(val, (int, float)) and not isinstance(val, bool):
                        valores.append(f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    else:
                        valores.append(str(val))
                produtos_table.add_row(*valores)
            
            console.print(produtos_table)
        
        # Informações adicionais
        if "sugestoes" in data and data["sugestoes"]:
            sugestoes_table = Table(title="Sugestões de Compra", box=box.ROUNDED)
            sugestoes_cols = ["cod", "nome", "qtd_sugerida", "motivo"]
            for col in sugestoes_cols:
                if col == "qtd_sugerida":
                    sugestoes_table.add_column(col, justify="right")
                else:
                    sugestoes_table.add_column(col)
            
            for sug in data["sugestoes"]:
                valores = []
                for col in sugestoes_cols:
                    val = sug.get(col, "")
                    if col == "qtd_sugerida" and isinstance(val, (int, float)):
                        valores.append(f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    else:
                        valores.append(str(val))
                sugestoes_table.add_row(*valores)
            
            console.print(sugestoes_table)
        
        # Metadados
        if "timestamp" in data:
            console.print(f"[dim]Verificação executada em: {data['timestamp']}[/dim]")
        
        return

    # Dados de entrada/saída única
    if isinstance(data, dict) and any(k in data for k in ["entrada_id", "saida_id"]):
        movimento_tipo = "Entrada" if "entrada_id" in data else "Saída"
        table = Table(title=f"{movimento_tipo} Registrada", box=box.ROUNDED)
        
        # Colunas base
        table.add_column("Campo")
        table.add_column("Valor")
        
        # Linhas específicas para movimentos
        for chave, valor in data.items():
            if chave in ["entrada_id", "saida_id"]:
                table.add_row("ID", str(valor))
            elif chave == "data":
                table.add_row("Data", valor)
            elif chave == "produto":
                table.add_row("Produto", f"{valor.get('cod', '')} - {valor.get('nome', '')}")
            elif chave == "quantidade":
                table.add_row("Quantidade", f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            elif chave == "vencimento" and valor:
                table.add_row("Vencimento", valor)
            elif chave == "lote" and valor:
                table.add_row("Lote", valor)
            elif chave == "notas" and valor:
                table.add_row("Notas", valor)
        
        console.print(table)
        return
    
    # Operações em lote
    if isinstance(data, dict) and "registros" in data and "total" in data:
        titulo = "Registros em Lote"
        if "tipo" in data:
            titulo = f"{data['tipo']} em Lote"
        
        panel_content = [
            f"Total de registros: {data['total']}",
            f"Processados com sucesso: {data.get('sucessos', 0)}",
        ]
        
        if "erros" in data and data["erros"]:
            panel_content.append(f"Erros: {len(data['erros'])}")
            
        console.print(Panel("\n".join(panel_content), title=titulo))
        
        if "erros" in data and data["erros"]:
            erro_table = Table(title="Erros Encontrados")
            erro_table.add_column("Linha")
            erro_table.add_column("Erro")
            
            for erro in data["erros"]:
                erro_table.add_row(str(erro.get("linha", "?")), erro.get("mensagem", "Erro desconhecido"))
            
            console.print(erro_table)
        
        return
    
    # Parâmetros
    if isinstance(data, dict) and "_defaults" in data:
        params_table = Table(title="Parâmetros do Sistema")
        params_table.add_column("Parâmetro")
        params_table.add_column("Valor Atual")
        params_table.add_column("Valor Padrão")
        
        for param in ["nivel_servico", "mu_t_dias_uteis", "sigma_t_dias_uteis"]:
            if param in data:
                params_table.add_row(
                    param, 
                    str(data[param]), 
                    str(data["_defaults"][param])
                )
        
        console.print(params_table)
        console.print(f"[dim]Banco de dados: {data.get('_db', 'N/A')}[/dim]")
        return
    
    # Fallback para outros formatos de dados - usar JSON
    _print_json(data)


# -----------------------
# comandos de infra
# -----------------------

@app.command("migrate")
def cmd_migrate(db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite")):
    """Aplica migrações e recria as views auxiliares."""
    apply_migrations(db_path)
    create_views(db_path)
    typer.echo(f">> Migrações aplicadas e views criadas em: {db_path}")


params_app = typer.Typer(help="Gerenciar parâmetros globais (nível de serviço e lead time).")
app.add_typer(params_app, name="params")


@params_app.command("set")
def cmd_params_set(
    nivel_servico: Optional[float] = typer.Option(None, help="Ex.: 0.95"),
    mu_t_dias_uteis: Optional[float] = typer.Option(None, help="Lead time médio em dias úteis (ex.: 6)"),
    sigma_t_dias_uteis: Optional[float] = typer.Option(None, help="Desvio do lead time em dias úteis (ex.: 1)"),
    db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite"),
):
    """Define parâmetros globais (apenas os informados são alterados)."""
    repo = ParamsRepo(db_path)
    items: List[tuple[str, str]] = []
    if nivel_servico is not None:
        items.append(("nivel_servico", str(nivel_servico)))
    if mu_t_dias_uteis is not None:
        items.append(("mu_t_dias_uteis", str(mu_t_dias_uteis)))
    if sigma_t_dias_uteis is not None:
        items.append(("sigma_t_dias_uteis", str(sigma_t_dias_uteis)))
    if not items:
        typer.echo("Nada a alterar. Informe pelo menos um parâmetro.")
        raise typer.Exit(code=1)
    repo.set_many(items)
    typer.echo(">> Parâmetros atualizados.")


@params_app.command("get")
def cmd_params_get(
    chave: str = typer.Argument(..., help="Ex.: nivel_servico | mu_t_dias_uteis | sigma_t_dias_uteis"),
    db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite"),
):
    """Mostra um parâmetro específico."""
    repo = ParamsRepo(db_path)
    val = repo.get(chave)
    if val is None:
        typer.echo("(None)")
    else:
        typer.echo(val)


@params_app.command("show")
def cmd_params_show(
    db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite"),
):
    """Exibe os parâmetros efetivos (com fallback para defaults)."""
    repo = ParamsRepo(db_path)
    out = {
        "nivel_servico": repo.get("nivel_servico", str(DEFAULTS.nivel_servico)),
        "mu_t_dias_uteis": repo.get("mu_t_dias_uteis", str(DEFAULTS.mu_t_dias_uteis)),
        "sigma_t_dias_uteis": repo.get("sigma_t_dias_uteis", str(DEFAULTS.sigma_t_dias_uteis)),
        "_defaults": {
            "nivel_servico": DEFAULTS.nivel_servico,
            "mu_t_dias_uteis": DEFAULTS.mu_t_dias_uteis,
            "sigma_t_dias_uteis": DEFAULTS.sigma_t_dias_uteis,
        },
        "_db": db_path,
    }
    _display_table(out, title="Parâmetros do Sistema")


# -----------------------
# comandos de verificação
# -----------------------

@app.command("verificar")
def cmd_verificar(db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite")):
    """
    Executa o cálculo completo: rebuild de demanda, métricas, SS/ROP e sugestões.
    Saída em tabelas formatadas.
    """
    res = run_verificar(db_path=db_path)
    _display_table(res, title="Verificação de Estoque")


# -----------------------
# comandos de movimentação
# -----------------------

@app.command("entrada-unica")
def cmd_entrada_unica(db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite")):
    """Registra uma entrada única via prompts no terminal."""
    rec = run_entrada_unica(db_path=db_path)
    _display_table(rec, title="Entrada Registrada")


@app.command("entrada-lotes")
def cmd_entrada_lotes(
    path: str = typer.Argument(..., help="Caminho do XLSX de ENTRADAS"),
    db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite"),
):
    """Registra entradas em lote a partir de um XLSX."""
    info = run_entrada_lote(path, db_path=db_path)
    _display_table(info, title="Processamento de Entradas em Lote")


@app.command("saida-unica")
def cmd_saida_unica(db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite")):
    """Registra uma saída única via prompts no terminal."""
    rec = run_saida_unica(db_path=db_path)
    _display_table(rec, title="Saída Registrada")


@app.command("saida-lotes")
def cmd_saida_lotes(
    path: str = typer.Argument(..., help="Caminho do XLSX de SAÍDAS"),
    db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite"),
):
    """Registra saídas em lote a partir de um XLSX."""
    info = run_saida_lote(path, db_path=db_path)
    _display_table(info, title="Processamento de Saídas em Lote")


rel_app = typer.Typer(help="Relatórios de estoque")
app.add_typer(rel_app, name="rel")

@rel_app.command("ruptura")
def rel_ruptura(
    horizonte_dias: int = typer.Option(7, help="Dias de cobertura máxima para alerta"),
    db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite"),
):
    """Gera relatório de produtos com risco de ruptura."""
    res = relatorio_alerta_ruptura(horizonte_dias=horizonte_dias, db_path=db_path)
    _display_table(res, title=f"Alerta de Ruptura (Horizonte: {horizonte_dias} dias)")

@rel_app.command("vencimentos")
def rel_vencimentos(
    janela_dias: int = typer.Option(60, help="Dias até o vencimento"),
    detalhar_por_lote: bool = typer.Option(True, help="True=detalhe por lote; False=agregado por produto"),
    db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite"),
):
    """Gera relatório de produtos próximos ao vencimento."""
    res = relatorio_produtos_a_vencer(janela_dias=janela_dias, detalhar_por_lote=detalhar_por_lote, db_path=db_path)
    _display_table(res, title=f"Produtos a Vencer (Próximos {janela_dias} dias)")

@rel_app.command("top-consumo")
def rel_top_consumo(
    inicio_ano_mes: str = typer.Option(..., help="YYYY-MM (início)"),
    fim_ano_mes: str = typer.Option(..., help="YYYY-MM (fim)"),
    top_n: int = typer.Option(20, help="Top N produtos"),
    db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite"),
):
    """Gera relatório dos produtos mais consumidos no período."""
    res = relatorio_mais_consumidos(inicio_ano_mes=inicio_ano_mes, fim_ano_mes=fim_ano_mes, top_n=top_n, db_path=db_path)
    _display_table(res, title=f"Top {top_n} Produtos Mais Consumidos ({inicio_ano_mes} a {fim_ano_mes})")

@rel_app.command("reposicao")
def rel_reposicao_cmd(
    db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite"),
):
    """Gera relatório de sugestões de reposição de estoque."""
    res = relatorio_reposicao(db_path=db_path)
    _display_table(res, title="Relatório de Reposição de Estoque")
    
@app.command("tui")
def cmd_tui():
    """
    Inicia a Interface Terminal (TUI) interativa do sistema.
    
    A TUI fornece uma interface de menu amigável para navegar e executar
    todas as funções do sistema sem precisar lembrar comandos específicos.
    """
    try:
        from estoque.adapters.mainframe_tui import main as tui_main
        typer.echo("🚀 Iniciando Interface Terminal...")
        tui_main()
    except ImportError:
        typer.echo("❌ TUI não disponível. Instale: pip install textual")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        typer.echo("\n👋 Saindo do TUI...")
        raise typer.Exit(0)


# Entry point opcional:
def main():
    app()


if __name__ == "__main__":
    main()
