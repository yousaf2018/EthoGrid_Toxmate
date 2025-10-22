# EthoGrid_App/workers/stats_processor.py

import os
import traceback
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib
# ### FIX for Matplotlib GUI warning ###
# Set the backend to a non-interactive one BEFORE importing pyplot
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from itertools import combinations
from PyQt5.QtCore import QThread, pyqtSignal

class StatsProcessor(QThread):
    finished = pyqtSignal()
    log = pyqtSignal(str)
    error = pyqtSignal(str)
    plot_generated = pyqtSignal(str, str)

    def __init__(self, group_files, analysis_level, endpoints_to_analyze, normality_test, alpha, force_parametric, parametric_test, nonparametric_test, plot_params, output_dir, parent=None):
        super().__init__(parent)
        self.group_files = group_files
        self.analysis_level = analysis_level
        self.endpoints_to_analyze = endpoints_to_analyze
        self.normality_test_name = normality_test
        self.alpha = alpha
        self.force_parametric = force_parametric
        self.parametric_test = parametric_test
        self.nonparametric_test = nonparametric_test
        self.plot_params = plot_params
        self.output_dir = output_dir
        self._is_running = True

    def stop(self):
        self._is_running = False

    def _load_data_for_level(self, file_paths, endpoint):
        # This method is unchanged
        all_rows = []
        for file_path in file_paths:
            try:
                if self.analysis_level == "Compare Grand Averages":
                    df = pd.read_excel(file_path, sheet_name='GRAND_AVERAGE_SUMMARY')
                    if endpoint in df.columns:
                        all_rows.append(df[[endpoint]])
                else:
                    xls = pd.ExcelFile(file_path)
                    for sheet_name in xls.sheet_names:
                        if sheet_name == 'GRAND_AVERAGE_SUMMARY': continue
                        df = pd.read_excel(xls, sheet_name=sheet_name)
                        if self.analysis_level == "Compare Sheet Averages":
                            df = df[df['Tank'] == 'AVERAGE']
                        else:
                            df = df[df['Tank'] != 'AVERAGE']
                        if endpoint in df.columns:
                            all_rows.append(df[[endpoint]])
            except Exception as e:
                self.log.emit(f"[WARNING] Could not process file {os.path.basename(file_path)}: {e}")
        if not all_rows: return pd.DataFrame()
        return pd.concat(all_rows, ignore_index=True)

    def run(self):
        try:
            full_report_data = []
            for i, endpoint in enumerate(self.endpoints_to_analyze):
                if not self._is_running: self.log.emit("Analysis cancelled."); break
                self.log.emit(f"\n--- Analyzing Endpoint {i+1}/{len(self.endpoints_to_analyze)}: {endpoint} ---")
                
                all_data = []
                for group_name, file_paths in self.group_files.items():
                    group_data_df = self._load_data_for_level(file_paths, endpoint)
                    if not group_data_df.empty:
                        group_data_df['Group'] = group_name
                        all_data.append(group_data_df)
                
                if len(all_data) < 1: self.log.emit(f"  - Skipping endpoint '{endpoint}': No data found."); continue
                
                df_endpoint = pd.concat(all_data, ignore_index=True)
                df_endpoint[endpoint] = pd.to_numeric(df_endpoint[endpoint], errors='coerce')
                df_endpoint.dropna(subset=[endpoint], inplace=True)
                
                if df_endpoint.empty or len(df_endpoint['Group'].unique()) < 2:
                    self.log.emit(f"  - Skipping: Not enough valid data points or groups for comparison."); continue
                
                report_rows, significance_results = self.perform_statistics(df_endpoint, endpoint)
                full_report_data.extend(report_rows)
                plot_path = self.generate_plot(df_endpoint, endpoint, significance_results)
                self.plot_generated.emit(endpoint, plot_path)
            
            if full_report_data:
                report_df = pd.DataFrame(full_report_data)
                report_path = os.path.join(self.output_dir, "statistical_summary_report.csv")
                report_df.to_csv(report_path, index=False, float_format='%.4f')
                self.log.emit(f"\n✓ Full statistical report saved to: {os.path.basename(report_path)}")

        except Exception as e:
            self.error.emit(f"An error occurred: {e}\n{traceback.format_exc()}")
        finally:
            self.finished.emit()

    def perform_statistics(self, df, endpoint):
        structured_results, significance_results = [], []
        groups = sorted(df['Group'].unique()); num_groups = len(groups)
        self.log.emit(f"ENDPOINT: {endpoint}")
        
        is_normal = True
        for group_name in groups:
            data = df[df['Group'] == group_name][endpoint].dropna()
            if len(data) < 3:
                self.log.emit(f"  - Normality for '{group_name}': Skipped (N < 3).")
                continue

            # ### FIX for "range zero" warning ###
            if np.ptp(data) == 0:
                self.log.emit(f"  - Normality ({self.normality_test_name}) for '{group_name}': Skipped (all values are identical). Data is considered NOT NORMAL.")
                is_normal = False
                continue

            if self.normality_test_name == "D'Agostino-Pearson": stat, p = stats.normaltest(data)
            else: stat, p = stats.shapiro(data)
            
            structured_results.append({'Endpoint': endpoint, 'Group': group_name, 'Test_Name': self.normality_test_name, 'Statistic': stat, 'P_Value': p, 'Conclusion': 'Normal' if p >= self.alpha else 'Not Normal'})
            self.log.emit(f"  - Normality ({self.normality_test_name}) for '{group_name}': p={p:.4f}")
            if p < self.alpha: is_normal = False
        
        use_parametric = is_normal or self.force_parametric
        if self.force_parametric and not is_normal: self.log.emit("Conclusion: Data is not normal, but PARAMETRIC test was forced by user.")
        elif is_normal: self.log.emit("Conclusion: Data appears normally distributed. Using PARAMETRIC tests.")
        else: self.log.emit("Conclusion: At least one group is not normally distributed. Using NON-PARAMETRIC tests.")

        if num_groups >= 2:
            pairs = list(combinations(groups, 2))
            for g1, g2 in pairs:
                g1_data, g2_data = df[df['Group'] == g1][endpoint], df[df['Group'] == g2][endpoint]
                if use_parametric:
                    test_name = "T-test"; stat, p = stats.ttest_ind(g1_data, g2_data, equal_var=True)
                else:
                    test_name = "Mann-Whitney U"; stat, p = stats.mannwhitneyu(g1_data, g2_data)
                
                self.log.emit(f"  - {test_name}: {g1} vs {g2}, p={p:.4f}")
                structured_results.append({'Endpoint': endpoint, 'Group': f"{g1} vs {g2}", 'Test_Name': test_name, 'Statistic': stat, 'P_Value': p, 'Conclusion': 'Significant' if p < self.alpha else 'Not Significant'})
                significance_results.append((g1, g2, p))
        
        return structured_results, significance_results

    def generate_plot(self, df, endpoint, significance_results):
        p = self.plot_params
        fig, ax = plt.subplots(figsize=(p['width'] / 100, p['height'] / 100), dpi=p['dpi'])
        font_title = {'fontsize': p['title_size'], 'fontweight': p['title_weight']}; font_axes = {'fontsize': p['axes_size'], 'fontweight': p['axes_weight']}
        
        error_map = {"SD": "sd", "SEM": lambda x: x.sem()}
        groups = sorted(df['Group'].unique())
        
        if p['central_tendency'] == 'Mean':
            central_data = df.groupby('Group')[endpoint].mean().reindex(groups)
            if p['error_bar'] == 'SD': error_data = df.groupby('Group')[endpoint].std().reindex(groups)
            else: error_data = df.groupby('Group')[endpoint].sem().reindex(groups)
        elif p['central_tendency'] == 'Median':
            central_data = df.groupby('Group')[endpoint].median().reindex(groups)
            error_data = None
        else:
            central_data = df.groupby('Group')[endpoint].mean().reindex(groups)
            error_data = None
            
        bar_positions = np.arange(len(groups))
        ax.bar(bar_positions, central_data, color=sns.color_palette(p['palette'], len(groups)), zorder=2)
        if error_data is not None:
            ax.errorbar(x=bar_positions, y=central_data, yerr=error_data, fmt='none', ecolor='black', capsize=5, elinewidth=1.5, zorder=3)
        
        sns.stripplot(x='Group', y=endpoint, data=df, ax=ax, color='black', alpha=0.5, order=groups, jitter=0.2, zorder=4)
        
        ax.set_title(f"Comparison of {endpoint}", fontdict=font_title); ax.set_xlabel("Experimental Group", fontdict=font_axes); ax.set_ylabel(endpoint, fontdict=font_axes)
        ax.set_xticks(bar_positions); ax.set_xticklabels(groups, rotation=45, ha='right', fontdict={'fontsize': p['tick_size']})
        ax.tick_params(axis='y', labelsize=p['tick_size'])

        if significance_results:
            y_max = (df.groupby('Group')[endpoint].mean() + df.groupby('Group')[endpoint].sem()).max()
            y_line = y_max * 1.15; line_offset = y_max * 0.08
            for g1, g2, p_val in significance_results:
                if p_val < self.alpha:
                    text = "***" if p_val < 0.001 else ("**" if p_val < 0.01 else "*")
                    x1, x2 = groups.index(g1), groups.index(g2)
                    ax.plot([x1, x1, x2, x2], [y_line, y_line*1.02, y_line*1.02, y_line], lw=1.5, c='black')
                    ax.text((x1 + x2) * .5, y_line * 1.02, text, ha='center', va='bottom', color='black', fontsize=14)
                    y_line += line_offset
        
        plt.tight_layout()
        safe_endpoint_name = endpoint.replace(' ', '_').replace('/', '_').replace('%', 'percent')[:50]
        plot_path = os.path.join(self.output_dir, f"{self.analysis_level.replace(' ', '_')}_{safe_endpoint_name}_plot.png")
        fig.savefig(plot_path, dpi=p['dpi']); plt.close(fig)
        return plot_path