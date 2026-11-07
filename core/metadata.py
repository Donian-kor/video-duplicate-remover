"""동영상 메타데이터 추출 (ffprobe 기반)."""
import json
import subprocess
import os

from core import ffmpeg_manager as fm

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
              ".m4v", ".mpg", ".mpeg", ".ts", ".m2ts", ".3gp"}


def is_video(path):
    return os.path.splitext(path)[1].lower() in VIDEO_EXTS


def _ffprobe_bin():
    p = fm.get_ffprobe_path()
    return p if p else "ffprobe"


def _run_ffprobe(path):
    cmd = [
        _ffprobe_bin(), "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,codec_name,bit_rate,nb_frames",
        "-show_entries", "format=duration,size,bit_rate,format_name",
        "-of", "json", path,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
    except Exception:
        return None
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except Exception:
        return None


def _parse_fps(s):
    if not s or s == "0/0":
        return 0.0
    try:
        if "/" in s:
            a, b = s.split("/")
            a, b = float(a), float(b)
            if b == 0:
                return 0.0
            return a / b
        return float(s)
    except Exception:
        return 0.0


def get_info(path):
    """파일 경로 -> VideoInfo dict. 실패 시 None."""
    data = _run_ffprobe(path)
    if not data:
        return None
    streams = data.get("streams") or []
    fmt = data.get("format") or {}
    v = streams[0] if streams else {}
    width = int(v.get("width") or 0)
    height = int(v.get("height") or 0)
    fps = _parse_fps(v.get("r_frame_rate"))
    codec = v.get("codec_name") or ""
    # 비트레이트: 스트림 우선, 없으면 포맷
    br = v.get("bit_rate")
    if not br:
        br = fmt.get("bit_rate")
    try:
        bitrate = int(br) if br else 0
    except (ValueError, TypeError):
        bitrate = 0
    dur = fmt.get("duration")
    try:
        duration = float(dur) if dur else 0.0
    except (ValueError, TypeError):
        duration = 0.0
    size = fmt.get("size")
    try:
        filesize = int(size) if size else os.path.getsize(path)
    except (ValueError, TypeError, OSError):
        try:
            filesize = os.path.getsize(path)
        except OSError:
            filesize = 0
    if width == 0 or height == 0 or duration <= 0:
        return None
    # 초당 비트레이트가 0이면 파일크기/길이로 추정
    if bitrate <= 0 and duration > 0:
        bitrate = int(filesize * 8 / duration)
    return {
        "path": path,
        "name": os.path.basename(path),
        "width": width,
        "height": height,
        "pixels": width * height,
        "fps": fps,
        "codec": codec,
        "bitrate": bitrate,
        "duration": duration,
        "filesize": filesize,
    }
