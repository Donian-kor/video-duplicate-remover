"""중복 그룹핑."""
from core.metadata import get_info


def _duration_close(a, b, tol_sec=2.0, tol_pct=0.01):
    da, db = a["duration"], b["duration"]
    if da <= 0 or db <= 0:
        return False
    diff = abs(da - db)
    if diff <= tol_sec:
        return True
    if diff / max(da, db) <= tol_pct:
        return True
    return False


def group_duplicates(infos, hashes_map, distance_threshold=12.0):
    """infos: list of VideoInfo dict. hashes_map: path -> hash list or None.
    Returns list of groups, each group is list of info dicts (size>=2)."""
    n = len(infos)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # 1) duration 기반 후보 쌍 비교
    for i in range(n):
        for j in range(i + 1, n):
            if not _duration_close(infos[i], infos[j]):
                continue
            # 해시 비교
            ha = hashes_map.get(infos[i]["path"])
            hb = hashes_map.get(infos[j]["path"])
            # 해시가 둘 다 있으면 시각 유사도
            if ha is not None and hb is not None:
                from core.hasher import video_distance
                d = video_distance(ha, hb)
                if d is None:
                    continue
                if d <= distance_threshold:
                    union(i, j)
            else:
                # 해시 없음: 메타데이터만으로 동일 가능성 (같은 길이 + 같은 해상도/용량)
                if (infos[i]["pixels"] == infos[j]["pixels"]
                        and infos[i]["filesize"] == infos[j]["filesize"]):
                    union(i, j)

    # 그룹 수집
    groups_map = {}
    for i in range(n):
        r = find(i)
        groups_map.setdefault(r, []).append(infos[i])
    groups = [g for g in groups_map.values() if len(g) >= 2]
    return groups
