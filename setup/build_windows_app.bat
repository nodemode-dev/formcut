@echo off
setlocal
where python >nul 2>nul || (echo python is required & exit /b 1)
where npm >nul 2>nul || (echo npm is required & exit /b 1)
where cargo >nul 2>nul || (echo Rust is required: https://rustup.rs & exit /b 1)
cargo tauri --version >nul 2>nul || cargo install tauri-cli --version ^^2 --locked

echo == Building the frontend ==
pushd frontend
if not exist node_modules call npm install
call npm run build
popd

echo == Building the engine ==
pushd backend
python -m venv .venv-package
call .venv-package\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt pyinstaller "maturin==1.15.0"
rem The Rust kernels with the GPU executor (DX12) every speed reading used, as the macOS and Linux builds have them.
if exist native-dist rmdir /s /q native-dist
python -m maturin build --release --manifest-path native\Cargo.toml --features gpu --out native-dist
if errorlevel 1 exit /b 1
for %%w in (native-dist\*.whl) do pip install --force-reinstall --no-deps "%%w"
python -c "import formcut_native; print('kernels load:', formcut_native.__file__)"
if errorlevel 1 (echo formcut's Rust kernels were built but do not load; stopping. & exit /b 1)
python -c "import formcut_native, sys; sys.exit(0 if hasattr(formcut_native, 'GpuFrame') else 1)"
if errorlevel 1 (echo formcut's Rust kernels were built without the GPU executor; stopping. & exit /b 1)
python prepare_cv.py
if errorlevel 1 exit /b 1
python freeze.py --onefile
if errorlevel 1 exit /b 1
dist\formcut-engine.exe --selfcheck
call deactivate
popd

echo == Placing the sidecar ==
for /f "tokens=2" %%i in ('rustc -Vv ^| findstr /b host:') do set TRIPLE=%%i
if not exist src-tauri\binaries mkdir src-tauri\binaries
copy /y backend\dist\formcut-engine.exe "src-tauri\binaries\formcut-engine-%TRIPLE%.exe"

echo == Generating icons ==
cargo tauri icon src-tauri\icons\icon.png

echo == Building the app bundle ==
cargo tauri build --bundles nsis

echo Done. Installer under src-tauri\target\release\bundle\nsis\
endlocal
