from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('PIT_DATA_DIR', ROOT / 'data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'pitscope.sqlite3'


def read_env(path: Path) -> dict:
    values = {}
    if path.is_file():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.strip().startswith('#'):
                key, value = line.split('=', 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def model_settings() -> dict:
    # External files are read only when explicitly configured by the operator.
    external = os.environ.get('PIT_ENV_FILE')
    values = {**(read_env(Path(external)) if external else {}), **read_env(ROOT / '.env'), **os.environ}
    return {
        'key': values.get('PIT_LLM_API_KEY') or values.get('DEEPSEEK_API_KEY', ''),
        'base_url': values.get('PIT_LLM_BASE_URL', 'https://api.deepseek.com').rstrip('/'),
        'model': values.get('PIT_LLM_MODEL', 'deepseek-chat'),
    }
