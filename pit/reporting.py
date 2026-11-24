from __future__ import annotations

import html
import io
import re
from datetime import datetime, timezone, timedelta

import markdown


def safe_html(text):
    return markdown.markdown(html.escape(text),extensions=['tables','fenced_code','nl2br'])


def evidence_list(evidence):
    lines=[]
    for e in evidence:
        where=f"PDF 第 {e['page']} 页" if e['page'] else e['section']
        lines.append(f"- [{e['citation']}] **{e['name']}**，{where}。{e['note']}" +
                     (f" [官方来源]({e['url']})" if e['url'] else ''))
    return '\n'.join(lines)


def result_table(analysis):
    lines=['| 工况 | 日期 | 开挖深度 m | 地表最大沉降 mm | 坑底最大隆起 mm |',
           '|---|---|---:|---:|---:|']
    for s in analysis['stages']:
        g=s['regions'].get('ground',{});b=s['regions'].get('bottom',{})
        gs=f"{g['max_downward_mm']:.3f}" if g else '未提供'
        bs=f"{b['max_upward_mm']:.3f}" if b else '未提供'
        lines.append(f"| {s['id']} | {s.get('date','未提供')} | {s.get('depth_m','—')} | {gs} | {bs} |")
    return '\n'.join(lines)


def report_text(case,analysis,evidence,narrative,engine):
    if not case['is_demo']:
        return unverified_report(case,analysis,evidence,narrative,engine)
    latest=analysis['latest']; g=latest['regions']['ground'];b=latest['regions'].get('bottom')
    point=g['downward_point']
    controls=[]
    for c in analysis['checks']:
        controls.append(f"| {c['label']} | {c['actual_mm']:.3f} | {c['limit_mm']:.3f} | {c['ratio']*100:.1f}% | {'超过演示阈值' if c['exceeded'] else '未超过演示阈值'} |")
    reference=evidence_list(evidence)
    up_point=b['upward_point'] if b else None
    return f'''# 基坑沉降与坑底隆起监测分析报告

**流程演示稿 · 合成数据 · 非现场检测成果**

项目：{case['name']}  
编号：{case['id']}  
报告日期：{datetime.now(timezone(timedelta(hours=8))).date().isoformat()}  
分析范围：地表竖向位移、坑底竖向位移及阶段变化  
文字生成：{engine}；数值表由 Python 确定性计算

## 1 工程概况与分析目的

本案例使用公开仓库自带的完全虚构勘察背景，演示开挖深度取 {case['depth_m']} m，支护形式假定为{case['support']}。本报告展示资料检索、合成位移统计、工程分析与报告导出的完整流程。工程背景与位移均不对应真实项目。

地质与周边环境说明来自 synthetic_geotech.md。异项目示例默认排除于当前案例的问答。检测仪器、精度检定、实际人员和签章资料均不存在。

## 2 编制依据与资料适用性

本次资料包括虚构勘察说明、演示监测要求、分析方法、案例说明和规范来源目录。具体检索原文与来源见第 8 节。规范来源目录只提供检索入口，不包含真实条文或沉降限值。

demo_monitoring_guide.md 使用 DEMO-M01 等编号描述人为构造的演示要求，不能作为工程规范引用。公开版未附带第三方规范全文或原始勘察报告；正式项目须自行上传有权使用的资料，并核实版本、适用范围和控制依据。

## 3 数据来源、坐标与统计方法

本次使用 {len(analysis['stages'])} 个阶段 CSV，各阶段地表含 {g['count']} 个节点，坑底含 {b['count'] if b else 0} 个节点。数据由演示脚本生成，既非现场观测，也非实际 FLAC3D 求解输出。[D1]

坐标及位移以 m 为单位，Y 轴正向朝下；settlement_mm = 1000 × uy_m，正值表示沉降，负值表示隆起。数据基准为{case['baseline']}。程序校验字段、重复节点、非有限数值和米毫米换算，分别提取地表最大向下位移与坑底最大向上位移。各阶段累计位移不得相加。

## 4 分阶段位移统计

{result_table(analysis)}

以上均为合成 CSV 的节点统计值。[D1] 最终阶段地表最大沉降为 {g['max_downward_mm']:.3f} mm，对应节点 {point['id'] if point else '—'}，局部坐标 {point['xyz_m'] if point else '—'} m。坑底最大隆起为 {b['max_upward_mm'] if b else 0:.3f} mm，对应节点 {up_point['id'] if up_point else '—'}，局部坐标 {up_point['xyz_m'] if up_point else '—'} m。节点极值不能代表导出区域之外的真实极值。

## 5 演示控制指标比较

| 指标 | 计算值 mm | 演示阈值 mm | 比值 | 数值比较 |
|---|---:|---:|---:|---|
{chr(10).join(controls)}

比较阈值来源：demo_project_brief.md“合成数据和演示控制值”。地表 20 mm、坑底 10 mm 均为人为设置的软件测试值，非规范限值或正式设计控制值。阈值触发只证明比较规则有效，不形成真实工程超限或安全结论。

## 6 变形特征、工程解释与监测建议

{narrative}

## 7 结论与复核事项

在所设演示工况中，阶段 S4 地表最大累计沉降 {g['max_downward_mm']:.3f} mm，坑底最大累计隆起 {b['max_upward_mm'] if b else 0:.3f} mm。系统已分别完成方向判别、区域统计及演示阈值比较。[D1]

本报告未执行实际 FLAC3D 求解，未核查网格、材料、边界、初始平衡和加载收敛，也未取得真实监测的基准点、仪器检定、原始记录及项目设计控制值。因此，本成果仅能作为报告格式、数据接口与专业对话流程的示例。正式使用时须替换真实项目资料及实测/计算数据，由专业人员复核、补充并签认。

## 8 检索证据与数据附件

{reference}

- [D1] data/cases/demo/case.json 与同目录 ground_s1.csv～ground_s4.csv、bottom_s1.csv～bottom_s4.csv；均为合成数据，可逐项复算。
- 完整检索片段、输入摘要及生成方式随报告 metadata.json 归档；页码为 PDF 物理页码，非正文印刷页码。
'''


def unverified_report(case,analysis,evidence,narrative,engine):
    latest=analysis['latest']
    lines=['# 基坑位移成果分析报告','', '**用户导入数据 · 工程条件待核实 · 报告初稿**','',
           f"项目：{case['name']}  ",f"案例编号：{case['id']}  ",f'文字生成：{engine}','',
           '## 1 资料与分析范围','',
           '本报告分析用户导入的节点位移 CSV。资料真实性、现场工程关联、计算工况、位移基准、材料边界及求解质量尚未核实。未提供项目勘察、设计、监测方案或经确认的控制值时，不自动套用演示案例条件。',
           '', '## 2 坐标与数据定义','',analysis['coordinate_convention']+'。该约定由输入接口定义，仍须与上游核对。未提供的施工深度和时间不推断。','',
           '## 3 位移统计','',result_table(analysis),'']
    for key,label in [('ground','地表'),('bottom','坑底')]:
        if key not in latest['regions']:
            lines.append(f'{label} CSV 未提供。');continue
        r=latest['regions'][key]
        lines += [f"{label} {r['count']} 个节点，最大向下位移 {r['max_downward_mm']:.3f} mm，最大向上位移 {r['max_upward_mm']:.3f} mm；向下极值点 {r['downward_point']}，向上极值点 {r['upward_point']}。[D1]",'']
    lines += ['## 4 控制指标','', '未配置经确认的项目控制值，不作数值超限判断。', '',
              '## 5 工程分析与复核建议','',narrative,'','## 6 结论与限制','',
              '统计只针对导出节点；数据来源、正方向和位移基准应由提供者核实。缺失求解或监测质量资料时，本稿不能用于正式安全评定。',
              '', '## 7 证据与附件','',evidence_list(evidence),'',
              '[D1] 本案例 case.json 及对应用户导入 CSV。资料来源和计算摘要随 metadata.json 归档。']
    return '\n'.join(lines)


def html_document(text):
    body=safe_html(text)
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>基坑工程分析报告</title>
    <style>@page{{size:A4;margin:20mm}}body{{font-family:"Microsoft YaHei",sans-serif;color:#20312f;line-height:1.8;max-width:850px;margin:32px auto;padding:0 24px}}h1{{font-size:27px}}h2{{font-size:18px;border-bottom:1px solid #ccd9d5;padding-bottom:8px}}table{{width:100%;border-collapse:collapse;font-size:12px}}th,td{{border:1px solid #cdd9d6;padding:7px;text-align:left}}th{{background:#edf4f1}}p,li{{font-size:13px}}code{{overflow-wrap:anywhere}}@media print{{body{{margin:0;padding:0}}h2{{break-after:avoid}}tr{{break-inside:avoid}}}}</style>{body}</html>'''


def docx_bytes(text):
    from docx import Document
    from docx.shared import Pt
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    document=Document()
    style=document.styles['Normal'];style.font.name='Microsoft YaHei';style.font.size=Pt(10)
    style.element.rPr.rFonts.set(qn('w:eastAsia'),'微软雅黑')
    lines=text.splitlines();i=0
    while i<len(lines):
        line=lines[i].strip()
        if line.startswith('|') and i+1<len(lines) and re.match(r'^\|[\s:|\-]+\|$',lines[i+1].strip()):
            headers=[x.strip() for x in line.strip('|').split('|')]
            table=document.add_table(rows=1, cols=len(headers));table.style='Light Shading Accent 1'
            for cell,value in zip(table.rows[0].cells,headers):cell.text=value
            i+=2
            while i<len(lines) and lines[i].strip().startswith('|'):
                for cell,value in zip(table.add_row().cells,lines[i].strip().strip('|').split('|')):cell.text=value.strip()
                i+=1
            continue
        clean=re.sub(r'\*\*|`','',line)
        if line.startswith('#'):
            level=min(3,len(line)-len(line.lstrip('#')))
            document.add_heading(clean.lstrip('# '),level=level)
        elif line:
            paragraph=document.add_paragraph(style='List Bullet' if line.startswith('- ') else None)
            if line.startswith('- '):clean=clean[2:]
            cursor=0
            for match in re.finditer(r'\[([^\]]+)\]\((https?://[^)]+)\)',clean):
                paragraph.add_run(clean[cursor:match.start()])
                link=OxmlElement('w:hyperlink')
                link.set(qn('r:id'),document.part.relate_to(match[2],RT.HYPERLINK,is_external=True))
                run=OxmlElement('w:r');props=OxmlElement('w:rPr');color=OxmlElement('w:color');color.set(qn('w:val'),'215E4B');props.append(color);run.append(props)
                value=OxmlElement('w:t');value.text=match[1];run.append(value);link.append(run);paragraph._p.append(link)
                cursor=match.end()
            paragraph.add_run(clean[cursor:])
        i+=1
    footer=document.sections[0].footer.paragraphs[0]
    synthetic='合成数据' in '\n'.join(text.splitlines()[:5])
    footer.text='PitScope · ' + ('流程演示稿 · 合成数据    ' if synthetic else '报告初稿 · 工程条件待核实    ')
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
    result=io.BytesIO();document.save(result);return result.getvalue()


def pdf_bytes(text):
    # PyMuPDF's bundled CJK font avoids depending on browser/PDF services.
    import pymupdf
    body=safe_html(text)
    css='body{font-family:sans-serif;font-size:10pt;line-height:1.55;color:#213c35} h1{font-size:19pt} h2{font-size:13pt;margin-top:16pt} table{border-collapse:collapse;width:100%;font-size:8pt} td,th{border:0.5pt solid #bdcdc6;padding:4pt} th{background-color:#e8f0eb} p{margin-bottom:7pt}'
    story=pymupdf.Story(html=body,user_css=css)
    result=io.BytesIO();writer=pymupdf.DocumentWriter(result)
    more=True
    while more:
        device=writer.begin_page(pymupdf.paper_rect('a4'))
        more,_=story.place(pymupdf.Rect(46,44,549,794))
        story.draw(device);writer.end_page()
    writer.close()
    doc=pymupdf.open(stream=result.getvalue(),filetype='pdf')
    label='DEMO / SYNTHETIC' if '合成数据' in '\n'.join(text.splitlines()[:5]) else 'DRAFT / UNVERIFIED'
    for i,page in enumerate(doc):
        page.insert_text((46,822),f'PitScope | {label} | {i+1}/{len(doc)}',fontsize=8,color=(.35,.4,.38))
    output=doc.tobytes();doc.close();return output
