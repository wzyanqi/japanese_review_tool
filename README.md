# japanese_review_tool

这是一个本地日语复习小工具。它会读取 `input/sentences.txt` 里的日语句子和中文意思，然后追加写入 `output/japanese_review.md`，作为当前待复习池，方便每天复习。

工具还会把每个新加入句子的复习次数保存到 `data.json`，并提供随机抽查 Quiz 模式帮助主动回忆。V13.0 起采用三池流转机制：待复习句子、错题和已掌握句子会在不同文件中流转。统计模式可以查看当前学习积累。处理完成后可以归档并清空输入区，方便长期使用。标签功能可以按场景分类和抽查。V12.3 支持手动导入语法点、重点单词和备注。还支持 CSV、Anki 导出和数据健康检查。

V12.3 版本保持简单：不联网，不调用 AI，不做自动纠错，只使用 Python 标准库。V10.1 优化了终端输出格式，V10.2 在保留美观输出的基础上加固了 macOS 和 Windows 11 的路径、编码、CSV 导出兼容性。V12.3 增加了备注字段，适合记录句子的学习重点、易错点和使用场景。

## 如何填写 sentences.txt

在 `input/sentences.txt` 中，每一行填写一个句子。可以使用旧格式：

```text
日语句子 | 中文意思
```

也可以使用带标签、语法点、重点单词、备注的结构化格式：

```text
日语句子 | 中文意思 | 标签
日语句子 | 中文意思 | 标签 | 语法点
日语句子 | 中文意思 | 标签 | 语法点 | 重点单词
日语句子 | 中文意思 | 标签 | 语法点 | 重点单词 | 备注
```

例如：

```text
今日は少し遅れてきます | 今天可能会晚一点 | 工作
仕事を済ませたいです | 我想把工作完成 | 工作
この件は田中さんに任せましょう | 这件事交给田中吧 | 常用表达
出かける前に、部屋を片付けておきたいです。 | 出门前，我想先把房间整理好。 | 生活 | 前に, ておく, たい | 出かける, 部屋, 片付ける
出かける前に、部屋を片付けておきたいです。 | 出门前，我想先把房间整理好。 | 生活 | 前に, ておく, たい | 出かける, 部屋, 片付ける | 重点关注「ておく」表示提前做好准备，不是单纯“做了”。
```

注意：

- 中间需要使用 `|` 分隔日语和中文。
- 标签可以用来表示场景，例如 `工作`、`旅行`、`常用表达`。
- 标签、语法点、重点单词、备注都是可选字段。
- 如果没有填写标签、语法点、重点单词或备注，程序会保存为空字符串，不会强制写入默认文本。
- 备注适合记录这句话最值得关注的学习重点，例如易错点、使用场景、ChatGPT 提醒或表达习惯说明。
- 程序不会自动识别语法点、重点单词或备注，需要你手动填写，或让 ChatGPT 生成后再粘贴导入。
- 空行会被忽略。
- 如果某一行没有 `|`，程序会在终端提示格式错误，并继续处理其他行。

## 如何运行

在项目目录下运行。

macOS：

```bash
python3 japanese_review.py
```

Windows 11：

```powershell
python japanese_review.py
```

Windows 上建议使用 PowerShell 或 Windows Terminal。下面命令示例主要使用 macOS 的 `python3`，如果你在 Windows 11 上运行，把 `python3` 换成 `python` 即可。

例如查看统计：

macOS：

```bash
python3 japanese_review.py --stats
```

Windows 11：

```powershell
python japanese_review.py --stats
```

运行结束后，终端会显示：

- 本次读取多少行
- 成功新增多少句
- 跳过多少句重复
- 有多少行格式错误

CSV 导出文件使用 `utf-8-sig` 编码，方便 Windows 11 上用 Excel 打开中文和日文，避免乱码和多余空行。

## 命令列表

进入交互式菜单模式：

```bash
python3 japanese_review.py --menu
```

快速添加一句：

```bash
python3 japanese_review.py --add "今日は少し遅れて行きます。" "今天我会稍微晚一点过去。"
```

快速添加一句，并填写标签、语法点、重点单词、备注：

```bash
python3 japanese_review.py --add "仕事が終わったら、連絡します。" "工作结束后，我会联系你。" --tag "工作" --grammar "たら, ます形" --words "仕事, 終わる, 連絡する" --note "重点关注「たら」表示某事完成后再做下一件事。"
```

普通追加复习本：

```bash
python3 japanese_review.py
```

普通追加复习本，但结束后不询问是否清空输入文件：

```bash
python3 japanese_review.py --no-prompt
```

只归档并清空输入文件：

```bash
python3 japanese_review.py --clear-input
```

普通随机抽查：

```bash
python3 japanese_review.py --quiz
```

连续抽查 5 题：

```bash
python3 japanese_review.py --quiz --count 5
```

无限随机复习，直到输入 `q` 或 `quit` 退出：

```bash
python3 japanese_review.py --quiz --loop
```

关闭答错后重答一次：

```bash
python3 japanese_review.py --quiz --loop --no-retry
```

只复习错题：

```bash
python3 japanese_review.py --quiz --wrong
```

连续复习 5 道错题：

```bash
python3 japanese_review.py --quiz --wrong --count 5
```

无限复习错题，直到输入 `q` 或 `quit` 退出：

```bash
python3 japanese_review.py --quiz --wrong --loop
```

查看学习统计：

```bash
python3 japanese_review.py --stats
```

查看今日学习面板：

```bash
python3 japanese_review.py --today
```

一键备份学习数据：

```bash
python3 japanese_review.py --backup
```

查看标签统计：

```bash
python3 japanese_review.py --tags
```

按标签普通抽查：

```bash
python3 japanese_review.py --quiz --tag 工作
```

按标签无限抽查：

```bash
python3 japanese_review.py --quiz --tag 工作 --loop
```

按标签连续抽查 5 题：

```bash
python3 japanese_review.py --quiz --tag 工作 --count 5
```

按标签复习错题：

```bash
python3 japanese_review.py --quiz --wrong --tag 工作 --count 5
```

导出当前待复习池 CSV：

```bash
python3 japanese_review.py --export-csv
```

导出 Anki 导入 CSV：

```bash
python3 japanese_review.py --export-anki
```

导出错题本 CSV：

```bash
python3 japanese_review.py --export-csv --wrong
```

导出已掌握本 CSV：

```bash
python3 japanese_review.py --export-csv --mastered
```

检查数据健康状态：

```bash
python3 japanese_review.py --check
```

恢复初始状态：

```bash
python3 japanese_review.py --reset
```

## 菜单模式

如果不想记命令，可以使用菜单模式：

macOS：

```bash
python3 japanese_review.py --menu
```

Windows 11：

```powershell
python japanese_review.py --menu
```

`--menu` 会进入交互式菜单模式，可以通过数字选择常用功能。原有命令行参数仍然可用，菜单模式只是新增入口，适合日常使用。

如果终端颜色显示异常，可以关闭颜色：

```bash
python3 japanese_review.py --menu --no-color
```

## 快速添加

如果只想添加一句日语，不想手动打开 `input/sentences.txt`，可以使用 `--add`。

macOS 最简示例：

```bash
python3 japanese_review.py --add "今日は少し遅れて行きます。" "今天我会稍微晚一点过去。"
```

macOS 完整示例：

```bash
python3 japanese_review.py --add "仕事が終わったら、連絡します。" "工作结束后，我会联系你。" --tag "工作" --grammar "たら, ます形" --words "仕事, 終わる, 連絡する"
```

macOS 带备注示例：

```bash
python3 japanese_review.py --add "出かける前に、部屋を片付けておきたいです。" "出门前，我想先把房间整理好。" --tag "生活" --grammar "前に, ておく, たい" --words "出かける, 部屋, 片付ける" --note "重点关注「ておく」表示提前做好准备，不是单纯“做了”。"
```

Windows 11 最简示例：

```powershell
python japanese_review.py --add "今日は少し遅れて行きます。" "今天我会稍微晚一点过去。"
```

Windows 11 完整示例：

```powershell
python japanese_review.py --add "仕事が終わったら、連絡します。" "工作结束后，我会联系你。" --tag "工作" --grammar "たら, ます形" --words "仕事, 終わる, 連絡する"
```

Windows 11 带备注示例：

```powershell
python japanese_review.py --add "出かける前に、部屋を片付けておきたいです。" "出门前，我想先把房间整理好。" --tag "生活" --grammar "前に, ておく, たい" --words "出かける, 部屋, 片付ける" --note "重点关注「ておく」表示提前做好准备，不是单纯“做了”。"
```

`--add` 会直接写入：

```text
output/japanese_review.md
output/daily/YYYY-MM-DD.md
```

它不会写入 `input/sentences.txt`，也不会触发清空输入文件提示。`--tag`、`--grammar`、`--words`、`--note` 都是可选字段，未填写时保存为空字符串。

如果 `output/japanese_review.md` 中已经存在完全相同的日语句子，程序会跳过添加，不会覆盖旧数据。

## 三池流转机制

从 V13.0 开始，工具采用三池流转机制：

- `output/japanese_review.md`：当前待复习池，也叫 review 池
- `output/wrong_book.md`：错题强化池，也叫 wrong 池
- `output/mastered.md`：已掌握池，也叫 master 池

普通 Quiz 中：

- 自评 `n`：句子从 review 移入 wrong，并触发“答错后重答一次”
- 正确度很高且确认完全掌握：句子从 review 移入 master
- 自评 `y` 但不确认完全掌握：句子继续留在 review

错题 Quiz 中：

- 自评 `y` 会增加掌握次数
- 掌握次数达到 3 次后，句子从 wrong 移入 master
- 自评 `n` 则留在 wrong，并触发“答错后重答一次”

因此 `japanese_review.md` 会随着学习推进而减少，`wrong_book.md` 会随着错题毕业而减少，`mastered.md` 会逐渐增加。

从 V13.1 开始，`mastered.md` 具有最高状态优先级。当一句话进入 `mastered.md` 后，程序会自动检查 `japanese_review.md` 和 `wrong_book.md`。如果 review 或 wrong 中仍有同一句日语，程序会自动删除对应记录，避免同一句同时处于“待复习”“错题”和“已掌握”多个状态。

清理时只按日语句子完全一致匹配，不做模糊匹配，不忽略标点或空格。

## Quiz 随机抽查

普通随机抽查：

```bash
python3 japanese_review.py --quiz
```

连续抽查 5 题：

```bash
python3 japanese_review.py --quiz --count 5
```

按标签抽查：

```bash
python3 japanese_review.py --quiz --tag 工作
python3 japanese_review.py --quiz --tag 工作 --count 5
```

无限随机复习：

macOS：

```bash
python3 japanese_review.py --quiz --loop
python3 japanese_review.py --quiz --wrong --loop
python3 japanese_review.py --quiz --tag "工作" --loop
```

Windows 11：

```powershell
python japanese_review.py --quiz --loop
python japanese_review.py --quiz --wrong --loop
python japanese_review.py --quiz --tag "工作" --loop
```

`--loop` 会一直随机出题，直到输入 `q` 或 `quit` 退出。如果同时使用 `--loop` 和 `--count`，`--count` 会被忽略。

Quiz 模式默认启用彩色高亮，参考答案、语法点、重点单词会更容易区分。如果终端颜色显示异常，可以使用 `--no-color` 关闭颜色。

macOS：

```bash
python3 japanese_review.py --quiz --loop
python3 japanese_review.py --quiz --loop --no-color
```

Windows 11：

```powershell
python japanese_review.py --quiz --loop
python japanese_review.py --quiz --loop --no-color
```

Quiz 模式会优先从 `output/japanese_review.md` 中读取已经积累的句子。程序会随机显示中文意思，并让你输入对应的日语。

输入后会显示：

- 你的输入
- 参考答案
- 正确度
- 中文意思

正确度是程序用文本相似度计算出来的参考值，只比较字面接近程度，不代表完整语法判断或自然度判断。计算时会忽略常见标点和空格，例如 `。`、`、`、`.`、`,`、`!`、`?`、普通空格和全角空格。

工具会把每条句子的上次正确度、历史最高正确度和记录次数保存到 `data.json`。下次复习同一句时，会显示本次正确度、上次正确度、变化幅度和历史最高正确度。最终是否掌握仍然由你自己通过 `y/n` 自评决定。

然后程序会询问：

```text
这题掌握了吗？y/n
```

输入 `y` 表示掌握，输入 `n` 表示未掌握。未掌握的句子会自动加入错题本。

默认情况下，Quiz 中选择 `n` 后会触发“答错后重答一次”：程序会先按原逻辑加入错题本，然后要求你立刻重新输入一次该句日语，帮助加深记忆。重答也会显示正确度，并记录到 `data.json`。

如果想关闭重答，可以使用：

```bash
python3 japanese_review.py --quiz --loop --no-retry
```

Windows 11：

```powershell
python japanese_review.py --quiz --loop --no-retry
```

目前不会用 AI 或语义理解自动判对错，因为日语表达可能有多种，需要你自己对照参考答案自评。

如果句子总数少于 `--count`，程序会允许重复抽取，适合反复强化记忆。

在输入答案时，如果输入 `q` 或 `quit`，会退出抽查模式。

如果怀疑终端或输入法导致日语输入不完整，可以临时开启输入调试：

```bash
python3 japanese_review.py --quiz --count 1 --debug-input
```

调试模式会显示 Python 实际收到的原始输入、长度，以及用于正确度计算的 normalize 后文本。

## 学习统计

运行：

```bash
python3 japanese_review.py --stats
```

统计模式会显示：

- 当前待复习句子数
- 当前错题数
- 已掌握句子数
- 今日新增句子数
- 已填写语法点的句子数
- 已填写重点单词的句子数
- 已填写备注的句子数
- 今日归档文件路径
- 当前错题率
- 错题毕业率
- 今日复习建议

统计数据来自：

```text
output/japanese_review.md
output/wrong_book.md
output/mastered.md
output/daily/YYYY-MM-DD.md
```

统计面板还会显示标签总数，以及句子最多的前 5 个标签。

## 今日学习面板

`--today` 偏当天复盘，回答“我今天到底学了什么”；`--stats` 偏长期总览。

macOS：

```bash
python3 japanese_review.py --today
```

Windows 11：

```powershell
python japanese_review.py --today
```

今日学习面板会显示：

- 今日新增句子
- 今日新增句子列表
- 当前待复习句子数
- 当前错题数
- 已掌握句子数
- 今日备份次数
- 最近备份文件

今日新增句子来自：

```text
output/daily/YYYY-MM-DD.md
```

## 标签

标签用于按场景分类句子。输入时可以写：

```text
明日また連絡します | 明天再联系 | 工作
駅はどこですか | 车站在哪里 | 旅行
```

生成的复习本、每日归档、错题本和已掌握本都会保存标签、语法点、重点单词、备注字段。

查看所有标签及数量：

```bash
python3 japanese_review.py --tags
```

输出类似：

```text
标签统计：
工作：12
旅行：8
常用表达：15
```

按标签做普通 Quiz：

```bash
python3 japanese_review.py --quiz --tag 工作
python3 japanese_review.py --quiz --tag 工作 --count 5
```

按标签做错题 Quiz：

```bash
python3 japanese_review.py --quiz --wrong --tag 工作 --count 5
```

如果旧数据里没有标签字段，程序会按空标签处理，不会报错。

## 一键备份

运行：

```bash
python3 japanese_review.py --backup
```

Windows 11：

```powershell
python japanese_review.py --backup
```

`--backup` 会将核心学习数据打包到：

```text
backup/YYYY-MM-DD_HHMMSS_backup.zip
```

备份内容包括：

- `data.json`
- `input/sentences.txt`
- `input/archive/`
- `output/japanese_review.md`
- `output/wrong_book.md`
- `output/mastered.md`
- `output/daily/`
- `output/export/`
- `README.md`
- `japanese_review.py`

`backup/` 目录本身不会被打包，避免备份文件无限变大。建议每周至少备份一次，或者在大批量新增句子前后备份一次。

## 恢复初始状态

`--reset` 是危险操作，会清空当前学习数据，让工具恢复到初始状态。执行前会要求输入 `RESET` 确认，并且会自动执行一次备份。

macOS：

```bash
python3 japanese_review.py --reset
```

Windows 11：

```powershell
python japanese_review.py --reset
```

reset 会清空或删除：

- `input/sentences.txt`
- `data.json`
- `input/archive/`
- `output/japanese_review.md`
- `output/wrong_book.md`
- `output/mastered.md`
- `output/daily/`
- `output/export/`

reset 会保留 `backup/` 目录，reset 前自动生成的备份也会保存在这里。

调试或自动化测试时可以跳过确认：

```bash
python3 japanese_review.py --reset --yes
```

`--yes` 会跳过二次确认，仅建议在调试或自动化测试时使用。

## 数据导出

导出文件会生成在：

```text
output/export/
```

导出当前待复习池：

```bash
python3 japanese_review.py --export-csv
```

输出文件：

```text
output/export/japanese_review.csv
```

字段包括：

- `japanese`
- `chinese`
- `tag`
- `grammar`
- `words`
- `note`
- `status`
- `date`

导出 Anki 导入文件：

```bash
python3 japanese_review.py --export-anki
```

输出文件：

```text
output/export/anki_import.csv
```

Anki 字段含义：

- `front` = 中文意思
- `back` = 日语句子 + 语法点 + 重点单词 + 备注
- `tag` = 标签

如果语法点、重点单词或备注为空，Anki 背面不会显示空标题。

导出错题本：

```bash
python3 japanese_review.py --export-csv --wrong
```

输出文件：

```text
output/export/wrong_book.csv
```

导出已掌握本：

```bash
python3 japanese_review.py --export-csv --mastered
```

输出文件：

```text
output/export/mastered.csv
```

如果没有找到对应数据，程序会提示先添加句子。

## 数据健康检查

运行：

```bash
python3 japanese_review.py --check
```

健康检查会读取：

```text
output/japanese_review.md
output/wrong_book.md
output/mastered.md
```

它会检查：

- 重复句子
- 空日语或空中文
- 格式异常
- 标签前后多余空格
- 英文标签大小写不一致
- 语法点、重点单词和备注字段格式是否能正常识别
- 错题本里缺少掌握次数或掌握次数不是数字
- 同一句是否同时存在于 review 和 wrong
- 同一句是否同时存在于 review 和 master
- 同一句是否同时存在于 wrong 和 master

`--check` 只检查并提示，不会自动修改文件，不会删除重复句子，不会修改标签，也不会移动错题或已掌握句子。

## 输入区清理

`input/sentences.txt` 可以当作“今日待处理输入区”。每天把新句子写进去，运行普通模式处理完成后，程序会询问：

```text
是否清空 input/sentences.txt？y/n
```

输入 `y` 时，程序会先把原始输入内容归档到：

```text
input/archive/YYYY-MM-DD_sentences.txt
```

如果当天已经有同名归档文件，会自动改名为：

```text
input/archive/YYYY-MM-DD_sentences_1.txt
input/archive/YYYY-MM-DD_sentences_2.txt
```

然后清空 `input/sentences.txt`。

输入 `n` 时，程序会保留 `input/sentences.txt`。

如果你希望普通模式结束后不弹出清理提示，可以运行：

```bash
python3 japanese_review.py --no-prompt
```

如果只想清理输入文件，不追加复习本、不进入 Quiz、不查看统计，可以运行：

```bash
python3 japanese_review.py --clear-input
```

建议每天处理完后清空输入区。这样第二天只需要放新句子，能减少重复跳过，也更容易判断当天是否真的新增了内容。

## 错题本

如果 Quiz 自评时输入 `n`，程序会把该题写入：

```text
output/wrong_book.md
```

错题本每条记录会包含：

- 日语句子
- 中文意思
- 标签
- 语法点
- 重点单词
- 备注
- 加入错题本的日期
- 掌握次数
- 状态：待复习

如果错题本里已经有完全相同的日语句子，程序不会重复添加，并会提示：

```text
已在错题本中，跳过重复添加：今日は少し遅れてきます
```

只复习错题：

```bash
python3 japanese_review.py --quiz --wrong
```

连续复习 5 道错题：

```bash
python3 japanese_review.py --quiz --wrong --count 5
```

如果错题本不存在或里面没有错题，程序会提示：

```text
目前没有错题，可以先进行普通 quiz。
```

## 错题毕业机制

错题本和已掌握本的位置分别是：

```text
output/wrong_book.md
output/mastered.md
```

区别是：

- `wrong_book.md` 保存还需要专项复习的句子。
- `mastered.md` 保存已经从错题本毕业的句子。

在普通 Quiz 中：

- 自评输入 `n` 会把句子加入 `wrong_book.md`。
- 自评输入 `y` 只表示本题这次掌握，不会进入 `mastered.md`。

在错题 Quiz 中：

```bash
python3 japanese_review.py --quiz --wrong
```

如果自评输入 `y`，该错题的掌握次数会加 1。掌握次数达到 3 次后，程序会：

- 从 `output/wrong_book.md` 移除该句
- 添加到 `output/mastered.md`
- 在终端提示该错题已毕业

如果自评输入 `n`，掌握次数保持不变。

旧版错题本如果没有“掌握次数”字段，程序会按 0 处理，并在下次写回时自动补齐。

## 输出文件怎么看

运行后会生成或更新：

```text
output/japanese_review.md
```

程序不会覆盖已有内容，而是把本次新加入的句子追加到文件末尾。每次追加会使用当天日期作为标题，例如：

```markdown
## 2026-05-30
```

这个 Markdown 文件会包含：

- 标题：日语复习本
- 当天日期
- 每个句子的编号
- 日语句子
- 中文意思
- 标签
- 语法点
- 重点单词
- 备注
- 状态：待复习
- 复习次数

## 如何避免重复

程序会检查 `output/japanese_review.md` 中已经出现过的日语句子。

如果输入文件里有完全相同的日语句子，程序不会再次追加，并会在终端提示：

```text
已跳过重复句子：今日は少し遅れてきます
```

去重判断只看日语句子是否完全相同。

## 每日归档文件

除了总复习文件，程序还会生成每日归档文件：

```text
output/daily/YYYY-MM-DD.md
```

例如：

```text
output/daily/2026-05-30.md
```

每日归档文件只保存当天本次运行中新加入的句子。重复句子不会写入每日归档。

## data.json 是什么

`data.json` 用来保存每个新加入句子的复习次数。结构大致如下：

```json
{
  "今日は少し遅れてきます|今天可能会晚一点": {
    "japanese": "今日は少し遅れてきます",
    "chinese": "今天可能会晚一点",
    "review_count": 1
  }
}
```

一般不需要手动修改这个文件。

## 完整使用示例

1. 编辑 `input/sentences.txt`：

```text
今日は少し遅れてきます | 今天可能会晚一点
仕事を済ませたいです | 我想把工作完成
この件は田中さんに任せましょう | 这件事交给田中吧
```

2. 运行：

```bash
python3 japanese_review.py
```

3. 查看总复习文件：

```text
output/japanese_review.md
```

4. 查看当天归档：

```text
output/daily/2026-05-30.md
```

5. 如果再次运行同样的输入，程序会跳过已经写入过的日语句子，并在终端显示运行结果总结。

6. 也可以直接快速添加一句：

```bash
python3 japanese_review.py --add "今日は少し遅れて行きます。" "今天我会稍微晚一点过去。"
```

7. 做一次随机抽查：

```bash
python3 japanese_review.py --quiz
```

8. 连续做 5 题随机抽查：

```bash
python3 japanese_review.py --quiz --count 5
```

9. 只复习错题：

```bash
python3 japanese_review.py --quiz --wrong
```

10. 连续做 5 道错题抽查：

```bash
python3 japanese_review.py --quiz --wrong --count 5
```

11. 查看已毕业句子：

```text
output/mastered.md
```

12. 查看学习统计：

```bash
python3 japanese_review.py --stats
```

13. 普通运行但不询问清空输入：

```bash
python3 japanese_review.py --no-prompt
```

14. 只归档并清空输入文件：

```bash
python3 japanese_review.py --clear-input
```

15. 查看标签统计：

```bash
python3 japanese_review.py --tags
```

16. 按标签做 Quiz：

```bash
python3 japanese_review.py --quiz --tag 工作
python3 japanese_review.py --quiz --wrong --tag 工作 --count 5
```

17. 导出 CSV：

```bash
python3 japanese_review.py --export-csv
python3 japanese_review.py --export-anki
python3 japanese_review.py --export-csv --wrong
python3 japanese_review.py --export-csv --mastered
```

18. 检查数据健康状态：

```bash
python3 japanese_review.py --check
```
