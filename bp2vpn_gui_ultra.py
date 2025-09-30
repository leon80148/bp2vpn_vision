#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BP2VPN Vision v2.0
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Set
import time
from collections import defaultdict
import zipfile

try:
    from PySide6.QtWidgets import (QApplication, QMessageBox, QMainWindow, QVBoxLayout, 
                                   QWidget, QPushButton, QLabel, QFileDialog, QTableWidget, 
                                   QTableWidgetItem, QHeaderView, QCheckBox, QHBoxLayout, 
                                   QLineEdit, QStatusBar, QProgressBar, QSpinBox, QComboBox,
                                   QDateEdit, QButtonGroup, QRadioButton)
    from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject, QDate
    from PySide6.QtGui import QFont, QColor, QBrush
except ImportError as e:
    print(f"錯誤: 無法匯入PySide6: {e}")
    print("請執行: pip install PySide6")
    sys.exit(1)

try:
    import dbf
except ImportError as e:
    print(f"錯誤: 無法匯入dbf模組: {e}")
    print("請執行: pip install dbf")
    sys.exit(1)


# ============================================================================
# 常數定義
# ============================================================================

class HealthInsuranceCode:
    """健保署規範代碼常數"""

    # 報告類別
    REPORT_TYPE = "1"

    # 醫事類別
    MEDICAL_CATEGORY = "11"  # 西醫

    # 案件分類
    CASE_TYPE = "01"  # 門診

    # 補卡註記
    CARD_REPLACEMENT = "1"

    # 診斷代碼
    DIAGNOSIS_CODE = "Y00006"  # 高血壓相關

    # 特定治療項目代號
    BP_ITEM_CODE = "0023"  # 血壓檢驗項目

    # 預設就醫序號
    DEFAULT_VISIT_SEQ = "Z000"

    # 轉檢FLAG
    TRANSFER_FLAG = "0"

    # 檢驗項目名稱
    BP_TEST_NAME = "血壓"
    BP_TEST_METHOD = "診間血壓監測(OBPM)"

    # 血壓測量項目序號
    SYSTOLIC_SEQ = "1"  # 收縮壓序號
    DIASTOLIC_SEQ = "2"  # 舒張壓序號

    # 血壓測量名稱
    SYSTOLIC_NAME = "收縮壓"
    DIASTOLIC_NAME = "舒張壓"

    # 血壓單位
    BP_UNIT = "mmHg"

    # 血壓參考範圍
    SYSTOLIC_REFERENCE = "90-130"
    DIASTOLIC_REFERENCE = "60-80"


class BloodPressureRange:
    """血壓數值合理範圍"""

    # 收縮壓範圍 (mmHg)
    SYSTOLIC_MIN = 50
    SYSTOLIC_MAX = 250

    # 舒張壓範圍 (mmHg)
    DIASTOLIC_MIN = 30
    DIASTOLIC_MAX = 150


# ============================================================================
# 輔助函式
# ============================================================================

def normalize_patient_id(patient_id: str) -> str:
    """
    統一格式化病歷號為7位數

    Args:
        patient_id: 原始病歷號

    Returns:
        格式化後的病歷號（7位數，左側補零）
    """
    return patient_id.strip().zfill(7)


def calculate_r10_time(hdate: str, htime: str, unified_second: int) -> str:
    """
    計算r10時間標籤（測量時間加一分鐘，秒數統一）

    Args:
        hdate: 測量日期（民國年格式 YYYMMDD）
        htime: 測量時間（HHMMSS）
        unified_second: 統一的秒數值

    Returns:
        r10時間字串（YYYMMDDHHMMSS）
    """
    try:
        if len(htime) >= 6:
            hour = int(htime[:2])
            minute = int(htime[2:4])

            # 加一分鐘
            minute += 1
            if minute >= 60:
                minute = 0
                hour += 1
                if hour >= 24:
                    hour = 0

            # 只有秒數使用統一值，其他保持原參數
            return f"{hdate}{hour:02d}{minute:02d}{unified_second:02d}"
        else:
            return hdate + htime
    except (ValueError, IndexError):
        return hdate + htime


class UltraBloodPressureLoader(QObject):
    """超級優化的血壓資料載入器"""
    progress = Signal(int, int)
    finished = Signal(dict)
    error_occurred = Signal(str)  # 新增錯誤信號
    
    def __init__(self, co18h_path: str, patient_ids: List[str], years_limit: float = None, start_date=None, end_date=None):
        super().__init__()
        self.co18h_path = co18h_path
        self.patient_set = {normalize_patient_id(pid) for pid in patient_ids}
        self.years_limit = years_limit
        self.start_date = start_date
        self.end_date = end_date
        
    def load(self):
        """優化的載入演算法"""
        try:
            # 計算日期限制
            today = datetime.now()
            
            if self.years_limit is not None:
                # 預設範圍模式
                if self.years_limit == 0.1:  # 今年
                    date_limit = datetime(today.year, 1, 1)  # 今年1月1日
                else:
                    days = int(self.years_limit * 365)
                    date_limit = today - timedelta(days=days)
                
                date_limit_tw = date_limit.year - 1911
                date_limit_str = f"{date_limit_tw:03d}{date_limit.month:02d}{date_limit.day:02d}"
                
                print(f"載入: {len(self.patient_set)} 位病患")
                print(f"今天: {today.strftime('%Y-%m-%d')} (民國{today.year-1911}年)")
                print(f"時間範圍參數: {self.years_limit}")
                if self.years_limit == 0.1:
                    print(f"使用今年模式 -> {date_limit.strftime('%Y-%m-%d')}")
                else:
                    days = int(self.years_limit * 365)
                    print(f"往前推{days}天 -> {date_limit.strftime('%Y-%m-%d')}")
                print(f"日期限制字串: {date_limit_str}")
                
                # 結束日期設為今天
                end_date_limit = today
                end_date_tw = end_date_limit.year - 1911
                end_date_str = f"{end_date_tw:03d}{end_date_limit.month:02d}{end_date_limit.day:02d}"
            else:
                # 自訂區間模式
                date_limit = datetime.combine(self.start_date, datetime.min.time())
                end_date_limit = datetime.combine(self.end_date, datetime.max.time())
                
                date_limit_tw = date_limit.year - 1911
                date_limit_str = f"{date_limit_tw:03d}{date_limit.month:02d}{date_limit.day:02d}"
                
                end_date_tw = end_date_limit.year - 1911
                end_date_str = f"{end_date_tw:03d}{end_date_limit.month:02d}{end_date_limit.day:02d}"
                
                print(f"載入: {len(self.patient_set)} 位病患")
                print(f"自訂日期區間: {self.start_date.strftime('%Y-%m-%d')} ~ {self.end_date.strftime('%Y-%m-%d')}")
                print(f"起始日期限制字串: {date_limit_str}")
                print(f"結束日期限制字串: {end_date_str}")
            
            # 使用字典快速儲存每個病患的最新血壓
            bp_data = {}
            patients_found = 0  # 已找到血壓記錄的病患數量
            target_patients = len(self.patient_set)
            
            for pid in self.patient_set:
                bp_data[pid] = {
                    'systolic': None,
                    'diastolic': None,
                    'date': None,
                    'time': None,
                    'hdate': None,  # 保存原始日期格式
                    'htime': None,  # 保存原始時間格式
                    'value': None,
                    'datetime_str': '',
                    'found': False  # 是否已找到該病患的血壓記錄
                }
            
            table = dbf.Table(self.co18h_path)
            table.open()
            
            processed = 0
            date_filtered = 0  # 通過日期篩選的記錄數
            bp_found = 0
            patient_matched = 0  # 病患匹配的記錄數
            matched = 0
            total_records = len(table)
            last_emit = time.time()
            batch_size = 1000  # 批次處理
            
            print(f"開始掃描 {total_records} 筆記錄，日期限制: {date_limit_str}...")
            
            # 記錄前幾筆的日期資料作為參考
            sample_dates = []
            
            for record in table:
                # 批次更新進度，減少UI更新頻率
                if processed % batch_size == 0 and time.time() - last_emit > 0.5:
                    self.progress.emit(processed, total_records)
                    last_emit = time.time()
                
                processed += 1
                
                try:
                    # 第一級篩選：日期範圍（最能快速排除大量記錄）
                    # 優化：先快速檢查日期格式，避免不必要的字串操作
                    try:
                        record_date = str(record.HDATE).strip()
                        
                        # 收集前10筆記錄的日期作為參考
                        if len(sample_dates) < 10:
                            sample_dates.append(record_date)
                        
                        if len(record_date) < 7:
                            continue
                        # 快速字串比較，避免複雜的日期解析
                        if record_date < date_limit_str:
                            continue
                        
                        # 自訂區間模式需要檢查結束日期
                        if self.years_limit is None and record_date > end_date_str:
                            continue
                    except:
                        continue
                    
                    date_filtered += 1
                    
                    # 第二級篩選：檢查HITEM（只處理血壓記錄）
                    hitem = str(record.HITEM).strip()
                    if hitem != 'BP':
                        continue
                    
                    bp_found += 1
                    
                    # 第三級篩選：檢查病歷號（只處理目標病患）
                    patient_id = normalize_patient_id(str(record.KCSTMR))
                    if patient_id not in self.patient_set:
                        continue
                        
                    patient_matched += 1
                    
                    # 解析血壓值
                    hval = str(record.HVAL).strip()
                    if '/' not in hval:
                        continue
                    
                    # 快速解析血壓值
                    try:
                        systolic_str, diastolic_str = hval.split('/', 1)
                        systolic = int(float(systolic_str))
                        diastolic = int(float(diastolic_str))

                        # 驗證血壓數值範圍
                        if not (BloodPressureRange.SYSTOLIC_MIN <= systolic <= BloodPressureRange.SYSTOLIC_MAX and
                                BloodPressureRange.DIASTOLIC_MIN <= diastolic <= BloodPressureRange.DIASTOLIC_MAX):
                            continue
                        
                        # 建立日期時間字串用於比較
                        time_str = str(record.HTIME).strip()
                        datetime_str = record_date + time_str
                        
                        # 只保留最新的記錄
                        patient_bp = bp_data[patient_id]
                        if not patient_bp['datetime_str'] or datetime_str > patient_bp['datetime_str']:
                            # 如果是第一次找到該病患的血壓記錄
                            if not patient_bp['found']:
                                patient_bp['found'] = True
                                patients_found += 1
                            
                            patient_bp['systolic'] = systolic
                            patient_bp['diastolic'] = diastolic
                            patient_bp['date'] = record_date
                            patient_bp['time'] = time_str
                            patient_bp['hdate'] = record_date  # 保存原始日期
                            patient_bp['htime'] = time_str  # 保存原始時間
                            patient_bp['value'] = hval
                            patient_bp['datetime_str'] = datetime_str
                            matched += 1
                        
                        # 優化：如果已經找到所有病患的最新記錄，可以提早結束
                        # （但通常我們還是要掃描完畢以確保真的是最新記錄）
                        
                    except (ValueError, IndexError):
                        continue
                        
                except Exception:
                    continue
            
            table.close()
            
            # 清理空資料和統計
            final_data = {}
            patients_with_bp = 0
            
            for pid, data in bp_data.items():
                if data['systolic']:
                    patients_with_bp += 1
                    final_data[pid] = {
                        'systolic': data['systolic'],
                        'diastolic': data['diastolic'],
                        'date': data['date'],
                        'time': data['time'],
                        'hdate': data.get('hdate', data['date']),
                        'htime': data.get('htime', data['time']),
                        'value': data['value']
                    }
                else:
                    final_data[pid] = {
                        'systolic': None,
                        'diastolic': None,
                        'date': None,
                        'time': None,
                        'hdate': None,
                        'htime': None,
                        'value': None
                    }
            
            print(f"掃描完成！篩選效果分析:")
            print(f"- 總記錄: {total_records}")
            if sample_dates:
                print(f"- 前10筆記錄日期樣本: {sample_dates}")
            print(f"- 通過日期篩選: {date_filtered} ({date_filtered/total_records*100:.1f}%)")
            if date_filtered > 0:
                print(f"- BP記錄: {bp_found} ({bp_found/date_filtered*100:.1f}% of date filtered)")
                if bp_found > 0:
                    print(f"- 病患匹配: {patient_matched} ({patient_matched/bp_found*100:.1f}% of BP records)")
            print(f"- 最終有血壓病患: {patients_with_bp}")
            
            self.finished.emit(final_data)

        except FileNotFoundError as e:
            error_msg = f"找不到檔案: {self.co18h_path}\n\n請確認DBF檔案是否存在"
            print(f"載入錯誤: {error_msg}")
            self.error_occurred.emit(error_msg)

        except PermissionError as e:
            error_msg = f"無法讀取檔案: {self.co18h_path}\n\n檔案可能正被其他程式使用"
            print(f"載入錯誤: {error_msg}")
            self.error_occurred.emit(error_msg)

        except Exception as e:
            error_msg = f"載入血壓資料時發生錯誤\n\n錯誤訊息: {str(e)}\n檔案: {self.co18h_path}"
            print(f"載入錯誤: {error_msg}")
            self.error_occurred.emit(error_msg)


class UltraPatientTableWidget(QTableWidget):
    """超級優化的病患表格"""
    
    data_changed = Signal()
    selection_changed = Signal()
    
    def __init__(self):
        super().__init__()
        self.setup_table()
        self.selected_patients = set()
        self.patient_data = []
        self.bp_data = {}
        self.dbf_folder = ""  # 儲存DBF資料夾路徑
        self._updating = False  # 防止遞迴更新
        
    def setup_table(self):
        """設定表格"""
        headers = ["選擇", "病歷號", "姓名", "身分證", "收縮壓", "舒張壓", "測量日期", "狀態"]
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        
        # 設定行高來配合SpinBox
        self.verticalHeader().setDefaultSectionSize(35)
        
        # 優化欄位寬度 - 移除原始值欄位，加大血壓欄位
        widths = [50, 80, 100, 100, 120, 120, 100, 100]
        for i, width in enumerate(widths):
            self.setColumnWidth(i, width)
    
    def load_vishfam(self, vishfam_path: str) -> List[str]:
        """載入VISHFAM資料"""
        patients = []
        patient_ids = []
        seen_pids = set()  # 用於去重
        
        # 設定DBF資料夾路徑
        self.dbf_folder = os.path.dirname(vishfam_path)
        
        try:
            table = dbf.Table(vishfam_path)
            table.open()
            total_records = len(table)
            duplicates_found = 0
            
            for record in table:
                try:
                    pat_pid = str(getattr(record, 'PAT_PID', '')).strip()
                    if not pat_pid or pat_pid == '0000000':
                        continue
                    
                    # 去重檢查
                    if pat_pid in seen_pids:
                        duplicates_found += 1
                        continue
                    seen_pids.add(pat_pid)
                    
                    patient = {
                        'pat_pid': pat_pid,
                        'pat_id': str(getattr(record, 'PAT_ID', '')).strip(),
                        'pat_namec': str(getattr(record, 'PAT_NAMEC', '')).strip(),
                        'reg_date': str(getattr(record, 'REG_DATE', '')).strip(),
                    }
                    
                    patients.append(patient)
                    patient_ids.append(pat_pid)
                    
                except Exception:
                    continue
            
            table.close()
            
            print(f"VISHFAM掃描完成:")
            print(f"- 總記錄: {total_records}")
            print(f"- 重複記錄: {duplicates_found}")
            print(f"- 最終病患: {len(patients)}")
            
            self.patient_data = patients
            print(f"Patient data assigned: {len(self.patient_data)} patients")
            # 不在這裡populate_table，等待血壓資料載入完成後再一起處理
            
        except Exception as e:
            raise Exception(f"讀取VISHFAM.DBF失敗: {str(e)}")
        
        return patient_ids
    
    def update_blood_pressure_data(self, bp_data: dict):
        """更新血壓資料"""
        self.bp_data = bp_data
        self.populate_table()
    
    def populate_table(self):
        """填充表格"""
        self._updating = True
        
        # 先完全清空表格
        self.clearContents()
        self.setRowCount(0)
        
        # 再設定正確的行數
        self.setRowCount(len(self.patient_data))
        
        print(f"Table refill: patients={len(self.patient_data)}, rows={self.rowCount()}")
        
        # 清空之前的選擇狀態
        self.selected_patients.clear()
        auto_selected = 0  # 統計自動選擇的數量
        
        for row, patient in enumerate(self.patient_data):
            patient_id = patient['pat_pid']
            bp_info = self.bp_data.get(patient_id.zfill(7), {})
            
            # 將血壓資料的時間資訊加入patient資料中
            if bp_info:
                patient['hdate'] = bp_info.get('hdate')
                patient['htime'] = bp_info.get('htime')
            
            # 判斷是否有血壓資料 (必須收縮壓和舒張壓都大於0)
            systolic = bp_info.get('systolic') or 0
            diastolic = bp_info.get('diastolic') or 0
            has_bp_data = (systolic > 0 and diastolic > 0)
            
            # 選擇框 - 如果有血壓資料則自動勾選
            checkbox = QCheckBox()
            if has_bp_data:
                checkbox.setChecked(True)
                # 使用統一格式的patient_id防止重複
                normalized_pid = normalize_patient_id(patient_id)
                self.selected_patients.add(normalized_pid)
                auto_selected += 1
            
            checkbox.stateChanged.connect(lambda state, r=row: self.on_checkbox_changed(r, state))
            self.setCellWidget(row, 0, checkbox)
            
            # 基本資料
            self.setItem(row, 1, QTableWidgetItem(patient_id))
            self.setItem(row, 2, QTableWidgetItem(patient.get('pat_namec', '')))
            self.setItem(row, 3, QTableWidgetItem(patient.get('pat_id', '')))
            
            # 血壓值 - 可編輯的SpinBox，設定合理範圍
            systolic_spin = QSpinBox()
            systolic_spin.setRange(0, BloodPressureRange.SYSTOLIC_MAX)
            systolic_spin.setMinimumHeight(28)
            systolic_spin.setMinimumWidth(100)
            systolic_spin.setToolTip(f"收縮壓合理範圍: {BloodPressureRange.SYSTOLIC_MIN}-{BloodPressureRange.SYSTOLIC_MAX} {HealthInsuranceCode.BP_UNIT}")
            if bp_info.get('systolic'):
                systolic_spin.setValue(bp_info['systolic'])

            # 連接變更事件，實現自動勾選功能
            systolic_spin.valueChanged.connect(lambda v, r=row: self.on_bp_value_changed(r))
            self.setCellWidget(row, 4, systolic_spin)

            diastolic_spin = QSpinBox()
            diastolic_spin.setRange(0, BloodPressureRange.DIASTOLIC_MAX)
            diastolic_spin.setMinimumHeight(28)
            diastolic_spin.setMinimumWidth(100)
            diastolic_spin.setToolTip(f"舒張壓合理範圍: {BloodPressureRange.DIASTOLIC_MIN}-{BloodPressureRange.DIASTOLIC_MAX} {HealthInsuranceCode.BP_UNIT}")
            if bp_info.get('diastolic'):
                diastolic_spin.setValue(bp_info['diastolic'])
            
            diastolic_spin.valueChanged.connect(lambda v, r=row: self.on_bp_value_changed(r))
            self.setCellWidget(row, 5, diastolic_spin)
            
            # 測量日期 (原本索引7改為6)
            date_str = ""
            if bp_info.get('date'):
                try:
                    date_tw = bp_info['date']
                    if len(date_tw) >= 7:
                        yy = int(date_tw[:3]) + 1911
                        mm = date_tw[3:5]
                        dd = date_tw[5:7]
                        date_str = f"{yy}/{mm}/{dd}"
                except:
                    date_str = bp_info['date']
            self.setItem(row, 6, QTableWidgetItem(date_str))
            
            # 狀態 (原本索引8改為7) - 初始設定
            if has_bp_data:
                status = "已選擇" if has_bp_data else "有資料"
                status_item = QTableWidgetItem(status)
                status_item.setBackground(QBrush(QColor(200, 255, 200)))  # 綠色
            else:
                status_item = QTableWidgetItem("待輸入")
                status_item.setBackground(QBrush(QColor(240, 240, 240)))  # 灰色
            self.setItem(row, 7, status_item)
        
        self._updating = False
        
        # 初始狀態已設定，無需再次更新
        
        if auto_selected > 0:
            print(f"自動選擇了 {auto_selected} 位有血壓資料的病患")
            print(f"實際選擇集合大小: {len(self.selected_patients)}")
        
        self.selection_changed.emit()
    
    def on_checkbox_changed(self, row, state):
        """選擇框變更 - 同時更新狀態欄位"""
        if self._updating or row >= len(self.patient_data):
            return
            
        patient_id = self.patient_data[row]['pat_pid']
        # 使用統一格式防止重複
        normalized_pid = normalize_patient_id(patient_id)
        if state == Qt.CheckState.Checked.value:
            self.selected_patients.add(normalized_pid)
        else:
            self.selected_patients.discard(normalized_pid)
        
        # 更新狀態欄位連動
        self.update_row_status(row)
        self.selection_changed.emit()
    
    def on_bp_value_changed(self, row):
        """血壓值變更時的處理 - 修正自動選擇邏輯"""
        if self._updating or row >= len(self.patient_data):
            return
        
        # 取得目前的血壓值
        systolic_spin = self.cellWidget(row, 4)
        diastolic_spin = self.cellWidget(row, 5)
        
        if systolic_spin and diastolic_spin:
            systolic = systolic_spin.value()
            diastolic = diastolic_spin.value()
            
            # 只有當兩個數值都有填入時才自動勾選
            if systolic > 0 and diastolic > 0:
                checkbox = self.cellWidget(row, 0)
                if checkbox and not checkbox.isChecked():
                    self._updating = True
                    checkbox.setChecked(True)
                    patient_id = self.patient_data[row]['pat_pid']
                    normalized_pid = normalize_patient_id(patient_id)
                    self.selected_patients.add(normalized_pid)
                    self._updating = False
        
        # 更新狀態顯示
        self.update_row_status(row)
        self.data_changed.emit()
        self.selection_changed.emit()
    
    def update_row_status(self, row):
        """更新單一列的狀態顯示"""
        if row >= len(self.patient_data):
            return
        
        # 檢查是否被選擇
        checkbox = self.cellWidget(row, 0)
        is_selected = checkbox.isChecked() if checkbox else False
        
        # 檢查是否有血壓值
        systolic_spin = self.cellWidget(row, 4)
        diastolic_spin = self.cellWidget(row, 5)
        has_bp_values = False
        
        if systolic_spin and diastolic_spin:
            systolic = systolic_spin.value()
            diastolic = diastolic_spin.value()
            has_bp_values = systolic > 0 or diastolic > 0
        
        # 更新狀態文字和顏色
        status_item = self.item(row, 7)
        if status_item:
            if is_selected:
                if has_bp_values:
                    status_item.setText("已選擇")
                    status_item.setBackground(QBrush(QColor(200, 255, 200)))  # 綠色
                else:
                    status_item.setText("已選擇")
                    status_item.setBackground(QBrush(QColor(200, 200, 255)))  # 藍色
            else:
                if has_bp_values:
                    status_item.setText("有資料")
                    status_item.setBackground(QBrush(QColor(255, 255, 200)))  # 黃色
                else:
                    status_item.setText("待輸入")
                    status_item.setBackground(QBrush(QColor(240, 240, 240)))  # 灰色
    
    def get_export_data(self) -> List[Dict]:
        """取得匯出資料 - 完全基於GUI表單中的勾選狀態"""
        export_data = []
        
        print(f"開始檢查匯出資料，表格總行數: {self.rowCount()}")
        
        # 遍歷表格中每一行，檢查勾選狀態
        for row in range(self.rowCount()):
            # 第一步：檢查是否勾選
            checkbox = self.cellWidget(row, 0)
            if not (checkbox and checkbox.isChecked()):
                continue  # 跳過未勾選的行
            
            # 第二步：取得病患基本資料
            if row >= len(self.patient_data):
                print(f"警告：第{row}行超出病患資料範圍")
                continue
                
            patient = self.patient_data[row].copy()
            patient_id = normalize_patient_id(patient['pat_pid'])
            
            # 第三步：從GUI取得當前血壓值（以GUI顯示為準）
            systolic_spin = self.cellWidget(row, 4)
            diastolic_spin = self.cellWidget(row, 5)
            
            if not (systolic_spin and diastolic_spin):
                print(f"警告：第{row}行血壓輸入框不存在")
                continue
            
            # 取得GUI中的血壓值
            systolic = systolic_spin.value()
            diastolic = diastolic_spin.value()
            
            # 第四步：驗證血壓數值範圍並只匯出有完整資料的病患
            if not (BloodPressureRange.SYSTOLIC_MIN <= systolic <= BloodPressureRange.SYSTOLIC_MAX and
                    BloodPressureRange.DIASTOLIC_MIN <= diastolic <= BloodPressureRange.DIASTOLIC_MAX):
                print(f"跳過第{row}行：血壓值超出合理範圍 (收縮壓:{systolic}, 舒張壓:{diastolic})")
                print(f"  合理範圍: 收縮壓 {BloodPressureRange.SYSTOLIC_MIN}-{BloodPressureRange.SYSTOLIC_MAX} {HealthInsuranceCode.BP_UNIT}, "
                      f"舒張壓 {BloodPressureRange.DIASTOLIC_MIN}-{BloodPressureRange.DIASTOLIC_MAX} {HealthInsuranceCode.BP_UNIT}")
                continue
                
            # 第五步：設定血壓值和時間資訊
            patient['systolic'] = systolic
            patient['diastolic'] = diastolic
            
            # 取得血壓記錄的時間資訊
            if patient_id in self.bp_data:
                bp_info = self.bp_data[patient_id]
                patient['hdate'] = bp_info.get('hdate', bp_info.get('date', ''))
                patient['htime'] = bp_info.get('htime', bp_info.get('time', ''))
            else:
                # 若無血壓記錄，使用當前時間
                current_date = datetime.now()
                tw_year = current_date.year - 1911
                patient['hdate'] = f"{tw_year:03d}{current_date.month:02d}{current_date.day:02d}"
                patient['htime'] = f"{current_date.hour:02d}{current_date.minute:02d}{current_date.second:02d}"
            
            # 向下兼容的日期時間格式
            patient['bp_date'] = patient.get('hdate', datetime.now().strftime("%Y%m%d")[2:])
            patient['bp_time'] = patient.get('htime', datetime.now().strftime("%H%M%S"))
            
            # 加入匯出清單
            export_data.append(patient)
            print(f"第{row}行已加入匯出：{patient_id} (收縮壓:{systolic}, 舒張壓:{diastolic})")
        
        print(f"匯出資料準備完成，共{len(export_data)}筆")
        return export_data
    
    def select_all(self):
        """全選"""
        self._updating = True
        for row in range(self.rowCount()):
            checkbox = self.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(True)
                if row < len(self.patient_data):
                    patient_id = self.patient_data[row]['pat_pid']
                    normalized_pid = normalize_patient_id(patient_id)
                    self.selected_patients.add(normalized_pid)
        self._updating = False
        self.selection_changed.emit()
    
    def clear_selection(self):
        """清除選擇"""
        self._updating = True
        for row in range(self.rowCount()):
            checkbox = self.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(False)
        self.selected_patients.clear()
        self._updating = False
        self.selection_changed.emit()


class UltraLoadingThread(QThread):
    """載入執行緒"""
    progress = Signal(int, int)
    finished = Signal(dict)
    error_occurred = Signal(str)  # 新增錯誤信號

    def __init__(self, co18h_path: str, patient_ids: List[str], years_limit: float = None, start_date=None, end_date=None):
        super().__init__()
        self.loader = UltraBloodPressureLoader(co18h_path, patient_ids, years_limit, start_date, end_date)
        self.loader.progress.connect(self.progress.emit)
        self.loader.finished.connect(self.finished.emit)
        self.loader.error_occurred.connect(self.error_occurred.emit)  # 連接錯誤信號
    
    def run(self):
        self.loader.load()


class UltraMainWindow(QMainWindow):
    """主視窗"""
    
    def __init__(self):
        super().__init__()
        self.loading_thread = None
        self.setup_ui()
        
    def setup_ui(self):
        """設定介面"""
        self.setWindowTitle("BP2VPN Vision v2.0")
        self.setGeometry(100, 100, 1200, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 標題
        title_label = QLabel("血壓紀錄批次檔生成器 v2.0")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 特色說明
        feature_label = QLabel("先選擇時間範圍，再輸入機構代碼，再選擇資料夾")
        feature_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        feature_label.setStyleSheet("color: #059669; font-weight: bold;")
        layout.addWidget(feature_label)
        
        # 控制區
        control_layout = QVBoxLayout()
        
        # 第一行按鈕
        button_layout1 = QHBoxLayout()
        
        self.select_folder_btn = QPushButton("選擇資料夾")
        self.select_folder_btn.clicked.connect(self.select_folder)
        button_layout1.addWidget(self.select_folder_btn)
        
        # 日期範圍選擇
        date_range_layout = QVBoxLayout()
        
        # 日期範圍模式選擇
        date_mode_layout = QHBoxLayout()
        date_mode_layout.addWidget(QLabel("資料範圍:"))
        
        self.date_mode_group = QButtonGroup()
        self.preset_radio = QRadioButton("預設範圍")
        self.custom_radio = QRadioButton("自訂區間")
        self.preset_radio.setChecked(True)  # 預設選擇預設範圍
        
        self.date_mode_group.addButton(self.preset_radio, 0)
        self.date_mode_group.addButton(self.custom_radio, 1)
        
        # 連接信號
        self.preset_radio.toggled.connect(self.on_date_mode_changed)
        self.custom_radio.toggled.connect(self.on_date_mode_changed)
        
        date_mode_layout.addWidget(self.preset_radio)
        date_mode_layout.addWidget(self.custom_radio)
        date_range_layout.addLayout(date_mode_layout)
        
        # 預設範圍選擇器
        preset_layout = QHBoxLayout()
        self.years_combo = QComboBox()
        self.years_combo.addItems(["今年", "三個月內", "半年內", "一年內"])
        self.years_combo.setCurrentText("一年內")
        preset_layout.addWidget(self.years_combo)
        preset_layout.addStretch()
        date_range_layout.addLayout(preset_layout)
        
        # 自訂日期區間選擇器
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel("起始日期:"))
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addDays(-365))  # 預設一年前
        self.start_date.setCalendarPopup(True)
        self.start_date.setEnabled(False)  # 初始為禁用
        custom_layout.addWidget(self.start_date)
        
        custom_layout.addWidget(QLabel("結束日期:"))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())  # 預設今天
        self.end_date.setCalendarPopup(True)
        self.end_date.setEnabled(False)  # 初始為禁用
        custom_layout.addWidget(self.end_date)
        custom_layout.addStretch()
        date_range_layout.addLayout(custom_layout)
        
        button_layout1.addLayout(date_range_layout)
        
        # 醫事機構代碼
        button_layout1.addWidget(QLabel("醫事機構代碼:"))
        self.hospital_code_input = QLineEdit()
        self.hospital_code_input.setPlaceholderText("請輸入10碼醫事機構代碼")
        self.hospital_code_input.setMaximumWidth(200)
        self.hospital_code_input.setMaxLength(10)  # 限制最多10個字元
        self.hospital_code_input.setToolTip("醫事機構代碼必須為10碼數字\n範例: 3522013684")
        button_layout1.addWidget(self.hospital_code_input)
        
        self.select_all_btn = QPushButton("全選")
        self.select_all_btn.clicked.connect(self.select_all)
        self.select_all_btn.setEnabled(False)
        button_layout1.addWidget(self.select_all_btn)
        
        self.clear_btn = QPushButton("清除選擇")
        self.clear_btn.clicked.connect(self.clear_selection)
        self.clear_btn.setEnabled(False)
        button_layout1.addWidget(self.clear_btn)
        
        self.export_btn = QPushButton("匯出XML")
        self.export_btn.clicked.connect(self.export_data)
        self.export_btn.setEnabled(False)
        button_layout1.addWidget(self.export_btn)
        
        button_layout1.addStretch()
        control_layout.addLayout(button_layout1)
        
        # 第二行搜尋和統計
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜尋:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("輸入病歷號或姓名...")
        self.search_input.textChanged.connect(self.filter_table)
        search_layout.addWidget(self.search_input)
        
        search_layout.addStretch()
        
        self.stats_label = QLabel("總計: 0 筆")
        search_layout.addWidget(self.stats_label)
        
        control_layout.addLayout(search_layout)
        layout.addLayout(control_layout)
        
        # 表格
        self.table = UltraPatientTableWidget()
        self.table.data_changed.connect(self.update_stats)
        self.table.selection_changed.connect(self.update_stats)
        layout.addWidget(self.table)
        
        # 狀態欄
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("準備就緒 - 請選擇包含VISHFAM.DBF的資料夾")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
    
    def on_date_mode_changed(self):
        """日期模式切換處理"""
        if self.preset_radio.isChecked():
            # 預設範圍模式
            self.years_combo.setEnabled(True)
            self.start_date.setEnabled(False)
            self.end_date.setEnabled(False)
        else:
            # 自訂區間模式
            self.years_combo.setEnabled(False)
            self.start_date.setEnabled(True)
            self.end_date.setEnabled(True)
    
    def select_folder(self):
        """選擇資料夾"""
        # 檢查是否已填入醫事機構代碼
        if not self.hospital_code_input.text().strip():
            QMessageBox.warning(
                self,
                "需要醫事機構代碼",
                "請先填入醫事機構代碼再選擇資料夾"
            )
            self.hospital_code_input.setFocus()
            return
        
        folder = QFileDialog.getExistingDirectory(
            self,
            "選擇包含DBF檔案的資料夾",
            ""
        )
        
        if folder:
            self.load_data(folder)
    
    def load_data(self, folder: str):
        """載入資料"""
        try:
            folder_path = Path(folder)
            vishfam_path = folder_path / "VISHFAM.DBF"
            co18h_path = folder_path / "CO18H.DBF"
            
            if not vishfam_path.exists():
                QMessageBox.critical(self, "錯誤", "找不到VISHFAM.DBF檔案")
                return
            
            # 載入VISHFAM
            self.status_bar.showMessage("正在載入病患名單...")
            patient_ids = self.table.load_vishfam(str(vishfam_path))
            
            if not patient_ids:
                QMessageBox.warning(self, "警告", "沒有找到有效的病患資料")
                return
            
            # 根據CO18H檔案是否存在決定處理方式
            if co18h_path.exists():
                # 有CO18H檔案，使用Ultra載入血壓資料
                if self.preset_radio.isChecked():
                    # 使用預設範圍
                    years_text = self.years_combo.currentText()
                    years_limit = {"今年": 0.1, "三個月內": 0.25, "半年內": 0.5, "一年內": 1.0}[years_text]
                    self.load_blood_pressure_ultra(str(co18h_path), patient_ids, years_limit, None, None)
                else:
                    # 使用自訂日期區間
                    start_date = self.start_date.date().toPython()  # 轉換為 Python datetime.date
                    end_date = self.end_date.date().toPython()
                    
                    # 驗證日期區間
                    if start_date >= end_date:
                        QMessageBox.warning(self, "日期錯誤", "起始日期必須早於結束日期")
                        return
                    
                    self.load_blood_pressure_ultra(str(co18h_path), patient_ids, None, start_date, end_date)
            else:
                # 沒有CO18H檔案，手動填充表格
                self.table.populate_table()
                self.update_stats()
                QMessageBox.information(
                    self, 
                    "載入完成",
                    f"已載入 {len(patient_ids)} 筆病患資料\\n\\n找不到CO18H.DBF檔案"
                )
                self.enable_controls()
            
        except Exception as e:
            QMessageBox.critical(self, "載入錯誤", f"載入資料時發生錯誤:\\n{str(e)}")
    
    def load_blood_pressure_ultra(self, co18h_path: str, patient_ids: List[str], years_limit: float = None, start_date=None, end_date=None):
        """血壓載入"""
        if years_limit is not None:
            # 預設範圍模式
            range_text = {0.1: "今年", 0.25: "三個月內", 0.5: "半年內", 1.0: "一年內"}.get(years_limit, f"{years_limit}年內")
        else:
            # 自訂區間模式
            range_text = f"{start_date.strftime('%Y/%m/%d')} ~ {end_date.strftime('%Y/%m/%d')}"
        
        self.status_bar.showMessage(f"載入中 - {range_text}血壓資料...")
        self.progress_bar.setVisible(True)
        self.select_folder_btn.setEnabled(False)
        
        self.loading_thread = UltraLoadingThread(co18h_path, patient_ids, years_limit, start_date, end_date)
        self.loading_thread.progress.connect(self.on_loading_progress)
        self.loading_thread.finished.connect(self.on_loading_finished)
        self.loading_thread.error_occurred.connect(self.on_loading_error)  # 連接錯誤處理
        self.loading_thread.start()
    
    def on_loading_progress(self, current: int, total: int):
        """更新進度"""
        percent = int(current * 100 / total) if total > 0 else 0
        self.progress_bar.setValue(percent)
        self.status_bar.showMessage(f"掃描中... {current}/{total} ({percent}%)")
    
    def on_loading_error(self, error_msg: str):
        """載入發生錯誤"""
        self.progress_bar.setVisible(False)
        self.select_folder_btn.setEnabled(True)
        self.status_bar.showMessage("載入失敗")

        QMessageBox.critical(
            self,
            "載入錯誤",
            error_msg
        )

    def on_loading_finished(self, bp_data: dict):
        """載入完成"""
        self.progress_bar.setVisible(False)
        self.select_folder_btn.setEnabled(True)

        # 檢查是否有數據（空字典可能是因為錯誤）
        if bp_data is None:
            return  # 錯誤已由 on_loading_error 處理

        self.table.update_blood_pressure_data(bp_data)
        
        # 統計
        total = len(self.table.patient_data)
        with_bp = sum(1 for data in bp_data.values() if data.get('systolic'))
        auto_selected = len(self.table.selected_patients)
        
        QMessageBox.information(
            self,
            "載入完成",
            f"優化載入完成!\n"
            f"📊 病患總數: {total} 筆\n"
            f"💉 有血壓記錄: {with_bp} 筆\n"
            f"☑️ 自動選擇: {auto_selected} 筆\n"
            f"✨ 特色功能已啟用:\n"
            f"• 有血壓資料的病患已自動勾選\n"
            f"• 輸入血壓值後會自動勾選\n"
            f"• 只顯示每位病患的最新記錄"
        )
        
        self.enable_controls()
        self.update_stats()
        self.status_bar.showMessage("就緒 - 可以開始操作")
    
    def enable_controls(self):
        """啟用控制項"""
        self.select_all_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
    
    def select_all(self):
        """全選"""
        self.table.select_all()
        self.update_stats()
    
    def clear_selection(self):
        """清除選擇"""
        self.table.clear_selection()
        self.update_stats()
    
    def filter_table(self, text: str):
        """篩選表格"""
        for row in range(self.table.rowCount()):
            show = True
            if text:
                pid = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
                name = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
                if text.lower() not in pid.lower() and text.lower() not in name.lower():
                    show = False
            self.table.setRowHidden(row, not show)
    
    def update_stats(self):
        """更新統計 - 修正總數統計"""
        if not self.table:
            return
        
        # 直接計算VISHFAM資料中有效的病患數量
        if hasattr(self.table, 'patient_data') and self.table.patient_data:
            # 去重計算，使用集合去重
            unique_patients = set()
            for patient in self.table.patient_data:
                if patient.get('pat_pid'):
                    unique_patients.add(normalize_patient_id(patient['pat_pid']))
            total = len(unique_patients)
        else:
            total = 0
        
        # 重新計算實際勾選數量
        actual_selected = 0
        self.table.selected_patients.clear()
        
        for row in range(min(total, self.table.rowCount())):
            checkbox = self.table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                actual_selected += 1
                if row < len(self.table.patient_data):
                    patient_id = self.table.patient_data[row]['pat_pid']
                    normalized_pid = normalize_patient_id(patient_id)
                    self.table.selected_patients.add(normalized_pid)
        
        selected = len(self.table.selected_patients)
        
        # 簡化統計顯示，只顯示總計和已選擇
        self.stats_label.setText(f"總計: {total} 筆 | 已選: {selected} 筆")
        
        # 調試資訊
        print(f"統計調試: 病患資料長度={len(self.table.patient_data) if self.table.patient_data else 0}, 表格行數={self.table.rowCount()}, 實際勾選={actual_selected}, 集合大小={selected}")
    
    def export_data(self):
        """匯出資料"""
        export_data = self.table.get_export_data()
        
        print(f"匯出調試: 準備匯出 {len(export_data)} 筆資料")
        for i, patient in enumerate(export_data[:5]):  # 顯示前5筆
            print(f"  {i+1}: {patient['pat_pid']} - 收縮壓:{patient.get('systolic', 0)}, 舒張壓:{patient.get('diastolic', 0)}")
        
        if not export_data:
            QMessageBox.warning(self, "警告", "請選擇至少一筆有血壓值的資料!")
            return
        
        # 詢問用戶要匯出的格式
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QRadioButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle("選擇匯出格式")
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("請選擇匯出格式:"))
        
        xml_radio = QRadioButton("僅匯出 XML 檔案")
        zip_radio = QRadioButton("匯出 ZIP 壓縮檔案 (可直接上傳VPN，建議使用)")
        xml_radio.setChecked(True)  # 預設選擇XML
        
        layout.addWidget(xml_radio)
        layout.addWidget(zip_radio)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() != QDialog.Accepted:
            return
        
        # 根據選擇決定檔案格式和名稱
        if zip_radio.isChecked():
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "儲存ZIP檔案",
                "TOTFA.zip",
                "ZIP檔案 (*.zip)"
            )
            export_as_zip = True
        else:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "儲存XML檔案",
                "TOTFA.xml",
                "XML檔案 (*.xml)"
            )
            export_as_zip = False
        
        if not filename:
            return
        
        try:
            if export_as_zip:
                self.write_xml_and_zip(export_data, filename)
            else:
                self.write_xml(export_data, filename)
            
            # 統計實際匯出的病患數（每個病患一筆資料，包含收縮壓和舒張壓）
            valid_exports = sum(1 for p in export_data if p.get('systolic', 0) > 0 and p.get('diastolic', 0) > 0)
            
            file_type = "ZIP 壓縮檔案" if export_as_zip else "XML檔案"
            QMessageBox.information(
                self,
                "匯出成功",
                f"✅ 匯出成功!\n"
                f"📁 檔案: {Path(filename).name}\n"
                f"📦 格式: {file_type}\n"
                f"📊 匯出: {valid_exports} 位病患血壓資料\n"
                f"📋 規範: 健保署XML格式\n"
                f"🔍 每位病患包含收縮壓與舒張壓記錄"
            )
            self.status_bar.showMessage(f"匯出完成 - {valid_exports} 位病患資料 ({file_type})")
            
        except Exception as e:
            QMessageBox.critical(self, "匯出錯誤", f"匯出失敗:\n{str(e)}")
    
    def write_xml(self, data: List[Dict], filename: str):
        """寫入XML - 符合健保署最新规范"""
        from datetime import datetime, timedelta
        import os
        
        # 取得並驗證醫事機構代碼
        hospital_code = self.hospital_code_input.text().strip()

        if not hospital_code:
            raise Exception("請先填入醫事機構代碼")

        if len(hospital_code) != 10:
            raise Exception(
                f"醫事機構代碼格式錯誤\n\n"
                f"您輸入的代碼: {hospital_code} ({len(hospital_code)}碼)\n"
                f"正確格式: 必須為10碼數字\n\n"
                f"範例: 3522013684"
            )

        if not hospital_code.isdigit():
            raise Exception(
                f"醫事機構代碼格式錯誤\n\n"
                f"您輸入的代碼: {hospital_code}\n"
                f"正確格式: 必須為10碼數字（不可包含英文或符號）\n\n"
                f"範例: 3522013684"
            )
        
        # 嘗試載入額外的DBF資料
        folder_path = self.table.dbf_folder
        co01m_data = {}
        co03l_data = {}
        
        # 嘗試讀取CO01M.DBF的出生日期資料
        co01m_path = os.path.join(folder_path, 'CO01M.DBF')
        if os.path.exists(co01m_path):
            try:
                table = dbf.Table(co01m_path)
                table.open()
                
                loaded_count = 0
                
                for record in table:
                    try:
                        # 直接使用欄位名稱訪問
                        pid = str(record.KCSTMR).strip().zfill(7) if record.KCSTMR else ''
                        birth_date = str(record.MBIRTHDT).strip() if record.MBIRTHDT else ''
                        
                        if pid and birth_date:
                            co01m_data[pid] = birth_date
                            loaded_count += 1
                            
                    except Exception as e:
                        continue
                
                table.close()
                print(f"CO01M載入: {loaded_count} 筆出生日期")
            except Exception as e:
                print(f"CO01M讀取失敗: {e}")
        
        # 嘗試讀取co03l.dbf的edate資料
        co03l_path = os.path.join(folder_path, 'co03l.dbf')
        if os.path.exists(co03l_path):
            try:
                table = dbf.Table(co03l_path)
                table.open()
                for record in table:
                    pid = str(record.KCSTMR).strip().zfill(7) if hasattr(record, 'KCSTMR') else ''
                    edate = str(record.EDATE).strip() if hasattr(record, 'EDATE') else ''
                    if pid and edate:
                        # 建立key為 pid+date 的索引
                        key = f"{pid}_{str(record.HDATE).strip() if hasattr(record, 'HDATE') else ''}"
                        co03l_data[key] = edate
                table.close()
            except:
                pass
        
        # 生成符合健保署規範的XML內容
        xml_lines = []
        xml_lines.append('<?xml version="1.0" encoding="Big5"?>')
        xml_lines.append('<patient>')
        
        # 獲取當前時間的秒數，用於統一所有r10標籤的秒數部分（避免重複上傳失敗）
        unified_second = datetime.now().second
        
        print(f"準備匯出 {len(data)} 位病患，CO01M資料: {len(co01m_data)} 筆")
        print(f"統一秒數設定: {unified_second:02d} (避免重複上傳)")
        h10_count = 0
        
        for patient in data:
            xml_lines.append('  <hdata>')
            
            # h1: 報告類別
            xml_lines.append(f'    <h1>{HealthInsuranceCode.REPORT_TYPE}</h1>')

            # h2: 醫事機構代碼
            xml_lines.append(f'    <h2>{hospital_code}</h2>')

            # h3: 醫事類別
            xml_lines.append(f'    <h3>{HealthInsuranceCode.MEDICAL_CATEGORY}</h3>')
            
            # h4: 血壓測量數值的年月 (從hdate取得)
            if patient.get('hdate'):
                # hdate格式為民國年YYYMMDD，取前5碼(YYYMM)
                h4_value = patient['hdate'][:5] if len(patient['hdate']) >= 5 else ''
            else:
                # 使用當前日期
                current_date = datetime.now()
                tw_year = current_date.year - 1911
                h4_value = f"{tw_year:03d}{current_date.month:02d}"
            xml_lines.append(f'    <h4>{h4_value}</h4>')
            
            # h5: 健保卡過卡日期時間 (使用hdate + htime)
            if patient.get('hdate') and patient.get('htime'):
                h5_value = patient['hdate'] + patient['htime']
            else:
                # 使用當前時間
                current_datetime = datetime.now()
                tw_year = current_datetime.year - 1911
                h5_value = f"{tw_year:03d}{current_datetime.month:02d}{current_datetime.day:02d}{current_datetime.hour:02d}{current_datetime.minute:02d}{current_datetime.second:02d}"
            xml_lines.append(f'    <h5>{h5_value}</h5>')
            
            # h6: 就醫類別
            xml_lines.append(f'    <h6>{HealthInsuranceCode.CASE_TYPE}</h6>')

            # h7: 就醫序號 (查詢co03l.dbf的edate欄位)
            h7_value = HealthInsuranceCode.DEFAULT_VISIT_SEQ
            if patient.get('pat_pid') and patient.get('hdate'):
                key = f"{patient['pat_pid'].zfill(7)}_{patient['hdate']}"
                if key in co03l_data:
                    edate = co03l_data[key]
                    # 去掉開頭的民國年(前3碼)
                    if len(edate) > 3:
                        h7_value = edate[3:].zfill(4)
                    if not h7_value or h7_value == '0000':
                        h7_value = HealthInsuranceCode.DEFAULT_VISIT_SEQ
                else:
                    h7_value = HealthInsuranceCode.BP_ITEM_CODE  # 若無資料使用血壓檢驗項目代碼
            xml_lines.append(f'    <h7>{h7_value}</h7>')

            # h8: 補卡註記
            xml_lines.append(f'    <h8>{HealthInsuranceCode.CARD_REPLACEMENT}</h8>')
            
            # h9: 身分證字號
            if patient.get('pat_id') and patient['pat_id'].strip():
                xml_lines.append(f'    <h9>{patient["pat_id"]}</h9>')
            
            # h10: 出生日期 (從CO01M.DBF取得)
            patient_pid = patient['pat_pid'].zfill(7)
            birth_date = co01m_data.get(patient_pid, '')
            if birth_date:
                xml_lines.append(f'    <h10>{birth_date}</h10>')
                h10_count += 1
            
            # h11: 就醫日期 (測量日期)
            if patient.get('hdate'):
                xml_lines.append(f'    <h11>{patient["hdate"]}</h11>')
            
            # h12: 同上
            if patient.get('hdate'):
                xml_lines.append(f'    <h12>{patient["hdate"]}</h12>')
            
            # h15: 診斷代碼
            xml_lines.append(f'    <h15>{HealthInsuranceCode.DIAGNOSIS_CODE}</h15>')
            
            # h16: 現在的時間點
            current_datetime = datetime.now()
            tw_year = current_datetime.year - 1911
            h16_value = f"{tw_year:03d}{current_datetime.month:02d}{current_datetime.day:02d}{current_datetime.hour:02d}{current_datetime.minute:02d}{current_datetime.second:02d}"
            xml_lines.append(f'    <h16>{h16_value}</h16>')
            
            # h20: 檢查時間 (日期+時間)
            if patient.get('hdate') and patient.get('htime'):
                # 只取時間部分的前4碼(時分)
                time_part = patient['htime'][:4] if len(patient['htime']) >= 4 else patient['htime']
                h20_value = patient['hdate'] + time_part
                xml_lines.append(f'    <h20>{h20_value}</h20>')
            
            # h22: 檢驗項目名稱
            xml_lines.append(f'    <h22>{HealthInsuranceCode.BP_TEST_NAME}</h22>')

            # h26: 轉檢FLAG
            xml_lines.append(f'    <h26>{HealthInsuranceCode.TRANSFER_FLAG}</h26>')
            
            # 報告資料段 - 收縮壓
            if patient.get('systolic', 0) > 0:
                xml_lines.append('    <rdata>')
                xml_lines.append(f'      <r1>{HealthInsuranceCode.SYSTOLIC_SEQ}</r1>')
                xml_lines.append(f'      <r2>{HealthInsuranceCode.SYSTOLIC_NAME}</r2>')
                xml_lines.append(f'      <r3>{HealthInsuranceCode.BP_TEST_METHOD}</r3>')
                xml_lines.append(f'      <r4>{patient["systolic"]}</r4>')
                xml_lines.append(f'      <r5>{HealthInsuranceCode.BP_UNIT}</r5>')
                xml_lines.append(f'      <r6-1>{HealthInsuranceCode.SYSTOLIC_REFERENCE}</r6-1>')
                xml_lines.append(f'      <r9>{hospital_code}</r9>')
                
                # r10: 測量時間 (htime加一分鐘，秒數統一)
                if patient.get('hdate') and patient.get('htime'):
                    r10_value = calculate_r10_time(patient['hdate'], patient['htime'], unified_second)
                    xml_lines.append(f'      <r10>{r10_value}</r10>')
                
                xml_lines.append('    </rdata>')
            
            # 報告資料段 - 舒張壓
            if patient.get('diastolic', 0) > 0:
                xml_lines.append('    <rdata>')
                xml_lines.append(f'      <r1>{HealthInsuranceCode.DIASTOLIC_SEQ}</r1>')
                xml_lines.append(f'      <r2>{HealthInsuranceCode.DIASTOLIC_NAME}</r2>')
                xml_lines.append(f'      <r3>{HealthInsuranceCode.BP_TEST_METHOD}</r3>')
                xml_lines.append(f'      <r4>{patient["diastolic"]}</r4>')
                xml_lines.append(f'      <r5>{HealthInsuranceCode.BP_UNIT}</r5>')
                xml_lines.append(f'      <r6-1>{HealthInsuranceCode.DIASTOLIC_REFERENCE}</r6-1>')
                xml_lines.append(f'      <r9>{hospital_code}</r9>')
                
                # r10: 測量時間 (htime加一分鐘，秒數統一)
                if patient.get('hdate') and patient.get('htime'):
                    r10_value = calculate_r10_time(patient['hdate'], patient['htime'], unified_second)
                    xml_lines.append(f'      <r10>{r10_value}</r10>')
                
                xml_lines.append('    </rdata>')
            
            xml_lines.append('  </hdata>')
        
        xml_lines.append('</patient>')
        
        print(f"XML生成完成，包含 {h10_count} 個h10標籤")

        # 寫入檔案 (Big5編碼，嚴格模式)
        xml_content = '\n'.join(xml_lines)

        try:
            # 先測試是否可以完整轉換為 Big5
            xml_content.encode('big5')

            # 確認可以轉換後才寫入檔案
            with open(filename, 'w', encoding='big5') as f:
                f.write(xml_content)

        except UnicodeEncodeError as e:
            # 找出無法編碼的字元
            problematic_chars = set()
            for char in xml_content:
                try:
                    char.encode('big5')
                except UnicodeEncodeError:
                    problematic_chars.add(char)

            error_msg = (
                f"部分中文字無法轉為Big5編碼\n\n"
                f"無法編碼的字元: {''.join(sorted(problematic_chars))}\n\n"
                f"建議:\n"
                f"1. 請檢查病患姓名是否包含特殊字（如：堃、煊、栢）\n"
                f"2. 可手動修改資料後重新匯出\n"
                f"3. 或聯絡系統管理員"
            )
            raise Exception(error_msg)
    
    def write_xml_and_zip(self, data: List[Dict], zip_filename: str):
        """寫入XML並壓縮成ZIP檔案"""
        import tempfile
        import os
        
        # 建立暫存目錄
        with tempfile.TemporaryDirectory() as temp_dir:
            # 產生XML檔案名稱（基於ZIP檔案名稱）
            zip_name = Path(zip_filename).stem
            xml_filename = os.path.join(temp_dir, f"{zip_name}.xml")
            
            # 寫入XML到暫存檔案
            self.write_xml(data, xml_filename)
            
            # 建立ZIP檔案
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
                # 將XML檔案加入ZIP
                zipf.write(xml_filename, f"{zip_name}.xml")
            
            print(f"ZIP檔案建立完成: {zip_filename}")
            print(f"壓縮內容: {zip_name}.xml")
    
    def closeEvent(self, event):
        """關閉事件"""
        if self.loading_thread and self.loading_thread.isRunning():
            reply = QMessageBox.question(
                self, 
                "確認", 
                "Ultra載入進行中，確定要關閉嗎?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.loading_thread.quit()
                self.loading_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    """主程式"""
    app = QApplication(sys.argv)
    app.setApplicationName("BP2VPN Vision")
    app.setApplicationVersion("2.0 Ultra")
    
    # Ultra樣式
    app.setStyleSheet("""
        QMainWindow {
            background-color: #F8FAFC;
        }
        QPushButton {
            background-color: #059669;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 600;
            min-width: 100px;
        }
        QPushButton:hover {
            background-color: #047857;
        }
        QPushButton:pressed {
            background-color: #065F46;
        }
        QPushButton:disabled {
            background-color: #94A3B8;
        }
        QTableWidget {
            gridline-color: #E2E8F0;
            background-color: white;
            alternate-background-color: #F0FDF4;
            border-radius: 8px;
        }
        QTableWidget::item {
            padding: 6px;
        }
        QHeaderView::section {
            background-color: #ECFDF5;
            padding: 8px;
            border: 1px solid #D1FAE5;
            font-weight: bold;
            color: #065F46;
        }
        QSpinBox {
            padding: 4px;
            border: 2px solid #E2E8F0;
            border-radius: 4px;
            background-color: white;
            min-height: 24px;
            font-size: 12px;
        }
        QSpinBox:focus {
            border-color: #059669;
        }
        QCheckBox {
            spacing: 2px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 2px solid #E2E8F0;
            border-radius: 3px;
            background-color: white;
        }
        QCheckBox::indicator:checked {
            background-color: #059669;
            border-color: #059669;
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xMSAwLjVMMy44IDcuN0wxIDQuOSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+);
        }
        QCheckBox::indicator:hover {
            border-color: #059669;
        }
        QProgressBar {
            border: 1px solid #D1FAE5;
            border-radius: 4px;
            text-align: center;
            color: #065F46;
            font-weight: bold;
        }
        QProgressBar::chunk {
            background-color: #059669;
            border-radius: 3px;
        }
        QComboBox {
            padding: 4px 8px;
            border: 1px solid #E2E8F0;
            border-radius: 4px;
            background-color: white;
            min-width: 80px;
        }
        QComboBox:focus {
            border-color: #059669;
        }
    """)
    
    try:
        window = UltraMainWindow()
        window.show()
        
        QTimer.singleShot(800, lambda: QMessageBox.information(
            window,
            "🚀 BP2VPN Vision",
            "🎯 血壓資料匯出系統\n\n"
            "🎨 操作提示:\n"
            "• 有血壓的病患會自動勾選\n"
            "• 輸入血壓值會自動勾選該病患\n"
            "• 綠色=已測量，黃色=待輸入"
        ))
        
        return app.exec()
    except Exception as e:
        import traceback
        error_msg = f"視窗初始化錯誤: {str(e)}\n\n詳細錯誤信息:\n{traceback.format_exc()}"
        print(error_msg)
        QMessageBox.critical(None, "程式錯誤", error_msg)
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        import traceback
        error_msg = f"程式啟動錯誤: {str(e)}\n\n詳細錯誤信息:\n{traceback.format_exc()}"
        print(error_msg)
        
        # 嘗試顯示圖形化錯誤訊息
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if not QApplication.instance():
                app = QApplication(sys.argv)
            QMessageBox.critical(None, "程式錯誤", error_msg)
        except:
            pass
        
        sys.exit(1)