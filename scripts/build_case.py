"""Generate a runnable demonstration and optionally refresh public sample artifacts."""
from __future__ import annotations

import argparse
import json
import shutil

from pit.assistant import answer
from pit.bootstrap import seed, load_case
from pit.analysis import analyze_case
from pit.reporting import docx_bytes, pdf_bytes, html_document
from pit.settings import ROOT


def main(offline=True, publish_samples=False):
    seed()
    result = answer('分析公开案例四阶段地表沉降与坑底隆起，结合演示资料生成完整报告。',
                    mode='report', engine='offline' if offline else 'auto')
    out = ROOT / ('examples/output' if publish_samples else 'deliverables')
    out.mkdir(parents=True, exist_ok=True)
    text = result['content']
    (out / 'report.md').write_text(text, encoding='utf-8')
    (out / 'report.html').write_text(html_document(text), encoding='utf-8')
    (out / 'report.docx').write_bytes(docx_bytes(text))
    (out / 'report.pdf').write_bytes(pdf_bytes(text))
    analysis = analyze_case(load_case())
    for stage in analysis['stages']:
        for region in stage['regions'].values():
            region.pop('points', None)
            region['source'] = 'examples/dataset/' + region['source'].replace('\\', '/').split('/')[-1]
    analysis['latest'] = analysis['stages'][-1]
    (out / 'summary.json').write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding='utf-8')
    evidence = [{k:v for k,v in e.items() if k not in ('path', 'id', 'document_id')}
                for e in result['evidence']]
    (out / 'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'generation.json').write_text(json.dumps({'case_id':analysis['case_id'],
        'engine':result['engine'], 'data_type':'synthetic', 'documents':'examples/corpus',
        'note':('Offline extractive sample; no model was called.' if result['engine']=='offline-extractive'
                else 'Model-generated narrative using only the synthetic public corpus and computed summary.')}, indent=2), encoding='utf-8')
    if publish_samples:
        dataset = ROOT / 'examples/dataset'
        dataset.mkdir(exist_ok=True)
        case = load_case()
        for stage in case['stages']:
            for region in ('ground', 'bottom'):
                source = ROOT / stage[region]
                shutil.copyfile(source, dataset / source.name)
                stage[region] = 'examples/dataset/' + source.name
        (dataset / 'case.json').write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'engine':result['engine'], 'output':str(out)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--llm', action='store_true', help='Explicitly call the configured model')
    parser.add_argument('--publish-samples', action='store_true')
    args = parser.parse_args()
    main(offline=not args.llm, publish_samples=args.publish_samples)
