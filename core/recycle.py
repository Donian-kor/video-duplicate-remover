"""Windows 휴지통 삭제 (send2trash + SHFileOperationW 폴백)."""
import os
import stat
import ctypes
from ctypes import wintypes


FO_DELETE = 3
FOF_ALLOWUNDO = 0x0040
FOF_NOCONFIRMATION = 0x0010
FOF_SILENT = 0x0004
FOF_NOERRORUI = 0x0400


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", wintypes.WORD),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", wintypes.LPVOID),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def _remove_readonly(path):
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def _shfile_delete(path):
    """SHFileOperationW(레거시)로 휴지통 이동. 성공 시 True."""
    try:
        if not os.path.exists(path):
            return False
        _remove_readonly(path)
        abs_path = os.path.abspath(path)
        # SHFileOperationW 는 더블 NULL 종료 문자열 필요
        buf = abs_path + "\x00\x00"
        op = _SHFILEOPSTRUCTW()
        op.hwnd = 0
        op.wFunc = FO_DELETE
        op.pFrom = buf
        op.pTo = None
        op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
        op.fAnyOperationsAborted = False
        op.hNameMappings = None
        op.lpszProgressTitle = None
        res = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        if res != 0:
            return False
        if op.fAnyOperationsAborted:
            return False
        return not os.path.exists(path)
    except Exception:
        return False


def recycle(path):
    """파일을 휴지통으로 이동. (성공여부, 방법문자열) 반환."""
    # 1차: send2trash (IFileOperation)
    try:
        import send2trash
        send2trash.send2trash(path)
        if not os.path.exists(path):
            return True, "휴지통(send2trash)"
    except Exception:
        pass

    # 2차: SHFileOperationW (레거시, IFileOperation 실패 시 자주 성공)
    if _shfile_delete(path):
        return True, "휴지통(SHFileOperation)"

    return False, None
