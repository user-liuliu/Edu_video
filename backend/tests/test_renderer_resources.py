import json
import os
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.parametrize('quota,expected',[('200000 100000',2),('150000 100000',2),('max 100000',None)])
def test_renderer_respects_container_cpu_quota_before_launching_encoder(tmp_path,quota,expected):
    if not hasattr(os,'sched_getaffinity'):pytest.skip('Linux CPU affinity check')
    available=len(os.sched_getaffinity(0))
    source=Path(__file__).resolve().parents[2]
    file=tmp_path/'cpu.max';file.write_text(quota)
    code='import json,os; from renderer.resources import limit_cpu_affinity; limit_cpu_affinity('+repr(str(file))+'); print(json.dumps(len(os.sched_getaffinity(0))))'
    result=subprocess.run([sys.executable,'-c',code],env={**os.environ,'PYTHONPATH':str(source)},capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)==(min(expected,available) if expected else available)
