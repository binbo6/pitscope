from __future__ import annotations

import csv
import math
from pathlib import Path

FIELDS = ('gp_id','x_m','y_m','z_m','ux_m','uy_m','uz_m','settlement_mm')


def read_points(path: Path):
    rows, ids = [], set()
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or any(x not in reader.fieldnames for x in FIELDS):
            raise ValueError('CSV 必须包含：' + ','.join(FIELDS))
        for line, raw in enumerate(reader, 2):
            try:
                row = {k:float(raw[k]) for k in FIELDS[1:]}
                row['gp_id'] = int(raw['gp_id'])
                if not all(math.isfinite(row[k]) for k in FIELDS[1:]):
                    raise ValueError('存在非有限数值')
                if abs(row['settlement_mm']-1000*row['uy_m']) > .001:
                    raise ValueError('settlement_mm 与 1000 × uy_m 不一致')
                if row['gp_id'] in ids:
                    raise ValueError('存在重复节点')
            except (ValueError,TypeError,KeyError) as exc:
                raise ValueError(f'{path.name} 第 {line} 行：{exc}') from exc
            ids.add(row['gp_id']);rows.append(row)
    if not rows:
        raise ValueError('CSV 没有数据')
    return rows


def statistics(rows):
    down = max(rows, key=lambda x:x['settlement_mm'])
    up = min(rows, key=lambda x:x['settlement_mm'])
    def point(row, exists):
        return {'id':row['gp_id'],'xyz_m':[row[k] for k in ('x_m','y_m','z_m')]} if exists else None
    return {
        'count':len(rows), 'max_downward_mm':max(0,down['settlement_mm']),
        'max_upward_mm':max(0,-up['settlement_mm']),
        'downward_point':point(down,down['settlement_mm']>0),
        'upward_point':point(up,up['settlement_mm']<0),
        'mean_signed_mm':round(sum(r['settlement_mm'] for r in rows)/len(rows),4),
        'range_mm':[up['settlement_mm'],down['settlement_mm']],
    }


def analyze_case(case):
    stages = []
    from .settings import ROOT
    for stage in case['stages']:
        regions = {}
        for region in ('ground','bottom'):
            if stage.get(region):
                path = ROOT / stage[region]
                rows = read_points(path)
                regions[region] = {**statistics(rows), 'points':rows, 'source':stage[region]}
        stages.append({k:v for k,v in stage.items() if k not in ('ground','bottom')} | {'regions':regions})
    latest = stages[-1]
    checks = []
    for region,metric,label in [('ground','max_downward_mm','地表累计沉降'),('bottom','max_upward_mm','坑底累计隆起')]:
        rule = case.get('controls',{}).get(region)
        if not rule or region not in latest['regions']:
            continue
        if rule.get('metric') != metric or not rule.get('source'):
            raise ValueError('控制指标须与分区、位移方向匹配，并提供来源')
        limit = rule.get('limit_mm')
        if isinstance(limit,bool) or not isinstance(limit,(int,float)) or not math.isfinite(limit) or limit <= 0:
            raise ValueError('控制值必须是有限正数')
        actual = latest['regions'][region][metric]
        checks.append({'region':region,'label':label,'actual_mm':actual,'limit_mm':limit,
                       'ratio':round(actual/limit,4),'exceeded':actual>limit,'source':rule['source'],
                       'is_demo':rule.get('is_demo',False)})
    return {'case_id':case['id'],'is_demo':case['is_demo'],'stages':stages,'latest':latest,'checks':checks,
            'coordinate_convention':'+Y 向下，settlement_mm = 1000 × uy_m；负值表示向上位移',
            'quality':case['quality']}
