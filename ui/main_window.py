"""UI 메인 윈도우."""
import os
import sys
import time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFileDialog, QProgressBar, QTableWidget,
    QTableWidgetItem, QCheckBox, QHeaderView, QMessageBox, QGroupBox,
    QSpinBox, QDoubleSpinBox, QPlainTextEdit, QAbstractItemView,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor

from core.metadata import is_video, get_info
from core.hasher import sample_hashes
from core.grouper import group_duplicates
from core.quality import pick_keeper, to_delete
from core import ffmpeg_manager as fm
from core import recycle as rcy
from ui.help_dialog import HelpDialog


def collect_videos(folder, recursive):
    out = []
    if recursive:
        for root, dirs, files in os.walk(folder):
            for f in files:
                p = os.path.join(root, f)
                if is_video(p):
                    out.append(p)
    else:
        for f in os.listdir(folder):
            p = os.path.join(folder, f)
            if os.path.isfile(p) and is_video(p):
                out.append(p)
    return sorted(out)


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def fmt_dur(d):
    m, s = divmod(int(d), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class ScanWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, folder, recursive, num_frames, threshold):
        super().__init__()
        self.folder = folder
        self.recursive = recursive
        self.num_frames = num_frames
        self.threshold = threshold
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            files = collect_videos(self.folder, self.recursive)
            if not files:
                self.finished.emit({"groups": [], "total_files": 0, "valid": 0})
                return
            infos = []
            total = len(files)
            for idx, f in enumerate(files):
                if self._stop:
                    self.finished.emit({"cancelled": True})
                    return
                self.progress.emit(int(idx / total * 40), f"메타데이터 분석 ({idx+1}/{total}): {os.path.basename(f)}")
                info = get_info(f)
                if info is not None:
                    infos.append(info)
            hashes_map = {}
            n = len(infos)
            for idx, info in enumerate(infos):
                if self._stop:
                    self.finished.emit({"cancelled": True})
                    return
                self.progress.emit(40 + int(idx / max(n, 1) * 50), f"프레임 해시 ({idx+1}/{n}): {os.path.basename(info['path'])}")
                h = sample_hashes(info["path"], num_frames=self.num_frames)
                hashes_map[info["path"]] = h
            self.progress.emit(95, "중복 그룹핑 중...")
            groups = group_duplicates(infos, hashes_map, self.threshold)
            self.progress.emit(100, f"완료: {len(files)}개 파일, {len(infos)}개 유효, {len(groups)}개 중복 그룹")
            self.finished.emit({"groups": groups, "hashes": hashes_map, "total_files": len(files),
                                "valid": len(infos)})
        except Exception as e:
            self.error.emit(str(e))



class FFmpegDownloadWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(bool, str)

    def run(self):
        try:
            ffmpeg_path, ffprobe_path = fm.download_and_install(
                lambda pct, msg: self.progress.emit(pct, msg))
            self.finished.emit(True, f"FFmpeg 설치 완료: {ffmpeg_path}")
        except Exception as e:
            self.finished.emit(False, str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("동영상 중복 제거기")
        self.resize(1100, 720)
        self.worker = None
        self.ff_worker = None
        self._help_dlg = None
        self.groups = []
        self._build_ui()
        QTimer.singleShot(200, self.check_ffmpeg)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        lay = QVBoxLayout(central)

        # 폴더 선택
        row = QHBoxLayout()
        row.addWidget(QLabel("폴더:"))
        self.folder_edit = QLineEdit()
        row.addWidget(self.folder_edit, 1)
        btn_browse = QPushButton("찾아보기")
        btn_browse.clicked.connect(self.browse)
        row.addWidget(btn_browse)
        lay.addLayout(row)

        # 옵션
        opt = QGroupBox("옵션")
        ol = QHBoxLayout(opt)
        self.recursive_cb = QCheckBox("하위 폴더 포함")
        self.recursive_cb.setChecked(True)
        ol.addWidget(self.recursive_cb)
        ol.addWidget(QLabel("샘플 프레임 수:"))
        self.frames_spin = QSpinBox()
        self.frames_spin.setRange(3, 16)
        self.frames_spin.setValue(8)
        self.frames_spin.setMinimumWidth(100)
        ol.addWidget(self.frames_spin)
        ol.addWidget(QLabel("유사도 임계값(낮을수록 엄격):"))
        self.thresh_spin = QDoubleSpinBox()
        self.thresh_spin.setRange(1, 40)
        self.thresh_spin.setValue(12)
        self.thresh_spin.setDecimals(1)
        self.thresh_spin.setMinimumWidth(120)
        ol.addWidget(self.thresh_spin)
        ol.addStretch()
        lay.addWidget(opt)

        # 버튼
        brow = QHBoxLayout()
        self.btn_scan = QPushButton("스캔 시작")
        self.btn_scan.clicked.connect(self.start_scan)
        brow.addWidget(self.btn_scan)
        self.btn_stop = QPushButton("중지")
        self.btn_stop.clicked.connect(self.stop_scan)
        self.btn_stop.setEnabled(False)
        brow.addWidget(self.btn_stop)
        self.btn_delete = QPushButton("선택한 파일 삭제 (휴지통)")
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_delete.setEnabled(False)
        brow.addWidget(self.btn_delete)
        self.btn_ffmpeg = QPushButton("FFmpeg 자동 설치")
        self.btn_ffmpeg.clicked.connect(self.manual_ffmpeg_install)
        brow.addWidget(self.btn_ffmpeg)
        self.btn_help = QPushButton("도움말")
        self.btn_help.clicked.connect(self.open_help)
        brow.addWidget(self.btn_help)
        brow.addStretch()
        lay.addLayout(brow)

        # 진행
        self.progress = QProgressBar()
        lay.addWidget(self.progress)
        self.status = QLabel("준비")
        lay.addWidget(self.status)

        # 결과 테이블
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["선택", "그룹", "파일명", "경로", "해상도", "비트레이트", "용량", "길이", "판정"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        lay.addWidget(self.table, 1)

        # 로그
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setPlaceholderText("로그...")
        lay.addWidget(self.log, 0)

    def browse(self):
        d = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if d:
            self.folder_edit.setText(d)

    def append_log(self, msg):
        self.log.appendPlainText(msg)

    def start_scan(self):
        if not fm.is_available():
            QMessageBox.warning(self, "FFmpeg 필요", "FFmpeg가 설치되어 있지 않습니다. 먼저 'FFmpeg 자동 설치'를 실행하세요.")
            return
        folder = self.folder_edit.text().strip()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "오류", "유효한 폴더를 선택하세요.")
            return
        self.table.setRowCount(0)
        self.groups = []
        self.btn_scan.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_delete.setEnabled(False)
        self.progress.setValue(0)
        self.worker = ScanWorker(folder, self.recursive_cb.isChecked(),
                                self.frames_spin.value(), self.thresh_spin.value())
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def stop_scan(self):
        if self.worker:
            self.worker.stop()
            self.status.setText("중지 요청됨...")

    def on_progress(self, val, msg):
        self.progress.setValue(val)
        self.status.setText(msg)

    def on_error(self, msg):
        self.btn_scan.setEnabled(True)
        self.btn_stop.setEnabled(False)
        QMessageBox.critical(self, "오류", msg)
        self.append_log(f"오류: {msg}")

    def on_finished(self, result):
        self.btn_scan.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if result.get("cancelled"):
            self.status.setText("취소됨")
            self.append_log("스캔 취소됨")
            return
        groups = result.get("groups", [])
        self.groups = groups
        total = result.get('total_files', 0)
        valid = result.get('valid', 0)
        self.append_log(f"스캔 완료: 전체 파일 {total}개, 유효 영상 {valid}개, 중복 그룹 {len(groups)}개")
        self.status.setText(f"완료: 전체 {total}개 / 유효 {valid}개 / 중복 그룹 {len(groups)}개")
        self._populate_table(groups)
        if groups:
            self.btn_delete.setEnabled(True)
            QMessageBox.information(self, "스캔 완료",
                f"전체 {total}개 파일 중 유효 영상 {valid}개를 분석했습니다.\n"
                f"중복 그룹 {len(groups)}개를 찾았습니다. 결과를 확인 후 삭제하세요.")
        else:
            if valid == 0:
                QMessageBox.warning(self, "스캔 결과",
                    "유효한 영상 파일을 찾지 못했습니다.\n"
                    "폴더 경로와 영상 형식을 확인하세요. (mp4, mkv, avi, mov 등)")
            else:
                QMessageBox.information(self, "스캔 결과",
                    f"유효 영상 {valid}개를 찾았지만 중복으로 판단된 영상이 없습니다.\n"
                    "임계값을 높이거나 다른 폴더를 시도해 보세요.")

    def _populate_table(self, groups):
        self.table.setRowCount(0)
        row = 0
        for gi, g in enumerate(groups, start=1):
            keeper, deletions = None, None
            from core.quality import to_delete, pick_keeper
            dels, keeper = to_delete(g)
            del_paths = {d["path"] for d in dels}
            for info in g:
                self.table.insertRow(row)
                # checkbox
                cb = QCheckBox()
                is_del = info["path"] in del_paths
                cb.setChecked(is_del)
                # 유지 판정 파일도 사용자가 체크하면 삭제 가능
                self.table.setCellWidget(row, 0, cb)
                self.table.setItem(row, 1, QTableWidgetItem(f"그룹 {gi}"))
                self.table.setItem(row, 2, QTableWidgetItem(info["name"]))
                self.table.setItem(row, 3, QTableWidgetItem(info["path"]))
                self.table.setItem(row, 4, QTableWidgetItem(f"{info['width']}x{info['height']}"))
                self.table.setItem(row, 5, QTableWidgetItem(f"{info['bitrate']//1000} kbps"))
                self.table.setItem(row, 6, QTableWidgetItem(human_size(info["filesize"])))
                self.table.setItem(row, 7, QTableWidgetItem(fmt_dur(info["duration"])))
                verdict = "유지 (최고 품질)" if info["path"] == keeper["path"] else "삭제 예정"
                item = QTableWidgetItem(verdict)
                if info["path"] == keeper["path"]:
                    item.setForeground(QColor("green"))
                else:
                    item.setForeground(QColor("red"))
                self.table.setItem(row, 8, item)
                row += 1
        self.table.resizeColumnsToContents()

    def check_ffmpeg(self):
        if fm.is_available():
            self.append_log(f"FFmpeg 확인됨: {fm.get_ffprobe_path()}")
            return
        ret = QMessageBox.question(
            self, "FFmpeg 필요",
            "FFmpeg가 설치되어 있지 않습니다.\n자동으로 다운로드/설치하시겠습니까? (약 30~80MB, 인터넷 필요)\n"
            "거부하면 수동으로 설치해야 스캔이 가능합니다.",
            QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.start_ffmpeg_download()
        else:
            self.append_log("FFmpeg 미설치 상태입니다. 'FFmpeg 자동 설치' 버튼으로 나중에 설치할 수 있습니다.")
            self.status.setText("FFmpeg 필요 - 스캔 불가")

    def manual_ffmpeg_install(self):
        if fm.is_available():
            QMessageBox.information(self, "정보", f"이미 설치되어 있습니다.\n{fm.get_ffprobe_path()}")
            return
        self.start_ffmpeg_download()

    def open_help(self):
        if getattr(self, "_help_dlg", None) is not None and self._help_dlg.isVisible():
            self._help_dlg.raise_()
            self._help_dlg.activateWindow()
            return
        dlg = HelpDialog(self)
        self._help_dlg = dlg
        dlg.finished.connect(lambda: setattr(self, "_help_dlg", None))
        dlg.show()

    def start_ffmpeg_download(self):
        self.btn_scan.setEnabled(False)
        self.btn_ffmpeg.setEnabled(False)
        self.progress.setValue(0)
        self.status.setText("FFmpeg 다운로드 준비 중...")
        self.ff_worker = FFmpegDownloadWorker()
        self.ff_worker.progress.connect(self.on_ffmpeg_progress)
        self.ff_worker.finished.connect(self.on_ffmpeg_finished)
        self.ff_worker.start()

    def on_ffmpeg_progress(self, val, msg):
        self.progress.setValue(val)
        self.status.setText(msg)

    def on_ffmpeg_finished(self, ok, msg):
        self.btn_scan.setEnabled(True)
        self.btn_ffmpeg.setEnabled(True)
        if ok:
            self.append_log(msg)
            self.status.setText("FFmpeg 설치 완료")
            QMessageBox.information(self, "완료", "FFmpeg 설치가 완료되었습니다. 이제 스캔할 수 있습니다.")
        else:
            self.append_log(f"FFmpeg 설치 실패: {msg}")
            self.status.setText("FFmpeg 설치 실패")
            QMessageBox.critical(self, "실패", f"FFmpeg 설치에 실패했습니다.\n{msg}\n\n수동 설치 방법은 사용법.html을 참고하세요.")

    def delete_selected(self):
        # 수집
        to_del = []
        for r in range(self.table.rowCount()):
            cb = self.table.cellWidget(r, 0)
            if isinstance(cb, QCheckBox) and cb.isChecked():
                path_item = self.table.item(r, 3)
                if path_item:
                    to_del.append(path_item.text())
        if not to_del:
            QMessageBox.information(self, "정보", "삭제할 파일이 선택되지 않았습니다.")
            return
        # 확인
        msg = f"{len(to_del)}개 파일을 삭제합니다.\n(휴지통 이동을 우선 시도하고, 실패 시 '_삭제된_중복영상' 폴더로 이동합니다.)\n계속하시겠습니까?"
        ret = QMessageBox.question(self, "확인", msg, QMessageBox.Yes | QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        import shutil
        ok, fail = 0, []
        success_paths = set()
        # 백업 폴더 (휴지통 이동 실패 시 대체) - 바탕화면
        backup_root = os.path.join(os.path.expanduser("~"), "Desktop", "_삭제된_중복영상")
        os.makedirs(backup_root, exist_ok=True)

        for p in to_del:
            # 1차/2차: 휴지통 이동 (send2trash -> SHFileOperationW)
            success, method = rcy.recycle(p)
            if success:
                ok += 1
                success_paths.add(p)
                self.append_log(f"삭제({method}): {p}")
                continue
            # 3차: 백업 폴더로 이동
            try:
                rel = os.path.basename(p)
                dest = os.path.join(backup_root, rel)
                stem, ext = os.path.splitext(rel)
                i = 1
                while os.path.exists(dest):
                    dest = os.path.join(backup_root, f"{stem}_{i}{ext}")
                    i += 1
                shutil.move(p, dest)
                ok += 1
                success_paths.add(p)
                self.append_log(f"휴지통 실패 -> 백업 폴더로 이동: {dest}")
            except Exception as e2:
                fail.append((p, str(e2)))
                self.append_log(f"실패: {p} -> {e2}")
        rows_to_remove = []
        for r in range(self.table.rowCount()):
            cb = self.table.cellWidget(r, 0)
            if isinstance(cb, QCheckBox) and cb.isChecked():
                pi = self.table.item(r, 3)
                if pi and pi.text() in success_paths:
                    rows_to_remove.append(r)
        for r in sorted(rows_to_remove, reverse=True):
            self.table.removeRow(r)
        if fail:
            QMessageBox.warning(self, "일부 실패", f"성공 {ok}, 실패 {len(fail)}\n{fail[0][1]}")
        else:
            QMessageBox.information(self, "완료", f"{ok}개 파일을 휴지통으로 이동했습니다.")
        # 테이블에서 삭제된 행 제거? 간단히 재스캔 안내
        self.append_log("※ 휴지통에서 복원 가능합니다.")


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
