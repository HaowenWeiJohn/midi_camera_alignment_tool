# Installation

The tool is a standalone Python/PyQt5 application. It runs on Windows, macOS, and Linux.

## Prerequisites

- **Python 3.9 or newer** (tested on Python 3.10+). `from __future__ import annotations` is used throughout, so older Python versions are not supported.
- A working C/C++ runtime for the `opencv-python` wheels. On Linux this means `libgl1` and `libglib2.0` are usually required:

    ```bash
    sudo apt-get install libgl1 libglib2.0-0
    ```

## Install dependencies

Pick the recipe that matches how you manage Python environments — both are authoritative. The tool has no `requirements.txt`.

=== "pip"

    ```bash
    python -m pip install PyQt5 mido pretty_midi opencv-python numpy
    ```

    !!! tip "Use a virtual environment"
        Keep these dependencies isolated from your system Python:
        ```bash
        python -m venv .venv
        source .venv/bin/activate        # Linux / macOS
        .venv\Scripts\activate           # Windows PowerShell / cmd
        python -m pip install PyQt5 mido pretty_midi opencv-python numpy
        ```

=== "conda"

    All five dependencies are on `conda-forge`. The `pyqt=5` pin avoids picking up PyQt6, which the app does not support.

    ```bash
    conda create -n alignment -c conda-forge python=3.11 "pyqt=5" mido pretty_midi opencv numpy
    conda activate alignment
    ```

    If you already have a conda environment and just want to add the packages:

    ```bash
    conda install -c conda-forge "pyqt=5" mido pretty_midi opencv numpy
    ```

    !!! note "Package names on conda-forge"
        `pyqt` (with `=5` pin) provides **PyQt5**, and `opencv` provides the `cv2` Python binding — equivalent to `opencv-python` on PyPI. `mido`, `pretty_midi`, and `numpy` use the same names as pip.

## Get the code

Clone the repository:

```bash
git clone https://github.com/HaowenWeiJohn/midi_camera_alignment_tool.git
cd midi_camera_alignment_tool
```

There is no installable package — the app is run directly from the source checkout as a module (see [First launch](first-launch.md)).

## Verify the install

```bash
python -c "import PyQt5, mido, pretty_midi, cv2, numpy; print('OK')"
```

If that prints `OK`, you're ready to [prepare your data](data-layout.md) and [launch the app](first-launch.md).
