# EthoGrid-Toxmate: Developer's Guide & Code Architecture

Welcome, developer! This document provides a high-level overview of the EthoGrid application's architecture. It is intended to help you understand how the different components interact so you can easily navigate the codebase, fix bugs, or add new features.

## Table of Contents
- [Core Philosophy](#core-philosophy)
- [Project Structure Overview](#project-structure-overview)
- [Detailed File Breakdown](#detailed-file-breakdown)
  - [1. `main.py`: The Entry Point](#1-mainpy-the-entry-point)
  - [2. `main_window.py`: The Application Hub](#2-main_windowpy-the-application-hub)
  - [3. The `core/` Directory: Central Logic & Utilities](#3-the-core-directory-central-logic--utilities)
    - [`core/grid_manager.py`](#coregrid_managerpy)
    - [`core/data_exporter.py`](#coredata_exporterpy)
    - [`core/endpoints_analyzer.py`](#coreendpoints_analyzerpy)
    - [`core/stopwatch.py`](#corestopwatchpy)
  - [4. The `widgets/` Directory: Custom UI Components](#4-the-widgets-directory-custom-ui-components)
    - [`widgets/timeline_widget.py`](#widgetstimeline_widgetpy)
    - [`widgets/yolo_inference_dialog.py` & `yolo_segmentation_dialog.py`](#widgetsyolo_inference_dialogpy--yolo_segmentation_dialogpy)
    - [`widgets/batch_dialog.py`](#widgetsbatch_dialogpy)
    - [`widgets/video_splitter_dialog.py` & `frame_extractor_dialog.py`](#widgetsvideo_splitter_dialogpy--frame_extractor_dialogpy)
    - [`widgets/analysis_dialog.py`](#widgetsanalysis_dialogpy)
  - [5. The `workers/` Directory: The Background Powerhouses](#5-the-workers-directory-the-background-powerhouses)
    - [`workers/video_loader.py` & `video_saver.py`](#workersvideo_loaderpy--video_saverpy)
    - [`workers/detection_processor.py`](#workersdetection_processorpy)
    - [`workers/yolo_processor.py` & `yolo_segmentation_processor.py`](#workersyolo_processorpy--yolo_segmentation_processorpy)
    - [`workers/batch_processor.py`](#workersbatch_processorpy)
    - [`workers/video_splitter.py` & `frame_extractor.py`](#workersvideo_splitterpy--frame_extractorpy)
    - [`workers/analysis_processor.py`](#workersanalysis_processorpy)
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
│   └── analysis_processor.py
|
└── widgets/
    ├── timeline_widget.py
    ├── yolo_inference_dialog.py
    ├── yolo_segmentation_dialog.py
    ├── batch_dialog.py
    ├── video_splitter_dialog.py
    ├── frame_extractor_dialog.py
    └── analysis_dialog.py
```
---

## Detailed File Breakdown

### 1. `main.py`: The Entry Point
The simplest file. Its only job is to initialize the `QApplication`, set high-DPI scaling, and launch the `VideoPlayer` from `main_window.py`.

### 2. `main_window.py`: The Application Hub
The central controller of the application.
-   **Class**: `VideoPlayer(QtWidgets.QWidget)`
-   **Responsibilities**:
    -   **UI Construction**: Builds the main window, toolbars, and the interactive control sidebar.
    -   **State Management**: Holds the application's current interactive state (`self.raw_detections`, `self.processed_detections`, `self.current_frame`, etc.).
    -   **Dialog Management**: Instantiates and launches all tool dialogs (YOLO, Batch, Analysis, etc.).
    -   **Interactive Visualization**: The `update_display` method uses OpenCV to render the video frame with all live annotations (grid, boxes, masks, centroids).

### 3. The `core/` Directory: Central Logic & Utilities

#### `core/grid_manager.py`
-   **Class**: `GridManager(QObject)`
-   **Responsibilities**: Exclusively manages the grid's properties (`center`, `angle`, `scale`). It maintains a `QTransform` matrix, recalculating it and emitting a signal whenever a property changes.

#### `core/data_exporter.py`
-   **Functions**: `export_...(...)`
-   **Responsibilities**: Contains all logic for creating the final output files from the Batch Annotation tool.
    -   `export_centroid_csv`: Creates the wide-format CSV for statistical software.
    -   `export_to_excel_sheets`: Creates the multi-sheet `.xlsx` file.
    -   `export_trajectory_image`: Generates the trajectory plot, correctly handling grid transformations and user-defined sampling rates/time gaps.
    -   `export_heatmap_image`: Generates the heatmap plot superimposed on the video's first frame.

#### `core/endpoints_analyzer.py`
-   **Class**: `EndpointsAnalyzer`
-   **Responsibilities**: Contains the pure scientific logic for calculating all behavioral endpoints for a **single tank's data**. It correctly calculates the true geometric center of a transformed tank and derives all metrics from that.

#### `core/stopwatch.py`
-   **Class**: `Stopwatch`
-   **Responsibilities**: A reusable helper class to calculate elapsed time and Estimated Time Remaining (ETR).

### 4. The `widgets/` Directory: Custom UI Components

All files here are `QtWidgets.QDialog` subclasses that provide the user interface for a specific long-running task.

#### `widgets/timeline_widget.py`
-   **Class**: `TimelineWidget(QtWidgets.QWidget)`
-   **Responsibilities**: A fully custom-painted widget that uses `QPainter` to draw the multi-tank behavior timeline.

#### `widgets/yolo_inference_dialog.py` & `yolo_segmentation_dialog.py`
-   **Responsibilities**: These dialogs manage the UI for running YOLO inference. They include robust file input (single, multiple, or directory), list management (remove/clear), and inference options like confidence and GPU batch size. They launch their respective `Yolo...Processor` workers.

#### `widgets/batch_dialog.py`
-   **Responsibilities**: Manages the UI for the main data annotation and export workflow. It combines file inputs with a `settings.json` input and provides checkboxes for all possible output formats (annotated video, various CSVs, Excel, trajectory plots, and heatmaps).

#### `widgets/video_splitter_dialog.py` & `frame_extractor_dialog.py`
-   **Responsibilities**: These are UIs for the standalone utility tools. They handle user input (e.g., chunk duration, number of frames to extract) and launch their respective worker threads.

#### `widgets/analysis_dialog.py`
-   **Responsibilities**: Manages the UI for the final endpoints analysis. It requires the user to provide the annotated CSVs and the `settings.json` file used to create them, ensuring scientifically accurate calculations.

### 5. The `workers/` Directory: The Background Powerhouses

All classes here are `QThread` subclasses, designed for long-running tasks.

#### `workers/video_loader.py` & `video_saver.py`
-   **Purpose**: Handle video file I/O for live playback and saving annotated videos, respectively.
-   **Magic (`video_saver.py`)**: Contains the `_get_clipped_mask` method to visually clip overflowing segmentation masks to their tank boundaries for cleaner video output.

#### `workers/detection_processor.py`
-   **Purpose**: The interactive processing engine for the main window. It takes raw detections, applies the current grid transform and "Max Animals per Tank" filter, and emits the processed data for live visualization.

#### `workers/yolo_processor.py` & `yolo_segmentation_processor.py`
-   **Purpose**: To run high-speed YOLO inference.
-   **Magic**: They implement a robust, two-stage process. **Stage 1** calls `model.predict()` on the entire video file at once, leveraging the `ultralytics` library's internal optimizations to maximize GPU/CPU throughput and save raw results to temporary text files. **Stage 2** then reads these text files frame-by-frame to perform custom logic (insetting, centroid calculation) and generate the final CSV and video files. They also include a fallback to a slower frame-by-frame method if the high-speed approach fails.

#### `workers/batch_processor.py`
-   **Purpose**: To orchestrate the non-interactive grid annotation and export workflow.
-   **Magic**: This is a master worker that loads detection data, applies the grid transform and "Max Animals" filter, and then calls the various export functions from `data_exporter.py` based on the user's selections.

#### `workers/video_splitter.py` & `frame_extractor.py`
-   **Purpose**: Backend logic for the utility tools. They use external libraries (`ffmpeg`) or custom logic (`random.sample`) to perform their tasks. `frame_extractor.py` notably uses a robust file naming convention to ensure extracted frames are always traceable to their source video's subfolder structure.

#### `workers/analysis_processor.py`
-   **Purpose**: To run the final endpoints analysis in batch.
-   **Magic**: It loads the `settings.json` to get the true grid and video dimensions. For each input CSV, it iterates through each tank, creates a new `pandas` DataFrame for that tank's data, and passes it to an `EndpointsAnalyzer` instance for calculation.

---

## Data Flow and Signal/Slot Mechanism

Understanding the signal/slot mechanism is key to understanding EthoGrid.

**Example Flow: Batch Processing**
1.  **User**: Fills out the `BatchProcessDialog` and clicks "Start".
2.  **`batch_dialog.py`**: The `start_processing` slot creates a `BatchProcessor` instance, moves it to a `QThread`, connects signals (`overall_progress`, `file_progress`, etc.) to its own update slots, and starts the thread.
3.  **`batch_processor.py`**: The `run()` method starts its main loop. For each video, it performs the complex logic of loading, assigning, filtering, and then calls the appropriate export functions from `core/data_exporter.py`. It emits progress signals throughout.
4.  **`batch_dialog.py`**: The dialog's slots (`update_file_progress`, etc.) receive these signals and update the GUI elements in real-time, keeping the user informed without freezing the UI.

---

## How to Add a New Feature (Example)

Let's say you want to add a feature to export a summary report (e.g., total time spent on each behavior per tank).

1.  **Add a UI Element**: In `main_window.py`'s `setup_ui`, add a `self.export_report_btn = QPushButton("Export Report")`.
2.  **Create a Utility Function**: In `core/data_exporter.py`, add a new function `export_summary_report(...)`. This function would take `processed_detections` and `fps` as input, calculate the statistics using `pandas`, and save them to a CSV.
3.  **Connect in Main Window**: In `main_window.py`, create a new slot `export_report`. In `setup_connections`, connect the button's `clicked` signal to this slot.
4.  **Implement the Slot**: The `export_report` method would:
    -   Open a file save dialog.
    -   Call the `export_summary_report` function from the `core` module.
    -   Show a success or failure message box based on the return value.
