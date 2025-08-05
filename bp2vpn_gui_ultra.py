#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BP2VPN Vision v2.0 Ultra版 - 超級優化版本
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Set
import time
from collections import defaultdict

try:
    from PySide6.QtWidgets import (QApplication, QMessageBox, QMainWindow, QVBoxLayout, 
                                   QWidget, QPushButton, QLabel, QFileDialog, QTableWidget, 
                                   QTableWidgetItem, QHeaderView, QCheckBox, QHBoxLayout, 
                                   QLineEdit, QStatusBar, QProgressBar, QSpinBox, QComboBox)
    from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject
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


class UltraBloodPressureLoader(QObject):
    """超級優化的血壓資料載入器"""
    progress = Signal(int, int)
    finished = Signal(dict)
    
    def __init__(self, co18h_path: str, patient_ids: List[str], years_limit: int = 3):
        super().__init__()
        self.co18h_path = co18h_path
        self.patient_set = {pid.strip().zfill(7) for pid in patient_ids}
        self.years_limit = years_limit
        
    def load(self):
        """超級優化的載入演算法"""
        try:
            # 計算日期限制
            today = datetime.now()
            date_limit = today - timedelta(days=self.years_limit * 365)
            date_limit_tw = date_limit.year - 1911
            date_limit_str = f"{date_limit_tw:03d}0101"
            
            print(f"Ultra載入: {len(self.patient_set)} 位病患, 日期限制: {date_limit_str}")
            
            # 使用字典快速儲存每個病患的最新血壓
            bp_data = {}
            for pid in self.patient_set:
                bp_data[pid] = {
                    'systolic': None,
                    'diastolic': None,
                    'date': None,
                    'time': None,
                    'value': None,
                    'datetime_str': ''
                }
            
            table = dbf.Table(self.co18h_path)
            table.open()
            
            processed = 0
            bp_found = 0
            matched = 0
            total_records = len(table)
            last_emit = time.time()
            batch_size = 1000  # 批次處理
            
            print(f"開始Ultra掃描 {total_records} 筆記錄...")
            
            for record in table:
                # 批次更新進度，減少UI更新頻率
                if processed % batch_size == 0 and time.time() - last_emit > 0.5:
                    self.progress.emit(processed, total_records)
                    last_emit = time.time()
                
                processed += 1
                
                try:
                    # 快速篩選：優先檢查HITEM
                    hitem = str(record.HITEM).strip()
                    if hitem != 'BP':
                        continue
                    
                    bp_found += 1
                    
                    # 快速篩選：檢查病歷號
                    patient_id = str(record.KCSTMR).strip().zfill(7)
                    if patient_id not in self.patient_set:
                        continue
                    
                    # 快速篩選：檢查日期
                    record_date = str(record.HDATE).strip()
                    if len(record_date) >= 7 and record_date < date_limit_str:
                        continue
                    
                    # 解析血壓值
                    hval = str(record.HVAL).strip()
                    if '/' not in hval:
                        continue
                    
                    # 快速解析血壓值
                    try:
                        systolic_str, diastolic_str = hval.split('/', 1)
                        systolic = int(float(systolic_str))
                        diastolic = int(float(diastolic_str))
                        
                        if systolic <= 0 or diastolic <= 0:
                            continue
                        
                        # 建立日期時間字串用於比較
                        time_str = str(record.HTIME).strip()
                        datetime_str = record_date + time_str
                        
                        # 只保留最新的記錄
                        patient_bp = bp_data[patient_id]
                        if not patient_bp['datetime_str'] or datetime_str > patient_bp['datetime_str']:
                            patient_bp['systolic'] = systolic
                            patient_bp['diastolic'] = diastolic
                            patient_bp['date'] = record_date
                            patient_bp['time'] = time_str
                            patient_bp['value'] = hval
                            patient_bp['datetime_str'] = datetime_str
                            matched += 1
                        
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
                        'value': data['value']
                    }
                else:
                    final_data[pid] = {
                        'systolic': None,
                        'diastolic': None,
                        'date': None,
                        'time': None,
                        'value': None
                    }
            
            print(f"Ultra掃描完成！")
            print(f"- 總記錄: {total_records}")
            print(f"- BP記錄: {bp_found}")
            print(f"- 匹配病患: {patients_with_bp}")
            
            self.finished.emit(final_data)
            
        except Exception as e:
            print(f"Ultra載入錯誤: {e}")
            self.finished.emit({})


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
        
        try:
            table = dbf.Table(vishfam_path)
            table.open()
            
            for record in table:
                try:
                    pat_pid = str(getattr(record, 'PAT_PID', '')).strip()
                    if not pat_pid or pat_pid == '0000000':
                        continue
                    
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
            
            print(f"VISHFAM loaded: {len(patients)} patients")
            self.patient_data = patients
            print(f"Patient data length after assignment: {len(self.patient_data)}")
            # 不在這裡populate_table，等待血壓資料載入完成後再一起處理
            
        except Exception as e:
            raise Exception(f"讀取VISHFAM.DBF失敗: {str(e)}")
        
        return patient_ids
    
    def update_blood_pressure_data(self, bp_data: dict):
        """更新血壓資料"""
        self.bp_data = bp_data
        self.populate_table()
    
    def populate_table(self):
        """填充表格 - Ultra版本"""
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
            
            # 判斷是否有血壓資料
            has_bp_data = bp_info.get('systolic') and bp_info.get('diastolic')
            
            # 選擇框 - 如果有血壓資料則自動勾選
            checkbox = QCheckBox()
            if has_bp_data:
                checkbox.setChecked(True)
                # 使用統一格式的patient_id防止重複
                normalized_pid = patient_id.strip().zfill(7)
                self.selected_patients.add(normalized_pid)
                auto_selected += 1
            
            checkbox.stateChanged.connect(lambda state, r=row: self.on_checkbox_changed(r, state))
            self.setCellWidget(row, 0, checkbox)
            
            # 基本資料
            self.setItem(row, 1, QTableWidgetItem(patient_id))
            self.setItem(row, 2, QTableWidgetItem(patient.get('pat_namec', '')))
            self.setItem(row, 3, QTableWidgetItem(patient.get('pat_id', '')))
            
            # 血壓值 - 可編輯的SpinBox，調整大小，移除單位顯示
            systolic_spin = QSpinBox()
            systolic_spin.setRange(0, 300)
            systolic_spin.setMinimumHeight(28)
            systolic_spin.setMinimumWidth(100)
            if bp_info.get('systolic'):
                systolic_spin.setValue(bp_info['systolic'])
            
            # 連接變更事件，實現自動勾選功能
            systolic_spin.valueChanged.connect(lambda v, r=row: self.on_bp_value_changed(r))
            self.setCellWidget(row, 4, systolic_spin)
            
            diastolic_spin = QSpinBox()
            diastolic_spin.setRange(0, 200)
            diastolic_spin.setMinimumHeight(28)
            diastolic_spin.setMinimumWidth(100)
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
        normalized_pid = patient_id.strip().zfill(7)
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
                    normalized_pid = patient_id.strip().zfill(7)
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
        """取得匯出資料"""
        export_data = []
        
        for row in range(self.rowCount()):
            checkbox = self.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                patient = self.patient_data[row].copy()
                
                systolic_spin = self.cellWidget(row, 4)
                diastolic_spin = self.cellWidget(row, 5)
                
                if systolic_spin and diastolic_spin:
                    systolic = systolic_spin.value()
                    diastolic = diastolic_spin.value()
                    
                    if systolic > 0 or diastolic > 0:
                        patient['systolic'] = systolic
                        patient['diastolic'] = diastolic
                        patient['bp_date'] = datetime.now().strftime("%Y%m%d")[2:]
                        patient['bp_time'] = datetime.now().strftime("%H%M%S")
                        export_data.append(patient)
        
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
                    normalized_pid = patient_id.strip().zfill(7)
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
    """Ultra載入執行緒"""
    progress = Signal(int, int)
    finished = Signal(dict)
    
    def __init__(self, co18h_path: str, patient_ids: List[str], years_limit: int = 3):
        super().__init__()
        self.loader = UltraBloodPressureLoader(co18h_path, patient_ids, years_limit)
        self.loader.progress.connect(self.progress.emit)
        self.loader.finished.connect(self.finished.emit)
    
    def run(self):
        self.loader.load()


class UltraMainWindow(QMainWindow):
    """Ultra主視窗"""
    
    def __init__(self):
        super().__init__()
        self.loading_thread = None
        self.setup_ui()
        
    def setup_ui(self):
        """設定介面"""
        self.setWindowTitle("BP2VPN Vision v2.0 - Ultra優化版")
        self.setGeometry(100, 100, 1200, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 標題
        title_label = QLabel("血壓資料匯出系統 - Ultra優化版")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 特色說明
        feature_label = QLabel("✓ 有血壓資料自動勾選 ✓ 輸入血壓後自動勾選 ✓ 超級優化算法 ✓ 只顯示最新記錄")
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
        
        # 時間範圍
        button_layout1.addWidget(QLabel("資料範圍:"))
        self.years_combo = QComboBox()
        self.years_combo.addItems(["1年內", "2年內", "3年內", "5年內", "全部"])
        self.years_combo.setCurrentText("3年內")
        button_layout1.addWidget(self.years_combo)
        
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
    
    def select_folder(self):
        """選擇資料夾"""
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
                years_text = self.years_combo.currentText()
                years_limit = {"1年內": 1, "2年內": 2, "3年內": 3, "5年內": 5, "全部": 10}[years_text]
                self.load_blood_pressure_ultra(str(co18h_path), patient_ids, years_limit)
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
    
    def load_blood_pressure_ultra(self, co18h_path: str, patient_ids: List[str], years_limit: int):
        """Ultra血壓載入"""
        self.status_bar.showMessage(f"Ultra載入中 - {years_limit}年內血壓資料...")
        self.progress_bar.setVisible(True)
        self.select_folder_btn.setEnabled(False)
        
        self.loading_thread = UltraLoadingThread(co18h_path, patient_ids, years_limit)
        self.loading_thread.progress.connect(self.on_loading_progress)
        self.loading_thread.finished.connect(self.on_loading_finished)
        self.loading_thread.start()
    
    def on_loading_progress(self, current: int, total: int):
        """更新進度"""
        percent = int(current * 100 / total) if total > 0 else 0
        self.progress_bar.setValue(percent)
        self.status_bar.showMessage(f"Ultra掃描中... {current}/{total} ({percent}%)")
    
    def on_loading_finished(self, bp_data: dict):
        """載入完成"""
        self.progress_bar.setVisible(False)
        self.select_folder_btn.setEnabled(True)
        
        self.table.update_blood_pressure_data(bp_data)
        
        # 統計
        total = len(self.table.patient_data)
        with_bp = sum(1 for data in bp_data.values() if data.get('systolic'))
        auto_selected = len(self.table.selected_patients)
        
        QMessageBox.information(
            self,
            "Ultra載入完成",
            f"Ultra優化載入完成!\\n\\n"
            f"📊 病患總數: {total} 筆\\n"
            f"💉 有血壓記錄: {with_bp} 筆\\n"
            f"☑️ 自動選擇: {auto_selected} 筆\\n\\n"
            f"✨ 特色功能已啟用:\\n"
            f"• 有血壓資料的病患已自動勾選\\n"
            f"• 輸入血壓值後會自動勾選\\n"
            f"• 只顯示每位病患的最新記錄"
        )
        
        self.enable_controls()
        self.update_stats()
        self.status_bar.showMessage("Ultra就緒 - 可以開始操作")
    
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
                    unique_patients.add(patient['pat_pid'].strip().zfill(7))
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
                    normalized_pid = patient_id.strip().zfill(7)
                    self.table.selected_patients.add(normalized_pid)
        
        selected = len(self.table.selected_patients)
        
        # 簡化統計顯示，只顯示總計和已選擇
        self.stats_label.setText(f"總計: {total} 筆 | 已選: {selected} 筆")
        
        # 調試資訊
        print(f"統計調試: 病患資料長度={len(self.table.patient_data) if self.table.patient_data else 0}, 表格行數={self.table.rowCount()}, 實際勾選={actual_selected}, 集合大小={selected}")
    
    def export_data(self):
        """匯出資料"""
        export_data = self.table.get_export_data()
        
        if not export_data:
            QMessageBox.warning(self, "警告", "請選擇至少一筆有血壓值的資料!")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "儲存XML檔案",
            f"bp_ultra_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml",
            "XML檔案 (*.xml)"
        )
        
        if not filename:
            return
        
        try:
            self.write_xml(export_data, filename)
            QMessageBox.information(
                self,
                "匯出成功",
                f"✅ Ultra匯出成功!\\n\\n"
                f"📁 檔案: {Path(filename).name}\\n"
                f"📊 匯出: {len(export_data)} 筆血壓資料\\n"
                f"📋 格式: 健保署XML規範"
            )
            self.status_bar.showMessage(f"Ultra匯出完成 - {len(export_data)} 筆資料")
            
        except Exception as e:
            QMessageBox.critical(self, "匯出錯誤", f"匯出失敗:\\n{str(e)}")
    
    def write_xml(self, data: List[Dict], filename: str):
        """寫入XML"""
        import xml.etree.ElementTree as ET
        from xml.dom import minidom
        
        root = ET.Element('patient')
        
        for patient in data:
            hdata = ET.SubElement(root, 'hdata')
            
            ET.SubElement(hdata, 'h1').text = '1'
            ET.SubElement(hdata, 'h2').text = '3522013684'
            ET.SubElement(hdata, 'h3').text = '11'
            ET.SubElement(hdata, 'h4').text = patient.get('bp_date', '')[:5]
            ET.SubElement(hdata, 'h5').text = f"{patient.get('bp_date', '')}{patient.get('bp_time', '')}"
            ET.SubElement(hdata, 'h6').text = '01'
            ET.SubElement(hdata, 'h7').text = '0023'
            ET.SubElement(hdata, 'h8').text = '1'
            
            if patient.get('pat_id'):
                ET.SubElement(hdata, 'h9').text = patient['pat_id']
            
            ET.SubElement(hdata, 'h10').text = patient['pat_pid'].zfill(7)
            ET.SubElement(hdata, 'h11').text = patient.get('bp_date', '')
            
            if patient.get('pat_namec'):
                ET.SubElement(hdata, 'h22').text = patient['pat_namec']
            
            # 收縮壓
            if patient.get('systolic', 0) > 0:
                rdata1 = ET.SubElement(hdata, 'rdata')
                ET.SubElement(rdata1, 'r1').text = '1'
                ET.SubElement(rdata1, 'r2').text = '收縮壓'
                ET.SubElement(rdata1, 'r3').text = '生理量測血壓(OBPM)'
                ET.SubElement(rdata1, 'r4').text = str(patient['systolic'])
                ET.SubElement(rdata1, 'r5').text = 'mmHg'
                ET.SubElement(rdata1, 'r6-1').text = '90-130'
            
            # 舒張壓
            if patient.get('diastolic', 0) > 0:
                rdata2 = ET.SubElement(hdata, 'rdata')
                ET.SubElement(rdata2, 'r1').text = '2'
                ET.SubElement(rdata2, 'r2').text = '舒張壓'
                ET.SubElement(rdata2, 'r3').text = '生理量測血壓(OBPM)'  
                ET.SubElement(rdata2, 'r4').text = str(patient['diastolic'])
                ET.SubElement(rdata2, 'r5').text = 'mmHg'
                ET.SubElement(rdata2, 'r6-1').text = '60-80'
        
        xml_str = ET.tostring(root, encoding='big5')
        dom = minidom.parseString(xml_str)
        
        with open(filename, 'w', encoding='big5') as f:
            f.write('<?xml version="1.0" encoding="Big5"?>\\n')
            pretty_xml = dom.documentElement.toprettyxml(indent='  ')
            f.write(pretty_xml)
    
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
    
    window = UltraMainWindow()
    window.show()
    
    QTimer.singleShot(800, lambda: QMessageBox.information(
        window,
        "🚀 BP2VPN Vision Ultra版",
        "🎯 血壓資料匯出系統 - Ultra優化版\\n\\n"
        "⚡ Ultra特色功能:\\n"
        "✅ 有血壓資料自動勾選\\n"
        "✅ 輸入血壓後自動勾選\\n"
        "✅ 超級優化載入算法\\n"
        "✅ 只保留最新一筆記錄\\n"
        "✅ 批次處理提升效能\\n\\n"
        "🎨 操作提示:\\n"
        "• 有血壓的病患會自動勾選\\n"
        "• 輸入血壓值會自動勾選該病患\\n"
        "• 綠色=已測量，黃色=待輸入"
    ))
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())