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
pip install -r requirements.txt pyinstaller
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
