## PitScope v0.1.0

公开作品集版本：将工程资料检索、位移 CSV 的确定性统计和可追溯报告生成连接起来。

### 可体验内容

- FastAPI + 原生浏览器界面，提供专业问答、报告段落和完整报告三种模式。
- PDF / DOCX / MD / TXT 解析；TF-IDF + BM25 + RRF 混合检索。
- 地表沉降与坑底隆起分区统计、极值位置、带来源的指标比较。
- 模型接口、历史追问、案例隔离、明确的离线回退。
- DOCX / PDF / Markdown / HTML 与 JSON 输出。
- 完全虚构的公开语料、四阶段 CSV、模型生成样例、架构图和截图。
- 14 项自动测试与 Windows / Linux CI。

### 直接运行

安装 `requirements.txt` 后运行 `python run.py --open-browser`。不配置密钥也可运行；命令行离线生成报告：`python run.py --demo --offline`。

### 附件

- `pitscope-v0.1.0.zip`：完整源码及公开案例。
- `report.pdf`：可直接阅读的演示报告。
- `report.docx`：可编辑的演示报告。

所有背景、位移和阈值均为软件演示数据，不用于真实工程安全判断。原始勘察资料、规范全文、密钥、上传文件和运行数据库不包含在公开版本中。神经 Embedding、Chroma、LangGraph 和直接 FLAC3D 执行尚未实现。
