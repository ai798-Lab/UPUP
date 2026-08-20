---
name: meta-write
description: 给首页、工具页、定价页写标题和描述，写完自动跑机械闸判 9 项：长度、主词位置、描述是不是在复述标题、有没有具体钩子、这个页型该回答的问题答了没有、全站是不是每页都不一样。也能直接吃一个线上地址，看现状差在哪。成本：零安装零付费，只用 python3 标准库，不给地址时不联网，约 30 秒。Use when 用户说「首页标题怎么写」「这页的 title 和 description 帮我写一下」「meta 描述怎么写」「定价页标题」「工具页怎么起名」「我的标题是不是太长了」「全站描述都一样怎么办」。不要用于写正文内容（那是 page-write）、查站点技术基建（那是 site-audit）、定该写什么题目（那是 rival-teardown）。产草稿绝不自动上线、不 push、不改生产分支。
---

# meta-write · 给核心功能页写标题和描述

搜索结果页上，用户先看到的只有两行字。这个 skill 管这两行。

**它管的是首页、工具页、定价页这类核心功能页。**内容页那种「回答一个具体问题」的写法在
`page-write`，两者的判据完全不同：内容页看事实密度和证据链，这两行字看长度、钩子和唯一性。

**产出的是草稿，不是上线。**要不要上线由你定。

## 为什么单独做一个

`site-audit` 已经在查 title 了（I1 长度与唯一、K1 一页一主词、K2 四处一致），
**但它只查不写，而且完全没查 meta description。**

description 缺失或全站复用是最常见的一处，代价也直接：搜索引擎会自己从正文抓一段来凑，
抓到的往往是导航文字或第一句废话。

## 成本，先说清楚

- **零安装**：只用 python3 标准库
- **零付费**：不调任何 API
- **不给 `--url` 时不联网**：判你手写的那一对，纯本地
- **约 30 秒**

## 你要给三样东西

1. **页型**：`home` / `tool` / `pricing`。不给的话「页型必答项」记未观察。
2. **主词**：这一页要吃的那个词。不给的话「主词在 title 前半」记未观察。
3. **一对 title 与 description**，或者一个线上地址让它去抓当前的。

## 三步

```
① 看现状   metagate.py --url 你的页面      抓当前这两行，看差在哪
② 真写     照 references/playbook.md 写
③ 机械闸   metagate.py --title ... --description ...   出 PASS / REWORK / REJECT
```

**第 ② 步只准改文案，不准改评分器。**判据在 `_shared/rubric.json`，那是四个 skill 共享的单一真相源。

### ① 看现状

```bash
python3 <skills>/meta-write/scripts/metagate.py \
  --url https://你的域名/free-tools/caption-generator \
  --page-type tool --keyword "caption generator" \
  --peers https://你的域名/free-tools/hashtag-generator,https://你的域名/pricing
```

`--peers` 给同组的其他几页，才能判出「全站是不是每页都不一样」。不给的话那一项记未观察。

页面取不到时它会直接退出并告诉你去用 `site-audit` 查 G1 与 G2，
**不会把「抓不到」判成「meta 写得不好」。**

### ② 真写

招式在 `references/playbook.md`：三种页型各自必须回答什么、钩子写什么、真实样例的字符数。

### ③ 机械闸

```bash
python3 <skills>/meta-write/scripts/metagate.py \
  --title "Free AI Caption Generator: Social Media Captions in Seconds" \
  --description "Generate on-brand social media captions instantly with our free AI caption generator. For Instagram, Facebook, LinkedIn, and more." \
  --page-type tool --keyword "caption generator" \
  --json runs/meta.json
```

退出码：`0` PASS，`1` REWORK（分不够），`2` REJECT（门槛未过）。

## 判据表

下面这张表由 `_shared/rubric.json` 生成，**不要手改**。
`python3 ../_shared/rubric_check.py --check-doc SKILL.md` 会断言两边一致。

<!-- RUBRIC-TABLE:meta START 由 rubric_check.py --print-table 生成，勿手改 -->
| 项 | 名称 | 怎么测 | 通过判据 | 出处等级 |
|---|---|---|---|---|
| C4 | 无营销腔 | 在正文里搜营销套话（#1 / best ever / amazing / world's best / free forever / revolutionary / 业界领先 / 遥遥领先 / 一键搞定 之类），命中就把原句抄出来。 | 3 分：0 处；2 分：1 处；1 分：2 到 3 处；0 分：4 处以上 | Research |
| MG1 | 两样都写了 | 查 title 与 meta description 是否都存在且非空白。title 少于 6 个字符、description 少于 20 个字符，视同没写。 | 两样都在，且长度分别不低于 6 与 20 | Heuristic |
| M1 | title 长度 | title 字符数，CJK 按 2 计（与 audit lane 的 I1 同一套计法）。 | 3 分：15 到 60；2 分：60 到 70，或 10 到 15；1 分：超出上述但非空；0 分：空 | Heuristic |
| M2 | description 长度 | meta description 字符数，CJK 按 2 计。 | 3 分：70 到 155；2 分：155 到 175，或 50 到 70；1 分：超出上述但非空；0 分：空 | Heuristic |
| M3 | 主词在 title 前半 | 取主词的实义词集合，找它们在 title 里首次出现的位置，除以 title 长度得到相对位置。没给主词时记未观察。 | 3 分：首次出现在前 1/3；2 分：出现在前 1/2；1 分：出现但落在后半；0 分：title 里根本没有主词 | Heuristic |
| M4 | description 不复述 title | 算 title 与 description 两边实义词集合的 Jaccard 相似度。 | 3 分：重叠度不超过 0.30；2 分：不超过 0.50；1 分：不超过 0.70；0 分：高于 0.70，基本是把标题又说了一遍 | Heuristic |
| M5 | description 里有具体钩子 | 在 description 里数四类具体信息各出现与否：① 带单位的数值（秒 / 分钟 / 次 / 个 / % / 美元 / 元 之类）；② 价格或币种；③ 免费程度（免费 / free / 不用注册 / no sign-up 之类）；④ 明确的产出物或支持范围（导出格式、平台名、文件类型）。计命中的类别数。 | 3 分：命中 2 类以上；2 分：命中 1 类；1 分：一类都没有但句子里含动词；0 分：通篇形容词，没有任何具体信息 | Heuristic |
| M6 | 页型必答项 | 按页型查 title 加 description 里必须出现的东西：home 要有品类词与人群或用途；tool 要有功能动词（生成 / 转换 / 检测 / generator / converter 之类）；pricing 要有价格数字与币种。没给页型时记未观察。 | 3 分：该页型要求的都出现了；2 分：出现一半；1 分：只出现一项；0 分：一项都没有 | Heuristic |
| M7 | 同组唯一 | 一次给多页时，在这一组之间查完全相同的 title 与完全相同的 description。只给一页时记未观察。 | 3 分：title 与 description 都全组唯一；2 分：description 有重复，title 唯一；1 分：title 有 1 处重复；0 分：title 有 2 处以上重复 | Heuristic |
<!-- RUBRIC-TABLE:meta END -->

跑机械闸时另外两个 lane 的项不在这里：正文事实密度、sitemap 通不通，
在「一对 title 与 description」这个输入上根本不存在。**那些不是通过，是没测。**

## 两个人工确认（机械闸替不了）

1. **这两行字换成竞品的名字，还成立吗？**成立的话，你写的是品类通用话术，不是你这一页。
2. **用户看到这一条，知道点进去会发生什么吗？**答不上来，钩子就还不够具体。

这两问答不了「是」，就不该上线，哪怕机械闸满分。

## 铁律

1. **未观察不等于零，也不等于通过。**没给页型就不判页型必答项，没给同组页就不判唯一性。
2. **不自动上线、不 push、不改生产分支。**
3. **机械分不许改。**每项都带 `machine_locked: true`，模型只能引用。
4. **抓不到页面时不判 meta。**那是 `site-audit` 的 G1 与 G2 该管的事。

## 文件

| 路径 | 作用 |
|---|---|
| `SKILL.md` | 本文件 |
| `scripts/metagate.py` | 机械闸入口，判据不在这里，只负责采集与组装输入 |
| `references/playbook.md` | 三种页型各自怎么写，含真实样例与实测字符数 |

共享地基（与本 skill 目录同级，四个 skill 共用，必须整个 `skills/` 一起拷）：

| 路径 | 作用 |
|---|---|
| `../_shared/fetch.py` | 页面事实的唯一提取口 |
| `../_shared/rubric.json` | 机械检查项的单一真相源 |
| `../_shared/rubric_check.py` | 机械分引擎 |

## 自检

```bash
python3 <repo>/evals/check.py                                  # 靶站与纪律回归全绿
python3 ../_shared/rubric_check.py --check-doc SKILL.md        # 本文件的表与 rubric.json 同步
```

## 已知边界（用之前先知道）

- **它判不了这两行字好不好，只判有没有写空。**真正的判据是上面那两个人工确认。
- **长度的 60 与 155 是经验值，不是平台规则。**实际截断位随设备、查询词和是否命中富摘要而变。
- **钩子那一项按关键词匹配。**写了「30 秒」算命中，但这个数字是不是真的，机器不知道。
- **主词位置按字符串首次出现算。**同义词、词形变化不算命中，给主词时用页面上真实出现的那个写法。
- **抓线上页时不跑 JS。**纯前端渲染才注入 meta 的站，这里会判成没写。爬虫看到的也是这样，
  但那是另一个问题，去 `site-audit` 查 G3。
