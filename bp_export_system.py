#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
血壓資料匯出系統
將DBF檔案中的血壓資料轉換為符合規格的XML格式
"""

import dbf
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
from typing import List, Dict, Tuple
import logging

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BloodPressureExporter:
    """血壓資料匯出器"""
    
    def __init__(self, data_path: str = "data"):
        self.data_path = data_path
        self.co01m_path = os.path.join(data_path, "CO01M.DBF")
        self.co18h_path = os.path.join(data_path, "CO18H.DBF")
        
    def read_patient_list(self, patient_ids: List[str]) -> Dict[str, Dict]:
        """
        讀取病患基本資料
        
        Args:
            patient_ids: 病歷號列表
            
        Returns:
            病患資料字典
        """
        patients = {}
        
        try:
            with dbf.Table(self.co01m_path) as table:
                for record in table:
                    # 將病歷號格式化為7位數
                    patient_id = str(record.kcstmr).strip().zfill(7)
                    
                    if patient_id in patient_ids:
                        patients[patient_id] = {
                            'id': patient_id,
                            'name': record.mname,
                            'sex': record.msex,
                            'birth_date': record.mbirthdt,
                            'person_id': record.mpersonid
                        }
                        
        except Exception as e:
            logging.error(f"讀取病患資料時發生錯誤: {e}")
            
        return patients
    
    def get_blood_pressure_data(self, patient_id: str) -> List[Dict]:
        """
        從CO18H取得病患血壓資料
        
        Args:
            patient_id: 病歷號
            
        Returns:
            血壓記錄列表
        """
        bp_records = []
        
        try:
            with dbf.Table(self.co18h_path) as table:
                for record in table:
                    if str(record.kcstmr).strip().zfill(7) == patient_id:
                        # 檢查是否為血壓相關項目
                        item_desc = str(record.hdscp).strip()
                        
                        if any(bp in item_desc for bp in ['收縮壓', '舒張壓', '血壓', 'BP']):
                            bp_records.append({
                                'date': record.hdate,
                                'time': record.htime,
                                'item': record.hitem,
                                'description': item_desc,
                                'value': record.hval,
                                'unit': self._extract_unit(record),
                                'reference': record.hrule
                            })
                            
        except Exception as e:
            logging.error(f"讀取血壓資料時發生錯誤: {e}")
            
        return bp_records
    
    def _extract_unit(self, record) -> str:
        """從記錄中提取單位"""
        # 血壓通常使用 mmHg
        if '血壓' in str(record.hdscp) or 'BP' in str(record.hdscp).upper():
            return 'mmHg'
        return ''
    
    def group_bp_measurements(self, bp_records: List[Dict]) -> List[Tuple[Dict, Dict]]:
        """
        將收縮壓和舒張壓配對
        
        Returns:
            配對的血壓測量列表 [(收縮壓, 舒張壓), ...]
        """
        # 按日期時間排序
        sorted_records = sorted(bp_records, key=lambda x: (x['date'], x['time']))
        
        # 配對邏輯：相同日期時間的收縮壓和舒張壓
        paired_measurements = []
        i = 0
        
        while i < len(sorted_records):
            current = sorted_records[i]
            
            # 尋找配對
            if '收縮壓' in current['description']:
                # 尋找相同時間的舒張壓
                for j in range(i+1, min(i+3, len(sorted_records))):
                    next_record = sorted_records[j]
                    if (next_record['date'] == current['date'] and 
                        '舒張壓' in next_record['description']):
                        paired_measurements.append((current, next_record))
                        i = j + 1
                        break
                else:
                    i += 1
            else:
                i += 1
                
        return paired_measurements
    
    def create_xml(self, patient_data: Dict, bp_measurements: List[Tuple[Dict, Dict]]) -> ET.Element:
        """
        建立XML結構
        """
        root = ET.Element('patient')
        
        for (systolic, diastolic) in bp_measurements:
            hdata = ET.SubElement(root, 'hdata')
            
            # 基本資料段 - 參考 totfa.xml 的實際格式
            ET.SubElement(hdata, 'h1').text = '1'  # 報告類別
            ET.SubElement(hdata, 'h2').text = '3522013684'  # 醫事機構代碼
            ET.SubElement(hdata, 'h3').text = '11'  # 醫事類別
            ET.SubElement(hdata, 'h4').text = systolic['date'][:5]  # 費用年月
            ET.SubElement(hdata, 'h5').text = f"{systolic['date']}{systolic['time']}"  # 健保卡過卡日期時間
            ET.SubElement(hdata, 'h6').text = '01'  # 案件分類
            ET.SubElement(hdata, 'h7').text = '0023'  # 特定治療項目代號(血壓)
            ET.SubElement(hdata, 'h8').text = '1'  # 就醫序號
            
            # 只有在有身分證號時才加入 h9
            if patient_data.get('person_id'):
                ET.SubElement(hdata, 'h9').text = patient_data['person_id']
            
            ET.SubElement(hdata, 'h10').text = patient_data['id']  # 病歷號
            ET.SubElement(hdata, 'h11').text = systolic['date']  # 就醫日期
            ET.SubElement(hdata, 'h12').text = systolic['date']  # 治療結束日期
            ET.SubElement(hdata, 'h15').text = 'Y00006'  # 主診斷碼（高血壓相關）
            ET.SubElement(hdata, 'h16').text = f"{systolic['date']}{systolic['time']}"  # 處方調劑日期時間
            ET.SubElement(hdata, 'h17').text = 'N125074991'  # 醫師身分證號
            ET.SubElement(hdata, 'h19').text = f"{systolic['date']}{systolic['time'][:4]}"  # 檢驗日期時間
            ET.SubElement(hdata, 'h20').text = f"{systolic['date']}{systolic['time'][:4]}"  # 報告日期時間
            
            # 只有在有姓名時才加入 h22
            if patient_data.get('name'):
                ET.SubElement(hdata, 'h22').text = patient_data['name']
            
            ET.SubElement(hdata, 'h26').text = '0'  # 轉檢FLAG
            
            # 收縮壓資料段
            rdata1 = ET.SubElement(hdata, 'rdata')
            ET.SubElement(rdata1, 'r1').text = '1'
            ET.SubElement(rdata1, 'r2').text = '收縮壓'
            ET.SubElement(rdata1, 'r3').text = '生理量測血壓(OBPM)'
            ET.SubElement(rdata1, 'r4').text = systolic['value']
            ET.SubElement(rdata1, 'r5').text = 'mmHg'
            ET.SubElement(rdata1, 'r6-1').text = '90-130'
            ET.SubElement(rdata1, 'r9').text = '3522013684'
            ET.SubElement(rdata1, 'r10').text = f"{systolic['date']}{systolic['time'][:4]}"
            
            # 舒張壓資料段
            rdata2 = ET.SubElement(hdata, 'rdata')
            ET.SubElement(rdata2, 'r1').text = '2'
            ET.SubElement(rdata2, 'r2').text = '舒張壓'
            ET.SubElement(rdata2, 'r3').text = '生理量測血壓(OBPM)'
            ET.SubElement(rdata2, 'r4').text = diastolic['value']
            ET.SubElement(rdata2, 'r5').text = 'mmHg'
            ET.SubElement(rdata2, 'r6-1').text = '60-80'
            ET.SubElement(rdata2, 'r9').text = '3522013684'
            ET.SubElement(rdata2, 'r10').text = f"{diastolic['date']}{diastolic['time'][:4]}"
            
        return root
    
    def export_to_xml(self, patient_ids: List[str], output_file: str = "bp_export.xml"):
        """
        主要匯出函數
        
        Args:
            patient_ids: 病歷號列表
            output_file: 輸出檔案名稱
        """
        # 格式化病歷號為7位數
        formatted_ids = [pid.strip().zfill(7) for pid in patient_ids]
        
        # 讀取病患資料
        patients = self.read_patient_list(formatted_ids)
        
        if not patients:
            logging.warning("找不到指定的病患資料")
            return
        
        # 建立根元素
        root = ET.Element('patient')
        
        # 處理每個病患
        for patient_id, patient_data in patients.items():
            logging.info(f"處理病患: {patient_id} - {patient_data.get('name', '')}")
            
            # 取得血壓資料
            bp_records = self.get_blood_pressure_data(patient_id)
            
            if bp_records:
                # 配對血壓測量
                paired_bps = self.group_bp_measurements(bp_records)
                
                # 為每個病患建立XML結構
                patient_root = self.create_xml(patient_data, paired_bps)
                
                # 將病患資料加入根元素
                for hdata in patient_root:
                    root.append(hdata)
        
        # 格式化並儲存XML
        self._save_formatted_xml(root, output_file)
        logging.info(f"匯出完成: {output_file}")
    
    def _save_formatted_xml(self, root: ET.Element, filename: str):
        """儲存格式化的XML檔案"""
        # 轉換為字串並格式化
        xml_str = ET.tostring(root, encoding='big5')
        dom = minidom.parseString(xml_str)
        
        # 寫入檔案，加上XML宣告
        with open(filename, 'w', encoding='big5') as f:
            f.write('<?xml version="1.0" encoding="Big5"?>\n')
            # 移除minidom加入的額外空行
            pretty_xml = dom.documentElement.toprettyxml(indent='')
            f.write(pretty_xml)


# 使用範例
if __name__ == "__main__":
    # 建立匯出器實例
    exporter = BloodPressureExporter(data_path="data")
    
    # 方式1: 直接提供病歷號列表
    patient_list = ["0480319", "0860718"]  # 範例病歷號
    exporter.export_to_xml(patient_list, "blood_pressure_export.xml")
    
    # 方式2: 從檔案讀取病歷號列表
    # with open("patient_list.txt", "r") as f:
    #     patient_list = [line.strip() for line in f if line.strip()]
    # exporter.export_to_xml(patient_list, "blood_pressure_export.xml")