# ShopPilot · 智选商城

面向毕业设计的独立开发初版：传统综合商城、管理员商品管理，以及按钮切换的独立购物对话界面。

**状态：可运行的业务初版，不是已经验收的完整毕设。** 默认初始化带 24 件明确标注的虚构教学商品；提供六类历史商品的一键采样导入。云环境已实际采样并导入600条Amazon 2023历史商品，原始数据不随Git分发，新克隆后需运行下方数据准备命令。历史商品未核验前保持下架。无真实支付、物流或全网浏览器搜索。未配置模型时明确显示规则筛选。

## 已实现

- 注册、登录、退出；PBKDF2 密码哈希、服务端过期会话、HttpOnly Cookie、基础登录限流。
- 公开商城：分类、搜索、价格排序、分页、详情；绿色商城视觉。
- 管理员：商品新增/查看/编辑/软下架、搜索分页、批量 JSON 导入、分类维护、用户启停、反馈处理、数据概览和操作审计。
- 用户隔离的收藏、购物对象档案与偏好、购物车、订单、导购历史。
- 模拟订单：事务内校验库存与上架状态，保存下单价格快照，扣库存；取消仅执行一次并恢复库存。
- 独立 Chat：从商城按钮进入，从商品详情或多选商品带入上下文；持久化预算/排除条件，支持“去掉预算”。
- 配料未知不会判为满足排除条件。长期偏好手动维护，本次预算不会自动写入档案。
- 结构化商品对比与标签 VC 每克成本计算；可移除预算、排除条件（不修改长期偏好）。
- 可选 OpenAI 兼容模型解释候选；失败回退规则筛选，价格与库存仍由服务端读取。
- JSON / JSONL / JSONL.GZ 数据导入，支持规范商品、DummyJSON 和 Amazon 2023 metadata。

## 本地启动

Python 3.12，浏览器访问同一个服务，无需 Node 构建。

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS / Linux: source .venv/bin/activate
python -m pip install -r requirements.lock.txt
python -m scripts.manage seed
python -m scripts.manage admin admin
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000 。管理员密码由交互输入设置，没有默认密码。普通账号在页面注册。seed 可重复执行，不覆盖已有商品。

API 文档：http://127.0.0.1:8000/docs 。运行测试：`python -m pytest tests -q`。

可选模型配置（PowerShell）：

```powershell
$env:LLM_API_KEY="你的密钥"
$env:LLM_MODEL="供应商提供的模型标识"
$env:LLM_BASE_URL="https://你的兼容服务/v1"
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

密钥只保存在服务端环境变量，不写入仓库。`.env.example` 是说明模板，程序不会自动加载 `.env`。公网部署须启用 HTTPS 和 `COOKIE_SECURE=1`，并补充网关限流、备份与部署验收。

## 数据导入

```bash
python -m scripts.manage import data/example-products.json --format normalized
python -m scripts.manage import path/to/products.json --format dummyjson --limit 500
python -m scripts.manage import path/to/meta_Category.jsonl.gz --format amazon2023 --limit 500
```

外部数据集导入时下架保存，库存为 0；保留原始 USD 币种，不伪装为人民币。管理员核实价格、币种、库存和资料后才能上架。此命令不负责下载数据。按来源 ID / 来源链接去重；没有来源键的规范记录按完整内容去重。已有来源记录会跳过，不覆盖管理员维护后的资料。没有来源键且内容改变的记录仍可能重复，需要人工核查。

- Amazon 2023：https://amazon-reviews-2023.github.io/ — 选 meta 文件，按来源条款使用、引用；不需下载全部评论。
- DummyJSON：https://dummyjson.com/docs/products — 测试/原型数据，不当成实时报价。
- 保健品可补充 NIH DSLD：https://dsld.od.nih.gov/api-guide ，当前未实现专门转换器。

数据集公开可下载不等于其中图片和品牌资料可任意再分发，导入前核查各自许可。本仓库仅提交虚构教学数据。

## 结构

- `backend/app.py`：API、SQLite 业务、账号权限、规则导购及模型适配。
- `backend/management.py`：分类、用户状态、反馈管理。
- `backend/comparison.py`、`backend/importing.py`：确定性对比与来源去重。
- `web/`：同源商城、管理页面、独立 Chat。
- `scripts/manage.py`：演示数据、管理员创建、数据集转换导入。
- `tests/`：权限、数据隔离、订单事务、约束筛选、导入校验。
- `docs/`：需求范围、设计、验收与待办。

## 与原项目的关系

本初版在独立目录重新实现，未复制原仓库的源码、商品数据、奖项或作者身份。交互方向来自需求讨论；原项目保留于原仓库且未修改。原有 React Chat、混合 RAG、语音、图片检索尚未迁移，不能据此声称已具有这些能力。

毕业设计最终是否合格取决于学校要求、导师确认、个人贡献、真实数据与评测，以及本人能够解释实现。本项目仅提供可验证的起点。

## 浏览器验收

```bash
npm ci
npx playwright-core install --with-deps chromium
python -m scripts.browser_smoke
```

浏览器验收自行创建临时数据库和测试账号、启动临时端口，结束后清理；不会访问本机正式数据库。覆盖商城浏览、登录、加购下单取消、条件移除、结构化对比、反馈回复、分类新增和后台分页。另检查390px与320px宽度无横向溢出。

可通过 `CHROMIUM_EXECUTABLE` 使用已有 Chromium，`SHOP_SCREENSHOTS` 指定内部验收截图目录。所有测试密码只用于临时账号，不是系统默认密码。

## 准备综合历史商品库

```bash
# 六类各100条；再次运行复用本地采样文件，来源ID去重
python -m scripts.bootstrap_catalog --per-category 100

# 也可以仅采样一个品类，再执行导入
python -m scripts.fetch_catalog --source amazon2023 --category Electronics --limit 100 --output data/downloads/electronics.jsonl
python -m scripts.manage import data/downloads/electronics.jsonl --format amazon2023
```

六个来源文件分别为美妆、数码、服饰、家居、食品、健康日用。原始商品名称多为英文，当前只有小型中英关键词表，不是完整跨语言语义检索。健康日用包含多种日用品，不能把全部商品当作保健品。

采样限定数量、扫描条数和下载/解压大小；请求失败不留下半成品。每份JSONL配有来源、获取时间、采样方式、SHA-256清单。导入会检查已有清单的校验和，内容被修改时拒绝导入。样本采用各文件最先遇到的有效带价格记录，不是随机样本，也不适合作为无偏评测集。云端实际采样报告见 `docs/data-sampling.json`。

### 核验后上架

1. 管理后台按来源选择“Amazon历史商品”，查看处于下架状态的候选。
2. 点击“核验上架”，打开商品来源确认同一规格，输入已核实的人民币售价、模拟库存、来源链接和核验说明。
3. 系统保存人民币报价快照，原始美元价格保留，不自动换汇，不将下载时间当成价格更新时间。
4. 上架后修改价格、配料、描述或规格，会重新下架并清除当前核验状态，旧报价快照保留。

核验记录是管理员声明与审计记录，不等于系统独立核实了网页。价格核验超过7天会提示复核；未知配料不会因为商品上架而变为已知。全网浏览器搜索和实时跨平台比价仍未实现。
