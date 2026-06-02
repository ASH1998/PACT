@echo off
setlocal enabledelayedexpansion
rem PACT PreToolUse hook launcher (native Windows / cmd.exe).
rem
rem hooks.json points at ".../scripts/run_hook" with no extension. On native
rem Windows, Claude Code runs hook commands through cmd.exe, which resolves the
rem extensionless path to THIS file via PATHEXT (.CMD). On POSIX / Git Bash the
rem sibling extensionless `run_hook` shell script runs instead. Keep the two in
rem sync.
rem
rem Like run_hook, pick the interpreter that can sign PACT envelopes (needs
rem PyNaCl) and pipe stdin (the hook event JSON) straight through to pact_hook.py.

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%..\.."
set "HOOK=%SCRIPT_DIR%pact_hook.py"

set "PY="
set "FALLBACK="
for %%P in (
  "%REPO_ROOT%\.venv\Scripts\python.exe"
  "%REPO_ROOT%\backend\.venv\Scripts\python.exe"
) do (
  if exist "%%~P" (
    if not defined FALLBACK set "FALLBACK=%%~P"
    if not defined PY (
      "%%~P" -c "import nacl" >nul 2>&1 <nul
      if !errorlevel! equ 0 set "PY=%%~P"
    )
  )
)

rem No PyNaCl-capable venv found: use the first venv that exists, else whatever
rem python is on PATH. pact_hook.py self-bootstraps into a PyNaCl-capable venv if
rem the chosen interpreter still lacks it.
if not defined PY if defined FALLBACK set "PY=%FALLBACK%"
if not defined PY set "PY=python"

"%PY%" "%HOOK%"
exit /b %errorlevel%
