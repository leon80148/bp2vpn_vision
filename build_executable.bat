@echo off
echo ===================================
echo   BP2VPN Vision 執行檔建置工具
echo ===================================
echo.

REM 檢查是否有虛擬環境
if not exist "venv\Scripts\activate.bat" (
    echo 建立虛擬環境...
    python -m venv venv
    if errorlevel 1 (
        echo 錯誤：無法建立虛擬環境，請確認已安裝Python
        pause
        exit /b 1
    )
)

REM 啟動虛擬環境
echo 啟動虛擬環境...
call venv\Scripts\activate.bat

REM 安裝依賴套件
echo 安裝依賴套件...
pip install dbf PySide6
if errorlevel 1 (
    echo 錯誤：安裝依賴套件失敗
    pause
    exit /b 1
)

REM 安裝 PyInstaller
echo 安裝 PyInstaller...
pip install pyinstaller
if errorlevel 1 (
    echo 錯誤：安裝 PyInstaller 失敗
    pause
    exit /b 1
)

REM 建立執行檔
echo.
echo 開始建立執行檔...
pyinstaller --onefile --windowed --name="BP2VPN_Vision" bp2vpn_gui_ultra.py

REM 檢查建置結果
if exist "dist\BP2VPN_Vision.exe" (
    echo.
    echo ✅ 建置成功！
    echo 執行檔位於: dist\BP2VPN_Vision.exe
    echo.
    echo 建議動作:
    echo 1. 將 dist\BP2VPN_Vision.exe 複製到目標電腦
    echo 2. 在相同目錄建立 data\ 資料夾
    echo 3. 將 DBF 檔案放入 data\ 資料夾
    echo.
) else (
    echo ❌ 建置失敗，請檢查錯誤訊息
)

echo 按任意鍵結束...
pause