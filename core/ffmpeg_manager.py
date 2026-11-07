"""FFmpeg/ffprobe 자동 탐지 및 자동 설치."""
import os
import sys
import shutil
import zipfile
import tempfile
import urllib.request


FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def app_root():
    if getattr(sys, "frozen", False):
        # 쓰기 가능한 사용자 폴더 사용 (Program Files 등 읽기전용 위치 대비)
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "VideoDedup")
    # core/ 의 상위 = 프로젝트 루트
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tools_dir():
    return os.path.join(app_root(), "tools", "ffmpeg")


def _find_in_tools(name):
    p = os.path.join(tools_dir(), name)
    if os.path.isfile(p):
        return p
    return None


def _find_in_path(name):
    return shutil.which(name)


def get_ffmpeg_path():
    p = _find_in_tools("ffmpeg.exe")
    if p:
        return p
    p = _find_in_path("ffmpeg")
    if p:
        return p
    # unix fallback
    p = _find_in_path("ffmpeg.exe")
    return p


def get_ffprobe_path():
    p = _find_in_tools("ffprobe.exe")
    if p:
        return p
    p = _find_in_path("ffprobe")
    if p:
        return p
    p = _find_in_path("ffprobe.exe")
    return p


def is_available():
    return get_ffmpeg_path() is not None and get_ffprobe_path() is not None


def _download(url, dest, progress_cb):
    with urllib.request.urlopen(url, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0) or 0)
        downloaded = 0
        chunk_size = 1024 * 256
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total > 0:
                    pct = min(99, int(downloaded * 100 / total))
                    progress_cb(pct, f"다운로드 중... {downloaded//1024//1024}MB / {total//1024//1024}MB")
    if progress_cb:
        progress_cb(100, "다운로드 완료")


def download_and_install(progress_cb=None):
    """FFmpeg를 다운로드하여 tools/ffmpeg 에 설치. (ffmpeg_path, ffprobe_path) 반환."""
    tmp_zip = os.path.join(tempfile.gettempdir(), "ffmpeg-essentials.zip")
    extract_dir = tempfile.mkdtemp(prefix="ffmpeg-extract-")
    try:
        if progress_cb:
            progress_cb(0, "다운로드 시작...")
        _download(FFMPEG_URL, tmp_zip, progress_cb)

        if progress_cb:
            progress_cb(100, "압축 해제 중...")
        with zipfile.ZipFile(tmp_zip) as z:
            z.extractall(extract_dir)

        ffmpeg_src = None
        ffprobe_src = None
        for root, _dirs, files in os.walk(extract_dir):
            for f in files:
                low = f.lower()
                if low == "ffmpeg.exe" and ffmpeg_src is None:
                    ffmpeg_src = os.path.join(root, f)
                elif low == "ffprobe.exe" and ffprobe_src is None:
                    ffprobe_src = os.path.join(root, f)

        if not ffmpeg_src or not ffprobe_src:
            raise RuntimeError("압축 파일에서 ffmpeg.exe/ffprobe.exe를 찾지 못했습니다.")

        dest = tools_dir()
        os.makedirs(dest, exist_ok=True)
        shutil.copy2(ffmpeg_src, os.path.join(dest, "ffmpeg.exe"))
        shutil.copy2(ffprobe_src, os.path.join(dest, "ffprobe.exe"))

        if progress_cb:
            progress_cb(100, "설치 완료")
        return get_ffmpeg_path(), get_ffprobe_path()
    finally:
        try:
            if os.path.isfile(tmp_zip):
                os.remove(tmp_zip)
        except OSError:
            pass
        shutil.rmtree(extract_dir, ignore_errors=True)
