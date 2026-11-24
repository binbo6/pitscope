from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
from contextlib import contextmanager
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .settings import DB

LOCK = threading.RLock()
SYNONYMS = {
    '隆起': '坑底 向上位移 底部 稳定性', '沉降': '竖向位移 地表 变形 监测',
    '地下水': '降水 承压水 潜水 突涌 渗透', '土层': '地质 淤泥 粘土 岩土 参数',
    '报警': '预警 控制值 累计变化 变化速率', '监测': '测点 观测 监测频率 巡查',
    '规范': '标准 规程 DB42 GB50497', '周边': '邻近 建筑物 地下管线 环境',
}


@contextmanager
def connect():
    db = sqlite3.connect(DB, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
            scope TEXT NOT NULL, path TEXT NOT NULL, url TEXT NOT NULL,
            note TEXT NOT NULL, sha256 TEXT NOT NULL, pages INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY, document_id TEXT NOT NULL, page INTEGER,
            section TEXT NOT NULL, text TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
            role TEXT NOT NULL, content TEXT NOT NULL, meta TEXT NOT NULL DEFAULT '{}');
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, markdown TEXT NOT NULL,
            meta TEXT NOT NULL, created_at TEXT NOT NULL);
        ''')


def paragraphs(path: Path):
    if path.suffix.lower() == '.pdf':
        import pymupdf
        with pymupdf.open(path) as doc:
            for page, item in enumerate(doc, 1):
                content = item.get_text(sort=True).strip()
                if content:
                    yield page, f'PDF 第 {page} 页', content
    elif path.suffix.lower() == '.docx':
        from docx import Document
        doc = Document(path)
        content = '\n'.join(p.text for p in doc.paragraphs)
        for table in doc.tables:
            content += '\n' + '\n'.join(' | '.join(c.text for c in row.cells) for row in table.rows)
        yield None, 'Word 正文（无固定页码）', content
    elif path.suffix.lower() in {'.txt', '.md'}:
        content = path.read_text(encoding='utf-8-sig')
        parts = re.split(r'(?=^#{1,4} |^8\.[1-9]\s*[^\n]+$)', content, flags=re.M)
        for part in parts:
            if part.strip():
                yield None, part.strip().splitlines()[0].lstrip('# ')[:100], part.strip()
    else:
        raise ValueError('支持 PDF、DOCX、Markdown、TXT；扫描 PDF 请先做 OCR。')


def ingest(path: Path, *, name=None, kind='reference', scope='reference', url='', note=''):
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    doc_id = hashlib.sha256((sha + scope + kind + str(name)).encode()).hexdigest()[:16]
    pieces = []
    pages = 0
    for page, section, text in paragraphs(path):
        pages = max(pages, page or 0)
        # Each PDF chunk stays on its original physical page.
        for start in range(0, len(text), 720):
            chunk = text[start:start + 880].strip()
            if len(chunk) >= 15:
                pieces.append((f'{doc_id}-{len(pieces)+1}', doc_id, page, section, chunk))
    if not pieces:
        raise ValueError('没有提取到可索引的文本；扫描件需要先做 OCR。')
    with LOCK, connect() as db:
        db.execute('INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?,?,?,?)',
                   (doc_id, name or path.name, kind, scope, str(path.resolve()), url, note, sha, pages))
        db.execute('DELETE FROM chunks WHERE document_id=?', (doc_id,))
        db.executemany('INSERT INTO chunks VALUES (?,?,?,?,?)', pieces)
    index.invalidate()
    return {'id': doc_id, 'name': name or path.name, 'chunks': len(pieces), 'pages': pages}


def documents():
    with connect() as db:
        return [dict(row) for row in db.execute('''SELECT d.id,d.name,d.kind,d.scope,d.url,d.note,
            d.pages,d.sha256,COUNT(c.id) AS chunks FROM documents d LEFT JOIN chunks c
            ON c.document_id=d.id GROUP BY d.id ORDER BY d.kind,d.name''')]


def tokenize(text):
    chinese = re.findall(r'[\u3400-\u9fff]+', text)
    return re.findall(r'[a-z0-9]+', text.lower()) + [s[i:i+2] for s in chinese for i in range(len(s)-1)]


class HybridIndex:
    """Local TF-IDF character vectors + BM25, fused by reciprocal rank.

    This deliberately has no external embedding dependency or network indexing call.
    """
    def __init__(self):
        self.rows = None

    def invalidate(self):
        with LOCK:
            self.rows = None

    def build(self):
        with connect() as db:
            self.rows = [dict(r) for r in db.execute('''SELECT c.*,d.name,d.kind,d.scope,d.url,d.note
                FROM chunks c JOIN documents d ON d.id=c.document_id ORDER BY c.id''')]
        if not self.rows:
            return
        texts = [r['section'] + '\n' + r['text'] for r in self.rows]
        self.vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2, 3), max_features=50000,
                                          sublinear_tf=True, norm='l2')
        self.matrix = self.vectorizer.fit_transform(texts)
        self.bags = [Counter(tokenize(t)) for t in texts]
        self.lengths = np.array([sum(b.values()) for b in self.bags])
        self.average = max(1, float(self.lengths.mean()))
        self.df = Counter(t for bag in self.bags for t in bag)

    def search(self, query, limit=7, include_reference=False, kind=None, scopes=None):
        with LOCK:
            if self.rows is None:
                self.build()
            if not self.rows:
                return []
            expanded = query + ' ' + ' '.join(v for k,v in SYNONYMS.items() if k in query)
            vector = (self.matrix @ self.vectorizer.transform([expanded]).T).toarray().ravel()
            bm = np.zeros(len(self.rows))
            for t in set(tokenize(expanded)):
                idf = math.log(1 + (len(self.rows)-self.df[t]+0.5)/(self.df[t]+0.5))
                for i, bag in enumerate(self.bags):
                    tf = bag[t]
                    if tf:
                        bm[i] += idf * tf * 2.5 / (tf + 1.5*(0.25+0.75*self.lengths[i]/self.average))
            eligible = [i for i,r in enumerate(self.rows) if (include_reference or r['scope'] != 'reference')
                        and (scopes is None or r['scope'] in scopes or (include_reference and r['scope']=='reference'))
                        and (not kind or r['kind'] == kind) and (vector[i] > 0.015 or bm[i] > 0)]
            vr = {i:n for n,i in enumerate(sorted(eligible, key=lambda i:vector[i], reverse=True), 1)}
            br = {i:n for n,i in enumerate(sorted(eligible, key=lambda i:bm[i], reverse=True), 1)}
            ranked = sorted(eligible, key=lambda i:1/(40+vr[i])+1/(40+br[i]), reverse=True)
            result, counts = [], Counter()
            for i in ranked:
                row = self.rows[i]
                if counts[row['document_id']] >= 3:
                    continue
                counts[row['document_id']] += 1
                result.append({**row, 'citation': f'E{len(result)+1}',
                               'score': round(1/(40+vr[i])+1/(40+br[i]), 5),
                               'vector_score': round(float(vector[i]), 4)})
                if len(result) >= limit:
                    break
            return result


index = HybridIndex()
