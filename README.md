# TableDoctor（脏表医生）

一个**本地运行、只诊断不改数据**的中文表格体检工具。给一张别人传来的 CSV / XLSX，一条命令告诉你它哪里脏、脏多少、脏在第几行，并输出一份可以直接转发给同事的**单文件 HTML 报告** + 一份机器可读的 JSON。

C9 自驱项目。选题不是"再写一个 pandas demo"，而是从我自己反复遇到的真实场景出发：

> 运营/行政/同学拿到供应商或系统导出的订单表，列名是中文、金额列里混着 `1,200元`、日期一列里既有 `2024-01-05` 又有 `2024/1/9`、主键有重复、还有一整列全空。用眼睛看要看半天，写脚本又每次重写一遍。

TableDoctor 把这件事收敛成一条命令，且**不上传任何数据、不联网、不依赖服务端**。

---

## 1. 快速开始

```powershell
pip install openpyxl
python -m tabledoctor check 你的表.xlsx --key 0 --out report.html --json report.json
```

输出（真实运行，见 `reports/` 目录）：

```
[issue] sev=error   check=duplicate_key       col=0  label=订单号 count=5
[issue] sev=error   check=duplicate_rows      col=-1 label=      count=4
[issue] sev=error   check=empty_column        col=6  label=废弃列 count=65
[issue] sev=error   check=type_mismatch       col=2  label=下单日期 count=2
[issue] sev=error   check=type_mismatch       col=4  label=金额   count=3
[issue] sev=warning check=high_missing_column col=3  label=地区   count=38
[issue] sev=warning check=near_empty_column   col=5  label=备注   count=62
[issue] sev=warning check=whitespace_cells    col=1  label=客户   count=35
[issue] sev=info    check=constant_column     col=7  label=渠道   count=65
[summary] file=orders_messy.xlsx rows=65 cols=8 enc=xlsx issues=9 error=5 warn=3 info=1 score=47
[out] html=reports\orders_messy.html json=reports\orders_messy.json
```

`--key 0` 指定主键列（可写列名或 0 基列号），只影响"主键重复"这一条。
`python -m tabledoctor checks` 列出全部规则。

---

## 2. 九条规则与阈值

阈值全部写死在代码里，读数可复算，不做"AI 猜"。

| 规则 | 严重度 | 触发条件 |
|---|---|---|
| `ragged_rows` 行列数不齐 | error | 该行单元格数 ≠ 表头列数（CSV 常见） |
| `empty_column` 整列为空 | error | 该列全部单元格为空白 |
| `near_empty_column` 近似空列 | warning | 表体 ≥20 行，且填充率 ≤5% |
| `high_missing_column` 缺失率偏高 | warning | 缺失率 >50% 且 ≤90%（100% 由整列为空接管） |
| `constant_column` 常量列 | info | 非空值 ≥5 个，且只有 1 个不同取值 |
| `duplicate_rows` 重复行 | error | 整行所有单元格完全一致 |
| `duplicate_key` 主键重复 | error | 指定主键列上同一取值出现 >1 次 |
| `type_mismatch` 类型不一致 | error | 非空值 ≥5 且 ≥90% 是数字但不满 100%（金额混文本）；或 ≥90% 可识别日期但不满 100% 是 ISO 格式 |
| `whitespace_cells` 首尾空格/不可见字符 | warning | 值 ≠ 去空格后的值，或含零宽字符、不间断空格 |

评分：满分 100，每个 error 扣 8、warning 扣 4、info 扣 1，下限 0。分低不等于数据不能用，只表示"脏点密度高"。

---

## 3. 评测：主动注入缺陷，量化召回

工具说有问题的列，到底是不是真有问题？我用**注入式评测**回答，而不是举几个例子。

`fixtures/gen.py` 生成三份表，并把每个注入缺陷登记进账本（`ground_truth.json`）：

| 用例 | 行×列 | 注入缺陷 | 检出 | 召回 | 精度 |
|---|---|---|---|---|---|
| `orders_messy.xlsx` | 65×8 | 9 | 9 | 1.0000 | 1.0000 |
| `orders_messy.csv`（GB18030 + 2 行残缺） | 65×8 | 10 | 10 | 1.0000 | 1.0000 |
| `clean_orders.csv`（干净对照组） | 20×5 | 0 | 0 | 1.0000 | 1.0000 |
| **合计** | — | **19** | **19** | **1.0000** | **1.0000** |

误报数 `false_pos=0`：三份表没有一条报告是"报了但账本里没有"。

**这里必须说清第一轮的真实结果**：初版 `recall=0.8947`（19 个里命中 17 个），漏了 `near_empty_column@col5`。我一开始怀疑是检测器阈值错，查下去发现是**样例与账本不一致**：我把 3 条备注写在 `note_start_rows`，但这几行恰好被"重复行注入"复制，重复行也让备注列的填充数从 3 变成 6，填充率 6/65=9.2% 越过 5% 阈值，于是检查器**正确地保持了沉默**。修的是样例生成逻辑，不是把阈值放宽。这条弯路原样记进了 AAR，因为它恰好说明"评测数字变好"有两种来源，一种是真的，一种是调参调到好看。

复现：

```powershell
python fixtures\gen.py          # 生成样例 + 账本，GEN_RC=0
python fixtures\evaluate.py     # 跑评测，EVAL_RC=0
python tests\test_checks.py     # 14 项单元测试
```

---

## 4. 设计取舍

- **只读诊断，不改数据。** 自动"修复"脏表比不修更危险——猜错主键会合并两个客户。工具只给证据，改不改、怎么改由人决定。
- **本地优先。** 表格里常有手机号、客户名、金额。整个工具零网络调用，`requirements.txt` 只有 `openpyxl`。
- **可解释。** 每条问题都带列号、中文列名、命中数量、最多 5 个样例。评审或同事质疑时能直接翻到原表核对。
- **中文表头一等公民。** 列名不要求 ASCII，报告内 UTF-8 渲染；控制台输出转义成 ASCII，避免 Windows 中文控制台乱码。
- **控制台与报告分离。** 终端只给机器友好的摘要行，人看的是 HTML。

---

## 5. 已知限制（不粉饰）

- 只支持 `.csv` / `.xlsx` / `.xlsm`；老式 `.xls` 会明确报错而不是猜。
- 近似空列要求 ≥20 行才有统计意义，小表不触发。
- 类型识别是正则启发式：不解析 Excel 公式结果、不识别自定义数字格式、不处理多语言数字（如 `1.234,56`）。
- 主键重复只在你指定 `--key` 时检查，不自动猜主键。
- CSV 编码按 `utf-8-sig` → `gb18030` 顺序探测，遇到第三种编码会误判为乱码列。
- 未做跨文件关联检查（如订单表与客户表对账）。

---

## 6. 目录结构

```
tabledoctor/          核心包：loader（读表+编码探测）、checks（9 条规则）、report（JSON/HTML）
tests/                14 项断言式单元测试，纯 ASCII 源码
fixtures/             gen.py 造脏表 + 账本，evaluate.py 算召回/精度
reports/              真实运行产出的报告样例（xlsx / csv / 干净表）
```

公开仓库：<https://github.com/Leo-web-lhy/c9-tabledoctor>

详细背景、AI 协作过程与复盘见同目录 `2023108610260_C9_proposal.md`、`2023108610260_C9_mvp.md`、`2023108610260_C9_AI日志.md`、`2023108610260_C9_拿来说明.md`、`2023108610260_C9_AAR_W1.md`。
