@echo off
setlocal
rem Open the four consoles with automatic board labels. F10 connects each port.
set "TASK_TERMINAL=%~dp0release\str8nf-v0.2.0\tools\nf_console.py"
set "TASK_PYTHONW=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
set "TASK_SERIAL_PACKAGES=%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\site-packages"
if not exist "%TASK_PYTHONW%" set "TASK_PYTHONW=%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe"
if not exist "%TASK_PYTHONW%" (
    echo Python was not found. Install Python with Tk and pyserial, then try again.
    pause
    exit /b 1
)
if not exist "%TASK_TERMINAL%" (
    echo Serial terminal not found: %TASK_TERMINAL%
    pause
    exit /b 1
)
if exist "%TASK_SERIAL_PACKAGES%\serial\__init__.py" (
    if defined PYTHONPATH (
        set "PYTHONPATH=%TASK_SERIAL_PACKAGES%;%PYTHONPATH%"
    ) else (
        set "PYTHONPATH=%TASK_SERIAL_PACKAGES%"
    )
)
for %%P in (COM3 COM4 COM5 COM8) do start "" "%TASK_PYTHONW%" "%TASK_TERMINAL%" --port %%P --baud 115200
exit /b 0
