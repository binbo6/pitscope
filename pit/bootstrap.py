"""Seed redistributable, entirely synthetic example data without network access."""
from __future__ import annotations

import csv
import json
import math
import shutil
from pathlib import Path

from .knowledge import initialize, ingest
from .settings import DATA, ROOT

DEMO_ID = 'DEMO-PIT-001'


def portable_path(path: Path) -> str:
    path = path.resolve()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def seed():
    initialize()
    sources = DATA / 'sources'
    sources.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / 'examples/corpus/manifest.json').read_text(encoding='utf-8'))
    result = []
    for item in manifest:
        original = ROOT / 'examples/corpus' / item['file']
        target = sources / item['file']
        if not target.exists() or target.read_bytes() != original.read_bytes():
            shutil.copyfile(original, target)
        result.append(ingest(target, kind=item['kind'], scope=item['scope'],
                             url=item.get('url', ''), note=item['note']))
    case_dir = DATA / 'cases/demo'
    case_dir.mkdir(parents=True, exist_ok=True)
    stages = []
    for i, (down, up, depth, date) in enumerate(zip(
        [3.8, 8.7, 14.6, 21.4], [.9, 2.1, 4.0, 6.2], [4, 8, 12, 15.7],
        ['2026-10-15', '2026-10-19', '2026-10-23', '2026-10-27']), 1):
        stage = {'id': f'S{i}', 'name': f'阶段 {i} · 演示开挖至 {depth} m',
                 'date': date, 'depth_m': depth}
        for region in ('ground', 'bottom'):
            path = case_dir / f'{region}_s{i}.csv'
            rows = []
            for j in range(72 if region == 'ground' else 35):
                if region == 'ground':
                    x, y, z = 20 + (j % 12) * 5, 0, (j // 12 - 2.5) * 10
                    value = round(down * math.exp(-((x - 30) / 37)**2 - ((z - 5) / 33)**2), 4)
                    ident = 1001 + j
                else:
                    x, y, z = (j % 7 - 3) * 5, 15.7, (j // 7 - 2) * 10
                    value = round(-up * math.exp(-(x / 18)**2 - (z / 22)**2), 4)
                    ident = 2001 + j
                rows.append([ident, x, y, z, 0, value / 1000, 0, value])
            with path.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['gp_id','x_m','y_m','z_m','ux_m','uy_m','uz_m','settlement_mm'])
                writer.writerows(rows)
            stage[region] = portable_path(path)
        stages.append(stage)
    case = {
        'id': DEMO_ID, 'name': '公开演示 · 基坑沉降与隆起分析', 'is_demo': True,
        'location': '虚构场地 / 演示局部坐标', 'depth_m': 15.7,
        'support': '地下连续墙 + 内支撑（虚构方案）',
        'baseline': '相对于同一初始基准的累计位移',
        'description': '完全虚构的勘察背景 + 演示监测要求 + 四阶段合成 CSV + 可追溯报告',
        'quality': {'data_type': 'synthetic', 'solver_run': False,
                    'project_linkage_verified': False,
                    'note': '公开示例全部虚构；未实施现场监测或 FLAC3D 求解。'},
        'stages': stages,
        'controls': {
            'ground': {'metric':'max_downward_mm', 'limit_mm':20,
                       'source':'demo_project_brief.md / 演示控制值（人为设定）', 'is_demo':True},
            'bottom': {'metric':'max_upward_mm', 'limit_mm':10,
                       'source':'demo_project_brief.md / 演示控制值（人为设定）', 'is_demo':True},
        },
    }
    (case_dir / 'case.json').write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def load_case():
    return json.loads((DATA / 'cases/demo/case.json').read_text(encoding='utf-8'))


if __name__ == '__main__':
    for item in seed():
        print(item['name'], item['chunks'], 'chunks')
