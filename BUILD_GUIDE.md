# 血壓紀錄批次檔生成器_for展望系統 建置與分發指南

## 簡單建置方式（推薦）

### 1. 一鍵建置執行檔
```bash
# 執行建置腳本
build_executable.bat
```
這會自動：
- 建立虛擬環境
- 安裝所需套件
- 使用 PyInstaller 建立單一執行檔
- 產生 `dist/BP2VPN_Vision.exe`

### 2. 建立分發包
```bash
# 建立完整的安裝包
create_installer.bat
```
這會產生：
- 完整的資料夾結構
- 使用說明文件
- 可選的壓縮檔案

## 建置需求

### 開發環境
- Python 3.8+
- Windows 10/11
- 足夠的磁碟空間 (建議 500MB)

### 所需套件
程式會自動安裝：
- PySide6 (GUI框架)
- dbf (DBF檔案處理)
- PyInstaller (執行檔建置)

## 分發選項

### 選項 1：單一執行檔
**適用**: 技術人員、少量部署
```
dist/
└── BP2VPN_Vision.exe    # 約 50-80MB
```

**優點**:
- 單一檔案，容易分享
- 不需安裝任何軟體
- 適合email或USB傳遞

**缺點**:
- 檔案較大
- 啟動速度稍慢

### 選項 2：完整安裝包
**適用**: 正式部署、多人使用
```
release/
└── BP2VPN_Vision/
    ├── BP2VPN_Vision.exe
    ├── data/                    # 資料夾
    ├── 使用說明.txt
    ├── 啟動程式.bat
    ├── README.md
    ├── XML_RULE.md
    └── CLAUDE.md
```

**優點**:
- 包含完整說明
- 預建資料夾結構
- 專業外觀

**缺點**:
- 多個檔案
- 需要保持資料夾完整

### 選項 3：壓縮安裝包
**適用**: 網路分發、版本控制
```
release/
└── BP2VPN_Vision_v2.0_Ultra.zip    # 約 25-40MB
```

## 手動建置步驟

如果自動腳本失效，可使用手動方式：

### 1. 準備環境
```bash
# 建立虛擬環境
python -m venv venv

# 啟動虛擬環境
venv\Scripts\activate.bat

# 安裝套件
pip install -r requirements.txt
pip install pyinstaller
```

### 2. 建立執行檔
```bash
# 使用自訂規格檔
pyinstaller BP2VPN_Vision.spec

# 或使用基本命令
pyinstaller --onefile --windowed --name="BP2VPN_Vision" bp2vpn_gui_ultra.py
```

### 3. 測試執行檔
```bash
# 測試執行檔
dist\BP2VPN_Vision.exe
```

## 高級建置選項

### 包含圖示檔案
```bash
pyinstaller --onefile --windowed --icon=icon.ico --name="BP2VPN_Vision" bp2vpn_gui_ultra.py
```

### 包含額外資源
```bash
pyinstaller --onefile --windowed --add-data="XML_RULE.md;." bp2vpn_gui_ultra.py
```

### 最佳化檔案大小
```bash
pyinstaller --onefile --windowed --strip --upx-dir=C:\upx bp2vpn_gui_ultra.py
```

## 疑難排解

### 常見問題

#### 1. 建置失敗：找不到模組
**解決方式**:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 2. 執行檔無法啟動
**檢查項目**:
- 確認目標電腦是64位元Windows
- 檢查防毒軟體是否阻擋
- 在命令提示字元中執行查看錯誤訊息

#### 3. DBF檔案讀取失敗
**確認事項**:
- data/資料夾存在
- DBF檔案編碼正確
- 檔案權限設定正確

#### 4. 執行檔太大
**優化方法**:
```bash
# 排除不必要的模組
pyinstaller --exclude-module tkinter --exclude-module matplotlib bp2vpn_gui_ultra.py
```

### 偵錯技巧

#### 1. 保留控制台輸出
```bash
pyinstaller --onefile --console bp2vpn_gui_ultra.py
```

#### 2. 產生詳細log
```bash
pyinstaller --log-level=DEBUG bp2vpn_gui_ultra.py
```

## 部署指南

### 給終端使用者

#### 簡單部署 (推薦)
1. 下載 `BP2VPN_Vision_v2.0_Ultra.zip`
2. 解壓縮到任意資料夾
3. 將DBF檔案放入 `data/` 資料夾
4. 雙擊 `BP2VPN_Vision.exe` 或 `啟動程式.bat`

#### 企業部署
1. 將整個 `BP2VPN_Vision/` 資料夾複製到共用磁碟
2. 建立桌面捷徑指向 `BP2VPN_Vision.exe`
3. 設定資料夾權限確保可讀寫

### 系統需求
- **作業系統**: Windows 10/11 (64位元)
- **記憶體**: 至少 4GB RAM
- **儲存空間**: 500MB 可用空間
- **其他**: 不需安裝Python或其他軟體

## 版本管理

### 版本號規則
- **主版本.次版本.修正版.建置號**
- 例：`2.0.0.0`

### 更新 version_info.txt
建置前記得更新版本資訊：
```
filevers=(2, 0, 1, 0),    # 新版本號
prodvers=(2, 0, 1, 0),    # 產品版本號
FileVersion=u'2.0.1.0',   # 檔案版本
ProductVersion=u'2.0.1.0' # 產品版本
```

## 自動化建置 (進階)

### GitHub Actions
可設定自動建置，每次推送時自動產生執行檔：

```yaml
# .github/workflows/build.yml
name: Build Executable
on: [push, pull_request]
jobs:
  build:
    runs-on: windows-latest
    steps:
    - uses: actions/checkout@v2
    - uses: actions/setup-python@v2
      with:
        python-version: 3.9
    - name: Install dependencies
      run: pip install -r requirements.txt pyinstaller
    - name: Build executable  
      run: pyinstaller BP2VPN_Vision.spec
    - name: Upload artifact
      uses: actions/upload-artifact@v2
      with:
        name: BP2VPN_Vision
        path: dist/
```

這樣可以確保每個版本都有對應的執行檔，方便分發給使用者。