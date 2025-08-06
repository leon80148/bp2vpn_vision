@echo off
echo ===================================
echo     建立 BP2VPN Vision 安裝包
echo ===================================
echo.

REM 檢查是否已建置執行檔
if not exist "dist\BP2VPN_Vision.exe" (
    echo 錯誤：找不到執行檔，請先執行 build_executable.bat
    pause
    exit /b 1
)

REM 建立發布目錄
if exist "release" rmdir /s /q release
mkdir release
mkdir release\BP2VPN_Vision

REM 複製執行檔和文件
echo 複製執行檔...
copy dist\BP2VPN_Vision.exe release\BP2VPN_Vision\
copy README.md release\BP2VPN_Vision\
copy XML_RULE.md release\BP2VPN_Vision\
copy CLAUDE.md release\BP2VPN_Vision\
copy 操作說明.md release\BP2VPN_Vision\

REM 建立資料夾結構
echo 建立資料夾結構...
mkdir release\BP2VPN_Vision\data
echo. > release\BP2VPN_Vision\data\請將DBF檔案放在此資料夾.txt

REM 複製圖片資料夾
if exist "img" (
    echo 複製圖片資料夾...
    xcopy img release\BP2VPN_Vision\img\ /E /I /Q
)

REM 建立使用說明
echo 建立使用說明...
(
echo 血壓紀錄批次檔生成器_for展望系統 v2.0 Ultra 使用說明
echo =====================================
echo.
echo 安裝步驟：
echo 1. 將整個資料夾複製到目標電腦
echo 2. 將您的 DBF 檔案放入 data\ 資料夾中
echo 3. 雙擊 BP2VPN_Vision.exe 啟動程式
echo.
echo 使用步驟：
echo 1. 填入10碼醫事機構代碼
echo 2. 選擇資料範圍（今年/三個月內/半年內/一年內）
echo 3. 點選「選擇資料夾」，選擇包含 DBF 檔案的資料夾
echo 4. 程式會自動載入病患名單和血壓資料
echo 5. 勾選要匯出的病患（有血壓資料的會自動勾選）
echo 6. 可手動修改血壓值
echo 7. 點選「匯出XML」產生符合健保署規範的檔案
echo.
echo 系統需求：
echo - Windows 10/11
echo - 無需安裝 Python 或其他軟體
echo.
echo 技術支援：
echo - 請參閱 README.md 和 XML_RULE.md
echo - 或聯繫系統開發者
) > release\BP2VPN_Vision\使用說明.txt

REM 建立啟動檔
echo 建立啟動檔...
(
echo @echo off
echo cd /d "%%~dp0"
echo start BP2VPN_Vision.exe
) > release\BP2VPN_Vision\啟動程式.bat

REM 打包成壓縮檔
if exist "C:\Program Files\7-Zip\7z.exe" (
    echo 建立壓縮檔...
    "C:\Program Files\7-Zip\7z.exe" a -tzip "release\BP2VPN_Vision_v2.0_Ultra.zip" "release\BP2VPN_Vision\*"
    echo.
    echo ✅ 安裝包建立完成！
    echo 📁 資料夾版本: release\BP2VPN_Vision\
    echo 📦 壓縮檔版本: release\BP2VPN_Vision_v2.0_Ultra.zip
) else (
    echo.
    echo ✅ 安裝包建立完成！
    echo 📁 位置: release\BP2VPN_Vision\
    echo 💡 建議: 安裝 7-Zip 以自動建立壓縮檔
)

echo.
echo 發布準備就緒！可以將 release\ 內容分享給使用者
pause