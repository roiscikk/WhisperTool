import sys
import os
import subprocess
import platform
import tempfile
import time
import json
import wave
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QTextEdit, QFileDialog,
    QMessageBox, QProgressBar, QListWidget, QCheckBox, QDialog,
    QFormLayout, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPalette, QColor

import whisper
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

AUDIO_RECORDING_AVAILABLE = SOUNDDEVICE_AVAILABLE and NUMPY_AVAILABLE


def format_timestamp(seconds: float, always_include_hours: bool = False, decimal_marker: str = '.'):
    assert seconds >= 0
    milliseconds = round(seconds * 1000.0)
    hours = milliseconds // 3_600_000
    milliseconds -= hours * 3_600_000
    minutes = milliseconds // 60_000
    milliseconds -= minutes * 60_000
    seconds = milliseconds // 1_000
    milliseconds -= seconds * 1_000
    hours_marker = f"{hours:02d}:" if always_include_hours or hours > 0 else ""
    return f"{hours_marker}{minutes:02d}:{seconds:02d}{decimal_marker}{milliseconds:03d}"

def write_srt(segments, file):
    for i, segment in enumerate(segments, start=1):
        start = format_timestamp(segment['start'], always_include_hours=True, decimal_marker=',')
        end = format_timestamp(segment['end'], always_include_hours=True, decimal_marker=',')
        file.write(f"{i}\n{start} --> {end}\n{segment['text'].strip()}\n\n")

def write_vtt(segments, file):
    file.write("WEBVTT\n\n")
    for segment in segments:
        start = format_timestamp(segment['start'], always_include_hours=True, decimal_marker='.')
        end = format_timestamp(segment['end'], always_include_hours=True, decimal_marker='.')
        file.write(f"{start} --> {end}\n{segment['text'].strip()}\n\n")

def write_tsv(segments, file):
    file.write("start\tend\ttext\n")
    for segment in segments:
        start = format_timestamp(segment["start"], always_include_hours=True, decimal_marker=".")
        end = format_timestamp(segment["end"], always_include_hours=True, decimal_marker=".")
        text = segment.get("text", "").strip().replace("\t", " ").replace("\n", " ").replace("\r", " ")
        file.write(f"{start}\t{end}\t{text}\n")

def write_json(segments, file):
    json.dump(segments, file, ensure_ascii=False, indent=2)
    file.write("\n")


SETTINGS_FILENAME = ".settings.json"

DEFAULT_SETTINGS = {
    "vad": False,
    "dark_mode": False,
    "model": "base",
    "device": "cpu",
    "language": "Auto",
    "translate": False,
    "translate_to": "en",
    "mic_device": None,
    "app_language": "en",
    "export_format": "txt",
    "last_open_dir": "",
    "last_save_dir": "",
}

LANG_CHOICES = [
    ("en", "English"),
    ("tr", "Turkish"),
    ("de", "German"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("it", "Italian"),
    ("ru", "Russian"),
    ("zh", "Chinese"),
    ("ja", "Japanese"),
]

def language_label(code: str) -> str:
    for c, lbl in LANG_CHOICES:
        if c == code:
            return lbl
    return code

UI_STRINGS = {
    "en": {
        "model": "Model:",
        "device": "Device:",
        "language": "Language:",
        "translate_to": "Translate to {lang}",
        "settings": "Settings",
        "settings_title": "Settings",
        "settings_vad": "Enable VAD (Silence Skipping):",
        "settings_dark_mode": "Dark Mode:",
        "settings_app_language": "App language:",
        "settings_transcription_language": "Transcription language:",
        "settings_translate_to": "Translate to:",
        "settings_microphone": "Microphone:",
        "settings_export_format": "Default Export Format:",
        "settings_ok": "OK",
        "settings_cancel": "Cancel",
        "add_files": "Add Files",
        "clear_list": "Clear List",
        "start_mic": "Start Mic Rec",
        "stop_mic": "Stop Mic Rec",
        "transcribe_one": "Transcribe",
        "transcribe_batch": "Transcribe Batch",
        "output_logs": "Output / Logs:",
        "export": "Export ({fmt})",
        "select_media_title": "Select Media Files",
        "warning": "Warning",
        "no_files": "No files to transcribe.",
    },
    "tr": {
        "model": "Model:",
        "device": "Cihaz:",
        "language": "Dil:",
        "translate_to": "{lang} diline çevir",
        "settings": "Ayarlar",
        "settings_title": "Ayarlar",
        "settings_vad": "VAD (Sessizliği atla):",
        "settings_dark_mode": "Karanlık mod:",
        "settings_app_language": "Uygulama dili:",
        "settings_transcription_language": "Transkripsiyon dili:",
        "settings_translate_to": "Çeviri hedefi:",
        "settings_microphone": "Mikrofon:",
        "settings_export_format": "Varsayılan export formatı:",
        "settings_ok": "Tamam",
        "settings_cancel": "İptal",
        "add_files": "Dosya Ekle",
        "clear_list": "Listeyi Temizle",
        "start_mic": "Mikrofon Kaydı Başlat",
        "stop_mic": "Mikrofon Kaydını Durdur",
        "transcribe_one": "Çevir",
        "transcribe_batch": "Toplu Çevir",
        "output_logs": "Çıktı / Log:",
        "export": "Dışa Aktar ({fmt})",
        "select_media_title": "Medya Dosyaları Seç",
        "warning": "Uyarı",
        "no_files": "Transcribe edilecek dosya yok.",
    },
}

def ui_lang(settings: dict) -> str:
    lang = settings.get("app_language", "en")
    return lang if lang in UI_STRINGS else "en"

SUPPORTED_MEDIA_EXTS = {
    ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma", ".aac", ".opus", ".aiff", ".aif", ".alac",
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v",
}

def settings_path() -> Path:
    return Path(__file__).resolve().parent / SETTINGS_FILENAME

def load_settings() -> dict:
    path = settings_path()
    if not path.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return dict(DEFAULT_SETTINGS)
        merged = dict(DEFAULT_SETTINGS)
        merged.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
        return merged
    except Exception:
        return dict(DEFAULT_SETTINGS)

def save_settings(data: dict) -> None:
    path = settings_path()
    safe = dict(DEFAULT_SETTINGS)
    safe.update({k: data.get(k, DEFAULT_SETTINGS[k]) for k in DEFAULT_SETTINGS})
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

def is_supported_media_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_MEDIA_EXTS

def media_file_dialog_filter() -> str:
    exts = sorted({e.lstrip(".") for e in SUPPORTED_MEDIA_EXTS})
    patterns = " ".join(f"*.{e}" for e in exts)
    return f"Media Files ({patterns});;All Files (*)"

def gather_supported_files(paths: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            for child in pp.rglob("*"):
                if is_supported_media_file(child):
                    s = str(child.resolve())
                    if s not in seen:
                        out.append(s)
                        seen.add(s)
        elif is_supported_media_file(pp):
            s = str(pp.resolve())
            if s not in seen:
                out.append(s)
                seen.add(s)
    return out

def list_input_devices():
    if not SOUNDDEVICE_AVAILABLE:
        return []
    try:
        devices = sd.query_devices()
        out = []
        for idx, d in enumerate(devices):
            try:
                in_ch = int(d.get("max_input_channels", 0))
            except Exception:
                in_ch = 0
            name = str(d.get("name", f"Device {idx}"))
            if in_ch > 0:
                out.append((idx, name))

        if out:
            return out

        # Fallback: if PortAudio reports no input channels, still expose devices so user can try.
        fallback = []
        for idx, d in enumerate(devices):
            name = str(d.get("name", f"Device {idx}"))
            fallback.append((idx, f"{name} (reported 0 in-ch)"))
        return fallback
    except Exception:
        return []

def resolve_input_device_index(wanted):
    if wanted is None or not SOUNDDEVICE_AVAILABLE:
        return None
    try:
        wanted_int = int(wanted)
    except Exception:
        return None
    available = {idx for idx, _ in list_input_devices()}
    return wanted_int if wanted_int in available else None


class SettingsDialog(QDialog):
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.settings = current_settings or dict(DEFAULT_SETTINGS)
        s = UI_STRINGS[ui_lang(self.settings)]
        self.setWindowTitle(s["settings_title"])
        layout = QFormLayout(self)
        self.vad_checkbox = QCheckBox()
        self.vad_checkbox.setChecked(self.settings.get("vad", False))
        layout.addRow(s["settings_vad"], self.vad_checkbox)
        self.dark_mode_checkbox = QCheckBox()
        self.dark_mode_checkbox.setChecked(self.settings.get("dark_mode", False))
        layout.addRow(s["settings_dark_mode"], self.dark_mode_checkbox)

        self.app_lang_combo = QComboBox()
        self.app_lang_combo.addItem("English", "en")
        self.app_lang_combo.addItem("Türkçe", "tr")
        wanted_app = self.settings.get("app_language", DEFAULT_SETTINGS["app_language"])
        idx = self.app_lang_combo.findData(wanted_app)
        if idx >= 0:
            self.app_lang_combo.setCurrentIndex(idx)
        layout.addRow(s["settings_app_language"], self.app_lang_combo)

        self.transcription_lang_combo = QComboBox()
        self.transcription_lang_combo.addItem("Auto", "Auto")
        for code, label in LANG_CHOICES:
            self.transcription_lang_combo.addItem(f"{label} ({code})", code)
        wanted_lang = self.settings.get("language", DEFAULT_SETTINGS["language"])
        idx = self.transcription_lang_combo.findData(wanted_lang)
        if idx >= 0:
            self.transcription_lang_combo.setCurrentIndex(idx)
        layout.addRow(s["settings_transcription_language"], self.transcription_lang_combo)

        self.translate_to_combo = QComboBox()
        for code, label in LANG_CHOICES:
            self.translate_to_combo.addItem(label, code)
        wanted = self.settings.get("translate_to", DEFAULT_SETTINGS["translate_to"])
        idx = self.translate_to_combo.findData(wanted)
        if idx >= 0:
            self.translate_to_combo.setCurrentIndex(idx)
        layout.addRow(s["settings_translate_to"], self.translate_to_combo)

        self.mic_combo = QComboBox()
        self.mic_combo.addItem("Default", None)
        if SOUNDDEVICE_AVAILABLE:
            devices = list_input_devices()
            if not devices:
                self.mic_combo.addItem("No devices found (check PortAudio/PipeWire/PulseAudio)", None)
            else:
                for idx, name in devices:
                    self.mic_combo.addItem(f"{name} (#{idx})", idx)
            wanted_mic = resolve_input_device_index(self.settings.get("mic_device"))
            idx = self.mic_combo.findData(wanted_mic)
            if idx >= 0:
                self.mic_combo.setCurrentIndex(idx)
        else:
            self.mic_combo.setEnabled(False)
            self.mic_combo.setToolTip("Recording unavailable (sounddevice missing)")
        layout.addRow(s["settings_microphone"], self.mic_combo)

        self.export_combo = QComboBox()
        self.export_combo.addItems(["txt", "srt", "vtt", "tsv", "json"])
        current_export = self.settings.get("export_format", "txt")
        idx = self.export_combo.findText(current_export)
        if idx >= 0:
            self.export_combo.setCurrentIndex(idx)
        layout.addRow(s["settings_export_format"], self.export_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_btn:
            ok_btn.setText(s["settings_ok"])
        if cancel_btn:
            cancel_btn.setText(s["settings_cancel"])
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self):
        return {
            "vad": self.vad_checkbox.isChecked(),
            "dark_mode": self.dark_mode_checkbox.isChecked(),
            "app_language": self.app_lang_combo.currentData(),
            "language": self.transcription_lang_combo.currentData(),
            "translate_to": self.translate_to_combo.currentData(),
            "mic_device": self.mic_combo.currentData(),
            "export_format": self.export_combo.currentText(),
        }


class TranscribeThread(QThread):
    finished = pyqtSignal(str, list)
    batch_finished = pyqtSignal()
    error = pyqtSignal(str)
    progress_text = pyqtSignal(str)

    def __init__(self, model_name: str, files: list, device: str, language: str, translate: bool, vad: bool):
        super().__init__()
        self.model_name = model_name
        self.files = files
        self.device = device
        self.language = language
        self.translate = translate
        self.vad = vad

    def run(self):
        try:
            self.progress_text.emit(f"Loading model {self.model_name} on {self.device}...")
            model = whisper.load_model(self.model_name, device=self.device)
            for idx, file_path in enumerate(self.files):
                self.progress_text.emit(f"Transcribing {idx+1}/{len(self.files)}: {Path(file_path).name}...")
                options = {}
                if self.language != "Auto":
                    options["language"] = self.language
                if self.translate:
                    options["task"] = "translate"
                if self.vad:
                    options["condition_on_previous_text"] = False
                    options["no_speech_threshold"] = 0.4
                result = model.transcribe(file_path, **options)
                text = result.get("text", "").strip()
                segments = result.get("segments", [])
                self.finished.emit(text, segments)
            self.batch_finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class RecordThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, duration=10, samplerate=16000, device=None):
        super().__init__()
        self.duration = duration
        self.samplerate = samplerate
        self.device = device
        self.recording = True

    def run(self):
        if not AUDIO_RECORDING_AVAILABLE:
            self.error.emit("sounddevice/numpy packages not found. Recording unavailable.")
            return
        try:
            temp_dir = tempfile.gettempdir()
            out_file = os.path.join(temp_dir, f"mic_record_{int(time.time())}.wav")
            q = []
            def callback(indata, frames, time, status):
                q.append(indata.copy())
            with sd.InputStream(samplerate=self.samplerate, channels=1, device=self.device, callback=callback):
                while self.recording:
                    sd.sleep(100)
            data = np.concatenate(q, axis=0).reshape(-1)
            data = np.clip(data, -1.0, 1.0)
            pcm16 = (data * 32767.0).astype(np.int16)
            with wave.open(out_file, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.samplerate)
                wf.writeframes(pcm16.tobytes())
            self.finished.emit(out_file)
        except Exception as e:
            self.error.emit(str(e))
    
    def stop(self):
        self.recording = False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Whisper Tool - Advanced")
        self.resize(900, 700)
        self.setAcceptDrops(True)
        self.settings = load_settings()
        save_settings(self.settings)
        self.current_segments = []

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        top_layout = QHBoxLayout()
        self.model_label = QLabel()
        top_layout.addWidget(self.model_label)
        self.model_combo = QComboBox()
        self.populate_models()
        self._apply_model_selection_from_settings()
        top_layout.addWidget(self.model_combo)

        self.device_label = QLabel()
        top_layout.addWidget(self.device_label)
        self.device_combo = QComboBox()
        self.device_combo.addItems(["cpu", "cuda"])
        self._apply_device_selection_from_settings()
        top_layout.addWidget(self.device_combo)

        self.language_label_widget = QLabel()
        top_layout.addWidget(self.language_label_widget)
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Auto")
        self.lang_combo.addItems(["en", "tr", "de", "es", "fr", "it", "ru", "zh", "ja"])
        self._apply_language_selection_from_settings()
        top_layout.addWidget(self.lang_combo)

        self.translate_cb = QCheckBox()
        self.translate_cb.setChecked(bool(self.settings.get("translate", False)))
        top_layout.addWidget(self.translate_cb)

        self.settings_btn = QPushButton()
        self.settings_btn.clicked.connect(self.open_settings)
        top_layout.addWidget(self.settings_btn)

        layout.addLayout(top_layout)

        file_layout = QHBoxLayout()
        self.file_list = QListWidget()
        file_layout.addWidget(self.file_list, 1)
        self.file_list.model().rowsInserted.connect(self._update_transcribe_button_state)
        self.file_list.model().rowsRemoved.connect(self._update_transcribe_button_state)
        self.file_list.model().modelReset.connect(self._update_transcribe_button_state)

        btn_layout = QVBoxLayout()
        self.add_btn = QPushButton("Add Files")
        self.add_btn.clicked.connect(self.add_files)
        btn_layout.addWidget(self.add_btn)
        
        self.clear_btn = QPushButton("Clear List")
        self.clear_btn.clicked.connect(self.file_list.clear)
        btn_layout.addWidget(self.clear_btn)

        self.mic_btn = QPushButton("Start Mic Rec")
        self.mic_btn.clicked.connect(self.toggle_mic)
        self.is_recording = False
        btn_layout.addWidget(self.mic_btn)

        self.transcribe_btn = QPushButton("Transcribe Batch")
        self.transcribe_btn.clicked.connect(self.start_transcription)
        self.transcribe_btn.setMinimumHeight(44)
        btn_layout.addWidget(self.transcribe_btn)
        
        file_layout.addLayout(btn_layout)
        layout.addLayout(file_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.output_label = QLabel()
        layout.addWidget(self.output_label)
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(False)
        layout.addWidget(self.output_text, 1)

        export_layout = QHBoxLayout()
        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self.export_current_format)
        export_layout.addWidget(self.export_btn)

        layout.addLayout(export_layout)

        self.statusBar().showMessage("Ready")
        self.apply_dark_mode()
        self._wire_settings_persistence()
        self._sync_export_button_label()
        self._sync_translate_checkbox_label()
        self._apply_ui_language()
        self._update_transcribe_button_state()

    def populate_models(self):
        models = ["tiny", "base", "small", "medium", "large"]
        cache_dir = Path.home() / ".cache" / "whisper"
        for m in models:
            cached = ""
            if cache_dir.exists():
                for f in cache_dir.iterdir():
                    if m in f.name:
                        cached = " (Cached)"
                        break
            self.model_combo.addItem(f"{m}{cached}", m)

    def apply_dark_mode(self):
        if self.settings["dark_mode"]:
            app = QApplication.instance()
            app.setStyle("Fusion")
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
            palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
            app.setPalette(palette)
        else:
            app = QApplication.instance()
            app.setPalette(app.style().standardPalette())

    def open_settings(self):
        dialog = SettingsDialog(self, self.settings)
        if dialog.exec():
            updated = dialog.get_settings()
            self.settings.update(updated)
            save_settings(self.settings)
            self.apply_dark_mode()
            self._sync_export_button_label()
            self._sync_translate_checkbox_label()
            self._apply_language_selection_from_settings()
            self._apply_ui_language()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls()]
        files = gather_supported_files(paths)
        for f in files:
            self.file_list.addItem(f)

    def add_files(self):
        start_dir = self.settings.get("last_open_dir") or str(Path.home())
        files, _ = QFileDialog.getOpenFileNames(
            self, UI_STRINGS[ui_lang(self.settings)]["select_media_title"], start_dir,
            media_file_dialog_filter()
        )
        if files:
            try:
                self.settings["last_open_dir"] = str(Path(files[0]).resolve().parent)
                save_settings(self.settings)
            except Exception:
                pass
        for f in files:
            self.file_list.addItem(f)

    def toggle_mic(self):
        if not AUDIO_RECORDING_AVAILABLE:
            QMessageBox.warning(self, "Error", "sounddevice/numpy missing.")
            return
        if not self.is_recording:
            self.is_recording = True
            mic_device = resolve_input_device_index(self.settings.get("mic_device"))
            self.record_thread = RecordThread(device=mic_device)
            self.record_thread.finished.connect(self.mic_finished)
            self.record_thread.error.connect(self.mic_error)
            self.record_thread.start()
            self._apply_ui_language()
        else:
            self.is_recording = False
            self.record_thread.stop()
            self._apply_ui_language()

    def mic_finished(self, path):
        self.file_list.addItem(path)
        self.log(f"Mic recording saved to {path}")

    def mic_error(self, err):
        QMessageBox.critical(self, "Mic Error", err)
        self.mic_btn.setText("Start Mic Rec")
        self.is_recording = False

    def log(self, text):
        self.output_text.append(f"[{time.strftime('%H:%M:%S')}] {text}")

    def start_transcription(self):
        files = [self.file_list.item(i).text() for i in range(self.file_list.count())]
        if not files:
            s = UI_STRINGS[ui_lang(self.settings)]
            QMessageBox.warning(self, s["warning"], s["no_files"])
            return
        
        model_name = self.model_combo.currentData()
        device = self.device_combo.currentText()
        language = self.lang_combo.currentText()
        translate = self.translate_cb.isChecked()
        vad = self.settings.get("vad", False)
        translate_to = self.settings.get("translate_to", DEFAULT_SETTINGS["translate_to"])
        if translate and translate_to != "en":
            self.log(f"Note: Whisper 'translate' outputs English only. Target '{language_label(translate_to)}' is UI-only for now.")
        self.settings["model"] = model_name
        self.settings["device"] = device
        self.settings["language"] = language
        self.settings["translate"] = bool(translate)
        save_settings(self.settings)

        self.transcribe_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.log("Starting batch transcription...")

        self.worker = TranscribeThread(model_name, files, device, language, translate, vad)
        self.worker.progress_text.connect(self.log)
        self.worker.finished.connect(self.transcription_finished)
        self.worker.batch_finished.connect(self.batch_finished)
        self.worker.error.connect(self.transcription_error)
        self.worker.start()

    def transcription_finished(self, text, segments):
        self.current_segments = segments
        self.output_text.append("\n--- Result ---\n")
        self.output_text.append(text)
        self.output_text.append("\n--------------\n")

    def batch_finished(self):
        self.progress_bar.setVisible(False)
        self.transcribe_btn.setEnabled(True)
        self.log("Batch transcription complete.")

    def transcription_error(self, err):
        self.log(f"Error: {err}")
        self.progress_bar.setVisible(False)
        self.transcribe_btn.setEnabled(True)

    def export_text(self, fmt):
        text = self.output_text.toPlainText()
        if not text:
            return

        last_dir = self.settings.get("last_save_dir") or self.settings.get("last_open_dir") or str(Path.home())
        name, _ = QFileDialog.getSaveFileName(
            self,
            f"Save {fmt.upper()}",
            str(Path(last_dir) / f"transcript.{fmt}"),
            f"{fmt.upper()} Files (*.{fmt});;All Files (*)",
        )
        if name:
            try:
                with open(name, "w", encoding="utf-8") as f:
                    if fmt == "txt":
                        f.write(text)
                    elif fmt == "srt":
                        write_srt(self.current_segments, f)
                    elif fmt == "vtt":
                        write_vtt(self.current_segments, f)
                    elif fmt == "tsv":
                        write_tsv(self.current_segments, f)
                    elif fmt == "json":
                        write_json(self.current_segments, f)
                self.log(f"Exported to {name}")
                try:
                    self.settings["last_save_dir"] = str(Path(name).resolve().parent)
                    self.settings["export_format"] = fmt
                    save_settings(self.settings)
                except Exception:
                    pass
                self.reveal_file(name)
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def export_current_format(self):
        fmt = self.settings.get("export_format", DEFAULT_SETTINGS["export_format"])
        self.export_text(fmt)

    def reveal_file(self, path):
        try:
            if platform.system() == "Windows":
                subprocess.run(["explorer", "/select,", os.path.normpath(path)])
            elif platform.system() == "Darwin":
                subprocess.run(["open", "-R", path])
            else:
                if subprocess.run(["which", "dolphin"], capture_output=True).returncode == 0:
                    subprocess.run(["dolphin", "--select", path])
                else:
                    subprocess.run(["xdg-open", os.path.dirname(path)])
        except Exception as e:
            self.log(f"Could not reveal file: {e}")

    def _apply_model_selection_from_settings(self):
        wanted = self.settings.get("model", DEFAULT_SETTINGS["model"])
        for i in range(self.model_combo.count()):
            if self.model_combo.itemData(i) == wanted:
                self.model_combo.setCurrentIndex(i)
                return

    def _apply_device_selection_from_settings(self):
        wanted = self.settings.get("device", DEFAULT_SETTINGS["device"])
        idx = self.device_combo.findText(wanted)
        if idx >= 0:
            self.device_combo.setCurrentIndex(idx)

    def _apply_language_selection_from_settings(self):
        wanted = self.settings.get("language", DEFAULT_SETTINGS["language"])
        idx = self.lang_combo.findText(wanted)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)

    def _wire_settings_persistence(self):
        def persist():
            try:
                self.settings["model"] = self.model_combo.currentData()
                self.settings["device"] = self.device_combo.currentText()
                self.settings["language"] = self.lang_combo.currentText()
                self.settings["translate"] = bool(self.translate_cb.isChecked())
                save_settings(self.settings)
            except Exception:
                pass

        self.model_combo.currentIndexChanged.connect(persist)
        self.device_combo.currentIndexChanged.connect(persist)
        self.lang_combo.currentIndexChanged.connect(persist)
        self.translate_cb.stateChanged.connect(persist)

    def _sync_export_button_label(self):
        fmt = self.settings.get("export_format", DEFAULT_SETTINGS["export_format"]).upper()
        self.export_btn.setText(f"Export ({fmt})")

    def _sync_translate_checkbox_label(self):
        code = self.settings.get("translate_to", DEFAULT_SETTINGS["translate_to"])
        s = UI_STRINGS[ui_lang(self.settings)]
        self.translate_cb.setText(s["translate_to"].format(lang=language_label(code)))

    def _apply_ui_language(self):
        s = UI_STRINGS[ui_lang(self.settings)]
        self.model_label.setText(s["model"])
        self.device_label.setText(s["device"])
        self.language_label_widget.setText(s["language"])
        self.settings_btn.setText(s["settings"])
        self.add_btn.setText(s["add_files"])
        self.clear_btn.setText(s["clear_list"])
        self.output_label.setText(s["output_logs"])
        if self.is_recording:
            self.mic_btn.setText(s["stop_mic"])
        else:
            self.mic_btn.setText(s["start_mic"])
        self._sync_export_button_label()
        self._sync_translate_checkbox_label()
        self._update_transcribe_button_state()

    def _update_transcribe_button_state(self, *args):
        count = self.file_list.count()
        s = UI_STRINGS[ui_lang(self.settings)]

        base_style = (
            "QPushButton {"
            " font-size: 15px;"
            " font-weight: 700;"
            " padding: 10px 14px;"
            " color: white;"
            " border-radius: 10px;"
            "}"
            "QPushButton:disabled { background-color: #9E9E9E; }"
        )

        if count <= 0:
            # Red + "Çevir" / "Transcribe"
            self.transcribe_btn.setText(s["transcribe_one"])
            self.transcribe_btn.setStyleSheet(
                base_style
                + "QPushButton { background-color: #C62828; }"
                + "QPushButton:hover { background-color: #A61F1F; }"
            )
        elif count == 1:
            self.transcribe_btn.setText(s["transcribe_one"])
            self.transcribe_btn.setStyleSheet(
                base_style
                + "QPushButton { background-color: #2E7D32; }"
                + "QPushButton:hover { background-color: #256628; }"
            )
        else:
            self.transcribe_btn.setText(s["transcribe_batch"])
            self.transcribe_btn.setStyleSheet(
                base_style
                + "QPushButton { background-color: #2E7D32; }"
                + "QPushButton:hover { background-color: #256628; }"
            )


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()