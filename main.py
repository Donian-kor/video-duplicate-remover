"""동영상 중복 제거기 실행 진입점."""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

# FFmpeg 경로 사전 등록 (있으면)
try:
    from core.ffmpeg_manager import find_ffmpeg_dir, _register_path
    d = find_ffmpeg_dir()
    if d:
        _register_path(d)
except Exception:
    pass

from ui.main_window import main

if __name__ == "__main__":
    main()
