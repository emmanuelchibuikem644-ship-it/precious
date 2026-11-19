# Smart Attendance System Using Face Recognition

Desktop application for the Department of Computer Science, Ignatius Ajuru University of Education.
Python 3.10+ | OpenCV | dlib (HOG detector + ResNet-34 face encoder) | SQLite | Tkinter

## Install
```
python -m venv venv
venv\Scripts\activate            (Windows)        source venv/bin/activate   (Linux / macOS)
pip install numpy opencv-python Pillow bcrypt cryptography reportlab
pip install dlib-bin face_recognition_models
pip install --no-deps face_recognition
```
(`dlib-bin` is a pre-built wheel; it avoids compiling dlib. If you prefer to compile, `pip install dlib face_recognition`
works when CMake and a C++ compiler are installed.)

## Run
```
python main.py
```
On first launch the program asks you to create the administrator account. A USB or built-in webcam is required for
enrolment and live attendance. Data is stored in the `data/` folder next to the program (set `SAFR_DATA_DIR` to move it).

## Test
```
pip install pytest scikit-image matplotlib
python -m pytest -v                 # 85 tests; the 9 GUI tests need a display (use xvfb-run on a headless Linux machine)
python tools/benchmark.py           # processing-time measurements on your computer
python tools/robustness.py          # lighting / blur / tilt / distance / occlusion experiment
```

## Layout
- `main.py`, `config.py`  - entry point and every adjustable setting (tolerance 0.60, 3-frame confirmation, 30-minute time-out ...)
- `core/`   - database, security (bcrypt, AES-256-GCM, sessions), face engine, attendance rules, camera, reports, backup
- `ui/`     - Tkinter screens (login, dashboard, students, courses, attendance, reports, administration)
- `tests/`  - automated tests
- `tools/`  - benchmark, robustness experiment, demonstration harness (synthetic camera + scripted recogniser), screenshot driver

## Privacy
Only 128-number face encodings are stored (never photographs), inside AES-256-GCM encrypted files. Consent must be confirmed
before enrolment, and a student's record and template can be erased from the Students screen.
