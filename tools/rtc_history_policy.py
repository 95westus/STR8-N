"""Read immutable-report exclusions without modifying baseline or board data."""
import hashlib,json
from pathlib import Path

def excluded_reports(baseline_index):
    index=Path(baseline_index);policy=index.parent/'history-exclusions.json'
    if not policy.exists():return set()
    data=json.loads(policy.read_text())
    assert data['baseline_index_sha256']==hashlib.sha256(index.read_bytes()).hexdigest(), 'Exclusion policy baseline mismatch'
    return {item['report_sha256'] for item in data['observations']}
