# EthoGrid: Developer's Guide & Code Architecture

Welcome, developer! This document provides a high-level overview of the EthoGrid application's architecture. It is intended to help you understand how the different components interact so you can easily navigate the codebase, fix bugs, or add new features.

## Table of Contents
- [Core Philosophy](#core-philosophy)
- [Project Structure Overview](#project-structure-overview)
- [Detailed File Breakdown](#detailed-file-breakdown)
  - [1. `main.py`: The Entry Point](#1-mainpy-the-entry-point)
  - [2. `main_window.py`: The Application Hub](#2-main_windowpy-the-application-hub)
  - [3. The `core/` Directory: Central Logic & Utilities](#3-the-core-directory-central-logic--utilities)
  - [4. The `widgets/` Directory: Custom UI Components](#4-the-widgets-directory-custom-ui-components)
  - [5. The `workers/` Directory: The Background Powerhouses](#5-the-workers-directory-the-background-powerhouses)
- [Data Flow and Signal/Slot Mechanism](#data-flow-and-signalslot-mechanism)
- [How to Add a New Feature (Example)](#how-to-add-a-new-feature-example)

---

## Core Philosophy

EthoGrid-Toxmate is built on a few key principles:

1.  **Modularity**: Each file and class has a single, clear responsibility. This makes the code easier to read, test, and maintain.
2.  **Responsive UI**: The user interface must never freeze. All long-running tasks (video I/O, AI inference, data processing) are offloaded to background threads (`QThread`).
3.  **Decoupling**: The UI (widgets) is decoupled from the business logic (workers). They communicate using Qt's signal and slot mechanism.
4.  **Clear Data Flow**: Data flows predictably: from user input (files, UI controls) -> to a background worker for processing -> back to the main window or dialog for feedback.

---

## Project Structure Overview
```text
EthoGrid_App/
├── main.py
├── main_window.py
|
├── core/
│   ├── grid_manager.py
│   ├── data_exporter.py
│   ├── endpoints_analyzer.py
│   └── stopwatch.py
|
├── workers/
│   ├── video_loader.py
│   ├── detection_processor.py
│   ├── video_saver.py
│   ├── yolo_processor.py
│   ├── yolo_segmentation_processor.py
│   ├── batch_processor.py
│   ├── video_splitter.py
│   ├── frame_extractor.py
│   ├── analysis_processor.py
│   └── stats_processor.py
|
└── widgets/
    ├── timeline_widget.py
    ├── range_slider.py
    ├── yolo_inference_dialog.py
    ├── yolo_segmentation_dialog.py
    ├── batch_dialog.py
    ├── video_splitter_dialog.py
    ├── frame_extractor_dialog.py
    ├── analysis_dialog.py
    └── stats_dialog.py
```
### Detailed File Breakdown

#### 1. `main.py`: The Entry Point
The simplest file. Its only job is to initialize the `QApplication`, set high-DPI scaling, and launch the `VideoPlayer` from `main_window.py`.

#### 2. `main_window.py`: The Application Hub
The central controller of the application.
-   **Class**: `VideoPlayer(QtWidgets.QWidget)`
-   **Responsibilities**:
    -   **UI Construction**: Builds the main window, toolbars, and the interactive control sidebar.
    -   **State Management**: Holds the application's current interactive state (`self.raw_detections`, `self.processed_detections`, etc.).
    -   **Dialog Management**: Instantiates and launches all tool dialogs (YOLO, Batch, Analysis, Stats, etc.).
    -   **Interactive Visualization**: The `update_display` method uses OpenCV to render the video frame with all live annotations.

#### 3. The `core/` Directory: Central Logic & Utilities
-   **`core/grid_manager.py`**: Manages the grid's properties (center, angle, scale) and the corresponding `QTransform` matrix.
-   **`core/data_exporter.py`**: Contains all logic for creating the final output files (CSVs, Excel, Trajectory Plots, Heatmaps).
-   **`core/endpoints_analyzer.py`**: The scientific engine for calculating behavioral endpoints. It features two distinct modes (Side View and Top View) and performs complex geometric calculations based on user-defined parameters.
-   **`core/stopwatch.py`**: A helper class for calculating elapsed time and ETR.

#### 4. The `widgets/` Directory: Custom UI Components
-   **`widgets/timeline_widget.py`**: A custom-painted widget that draws the multi-tank behavior timeline.
-   **`widgets/range_slider.py`**: A custom double-ended slider for defining the "Top" and "Bottom" zones in the Endpoints Analysis dialog.
-   **`widgets/yolo..._dialog.py`, `batch_dialog.py`, `video_splitter_dialog.py`, `frame_extractor_dialog.py`**: These are `QDialog` subclasses for specific tasks. They all share a consistent UI pattern: a file/directory input section, a parameter section, and a progress/log section. They are responsible for collecting user input and launching the appropriate worker.
-   **`widgets/analysis_dialog.py`**: A highly interactive dialog for calculating endpoints. Its key feature is the live visualization pane, which allows users to load a sample video and grid to visually confirm and adjust parameters (like tank centers) before running the analysis.
-   **`widgets/stats_dialog.py`**: The final analysis stage. This dialog allows users to design a statistical comparison between experimental groups.
    -   **Dynamic UI**: The UI dynamically creates sections for each experimental group defined by the user.
    -   **Flexible Data Grouping**: Users can assign `.xlsx` files to different groups (e.g., "Control", "Treatment A").
    -   **Multi-Level Analysis**: A master dropdown lets the user choose the level of comparison: between individual tanks, between sheet averages, or between grand averages across files.

#### 5. The `workers/` Directory: The Background Powerhouses
All classes here are `QThread` subclasses, designed for long-running tasks.
-   **`workers/video_loader.py` & `video_saver.py`**: Handle video file I/O. `video_saver.py` contains the `_get_clipped_mask` method to visually clip overflowing segmentation masks to their tank boundaries.
-   **`workers/detection_processor.py`**: The interactive processing engine for the main window. It takes raw detections and applies the current grid transform and filters.
-   **`workers/yolo..._processor.py`**: Run high-speed YOLO inference using a robust two-stage process (GPU-bound inference followed by CPU-bound post-processing) with a fallback to a safer frame-by-frame method.
-   **`workers/batch_processor.py`**: Orchestrates the non-interactive grid annotation and export workflow.
-   **`workers/video_splitter.py` & `frame_extractor.py`**: Backend logic for the utility tools.
-   **`workers/analysis_processor.py`**: The batch engine for calculating endpoints. It iterates through each tank in each input file, creates a `pandas` DataFrame for that specific subset of data, and passes it along with a rich `params` dictionary to an `EndpointsAnalyzer` instance. It consolidates all results into a multi-sheet Excel file.
-   **`workers/stats_processor.py`**: The final statistical engine.
    -   **Magic**: It receives a complex set of instructions from the `StatsDialog`, including the analysis level, group assignments, and a list of endpoints to analyze. It loops through each endpoint, aggregates the correct data from the input Excel files based on the chosen level, performs normality tests, automatically selects and runs the appropriate significance test (e.g., T-test or Mann-Whitney), and generates a publication-quality plot and a detailed report entry for each.

### Data Flow and Signal/Slot Mechanism
Understanding the signal/slot mechanism is key to understanding EthoGrid.

**Example Flow: Statistical Analysis**
1.  **User**: In `StatsDialog`, assigns a "Control" file and a "Treatment" file, selects "Compare Grand Averages", checks three endpoints to analyze, and clicks "Run Analysis".
2.  **`stats_dialog.py`**: The `start_analysis` slot gathers all this information into a `group_files` dictionary and a `plot_params` dictionary. It creates a `StatsProcessor` instance, moves it to a `QThread`, connects signals (`plot_generated`, `log`, etc.) to its own update slots, and starts the thread.
3.  **`stats_processor.py`**: The `run()` method starts its main loop over the three selected endpoints.
    -   For "Endpoint 1", it calls `_load_data_for_level` to read the "GRAND_AVERAGE_SUMMARY" sheet from the Control and Treatment files.
    -   It runs `perform_statistics` to get the p-value.
    -   It runs `generate_plot` to create the PNG file.
    -   It emits a `plot_generated` signal with the path to the new plot.
    -   The loop repeats for "Endpoint 2" and "Endpoint 3".
4.  **`stats_dialog.py`**: The dialog's `add_plot_tab` slot receives each `plot_generated` signal as it's emitted. It creates a new tab with the plot image, allowing the user to see results as they are generated. The `log` signal updates the text report in real-time.

### How to Add a New Feature (Example)
Let's say you want to add a new endpoint, "Path Convexity".
1.  **Add the Logic**: In `core/endpoints_analyzer.py`, create a new helper function `calculate_convexity(...)` that takes a list of coordinates. In the `analyze` method, call this function and store the result in `self.results['Path Convexity']`.
2.  **Add to UI**: In `widgets/analysis_dialog.py`, add a new `QtWidgets.QCheckBox("Path Convexity")` to the appropriate endpoint dictionary (e.g., `top_view_endpoints_checkboxes`).
3.  **That's it!** The existing architecture will handle the rest. The `start_analysis` method will automatically pick up the new checkbox, the `analysis_processor` will pass it along in the `params`, and the `endpoints_analyzer` will see it in the `selected_endpoints` list and include it in the final filtered output.
