@echo off
REM ====== CONFIG ======
REM Default Python executable
if "%PY%"=="" set PY=python

REM Virtual environment directory
if "%VENV%"=="" set VENV=.venv

REM Python executables in venv
set PIP=%VENV%\Scripts\pip.exe
set PYTHON=%VENV%\Scripts\python.exe
set PYTEST=%VENV%\Scripts\pytest.exe
set RUFF=%VENV%\Scripts\ruff.exe

REM Default database
if "%DB%"=="" set DB=estoque.db

REM ====== HELP ======
if "%1"=="help" (
    echo Alvos principais (Windows CMD):
    echo   build.bat venv           -^> cria venv local em %VENV%
    echo   build.bat install        -^> instala dependencias ^(app + dev^)
    echo   build.bat install-min    -^> instala dependencias minimas ^(sem dev^)
    echo   build.bat migrate        -^> aplica migracoes e cria views ^(DB=%DB%^)
    echo   build.bat verificar      -^> executa calculo completo ^(DB=%DB%^)
    echo   build.bat params-show    -^> exibe parametros globais ^(DB=%DB%^)
    echo   build.bat params-set NS=0.95 MU=6 ST=1 -^> grava parametros
    echo   build.bat entrada-lotes FILE=entradas.xlsx -^> entrada lotes ^(DB=%DB%^)
    echo   build.bat saida-lotes FILE=saidas.xlsx     -^> saida lotes ^(DB=%DB%^)
    echo   build.bat rel-ruptura H=3                  -^> relatorio ruptura ^(DB=%DB%^)
    echo   build.bat rel-vencimentos D=60             -^> relatorio vencimentos ^(DB=%DB%^)
    echo   build.bat rel-top INI=2025-01 FIM=2025-06 N=10 -^> top consumo ^(DB=%DB%^)
    echo   build.bat rel-reposicao                    -^> relatorio reposicao ^(DB=%DB%^)
    echo   build.bat test                             -^> pytest
    echo   build.bat lint                             -^> ruff check
    echo   build.bat doctor                           -^> lint + tests + lock-verify
    echo   build.bat ci                               -^> pipeline local completa
    echo   build.bat clean/distclean                  -^> limpeza
    goto :eof
)

REM ====== VENV / INSTALL ======
if "%1"=="venv" (
    if not exist %VENV% (
        echo Criando ambiente virtual...
        %PY% -m venv %VENV%
        %PIP% install --upgrade pip setuptools wheel
        echo Ambiente virtual criado em %VENV%
    ) else (
        echo Ambiente virtual ja existe em %VENV%
    )
    goto :eof
)

if "%1"=="install" (
    call %0 venv
    echo Instalando dependencias completas...
    %PIP% install -e .
    %PIP% install pandas openpyxl scipy typer tabulate
    %PIP% install pytest pytest-cov ruff
    echo Instalacao completa finalizada.
    goto :eof
)

if "%1"=="install-min" (
    call %0 venv
    echo Instalando dependencias minimas...
    %PIP% install -e .
    %PIP% install pandas openpyxl scipy typer tabulate
    echo Instalacao minima finalizada.
    goto :eof
)

REM ====== MIGRACAO / OPERACAO ======
if "%1"=="migrate" (
    %PYTHON% app.py migrate --db %DB%
    goto :eof
)

if "%1"=="verificar" (
    %PYTHON% app.py verificar --db %DB%
    goto :eof
)

if "%1"=="params-show" (
    %PYTHON% app.py params show --db %DB%
    goto :eof
)

if "%1"=="params-set" (
    if "%NS%"=="" if "%MU%"=="" if "%ST%"=="" (
        echo Uso: build.bat params-set NS=^<nivel_servico^> MU=^<mu_t^> ST=^<sigma_t^>
        echo Exemplo: set NS=0.95 ^&^& set MU=6 ^&^& set ST=1 ^&^& build.bat params-set
        exit /b 1
    )
    set CMD=%PYTHON% app.py params set --db %DB%
    if not "%NS%"=="" set CMD=%CMD% --nivel-servico %NS%
    if not "%MU%"=="" set CMD=%CMD% --mu-t-dias-uteis %MU%
    if not "%ST%"=="" set CMD=%CMD% --sigma-t-dias-uteis %ST%
    %CMD%
    goto :eof
)

REM ====== MOVIMENTACAO (LOTE) ======
if "%1"=="entrada-lotes" (
    if "%FILE%"=="" (
        echo Informe FILE=^<planilha.xlsx^>
        echo Exemplo: set FILE=entradas.xlsx ^&^& build.bat entrada-lotes
        exit /b 1
    )
    %PYTHON% app.py entrada-lotes "%FILE%" --db %DB%
    goto :eof
)

if "%1"=="saida-lotes" (
    if "%FILE%"=="" (
        echo Informe FILE=^<planilha.xlsx^>
        echo Exemplo: set FILE=saidas.xlsx ^&^& build.bat saida-lotes
        exit /b 1
    )
    %PYTHON% app.py saida-lotes "%FILE%" --db %DB%
    goto :eof
)

REM ====== RELATORIOS ======
if "%1"=="rel-ruptura" (
    if "%H%"=="" (
        echo Uso: build.bat rel-ruptura H=^<horizonte_dias^>
        echo Exemplo: set H=3 ^&^& build.bat rel-ruptura
        exit /b 1
    )
    %PYTHON% app.py rel ruptura --horizonte-dias %H% --db %DB%
    goto :eof
)

if "%1"=="rel-vencimentos" (
    if "%D%"=="" (
        echo Uso: build.bat rel-vencimentos D=^<janela_dias^>
        echo Exemplo: set D=60 ^&^& build.bat rel-vencimentos
        exit /b 1
    )
    set CMD=%PYTHON% app.py rel vencimentos --janela-dias %D%
    if "%DETALHE%"=="0" set CMD=%CMD% --no-detalhar-por-lote
    %CMD% --db %DB%
    goto :eof
)

if "%1"=="rel-top" (
    if "%INI%"=="" (
        echo Uso: build.bat rel-top INI=YYYY-MM FIM=YYYY-MM [N=20]
        echo Exemplo: set INI=2025-01 ^&^& set FIM=2025-06 ^&^& set N=10 ^&^& build.bat rel-top
        exit /b 1
    )
    if "%FIM%"=="" (
        echo Uso: build.bat rel-top INI=YYYY-MM FIM=YYYY-MM [N=20]
        echo Exemplo: set INI=2025-01 ^&^& set FIM=2025-06 ^&^& set N=10 ^&^& build.bat rel-top
        exit /b 1
    )
    set CMD=%PYTHON% app.py rel top-consumo --inicio-ano-mes %INI% --fim-ano-mes %FIM%
    if not "%N%"=="" set CMD=%CMD% --top-n %N%
    %CMD% --db %DB%
    goto :eof
)

if "%1"=="rel-reposicao" (
    %PYTHON% app.py rel reposicao --db %DB%
    goto :eof
)

REM ====== TESTES / LINT ======
if "%1"=="test" (
    %PYTEST% -q --maxfail=1 --disable-warnings --cov=estoque --cov-report=term-missing
    goto :eof
)

if "%1"=="lint" (
    %RUFF% check .
    goto :eof
)

REM ====== LOCK ======
if "%1"=="lock" (
    call %0 install
    echo ^>^> Gerando constraints.txt ...
    %PYTHON% -m pip freeze | findstr /v "^-e " > constraints.txt
    echo ^>^> constraints.txt atualizado.
    goto :eof
)

if "%1"=="relock" (
    call %0 distclean
    call %0 venv
    call %0 install
    call %0 lock
    echo ^>^> Relock concluido.
    goto :eof
)

if "%1"=="lock-verify" (
    call %0 distclean
    call %0 venv
    %PIP% install -r requirements.txt -c constraints.txt
    goto :eof
)

REM ====== HEALTHCHECK ======
if "%1"=="doctor" (
    call %0 lint
    if errorlevel 1 exit /b %errorlevel%
    call %0 test  
    if errorlevel 1 exit /b %errorlevel%
    call %0 lock-verify
    if errorlevel 1 exit /b %errorlevel%
    echo ^>^> Tudo certo: lint + tests + lock verificados.
    goto :eof
)

if "%1"=="ci" (
    call %0 install
    if errorlevel 1 exit /b %errorlevel%
    call %0 migrate
    if errorlevel 1 exit /b %errorlevel%
    call %0 doctor
    if errorlevel 1 exit /b %errorlevel%
    echo ^>^> Rodando relatorio de ruptura ^(horizonte=5^) como sanity-check...
    set H=5
    call %0 rel-ruptura
    goto :eof
)

REM ====== CLEAN ======
if "%1"=="clean" (
    echo Limpando arquivos de cache...
    for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
    if exist .pytest_cache rd /s /q .pytest_cache
    if exist .ruff_cache rd /s /q .ruff_cache
    if exist .mypy_cache rd /s /q .mypy_cache
    if exist build rd /s /q build
    if exist dist rd /s /q dist
    for %%i in (*.egg-info) do if exist "%%i" rd /s /q "%%i"
    echo Cache limpo.
    goto :eof
)

if "%1"=="distclean" (
    call %0 clean
    if exist %VENV% (
        echo Removendo ambiente virtual %VENV%...
        rd /s /q %VENV%
    )
    echo Limpeza completa finalizada.
    goto :eof
)

REM ====== DEFAULT ======
if "%1"=="" (
    call %0 help
    goto :eof
)

echo Comando desconhecido: %1
echo Use: build.bat help para ver os comandos disponiveis
exit /b 1