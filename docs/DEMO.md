# 5 分钟演示与复现

## 1. 启动（约 1 分钟）

按 README 安装依赖，运行 `python run.py --open-browser`。首次启动将从 `examples/corpus/` 构建运行资料，并生成四阶段数据；无需网络下载模型或规范。

## 2. 数值与证据（约 1 分钟）

点击“分析沉降与隆起”。无密钥时使用离线证据摘录，检查：

- 地表最大沉降为 21.400 mm，坑底最大隆起为 6.200 mm。
- 存在 `[D1]` 数据来源与 `[E1]` 文本证据。
- 点击“查看依据”能查看原文；界面和正文保留合成数据标识。

## 3. 文档检索（约 1 分钟）

进入知识库，搜索 `DEMO-M02 数据异常复核`。这是作者构造的演示要求，原文应明确说明其不是标准条款。真实规范可通过“导入资料”上传并指定适用范围。

## 4. 生成并下载报告（约 1 分钟）

选择“完整报告”或进入成果报告页面生成，下载 Word / PDF。检查数据表、比较阈值来源、资料性质和结论限制。示例报告的原文与 JSON 同时保存到运行目录。

## 5. 导入自己的 CSV（约 1 分钟）

用 `examples/dataset/ground_s4.csv` 创建独立案例，暂不提供坑底。新案例应显示坑底未提供，没有继承 20 / 10 mm 演示阈值，报告不套用原案例的施工深度或勘察背景。

## 配置模型后的演示

填入自己的 `.env` 后选择“大模型分析”，可询问：“结合当前案例资料，写一段可用于报告的变形分析，并引用证据。”下一轮追问“继续给出复核建议”。模型不可用时会明确显示回退，不能把回退文本称为模型回答。

## 浏览器验证与截图

```bash
python -m pip install -r requirements-browser.txt
# 已安装 Edge / Chrome 时可指定可执行文件；否则先安装 Playwright Chromium：
python -m playwright install chromium
python run.py --port 8767
# 另一个终端：
python scripts/browser_qa.py --base-url http://127.0.0.1:8767
```

Windows 本机 Edge 示例：

```powershell
$env:PIT_BROWSER_EXECUTABLE='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
python scripts/browser_qa.py --base-url http://127.0.0.1:8767
```

检查记录输出到 `artifacts/browser_qa.json`。截图会更新 `docs/images/`；该脚本在运行实例中创建演示会话和报告，请针对专用演示实例使用。
