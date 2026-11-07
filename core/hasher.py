"""프레임 샘플링 + 지각 해시(perceptual hash)."""
import cv2
import numpy as np


def _phash_frame(frame, hash_size=8):
    """단일 프레임 -> 64비트 정수 해시."""
    if frame is None:
        return None
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
    # DCT
    dct = cv2.dct(np.float32(resized))
    # 좌상단 8x8 (DC 제외하지 않고 사용; median 기준)
    low = dct[:8, :8].flatten()
    med = np.median(low)
    bits = (low > med).astype(np.uint8)
    # 64비트 정수로 패킹
    val = 0
    for b in bits:
        val = (val << 1) | int(b)
    return val


def sample_hashes(path, num_frames=8, fractions=None):
    """영상에서 num_frames 개 프레임을 균등 샘플링해 해시 리스트 반환.
    실패 시 None."""
    if fractions is None:
        # 양 끝 제외, 균등
        fractions = [i / (num_frames + 1) for i in range(1, num_frames + 1)]
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps if fps and fps > 0 else 0
        # duration이 0이면 프레임 수로만
        hashes = []
        for f in fractions:
            if total > 0:
                idx = int(total * f)
                if idx >= total:
                    idx = total - 1
                if idx < 0:
                    idx = 0
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            else:
                # fallback: 시간 기반
                if duration > 0:
                    cap.set(cv2.CAP_PROP_POS_MSEC, duration * 1000 * f)
            ok, frame = cap.read()
            if not ok or frame is None:
                # 재시도: POS_MSEC
                if duration > 0:
                    cap.set(cv2.CAP_PROP_POS_MSEC, duration * 1000 * f)
                    ok, frame = cap.read()
            if not ok or frame is None:
                hashes.append(None)
                continue
            h = _phash_frame(frame)
            hashes.append(h)
        # 유효 해시가 너무 적으면 실패
        valid = [h for h in hashes if h is not None]
        if len(valid) < max(1, num_frames // 2):
            return None
        return hashes
    finally:
        cap.release()


def hamming(a, b):
    if a is None or b is None:
        return None
    x = a ^ b
    # bit count
    return bin(x).count("1")


def video_distance(hashes_a, hashes_b):
    """두 해시 리스트 간 평균 해밍 거리. None 반환 시 비교 불가."""
    if not hashes_a or not hashes_b:
        return None
    n = min(len(hashes_a), len(hashes_b))
    dists = []
    for i in range(n):
        d = hamming(hashes_a[i], hashes_b[i])
        if d is not None:
            dists.append(d)
    if not dists:
        return None
    return sum(dists) / len(dists)
