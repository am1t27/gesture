__author__ = 'Shadab Shaikh, Obaid Kazi, Ansari Mohd Adnan'

import os
import sys
import json
import shutil
import argparse
import threading
import urllib.request
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import (
    QMessageBox, QLabel, QPushButton, QFrame, QVBoxLayout, QHBoxLayout,
    QGridLayout, QSlider, QLineEdit, QTextEdit, QWidget, QFileDialog,
    QCheckBox
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap

from recognition_engine import RecognitionEngine
from gesture_capture import GestureCapture
from sentence_engine import SentenceEngine

SESSION_RESULT_URL = "http://127.0.0.1:5000/api/session-result"

# ── Theme (matches the web dashboard: forest shell, lime accent, white cards) ──

FOREST = "#12463A"
FOREST_DEEP = "#0B3129"
FOREST_LINE = "#1E5A49"
LIME = "#D9F04F"
LIME_DIM = "#C4DA43"
MINT = "#BFDACC"
INK = "#10352A"
INK_2 = "#4E6B5F"
CREAM = "#F6F8EE"

APP_QSS = f"""
QMainWindow, QWidget#root {{
    background-color: {FOREST};
}}
QLabel {{
    color: {MINT};
    font-size: 13px;
    background: transparent;
}}
QLabel#h1 {{
    color: #FFFFFF;
    font-size: 21px;
    font-weight: 600;
}}
QLabel#sub {{
    color: {MINT};
    font-size: 13px;
}}
QLabel#cardTitle {{
    color: {INK_2};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
}}
QLabel#bigLetter {{
    color: {INK};
    font-size: 84px;
    font-weight: 700;
    font-family: Menlo, Consolas, monospace;
}}
QLabel#inCard {{
    color: {INK_2};
    font-size: 12px;
}}
QFrame#card {{
    background-color: #FFFFFF;
    border: none;
    border-radius: 14px;
}}
QFrame#heroCard {{
    background-color: {FOREST_DEEP};
    border: 1px solid {FOREST_LINE};
    border-radius: 16px;
}}
QPushButton {{
    font-size: 13px;
    font-weight: 600;
}}
QPushButton#primary {{
    background-color: {LIME};
    color: {FOREST_DEEP};
    border: none;
    border-radius: 18px;
    padding: 9px 22px;
}}
QPushButton#primary:hover {{ background-color: #E4F76A; }}
QPushButton#primary:disabled {{ background-color: {FOREST_LINE}; color: {MINT}; }}
QPushButton#ghost {{
    background-color: transparent;
    color: #FFFFFF;
    border: 1px solid {FOREST_LINE};
    border-radius: 18px;
    padding: 9px 22px;
}}
QPushButton#ghost:hover {{ border-color: {LIME}; color: {LIME}; }}
QPushButton#mode {{
    background-color: #FFFFFF;
    color: {INK};
    border: none;
    border-radius: 14px;
    padding: 22px;
    font-size: 14px;
    font-weight: 600;
    text-align: left;
}}
QPushButton#mode:hover {{ background-color: {CREAM}; }}
QPushButton#modeLime {{
    background-color: {LIME};
    color: {FOREST_DEEP};
    border: none;
    border-radius: 14px;
    padding: 22px;
    font-size: 14px;
    font-weight: 600;
    text-align: left;
}}
QPushButton#modeLime:hover {{ background-color: #E4F76A; }}
QSlider::groove:horizontal {{
    border: none;
    height: 6px;
    background: {FOREST_LINE};
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {LIME};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {LIME};
    border: 2px solid {FOREST_DEEP};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 9px;
}}
QCheckBox {{
    color: {INK_2};
    font-size: 12px;
    font-weight: 600;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border-radius: 4px;
    border: 1px solid #C8CFBC;
    background: #FFFFFF;
}}
QCheckBox::indicator:checked {{
    background: {LIME};
    border-color: {LIME_DIM};
}}
QLineEdit {{
    background: #FFFFFF;
    color: {INK};
    border: 1px solid #D2D7C8;
    border-radius: 9px;
    padding: 8px 12px;
    font-size: 13px;
}}
QLineEdit:focus {{ border-color: {FOREST}; }}
QTextEdit {{
    background: #FFFFFF;
    color: {INK};
    border: none;
    border-radius: 10px;
    padding: 10px;
    font-family: Menlo, Consolas, monospace;
    font-size: 16px;
}}
QMessageBox {{ background-color: #FFFFFF; }}
QMessageBox QLabel {{ color: {INK}; }}
"""


def removeFile():
    try:
        os.remove("temp.txt")
    except OSError:
        pass
    try:
        shutil.rmtree("TempGest")
    except OSError:
        pass


def checkFile():
    if os.path.isfile('temp.txt'):
        with open("temp.txt", "r") as fr:
            return fr.read()
    return "No Content Available"


def speak_async(text):
    """TTS on a worker thread — runAndWait() would freeze the Qt event loop."""
    def _run():
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


class Dashboard(QtWidgets.QMainWindow):
    def __init__(self, session_id=None, start_mode=None):
        super(Dashboard, self).__init__()
        self.setWindowIcon(QtGui.QIcon('icons/windowLogo.png'))
        self.setWindowTitle('Gesture Vocalization')
        self.setStyleSheet(APP_QSS)
        self.resize(980, 660)

        self.session_id = session_id
        self.result_posted = False

        self.rec_engine = RecognitionEngine()
        self.sent_engine = SentenceEngine()

        self.timer = QTimer()
        self.timer.timeout.connect(self.process_frame)
        self.current_mode = None
        self.capture_requested = False

        self.load_dash()
        launchers = {
            'scanSingle': self.load_scan_single,
            'scanSent': self.load_scan_sent,
            'createGest': self.load_create_gest,
        }
        if start_mode in launchers:
            QTimer.singleShot(0, launchers[start_mode])

    # ── Building blocks ────────────────────────────────────────────────────

    def _fresh_root(self):
        """Stop any camera work and install a new central widget."""
        self.timer.stop()
        root = QWidget()
        root.setObjectName('root')
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        return layout

    def _header(self, layout, title, subtitle, back=True):
        row = QHBoxLayout()
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        h1 = QLabel(title)
        h1.setObjectName('h1')
        sub = QLabel(subtitle)
        sub.setObjectName('sub')
        text_col.addWidget(h1)
        text_col.addWidget(sub)
        row.addLayout(text_col)
        row.addStretch()
        if back:
            back_btn = QPushButton("Back to menu")
            back_btn.setObjectName('ghost')
            back_btn.setCursor(Qt.PointingHandCursor)
            back_btn.clicked.connect(self.load_dash)
            row.addWidget(back_btn, alignment=Qt.AlignTop)
        layout.addLayout(row)

    @staticmethod
    def _card(title=None):
        """White rounded card with an optional small caps title. Returns
        (frame, inner_layout)."""
        frame = QFrame()
        frame.setObjectName('card')
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(16, 14, 16, 16)
        inner.setSpacing(8)
        if title:
            t = QLabel(title.upper())
            t.setObjectName('cardTitle')
            inner.addWidget(t)
        return frame, inner

    def _build_scan_layout(self, layout, right_widgets):
        """Camera card on the left, given widgets stacked on the right,
        threshold slider underneath. Shared by all three camera modes."""
        body = QHBoxLayout()
        body.setSpacing(16)

        cam_card, cam_inner = self._card("Camera")
        self.camera_label = QLabel("Starting camera…")
        self.camera_label.setObjectName('inCard')
        self.camera_label.setFixedSize(420, 315)
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setWordWrap(True)
        self.camera_label.setScaledContents(True)
        cam_inner.addWidget(self.camera_label)
        body.addWidget(cam_card, stretch=0, alignment=Qt.AlignTop)

        right_col = QVBoxLayout()
        right_col.setSpacing(16)
        for w in right_widgets:
            right_col.addWidget(w)
        right_col.addStretch()
        body.addLayout(right_col, stretch=1)

        layout.addLayout(body)

        # Threshold row — automatic by default, with a manual override
        slider_card, slider_inner = self._card("Mask threshold")
        slider_row = QHBoxLayout()

        self.auto_threshold = QCheckBox("Automatic")
        self.auto_threshold.setChecked(True)
        slider_row.addWidget(self.auto_threshold)

        self.trackbar = QSlider(Qt.Horizontal)
        self.trackbar.setRange(0, 255)
        self.trackbar.setValue(150)
        self.trackbar.setEnabled(False)
        slider_row.addWidget(self.trackbar)

        self.slider_value_label = QLabel("auto")
        self.slider_value_label.setObjectName('inCard')
        self.slider_value_label.setFixedWidth(38)
        slider_row.addWidget(self.slider_value_label)

        self.auto_threshold.toggled.connect(self._on_auto_toggled)
        self.trackbar.valueChanged.connect(
            lambda v: self.slider_value_label.setText(str(v)))
        slider_inner.addLayout(slider_row)

        hint = QLabel("The threshold is picked for you. Switch to manual only if "
                      "the mask does not show a clean white hand.")
        hint.setObjectName('inCard')
        hint.setWordWrap(True)
        slider_inner.addWidget(hint)
        layout.addWidget(slider_card)

    def _on_auto_toggled(self, checked):
        self.trackbar.setEnabled(not checked)
        self.slider_value_label.setText("auto" if checked else str(self.trackbar.value()))

    def _threshold(self):
        """None means let the engine choose the threshold with Otsu."""
        if not hasattr(self, 'trackbar'):
            return None
        if hasattr(self, 'auto_threshold') and self.auto_threshold.isChecked():
            return None
        return self.trackbar.value()

    def _mask_card(self):
        card, inner = self._card("Mask")
        self.mask_label = QLabel()
        self.mask_label.setFixedSize(146, 146)
        self.mask_label.setScaledContents(True)
        self.mask_label.setStyleSheet(f"background: {INK}; border-radius: 8px;")
        inner.addWidget(self.mask_label, alignment=Qt.AlignCenter)
        return card

    def _prediction_card(self):
        card, inner = self._card("Recognized")
        self.pred_label = QLabel("—")
        self.pred_label.setObjectName('bigLetter')
        self.pred_label.setAlignment(Qt.AlignCenter)
        self.pred_label.setMinimumHeight(110)
        inner.addWidget(self.pred_label)
        self.pred_status = QLabel("Show a hand in the box")
        self.pred_status.setObjectName('inCard')
        self.pred_status.setAlignment(Qt.AlignCenter)
        inner.addWidget(self.pred_status)
        return card

    # ── Screens ────────────────────────────────────────────────────────────

    def load_dash(self):
        self.rec_engine.stop()
        self.current_mode = None
        layout = self._fresh_root()

        hero = QFrame()
        hero.setObjectName('heroCard')
        hero_l = QVBoxLayout(hero)
        hero_l.setContentsMargins(24, 22, 24, 22)
        hero_l.setSpacing(4)
        h1 = QLabel("Gesture Vocalization")
        h1.setObjectName('h1')
        sub = QLabel("Camera → Recognition → Text → Speech. Pick a mode to open the camera.")
        sub.setObjectName('sub')
        hero_l.addWidget(h1)
        hero_l.addWidget(sub)
        layout.addWidget(hero)

        grid = QGridLayout()
        grid.setSpacing(16)

        modes = [
            ("Scan one letter\nHold a hand shape, read the letter live", 'modeLime', self.load_scan_single),
            ("Build a sentence\nPress C to capture letters into a sentence", 'mode', self.load_scan_sent),
            ("Teach a gesture\nSave your own hand shape under a name", 'mode', self.load_create_gest),
            ("Export and speak\nHear the saved sentence and save it to a file", 'mode', self.load_export),
        ]
        for i, (text, style, handler) in enumerate(modes):
            btn = QPushButton(text)
            btn.setObjectName(style)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(88)
            btn.clicked.connect(handler)
            grid.addWidget(btn, i // 2, i % 2)

        layout.addLayout(grid)
        layout.addStretch()

        quit_row = QHBoxLayout()
        quit_row.addStretch()
        quit_btn = QPushButton("Quit")
        quit_btn.setObjectName('ghost')
        quit_btn.setCursor(Qt.PointingHandCursor)
        quit_btn.clicked.connect(self.quitApplication)
        quit_row.addWidget(quit_btn)
        layout.addLayout(quit_row)

    def load_scan_single(self):
        self.current_mode = 'scan_single'
        layout = self._fresh_root()
        self._header(layout, "Scan one letter",
                     "Keep your hand inside the green box and hold the shape steady.")
        self._build_scan_layout(layout, [self._prediction_card(), self._mask_card()])
        self.rec_engine.start()
        self.timer.start(33)

    def load_scan_sent(self):
        self.current_mode = 'scan_sent'
        self.sent_engine.clear()
        layout = self._fresh_root()
        self._header(layout, "Build a sentence",
                     "Press C to capture the current letter. Save when you're done.")

        pred = self._prediction_card()
        mask = self._mask_card()

        sent_card, sent_inner = self._card("Sentence")
        self.sentence_view = QTextEdit()
        self.sentence_view.setReadOnly(True)
        self.sentence_view.setFixedHeight(72)
        sent_inner.addWidget(self.sentence_view)
        save_btn = QPushButton("Save sentence")
        save_btn.setObjectName('primary')
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self.save_sentence_buffer)
        sent_inner.addWidget(save_btn, alignment=Qt.AlignLeft)

        self._build_scan_layout(layout, [pred, mask, sent_card])
        self.rec_engine.start()
        self.timer.start(33)

    def load_create_gest(self):
        self.current_mode = 'create_gest'
        layout = self._fresh_root()
        self._header(layout, "Teach a gesture",
                     "Hold the new hand shape in the box, name it, then save.")

        pred = self._mask_card()

        name_card, name_inner = self._card("Gesture name")
        self.gest_name_input = QLineEdit()
        self.gest_name_input.setPlaceholderText("e.g. hello — or sp for a space")
        name_inner.addWidget(self.gest_name_input)
        save_btn = QPushButton("Save gesture")
        save_btn.setObjectName('primary')
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self.save_custom_gesture)
        name_inner.addWidget(save_btn, alignment=Qt.AlignLeft)

        self._build_scan_layout(layout, [name_card, pred])
        self.rec_engine.start()
        self.timer.start(33)

    def load_export(self):
        self.rec_engine.stop()
        self.current_mode = 'export'
        layout = self._fresh_root()
        self._header(layout, "Export and speak",
                     "The last saved sentence, read aloud and ready to save as a text file.")

        content = checkFile()

        text_card, text_inner = self._card("Saved sentence")
        view = QTextEdit()
        view.setReadOnly(True)
        view.setPlainText(content)
        view.setFixedHeight(140)
        text_inner.addWidget(view)

        btn_row = QHBoxLayout()
        speak_btn = QPushButton("Speak")
        speak_btn.setObjectName('primary')
        speak_btn.setCursor(Qt.PointingHandCursor)
        speak_btn.clicked.connect(lambda: speak_async(str(checkFile()).lower()))
        btn_row.addWidget(speak_btn)

        export_btn = QPushButton("Save to file")
        export_btn.setObjectName('primary')
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.clicked.connect(self.on_export_click)
        btn_row.addWidget(export_btn)
        btn_row.addStretch()
        text_inner.addLayout(btn_row)

        has_content = content not in ("File Not Found", "No Content Available")
        speak_btn.setEnabled(has_content)
        export_btn.setEnabled(has_content)
        if has_content:
            speak_async(str(content).lower())

        layout.addWidget(text_card)
        layout.addStretch()

    # ── Actions ────────────────────────────────────────────────────────────

    def save_sentence_buffer(self):
        self.sent_engine.save_sentence()
        QMessageBox.about(self, "Saved", "Sentence saved. Open Export & speak to hear or export it.")

    def save_custom_gesture(self):
        ges_name = self.gest_name_input.text().strip()
        if not ges_name:
            QMessageBox.warning(self, "Name needed", "Type a name for the gesture first.")
            return

        result = self.rec_engine.process_frame(self._threshold())
        if not result or result.get("mask_64") is None:
            QMessageBox.warning(self, "No frame", "The camera did not return a frame. Try again.")
            return
        if not result["hand_present"]:
            QMessageBox.warning(
                self, "No hand detected",
                "The mask does not show a clean hand shape. Adjust your hand or "
                "the threshold, then save again.")
            return
        if GestureCapture.save_gesture(ges_name, result["mask_64"]):
            QMessageBox.about(self, "Saved", f"Gesture '{ges_name}' saved.")

    def on_export_click(self):
        content = checkFile()
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save sentence", "sentence.txt", "Text files (*.txt)")
        if filename:
            if not filename.endswith('.txt'):
                filename += '.txt'
            with open(filename, "w") as fw:
                fw.write(content if content != 'No Content Available' else " ")
            removeFile()
            QMessageBox.about(self, "Saved", "Sentence saved to file.")
            self.load_export()

    # ── Frame loop ─────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_C and self.current_mode == 'scan_sent':
            self.capture_requested = True
        else:
            super(Dashboard, self).keyPressEvent(event)

    def process_frame(self):
        result = self.rec_engine.process_frame(self._threshold())
        if not result:
            if hasattr(self, 'camera_label'):
                self.camera_label.setText(
                    "Camera unavailable.\n\n"
                    "Grant camera permission to the app/terminal that launched "
                    "this window\n(System Settings > Privacy & Security > Camera), "
                    "then reopen this screen.")
            return

        cam_frame = result["camera_frame"]
        h, w, ch = cam_frame.shape
        q_img_cam = QImage(cam_frame.data, w, h, ch * w, QImage.Format_RGB888)
        self.camera_label.setPixmap(QPixmap.fromImage(q_img_cam))

        mask_frame = result["mask_frame"]
        h, w = mask_frame.shape
        q_img_mask = QImage(mask_frame.data, w, h, w, QImage.Format_Grayscale8)
        self.mask_label.setPixmap(QPixmap.fromImage(q_img_mask))

        if self.current_mode == 'create_gest':
            return

        prediction = result["prediction"]
        self._show_prediction(result)

        if self.current_mode == 'scan_sent':
            if self.capture_requested:
                self.capture_requested = False
                if prediction:
                    new_text = self.sent_engine.append_character(prediction, result["mask_64"])
                    self.sentence_view.setPlainText(new_text)

    def _show_prediction(self, result):
        """Letter plus an honest note about why it is or isn't settled."""
        prediction = result["prediction"]
        if prediction:
            self.pred_label.setText(prediction if prediction.strip() else "␣")
            if result["source"] == 'custom':
                self.pred_status.setText("Your saved gesture")
            else:
                self.pred_status.setText(f"{result['confidence'] * 100:.0f}% confident")
            return

        self.pred_label.setText("—")
        if not result["hand_present"]:
            self.pred_status.setText(
                "No hand detected — check the mask shows a white hand"
                if result["fill"] > 0.75 else "Show a hand in the box")
        else:
            self.pred_status.setText("Hold the shape steady…")

    # ── Session lifecycle ──────────────────────────────────────────────────

    def post_session_result(self):
        """Report results back to the Flask dashboard (fire-and-forget)."""
        if self.session_id is None or self.result_posted:
            return
        self.result_posted = True
        payload = json.dumps({
            'session_id': self.session_id,
            'letters': self.sent_engine.new_text,
            'gesture_count': self.sent_engine.counts,
        }).encode()
        req = urllib.request.Request(
            SESSION_RESULT_URL, data=payload,
            headers={'Content-Type': 'application/json'})
        try:
            urllib.request.urlopen(req, timeout=2)
        except Exception:
            pass  # Flask not running — standalone launch is fine

    def quitApplication(self):
        reply = QMessageBox.question(
            self, 'Quit', "Quit Gesture Vocalization?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.close()

    def closeEvent(self, event):
        """Single cleanup path — camera always released."""
        self.timer.stop()
        self.rec_engine.stop()
        self.post_session_result()
        removeFile()
        event.accept()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Sign Language Recognition Dashboard')
    parser.add_argument('--session-id', type=int, default=None,
                        help='DB session row id assigned by the Flask app')
    parser.add_argument('--mode', default=None,
                        choices=['scanSingle', 'scanSent', 'createGest'],
                        help='Screen to open on startup')
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    window = Dashboard(session_id=args.session_id, start_mode=args.mode)
    window.show()
    sys.exit(app.exec_())
