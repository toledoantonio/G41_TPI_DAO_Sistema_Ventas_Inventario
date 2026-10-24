@echo off
setlocal
pushd "%~dp0"

rem No usa PowerShell ni cambia la politica de ejecucion del equipo.
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" goto runtime_local
where py.exe >nul 2>&1
if not errorlevel 1 goto lanzador_python
where python.exe >nul 2>&1
if not errorlevel 1 goto python_path

echo No se encontro Python. Instale Python 3.11 o superior con Tkinter.
set "APP_EXIT=1"
goto finalizar

:runtime_local
"%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m backend.main %*
set "APP_EXIT=%ERRORLEVEL%"
goto finalizar

:lanzador_python
py -3 -m backend.main %*
set "APP_EXIT=%ERRORLEVEL%"
goto finalizar

:python_path
python -m backend.main %*
set "APP_EXIT=%ERRORLEVEL%"

:finalizar
popd
if not "%APP_EXIT%"=="0" (
    echo La aplicacion termino con codigo %APP_EXIT%.
    pause
)
exit /b %APP_EXIT%
