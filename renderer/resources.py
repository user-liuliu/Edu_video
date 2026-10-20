"""Keep browser/encoder worker pools within the container CPU allocation."""
import math
import os
from pathlib import Path


def limit_cpu_affinity(quota_file='/sys/fs/cgroup/cpu.max'):
    if not hasattr(os,'sched_getaffinity'):return
    try:
        quota,period=Path(quota_file).read_text().split()
        if quota=='max':return
        budget=max(1,math.ceil(int(quota)/int(period)))
        allowed=sorted(os.sched_getaffinity(0))
        if len(allowed)>budget:os.sched_setaffinity(0,allowed[:budget])
    except (OSError,ValueError,ZeroDivisionError):
        # Non-cgroup and non-Linux development environments retain defaults.
        return
