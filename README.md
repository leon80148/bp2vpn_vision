# 血壓資料匯出系統

這個系統可以從 DBF 檔案中讀取病患的血壓資料，並轉換成符合健保署規範的 XML 格式。

## 系統需求

- Python 3.6 或以上版本
- 必要套件：`dbf`

## 安裝

### Windows 環境

1. 執行安裝腳本：
```cmd
setup_venv.bat
```

2. 或手動安裝：
```cmd
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
```

### Mac/Linux 環境

1. 建立虛擬環境：
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 檔案說明

- `bp_export_system.py` - 核心匯出邏輯
- `bp_export_cli.py` - 命令列介面
- `patient_list_example.txt` - 病歷號列表範例
- `data/` - DBF 資料檔案目錄
  - `CO01M.DBF` - 病患基本資料
  - `CO18H.DBF` - 檢驗歷史資料（包含血壓）

## 使用方式

### 1. 匯出單一病患
```bash
python bp_export_cli.py -p 0480319
```

### 2. 匯出多個病患
```bash
python bp_export_cli.py -p 0480319 0860718 1234567
```

### 3. 從檔案讀取病歷號列表
```bash
python bp_export_cli.py -f patient_list_example.txt
```

### 4. 指定輸出檔案名稱
```bash
python bp_export_cli.py -p 0480319 -o my_blood_pressure.xml
```

### 5. 顯示詳細執行訊息
```bash
python bp_export_cli.py -p 0480319 -v
```

## 病歷號格式

- 系統會自動將病歷號格式化為 7 位數
- 不足 7 位會在左側補零
- 例如：`480319` 會被轉換為 `0480319`

## 輸出格式

輸出的 XML 檔案符合健保署規範，包含：
- 病患基本資訊
- 血壓測量記錄（收縮壓/舒張壓配對）
- 測量時間、數值、單位、參考值範圍

## 注意事項

1. DBF 檔案必須放在 `data/` 目錄下
2. 輸出檔案編碼為 Big5（符合健保署要求）
3. 系統會自動配對同時間測量的收縮壓和舒張壓
4. 如果找不到病患資料或血壓記錄，會在日誌中顯示警告

## 故障排除

### 問題：找不到 DBF 檔案
確認 `data/` 目錄下有 `CO01M.DBF` 和 `CO18H.DBF` 檔案。

### 問題：編碼錯誤
確認 DBF 檔案的編碼格式，本系統預設處理 Big5 編碼。

### 問題：找不到病患資料
檢查病歷號是否正確，系統會自動格式化為 7 位數。

## 程式化使用

您也可以在自己的 Python 程式中使用：

```python
from bp_export_system import BloodPressureExporter

# 建立匯出器
exporter = BloodPressureExporter(data_path="data")

# 匯出病患血壓資料
patient_list = ["0480319", "0860718"]
exporter.export_to_xml(patient_list, "output.xml")
```