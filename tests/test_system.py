import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

SANDBOX = tempfile.TemporaryDirectory(prefix='pitscope-tests-')
os.environ['PIT_DATA_DIR'] = SANDBOX.name

from fastapi.testclient import TestClient
from pit.analysis import read_points, statistics, analyze_case
from pit.bootstrap import seed, load_case
from pit.knowledge import documents, index, ingest
from pit.assistant import answer, evidence_for
from pit.reporting import docx_bytes, pdf_bytes, safe_html
from pit.server import app
from pit.settings import model_settings


class SystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed()

    def csv(self, lines):
        path = Path(SANDBOX.name) / 'input.csv'
        path.write_text('gp_id,x_m,y_m,z_m,ux_m,uy_m,uz_m,settlement_mm\n' + lines, encoding='utf-8')
        return path

    def test_csv_units_duplicates_nonfinite_and_empty(self):
        for lines in ['', '1,0,0,0,0,.002,0,20\n', '1,0,0,0,0,nan,0,0\n',
                      '1,0,0,0,0,0,0,0\n1,0,0,0,0,0,0,0\n']:
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                read_points(self.csv(lines))

    def test_direction_zero_id_and_locations(self):
        stats = statistics(read_points(self.csv('0,1,2,3,0,-.004,0,-4\n')))
        self.assertIsNone(stats['downward_point'])
        self.assertEqual(stats['max_downward_mm'], 0)
        self.assertEqual(stats['upward_point'], {'id':0, 'xyz_m':[1,2,3]})

    def test_four_stage_extrema_and_control_direction(self):
        data = analyze_case(load_case())
        self.assertEqual([s['regions']['ground']['max_downward_mm'] for s in data['stages']], [3.8,8.7,14.6,21.4])
        self.assertEqual(data['latest']['regions']['bottom']['max_upward_mm'], 6.2)
        self.assertTrue(data['checks'][0]['exceeded'])
        self.assertFalse(data['checks'][1]['exceeded'])
        case = load_case();case['controls']['bottom']['metric'] = 'max_downward_mm'
        with self.assertRaises(ValueError):analyze_case(case)

    def test_control_value_requires_finite_number_and_source(self):
        for value in [True, float('inf'), -1]:
            case = load_case();case['controls']['ground']['limit_mm'] = value
            with self.assertRaises(ValueError):analyze_case(case)
        case = load_case();case['controls']['ground']['source'] = ''
        with self.assertRaises(ValueError):analyze_case(case)

    def test_seed_idempotence_and_reference_exclusion(self):
        before = len(documents());seed()
        self.assertEqual(before, len(documents()))
        hits = index.search('异项目 基坑 地下水 沉降', limit=20)
        self.assertTrue(hits)
        self.assertFalse(any(h['scope'] == 'reference' for h in hits))

    def test_demo_requirements_retrieval(self):
        hits = index.search('DEMO-M02 数据异常复核 重复节点')
        self.assertTrue(any(h['name']=='demo_monitoring_guide.md' and 'DEMO-M02' in h['text'] for h in hits))

    def test_pdf_ingestion_retains_physical_page(self):
        import pymupdf
        path = Path(SANDBOX.name) / 'fixture.pdf'
        doc = pymupdf.open();page=doc.new_page();page.insert_text((72,72),'Settlement monitoring fixture page one.')
        page=doc.new_page();page.insert_text((72,72),'UniqueAlpha evidence on physical page two.');doc.save(path);doc.close()
        ingest(path, kind='reference', scope='reference', note='Synthetic test fixture')
        hits=index.search('UniqueAlpha', include_reference=True)
        self.assertTrue(any(h['page']==2 and h['name']=='fixture.pdf' for h in hits))

    def test_imported_scope_excludes_demo_background(self):
        hits=evidence_for('地下水 基坑 变形', report=True, case_id='USER-abcdefabcdef')
        self.assertTrue(hits)
        self.assertFalse(any(h['scope']=='demo' for h in hits))

    def test_explicit_offline_never_calls_provider(self):
        with patch('pit.llm.generate') as model:
            result=answer('分析地表沉降', engine='offline')
        model.assert_not_called()
        self.assertEqual(result['engine'],'offline-extractive')
        self.assertIn('21.400',result['content'])

    def test_model_failure_and_invalid_citation_fallback(self):
        for failure in [RuntimeError('unavailable'), ('unsupported [E999]','test-model')]:
            with patch('pit.llm.generate', **({'side_effect':failure} if isinstance(failure,Exception) else {'return_value':failure})):
                result=answer('分析沉降',engine='auto')
            self.assertEqual(result['engine'],'offline-extractive')
            self.assertTrue(result['warning'])

    def test_history_and_case_isolation(self):
        with patch('pit.llm.generate',return_value=('演示分析 [D1]','test-model')) as model:
            result=answer('分析沉降')
            answer('继续写复核建议', session_id=result['session_id'])
            self.assertEqual(model.call_args.args[3][0]['content'],'分析沉降')
        with self.assertRaises(ValueError):
            answer('跨案例问题',session_id=result['session_id'],case_id='USER-abcdefabcdef')

    def test_env_files_are_explicit_and_not_inherited(self):
        with patch.dict(os.environ, {'PIT_ENV_FILE':'', 'DEEPSEEK_API_KEY':'', 'PIT_LLM_API_KEY':''}):
            self.assertEqual(model_settings()['key'],'')

    def test_docx_pdf_and_html_escaping(self):
        text='# 报告\n\n中文沉降分析。\n\n| 指标 | 值 |\n|---|---|\n| 沉降 | 21.4 mm |'
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(docx_bytes(text))))
        import pymupdf
        with pymupdf.open(stream=pdf_bytes(text), filetype='pdf') as doc:
            self.assertIn('沉降',''.join(p.get_text() for p in doc))
        self.assertNotIn('<script>',safe_html('<script>alert(1)</script>'))

    def test_api_import_missing_bottom_and_all_exports(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/').status_code,200)
            self.assertEqual(client.get('/api/status').status_code,200)
            self.assertEqual(client.get('/assets/app.js').headers['content-type'].split(';')[0],'application/javascript')
            self.assertEqual(client.post('/api/chat',json={'question':'test'},headers={'origin':'https://foreign.invalid'}).status_code,403)
            raw=b'gp_id,x_m,y_m,z_m,ux_m,uy_m,uz_m,settlement_mm\n7,0,0,0,0,.001,0,1\n'
            response=client.post('/api/cases/import', files={'ground':('ground.csv',raw,'text/csv')}, data={'project_name':'User fixture'})
            self.assertEqual(response.status_code,200,response.text)
            reply=client.post('/api/chat',json={'question':'生成完整报告','mode':'report','engine':'offline','case_id':response.json()['id']})
            self.assertEqual(reply.status_code,200,reply.text)
            data=reply.json();self.assertIn('坑底 CSV 未提供',data['content'])
            self.assertNotIn('20 mm',data['content']);self.assertNotIn('15.7',data['content'])
            for fmt in ('md','html','docx','pdf','json'):
                self.assertEqual(client.get(f"/api/reports/{data['report_id']}/{fmt}").status_code,200)


if __name__ == '__main__':
    try:unittest.main()
    finally:SANDBOX.cleanup()
