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
from typing import Optional, List

import typer

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
    typer.echo(json.dumps(obj, ensure_ascii=False, indent=2))


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
    _print_json(out)


# -----------------------
# comandos de verificação
# -----------------------

@app.command("verificar")
def cmd_verificar(db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite")):
    """
    Executa o cálculo completo: rebuild de demanda, métricas, SS/ROP e sugestões.
    Saída em JSON.
    """
    res = run_verificar(db_path=db_path)
    _print_json(res)


# -----------------------
# comandos de movimentação
# -----------------------

@app.command("entrada-unica")
def cmd_entrada_unica(db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite")):
    """Registra uma entrada única via prompts no terminal."""
    rec = run_entrada_unica(db_path=db_path)
    _print_json(rec)


@app.command("entrada-lotes")
def cmd_entrada_lotes(
    path: str = typer.Argument(..., help="Caminho do XLSX de ENTRADAS"),
    db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite"),
):
    """Registra entradas em lote a partir de um XLSX."""
    info = run_entrada_lote(path, db_path=db_path)
    _print_json(info)


@app.command("saida-unica")
def cmd_saida_unica(db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite")):
    """Registra uma saída única via prompts no terminal."""
    rec = run_saida_unica(db_path=db_path)
    _print_json(rec)


@app.command("saida-lotes")
def cmd_saida_lotes(
    path: str = typer.Argument(..., help="Caminho do XLSX de SAÍDAS"),
    db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite"),
):
    """Registra saídas em lote a partir de um XLSX."""
    info = run_saida_lote(path, db_path=db_path)
    _print_json(info)

rel_app = typer.Typer(help="Relatórios de estoque")
app.add_typer(rel_app, name="rel")

@rel_app.command("ruptura")
def rel_ruptura(
    horizonte_dias: int = typer.Option(7, help="Dias de cobertura máxima para alerta"),
    db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite"),
):
    res = relatorio_alerta_ruptura(horizonte_dias=horizonte_dias, db_path=db_path)
    _print_json(res)

@rel_app.command("vencimentos")
def rel_vencimentos(
    janela_dias: int = typer.Option(60, help="Dias até o vencimento"),
    detalhar_por_lote: bool = typer.Option(True, help="True=detalhe por lote; False=agregado por produto"),
    db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite"),
):
    res = relatorio_produtos_a_vencer(janela_dias=janela_dias, detalhar_por_lote=detalhar_por_lote, db_path=db_path)
    _print_json(res)

@rel_app.command("top-consumo")
def rel_top_consumo(
    inicio_ano_mes: str = typer.Option(..., help="YYYY-MM (início)"),
    fim_ano_mes: str = typer.Option(..., help="YYYY-MM (fim)"),
    top_n: int = typer.Option(20, help="Top N produtos"),
    db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite"),
):
    res = relatorio_mais_consumidos(inicio_ano_mes=inicio_ano_mes, fim_ano_mes=fim_ano_mes, top_n=top_n, db_path=db_path)
    _print_json(res)

@rel_app.command("reposicao")
def rel_reposicao_cmd(
    db_path: str = typer.Option(DB_PATH, "--db", help="Caminho do SQLite"),
):
    res = relatorio_reposicao(db_path=db_path)
    _print_json(res)
    
# Entry point opcional:
def main():
    app()


if __name__ == "__main__":
    main()
