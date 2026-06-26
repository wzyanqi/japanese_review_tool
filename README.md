# japanese_review_tool

本地日语复习小工具。它不联网、不调用 AI、不做自动纠错，只用 Python 标准库管理你的日语句子、错题、已掌握句子和每日复习进度。

核心用途：

- 从 `input/sentences.txt` 批量导入日语句子
- 用 `--add` 快速添加一句
- 通过 Quiz 主动回忆日语
- 在 review / wrong / master 三个池子之间流转句子
- 记录正确度、错题、毕业、趋势和长期进度
- 导出 CSV / Anki CSV，备份和检查数据健康

## 快速开始

macOS：

```bash
python3 japanese_review.py --menu
```

Windows 11：

```powershell
python japanese_review.py --menu
```

`--menu` 是日常推荐入口。它会显示今日推荐，并让你通过数字选择常用功能。

## 输入格式

在 `input/sentences.txt` 中，每行一条句子，用 `|` 分隔字段。

支持格式：

```text
日语句子 | 中文意思
日语句子 | 中文意思 | 标签
日语句子 | 中文意思 | 标签 | 语法点
日语句子 | 中文意思 | 标签 | 语法点 | 重点单词
日语句子 | 中文意思 | 标签 | 语法点 | 重点单词 | 备注
```

示例：

```text
今日は少し遅れてきます | 今天可能会晚一点 | 工作
仕事を済ませたいです | 我想把工作完成 | 工作
出かける前に、部屋を片付けておきたいです。 | 出门前，我想先把房间整理好。 | 生活 | 前に, ておく, たい | 出かける, 部屋, 片付ける | 注意「ておく」表示提前做好准备。
```

说明：

- 日语和中文必填。
- 标签、语法点、重点单词、备注可选，未填写时保存为空字符串。
- 空行会被忽略。
- 缺少 `|` 的行不会让程序崩溃，终端会提示格式错误。
- 程序不会自动识别语法点、重点单词或备注，需要你手动填写。

## 常用命令

```bash
python3 japanese_review.py --menu
python3 japanese_review.py
python3 japanese_review.py --no-prompt
python3 japanese_review.py --clear-input
python3 japanese_review.py --add "今日は忙しいです。" "今天很忙。"
python3 japanese_review.py --add "仕事が終わったら、連絡します。" "工作结束后，我会联系你。" --tag "工作" --grammar "たら" --words "仕事, 終わる, 連絡する" --note "たら 表示某事完成后。"
python3 japanese_review.py --quiz
python3 japanese_review.py --quiz --count 5
python3 japanese_review.py --quiz --count 5 --clean
python3 japanese_review.py --quiz --loop
python3 japanese_review.py --quiz --loop --clean
python3 japanese_review.py --quiz --wrong
python3 japanese_review.py --quiz --wrong --count 5
python3 japanese_review.py --quiz --wrong --count 5 --clean
python3 japanese_review.py --quiz --wrong --loop
python3 japanese_review.py --quiz --tag 工作 --count 5
python3 japanese_review.py --quiz --wrong --tag 工作 --count 5
python3 japanese_review.py --stats
python3 japanese_review.py --today
python3 japanese_review.py --plan
python3 japanese_review.py --trend
python3 japanese_review.py --trend --days 14
python3 japanese_review.py --tags
python3 japanese_review.py --export-csv
python3 japanese_review.py --export-anki
python3 japanese_review.py --export-csv --wrong
python3 japanese_review.py --export-csv --mastered
python3 japanese_review.py --check
python3 japanese_review.py --backup
python3 japanese_review.py --reset
```

Windows 上把 `python3` 换成 `python` 即可。建议使用 PowerShell 或 Windows Terminal。

查看所有参数：

```bash
python3 japanese_review.py --help
```

如果终端颜色显示异常，可以关闭 ANSI 彩色输出：

```bash
python3 japanese_review.py --menu --no-color
```

## 菜单模式

运行：

```bash
python3 japanese_review.py --menu
```

V16.0 起，`--menu` 首页重排为 Console 今日首页。首页会优先显示：

- 今日建议
- review / wrong / master 三池状态
- 今日复习进度
- 当前 master 目标
- 固定菜单入口

示例：

```text
📘 日语复习工具｜今日首页
────────────────────────────

📌 今日建议
wrong 池还有 6 句，建议先做错题 Quiz 5 题。
预计用时：5 分钟。

📊 今日状态
review 32 句｜wrong 6 句｜master 68 句
今日复习 8 题｜master +2｜新增错题 +1

🎯 当前目标
master 68 句｜距离 100 句还差 32 句
```

菜单编号保持稳定，不会根据当前状态变化。

当前菜单：

```text
1. 开始今日推荐复习

2. 普通 Quiz
3. 错题 Quiz
4. 快速添加句子
5. 批量导入 sentences.txt

6. 今日学习面板
7. 当前库存
8. 今天该做什么
9. 最近有没有坚持
10. 一键备份

0. 退出
```

菜单输入支持日文输入法下的全角数字：

```text
２ -> 2
１０ -> 10
１ ０ -> 10
１　０ -> 10
０ -> 0
ｑ / Ｑ -> q
```

控制输入支持全角 `y/n/q`：

```text
ｙ / Ｙ -> y
ｎ / Ｎ -> n
ｑ / Ｑ -> q
```

退出统一使用 `q`。`quit` 不再作为退出别名。Quiz 答案、快速添加内容和 `RESET` 确认不会被自动转换。

## 三池机制

工具使用三个学习池：

```text
review  当前待复习池：output/japanese_review.md
wrong   错题强化池：output/wrong_book.md
master  已掌握池：output/mastered.md
```

普通 Quiz：

- 自评 `n`：句子从 review 移入 wrong，并触发“再练一次”
- 自评 `y`：句子继续留在 review
- 正确度很高且二次确认掌握：句子从 review 移入 master

错题 Quiz：

- 自评 `y`：掌握次数 +1
- 掌握次数达到 3：句子从 wrong 移入 master
- 自评 `n`：句子留在 wrong，并可触发“再练一次”

三池优先级为：

```text
master > wrong > review
```

如果一句话进入 master，程序会清理 review 和 wrong 中的同句，避免状态冲突。

## Quiz 功能

普通 Quiz：

```bash
python3 japanese_review.py --quiz
python3 japanese_review.py --quiz --count 5
python3 japanese_review.py --quiz --loop
```

错题 Quiz：

```bash
python3 japanese_review.py --quiz --wrong
python3 japanese_review.py --quiz --wrong --count 5
python3 japanese_review.py --quiz --wrong --loop
```

按标签：

```bash
python3 japanese_review.py --quiz --tag 工作 --count 5
python3 japanese_review.py --quiz --wrong --tag 工作 --count 5
```

### 专注清屏模式

如果希望每道题像单独卡片一样显示，可以使用：

```bash
python3 japanese_review.py --quiz --count 5 --clean
python3 japanese_review.py --quiz --wrong --count 5 --clean
python3 japanese_review.py --quiz --loop --clean
```

开启后：

- 每题开始前会清空屏幕
- 提交答案后的参考答案、正确度和差异提示不会被清掉
- 自评完成后，进入下一题前才清屏
- 答错后的“再练一次”开始前也会清屏
- Quiz 结束页不会清屏，方便查看本轮小结和长期进度

菜单模式中启动 Quiz 时，默认启用专注清屏模式。命令行直接运行 Quiz 时，需要显式添加 `--clean`。

Quiz 会显示中文意思，让你输入日语。输入后会显示：

- 你的输入
- 参考答案
- 正确度
- 差异提示
- 中文意思
- 语法点、重点单词、备注

正确度只是字面相似度参考，不代表语义或语法完全正确。最终是否掌握仍由你通过 `y/n` 自评决定。

如果输入 `q`、`Q`、`ｑ` 或 `Ｑ`，会退出当前 Quiz。`quit` 会被当作普通答案，不作为退出别名。

## 正确度、差异提示和重答

正确度会忽略常见标点和空格，例如 `。`、`、`、`.`、`,`、`!`、`?`、普通空格和全角空格。

工具会在 `data.json` 中记录每条句子的：

- 上次正确度
- 历史最高正确度
- 正确度记录次数

差异提示会帮助你定位哪里少写、多写或写错。例如：

```text
你的输入：仕事が終わたら、連絡します。
参考答案：仕事が終わったら、連絡します。

差异提示：
可能少写：っ
差异附近：終わったら
```

默认情况下，自评 `n` 后会触发“再练一次”。如果想关闭：

```bash
python3 japanese_review.py --quiz --no-retry
```

如果怀疑终端输入丢字，可以使用：

```bash
python3 japanese_review.py --quiz --count 1 --debug-input
```

## 复习结束反馈

每轮 Quiz 结束后会显示两层反馈：

1. 本轮复习小结  
   包括本轮题数、新增错题、进入 master 的句子、重答次数和下一步建议。

2. 长期进度  
   包括今日进度、本周进度、累计 master 数量和下一个掌握目标。

示例：

```text
今日：复习 8 题｜新增错题 1 句｜进入 master 2 句
本周：复习 31 题｜学习 4 天｜进入 master 7 句
累计：master 68 句｜距离 100 句还差 32 句
下一步：今天已经完成一轮有效复习，可以收工。
```

## 错题智能抽题

错题 Quiz 不完全随机。wrong 池中：

- 越久没复习
- 掌握次数越低

越容易被抽到。

`wrong_book.md` 中会记录：

```text
- 最后复习日期：YYYY-MM-DD
- 掌握次数：0
```

旧错题没有“最后复习日期”时，会按很久没复习处理，并在下次保存时补齐字段。

## 日语朗读

macOS 可使用系统 `say` 朗读参考答案：

```bash
python3 japanese_review.py --quiz --speak
python3 japanese_review.py --quiz --wrong --speak
python3 japanese_review.py --quiz --speak --voice Kyoko
python3 japanese_review.py --quiz --speak --voice Otoya
```

如果当前系统不支持 `say`，程序会友好跳过朗读，不影响 Quiz。

## 统计、今日面板和趋势

```bash
python3 japanese_review.py --stats
python3 japanese_review.py --today
python3 japanese_review.py --plan
python3 japanese_review.py --trend
python3 japanese_review.py --trend --days 14
```

用途：

- `--stats`：查看三池库存、字段完整度、标签概览和整体建议
- `--today`：查看今日新增、三池状态、备份情况和提醒
- `--plan`：回答“今天该做什么”
- `--trend`：查看最近学习趋势，包括 Quiz 次数、平均正确度、进入 master、重答次数

趋势数据保存在：

```text
output/activity_log.json
```

## 标签

查看标签统计：

```bash
python3 japanese_review.py --tags
```

按标签 Quiz：

```bash
python3 japanese_review.py --quiz --tag 工作
python3 japanese_review.py --quiz --wrong --tag 工作 --count 5
```

旧数据没有标签时会显示为空标签，不会影响运行。

## 导出

导出 review 池：

```bash
python3 japanese_review.py --export-csv
```

导出 Anki：

```bash
python3 japanese_review.py --export-anki
```

导出 wrong / master：

```bash
python3 japanese_review.py --export-csv --wrong
python3 japanese_review.py --export-csv --mastered
```

导出文件位置：

```text
output/export/
```

CSV 使用 `utf-8-sig` 编码，方便 Windows Excel 打开中文和日文。Anki 文件中：

```text
front = 中文意思
back  = 日语句子 + 语法点 + 重点单词 + 备注
tag   = 标签
```

## 备份、检查和重置

一键备份：

```bash
python3 japanese_review.py --backup
```

数据健康检查：

```bash
python3 japanese_review.py --check
```

恢复初始状态：

```bash
python3 japanese_review.py --reset
```

`--reset` 是危险操作，会先自动备份，并要求输入 `RESET` 确认。需要跳过二次确认时：

```bash
python3 japanese_review.py --reset --yes
```

## 输入区清理

普通导入结束后，程序会询问是否清空 `input/sentences.txt`。如果选择清空，会先归档到：

```text
input/archive/YYYY-MM-DD_sentences.txt
```

不想询问：

```bash
python3 japanese_review.py --no-prompt
```

只归档并清空输入文件：

```bash
python3 japanese_review.py --clear-input
```

## 输出文件

```text
input/sentences.txt                  输入区
input/archive/                       输入归档
data.json                            正确度和复习记录
output/japanese_review.md            review 池
output/wrong_book.md                 wrong 池
output/mastered.md                   master 池
output/daily/YYYY-MM-DD.md           每日新增归档
output/activity_log.json             学习趋势日志
output/export/                       CSV / Anki 导出
backup/                              备份 zip
```

## 使用建议

日常最简单流程：

```bash
python3 japanese_review.py --menu
```

然后选择：

```text
1. 开始今日推荐复习
```

如果要添加新句子：

```bash
python3 japanese_review.py --add "今日は忙しいです。" "今天很忙。" --tag "生活"
```

如果要批量导入，就编辑 `input/sentences.txt` 后运行：

```bash
python3 japanese_review.py
```
