@echo off
REM 建立虛擬環境並安裝依賴

echo 建立 Python 虛擬環境...
python -m venv venv

echo 啟動虛擬環境...
call venv\Scripts\activate.bat

echo 安裝依賴套件...
pip install -r requirements.txt

echo.
echo 安裝完成！
echo 請使用以下命令啟動虛擬環境：
echo venv\Scripts\activate.bat
pause