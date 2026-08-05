@echo off
setlocal EnableExtensions
set "UV_EXE="
if defined UV_EXE if exist "%UV_EXE%" goto run
if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV_EXE=%USERPROFILE%\.local\bin\uv.exe"
if not defined UV_EXE for %%I in (uv.exe) do if not "%%~$PATH:I"=="" set "UV_EXE=%%~$PATH:I"
if not defined UV_EXE (
  >&2 echo uv.exe not found. Install uv or add %%USERPROFILE%%\.local\bin to PATH.
  exit /b 9009
)
:run
"%UV_EXE%" run --project "%~dp0.." python %*
