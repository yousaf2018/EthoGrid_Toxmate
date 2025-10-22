# EthoGrid-ToxMate: High-Speed Behavioral Analysis for Large-Volume Data

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![UI Framework](https://img.shields.io/badge/UI-PyQt5-green.svg)](https://pypi.org/project/PyQt5/)
[![Deep Learning](https://img.shields.io/badge/AI-YOLO-purple.svg)](https://ultralytics.com/)

**EthoGrid-ToxMate** is a specialized, high-performance desktop application engineered for researchers working with large-volume behavioral data, such as 24-hour recordings from automated systems like **ToxMate**. It provides a massively accelerated, end-to-end workflow to take you from raw, multi-hour videos to final, publication-ready statistical reports and graphs in a fraction of the time.

Every stage of the EthoGrid-ToxMate pipeline is designed to be **transparent, customizable, and efficient**, giving you full scientific control over your high-throughput data.

<p align="center">
  <img src="https://github.com/yousaf2018/EthoGrid_Toxmate/blob/main/images/android-chrome-512x512.png" alt="EthoGrid-ToxMate Logo" width="200">
</p>

![Tool Overview](https://raw.githubusercontent.com/yousaf2018/EthoGrid/main/images/EthoGridGUI.png)
*A snapshot of the EthoGrid-ToxMate interface showing a video with an overlaid grid, detections with centroids, a behavior legend, and a multi-tank timeline.*

---


## The EthoGrid-ToxMate Philosophy: Speed and Control for Big Data

Designed specifically to address the challenges of long-duration recordings, EthoGrid-ToxMate eliminates the bottlenecks of traditional analysis. It provides a single, unified platform optimized for speed:

1.  **High-Speed Video Preparation**: Automatically split massive 24-hour recordings into manageable 1-hour chunks with a single click, preserving original quality without slow re-encoding.
2.  **GPU-Accelerated AI Tracking**: Run high-performance YOLO models using an optimized process that maximizes GPU utilization, generating tracking data at high speeds.
3.  **Rapid Annotation & Cleaning**: Interactively align a virtual grid to your experimental setup once, then apply it to hundreds of video segments automatically in a powerful batch processing workflow.
4.  **Interactive Endpoint Calculation**: Compute a rich set of scientific endpoints with a powerful interactive tool. Visually validate and fine-tune parameters like the true center of each tank before running the final batch analysis.
5.  **One-Click Statistical Analysis**: Perform a full suite of statistical tests (T-test, ANOVA, Mann-Whitney, etc.) across multiple custom-named experimental groups and all relevant endpoints simultaneously, generating a folder of publication-quality plots and a consolidated data report with a single click.

---

## Table of Contents
- [Key Features](#key-features)
- [Standalone Utilities](#standalone-utilities)
- [The Complete Workflow](#the-complete-workflow-a-step-by-step-guide)
- [Documentation](#documentation)
- [Output Files](#output-files)
- [Getting Started for Users](#getting-started-for-users)
- [For Developers](#for-developers)
- [Contributing](#contributing)
- [License](#license)

---

## Key Features

-   **Optimized for High-Throughput**: Every module, from video splitting to statistical analysis, is designed to work in batch mode on large numbers of files, saving countless hours of manual work.
-   **High-Performance Processing**:
    -   **YOLO Inference**: Automatically detects and utilizes NVIDIA GPUs for massive speed improvements, with a graceful fallback to CPU.
    -   **Video Resizing**: Leverages NVIDIA GPU hardware acceleration (`h264_nvenc`) for extremely fast video downscaling.
-   **Interactive Grid System**:
    -   Define a virtual grid and interactively translate, rotate, and scale it for perfect alignment.
    -   **Settings Persistence**: Save and load complex grid configurations to a JSON file, ensuring reproducibility.
-   **Advanced Batch Processing & Data Cleaning**:
    -   Apply a saved grid configuration to entire datasets automatically.
    -   Filter detections within each tank to keep only the highest-confidence animal per frame.
-   **Comprehensive Data Export**:
    -   Generate annotated videos, trajectory plots, heatmaps, and multiple data formats (`.csv`, `.xlsx`).
-   **Interactive & Customizable Endpoints Analysis**:
    -   A dedicated module for calculating behavioral endpoints with visual validation.
    -   **Flexible Analysis Modes**: Switch between "Top View" and "Side View" modes with different parameters and endpoint calculations.
    -   **Per-Tank Customization**: Define different zone division axes for each individual tank to handle complex camera angles.
-   **Publication-Ready Statistical Analysis**:
    -   **Intelligent Test Selection**: Automatically performs normality tests and selects the appropriate significance test (T-test/ANOVA vs. Mann-Whitney/Kruskal-Wallis).
    -   **Full User Control**: Override automatic test selection and customize every aspect of your plots (colors, fonts, sizes, error bars, mean/median).
    -   **"Analyze All" Functionality**: Analyze all selected endpoints across multiple custom-named experimental groups with a single click.

---

## Standalone Utilities

-   **Video Splitter**: Optimized for splitting multi-hour recordings (e.g., 24-hour ToxMate videos) into manageable chunks without quality loss.
-   **Frame Extractor**: A powerful tool for creating datasets by recursively finding all videos in a directory and extracting random, traceable frames.
-   **Video Quality Control**: A high-speed, GPU-accelerated tool to downscale large video files (e.g., 4K to 1080p), saving disk space and speeding up subsequent analysis.

---

## The Complete Workflow: A Step-by-Step Guide

This workflow demonstrates how to go from a raw video to a final statistical graph.

1.  **Prepare Video (Optional)**: Use the **✂️ Video Splitter** to cut a long recording into 1-hour segments.
2.  **Generate Tracking Data**: Use **🎨 Run YOLO Segmentation...** to run your trained model on the video segments. This produces a raw `_segmentations.csv` file for each.
3.  **Annotate Data**: In the main window, **🎬 Load** a sample video and the corresponding `_segmentations.csv`. Interactively create and align the grid, then **💾 Save Settings** to a `grid.json` file.
4.  **Batch Process**: Use **🚀 Batch Annotation...** to apply your saved `grid.json` to all your video segments and their `_segmentations.csv` files. This will generate the final, clean `_with_tanks.csv` files.
5.  **Calculate Endpoints**: Use **📈 Run Analysis...** to process your `_with_tanks.csv` files. In this interactive dialog, you can fine-tune tank centers and other parameters, then run the analysis to produce a `consolidated_endpoints.xlsx` file.
6.  **Perform Statistics**: Use **📊 Statistical Analysis...** to load your `consolidated_endpoints.xlsx` files, assign them to Control and Treatment groups, select the endpoints you want to compare, and run the analysis. The result is a folder of publication-quality plots and a final statistical report.

---
## Documentation

For a deeper dive into the application's architecture and methods, please see the following guides:

-   **[Developer's Guide & Code Architecture](DEVELOPER_GUIDE.md)**: A comprehensive overview of the project structure, class responsibilities, and data flow. Essential reading for anyone looking to modify or contribute to the codebase.
-   **[Statistical Analysis Guide](STATISTICAL_ANALYSIS_GUIDE.md)**: A detailed explanation of every statistical test and calculation performed by the analysis module, including the formulas used and their scientific purpose.

---

## Output Files

1.  **From AI Inference**:
    -   `{video_name}_inference.mp4` / `_segmentation.mp4`: Videos showing the raw AI results.
    -   `{video_name}_detections.csv` / `_segmentations.csv`: The data files for the next stage.
2.  **From Batch Annotation**:
    -   `{video_name}_with_tanks.csv`: The final "long-format" data file with tank numbers.
    -   `{video_name}_centroids_wide.csv`: The final "wide-format" data file for statistical software.
    -   `{video_name}_by_tank.xlsx`: An Excel file with data for each tank on a separate sheet.
    -   `{video_name}_trajectory.png`: A high-quality image plotting the centroid paths.
    -   `{video_name}_heatmap.png`: A high-quality heatmap image superimposed on the video's first frame.
    -   `{video_name}_annotated.mp4`: A clean final video, with or without overlays.
3.  **From Endpoints Analysis**:
    -   `{video_name}_endpoints.csv`: A CSV file containing all calculated behavioral endpoints for each tank.

---

## Documentation

For a deeper dive into the application's architecture and methods, please see the following guides:

-   **[Developer's Guide & Code Architecture](DEVELOPER_GUIDE.md)**: A comprehensive overview of the project structure, class responsibilities, and data flow. Essential reading for anyone looking to modify or contribute to the codebase.
-   **[Statistical Analysis Guide](STATISTICAL_ANALYSIS_GUIDE.md)**: A detailed explanation of every statistical test and calculation performed by the analysis module, including the formulas used and their scientific purpose.

---


## Contributing

Contributions are welcome! Please fork the repository, create a feature branch, and submit a pull request.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/NewFeature`)
3.  Commit your Changes (`git commit -m 'Add some NewFeature'`)
4.  Push to the Branch (`git push origin feature/NewFeature`)
5.  Open a Pull Request

---

## Acknowledgements

This application was developed in the **[Laboratory of Professor Chung-Der Hsiao](https://cdhsiao.weebly.com/pi-cv.html)** in collaboration with **Chung Yuan Christian University, Taiwan 🇹🇼**. Special credit and sincere gratitude are extended to **Professor Hsiao**, who shared his extensive research experience in biology and multiple domains, providing invaluable guidance and supervision throughout the development of this application.

<p align="center">
  <a href="https://www.cycu.edu.tw/">
    <img src="https://raw.githubusercontent.com/yousaf2018/EthoGrid/main/images/cycu.jpg" alt="Chung Yuan Christian University Logo" width="250">
  </a>
</p>

---

## License


Distributed under the MIT License. See the `LICENSE` file for more information.











