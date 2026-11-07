"""품질 점수 및 유지 파일 선택."""
import os


def quality_key(info):
    """정렬용 키: 높을수록 좋은 품질. (pixels, bitrate, filesize, fps)"""
    return (info.get("pixels", 0),
            info.get("bitrate", 0),
            info.get("filesize", 0),
            info.get("fps", 0))


def pick_keeper(group):
    """그룹에서 유지할(가장 좋은 품질) 파일 info 반환."""
    best = max(group, key=quality_key)
    return best


def to_delete(group):
    keeper = pick_keeper(group)
    return [g for g in group if g["path"] != keeper["path"]], keeper
