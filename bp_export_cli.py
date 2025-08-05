#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
血壓資料匯出系統 - 命令列介面
提供簡單的介面來匯出血壓資料
"""

import argparse
import sys
from bp_export_system import BloodPressureExporter
import logging

def main():
    parser = argparse.ArgumentParser(
        description='血壓資料匯出系統 - 將DBF檔案中的血壓資料轉換為XML格式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  # 匯出單一病患
  python bp_export_cli.py -p 0480319
  
  # 匯出多個病患
  python bp_export_cli.py -p 0480319 0860718
  
  # 從檔案讀取病歷號列表
  python bp_export_cli.py -f patient_list.txt
  
  # 指定輸出檔案名稱
  python bp_export_cli.py -p 0480319 -o my_bp_export.xml
  
  # 指定資料目錄
  python bp_export_cli.py -p 0480319 -d /path/to/data
        """
    )
    
    parser.add_argument('-p', '--patients', nargs='+', 
                       help='病歷號列表（可輸入多個，以空格分隔）')
    parser.add_argument('-f', '--file', 
                       help='包含病歷號列表的文字檔案（每行一個病歷號）')
    parser.add_argument('-o', '--output', default='blood_pressure_export.xml',
                       help='輸出XML檔案名稱（預設: blood_pressure_export.xml）')
    parser.add_argument('-d', '--data-path', default='data',
                       help='DBF檔案所在目錄（預設: data）')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='顯示詳細執行訊息')
    
    args = parser.parse_args()
    
    # 設定日誌等級
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, 
                          format='%(asctime)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, 
                          format='%(message)s')
    
    # 收集病歷號
    patient_ids = []
    
    if args.patients:
        patient_ids.extend(args.patients)
    
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                file_patients = [line.strip() for line in f if line.strip()]
                patient_ids.extend(file_patients)
                logging.info(f"從檔案 {args.file} 讀取了 {len(file_patients)} 個病歷號")
        except FileNotFoundError:
            logging.error(f"找不到檔案: {args.file}")
            sys.exit(1)
        except Exception as e:
            logging.error(f"讀取檔案時發生錯誤: {e}")
            sys.exit(1)
    
    if not patient_ids:
        logging.error("請提供病歷號（使用 -p 參數）或病歷號檔案（使用 -f 參數）")
        parser.print_help()
        sys.exit(1)
    
    # 移除重複的病歷號
    patient_ids = list(set(patient_ids))
    logging.info(f"準備處理 {len(patient_ids)} 位病患的血壓資料")
    
    try:
        # 建立匯出器並執行匯出
        exporter = BloodPressureExporter(data_path=args.data_path)
        exporter.export_to_xml(patient_ids, args.output)
        
        logging.info(f"\n✅ 匯出成功！")
        logging.info(f"📄 輸出檔案: {args.output}")
        logging.info(f"📊 處理病患數: {len(patient_ids)}")
        
    except Exception as e:
        logging.error(f"\n❌ 匯出失敗: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()