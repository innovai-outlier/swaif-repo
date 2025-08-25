import json
from pathlib import Path
from typer.testing import CliRunner

from estoque.adapters.cli import app

runner = CliRunner()

def test_cli_migrate_and_params_show(tmp_path: Path):
    db_path = tmp_path / "estoque_test.sqlite"
    # migrate
    result = runner.invoke(app, ["migrate", "--db", str(db_path)])
    assert result.exit_code == 0, result.output

    # params show (deve sair JSON com defaults se nada foi setado)
    result = runner.invoke(app, ["params", "show", "--db", str(db_path)])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert "nivel_servico" in data
    assert "mu_t_dias_uteis" in data
    assert "sigma_t_dias_uteis" in data

def test_cli_params_set_and_get(tmp_path: Path):
    db_path = tmp_path / "estoque_test.sqlite"
    # migrate
    result = runner.invoke(app, ["migrate", "--db", str(db_path)])
    assert result.exit_code == 0

    # set params
    result = runner.invoke(
        app,
        [
            "params", "set",
            "--db", str(db_path),
            "--nivel-servico", "0.97",
            "--mu-t-dias-uteis", "7",
            "--sigma-t-dias-uteis", "1.5",
        ],
    )
    assert result.exit_code == 0, result.output

    # get one
    result = runner.invoke(app, ["params", "get", "nivel_servico", "--db", str(db_path)])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.97"
