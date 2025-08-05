@echo off
REM 血壓資料匯出快速執行腳本

REM 檢查虛擬環境是否存在
if not exist "venv" (
    echo 虛擬環境不存在，正在建立...
    call setup_venv.bat
)

REM 啟動虛擬環境
call venv\Scripts\activate.bat

REM 執行匯出程式
echo.
echo 血壓資料匯出系統
echo ==================
echo.

REM 如果有參數傳入，直接使用參數
if "%~1"=="" (
    echo 使用方式：
    echo   run_export.bat -p 病歷號1 病歷號2 ...
    echo   run_export.bat -f 病歷號檔案.txt
    echo.
    echo 範例：
    echo   run_export.bat -p 0480319 0860718
    echo   run_export.bat -f patient_list_example.txt
    echo.
    pause
) else (
    python bp_export_cli.py %*
    echo.
    pause
)