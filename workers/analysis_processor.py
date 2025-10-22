# EthoGrid_App/workers/analysis_processor.py

import os
import csv
import json
import traceback
import pandas as pd
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QTransform

from core.endpoints_analyzer import EndpointsAnalyzer

def find_common_prefix(filenames):
    """Finds the longest common starting string from a list of filenames."""
    if not filenames:
        return "analysis"
    # Use os.path.commonprefix on the basenames without extensions
    basenames = [os.path.splitext(os.path.basename(f))[0] for f in filenames]
    prefix = os.path.commonprefix(basenames)
    # Clean up trailing characters that are often part of separators
    return prefix.strip('_- ')

class AnalysisProcessor(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal()
    log = pyqtSignal(str)

    def __init__(self, csv_files, params, output_dir, parent=None):
        super().__init__(parent)
        self.csv_files = csv_files
        self.params = params
        self.output_dir = output_dir
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        grand_total_results = []
        total_files = len(self.csv_files)
        
        # ### THE FIX IS HERE ###
        # Generate the output filename based on the common prefix of the input files
        common_prefix = find_common_prefix(self.csv_files)
        output_filename = f"{common_prefix}_endpoints.xlsx"
        output_path = os.path.join(self.output_dir, output_filename)
        
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                for i, file_path in enumerate(self.csv_files):
                    if not self._is_running: self.log.emit("Analysis cancelled."); break
                    
                    filename = os.path.basename(file_path)
                    self.progress.emit(i, total_files, filename)
                    self.log.emit(f"\nAnalyzing file {i+1}/{total_files}: {filename}")

                    try:
                        df = pd.read_csv(file_path)
                        required_cols = ['frame_idx', 'cx', 'cy', 'tank_number']
                        if not all(col in df.columns for col in required_cols):
                            self.log.emit(f"[WARNING] Skipping {filename}: missing required columns."); continue
                        
                        current_file_results = []
                        for tank_num in sorted(df['tank_number'].unique()):
                            if pd.isna(tank_num): continue
                            if not self._is_running: break
                            
                            tank_num = int(tank_num)
                            self.log.emit(f"  - Processing Tank {tank_num}...")
                            tank_df = df[df['tank_number'] == tank_num].copy()
                            
                            if len(tank_df) < 3:
                                self.log.emit(f"  - Skipping Tank {tank_num}: not enough data points."); continue

                            current_tank_params = self.params.copy()
                            if 'adjusted_tank_centers' in self.params and tank_num in self.params['adjusted_tank_centers']:
                                current_tank_params['tank_center'] = self.params['adjusted_tank_centers'][tank_num]
                            if 'tank_corners' in self.params and tank_num in self.params['tank_corners']:
                                current_tank_params['tank_corners'] = self.params['tank_corners'][tank_num]
                            if self.params['analysis_mode'] == 'Side View' and 'side_view_configs' in self.params and tank_num in self.params['side_view_configs']:
                                tank_config = self.params['side_view_configs'][tank_num]
                                current_tank_params['side_view_axis'] = self.params.get('side_view_axis', 'Top-Bottom')
                                current_tank_params['zone1_percent'] = tank_config.get('zone1', 33)
                                current_tank_params['zone2_percent'] = tank_config.get('zone2', 33)
                            
                            analyzer = EndpointsAnalyzer(tank_df, current_tank_params)
                            endpoints = analyzer.analyze()
                            endpoints['File'] = filename; endpoints['Tank'] = tank_num
                            current_file_results.append(endpoints)
                        
                        if current_file_results:
                            file_df = pd.DataFrame(current_file_results)
                            numeric_cols = [col for col in file_df.columns if col not in ['File', 'Tank']]
                            for col in numeric_cols:
                                file_df[col] = pd.to_numeric(file_df[col], errors='coerce')
                            
                            avg_row = file_df[numeric_cols].mean().to_dict()
                            avg_row['File'] = filename; avg_row['Tank'] = 'AVERAGE'
                            avg_df = pd.DataFrame([avg_row])

                            final_file_df = pd.concat([file_df, avg_df], ignore_index=True)
                            
                            cols = final_file_df.columns.tolist()
                            if 'File' in cols and 'Tank' in cols:
                                cols.insert(0, cols.pop(cols.index('Tank'))); cols.insert(0, cols.pop(cols.index('File')))
                                final_file_df = final_file_df[cols]
                            
                            sheet_name = os.path.splitext(filename)[0]
                            invalid_chars = r'[]:*?/\\ '; [sheet_name := sheet_name.replace(char, '_') for char in invalid_chars]
                            if len(sheet_name) > 31:
                                sheet_name = sheet_name[-31:]

                            self.log.emit(f"  - Writing sheet: {sheet_name}")
                            final_file_df.to_excel(writer, sheet_name=sheet_name, index=False, float_format="%.4f")
                            
                            grand_total_results.extend(current_file_results)

                    except Exception as e:
                        self.log.emit(f"[ERROR] Failed to process {filename}: {e}"); self.log.emit(traceback.format_exc()); continue
                
                if grand_total_results:
                    self.log.emit("\n--- Writing final summary sheet ---")
                    grand_df = pd.DataFrame(grand_total_results)
                    numeric_cols = [col for col in grand_df.columns if col not in ['File', 'Tank']]
                    for col in numeric_cols:
                        grand_df[col] = pd.to_numeric(grand_df[col], errors='coerce')

                    grand_avg_row = grand_df[numeric_cols].mean().to_frame().T
                    grand_avg_row['File'] = 'GRAND AVERAGE'; grand_avg_row['Tank'] = ''
                    
                    cols = grand_avg_row.columns.tolist()
                    cols.insert(0, 'Tank'); cols.insert(0, 'File')
                    
                    grand_avg_row[cols].to_excel(writer, sheet_name='GRAND_AVERAGE_SUMMARY', index=False, float_format="%.4f")

            self.log.emit(f"\n✓ Successfully saved consolidated results to: {output_filename}")

        except Exception as e:
            self.log.emit(f"[ERROR] Failed to create or write to Excel file: {e}")
            self.log.emit(traceback.format_exc())

        self.progress.emit(total_files, total_files, "Finished")
        self.finished.emit()