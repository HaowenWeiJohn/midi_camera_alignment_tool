import os
from datetime import datetime, timezone

file_path = r"C:\Users\mitim\Desktop\MITHIC\data\010\disklavier\20250515_155406_pia02_s010_008_ap1a_generalization.mid"


def fmt(ts: float) -> str:
    local = datetime.fromtimestamp(ts).isoformat()
    utc = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    return f"{ts:.3f}  |  local={local}  |  utc={utc}"


stat = os.stat(file_path)

print(f"File: {file_path}\n")
print(f"Modified  (mtime): {fmt(stat.st_mtime)}")
print(f"Accessed  (atime): {fmt(stat.st_atime)}")
print(f"Created   (ctime): {fmt(stat.st_ctime)}")  # Windows: creation time; Unix: inode change time

# Cross-platform "birth time" (true creation time) — available on Windows and macOS.
birth = getattr(stat, "st_birthtime", None)
if birth is not None:
    print(f"Birth   (btime): {fmt(birth)}")

print(f"\nSize: {stat.st_size} bytes")
