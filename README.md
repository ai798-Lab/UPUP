# UPUP

三个 Agent Skill，管你的产品上线之后**怎么被搜索引擎和 AI 找到**。

零安装、零付费、只用 python3 标准库。不装 npm，不开浏览器，不登录任何账号，不调任何 API。

功能对不对是另一件事，那是 [Karman](https://github.com/ai798-Lab/karman) 管的。
UPUP 只管功能没问题之后，怎么让人和 AI 找得到你。

---

## 目录

- [它解决什么问题](#它解决什么问题)
- [工作原理](#工作原理)
- [三个 skill](#三个-skill)
- [安装](#安装)
- [怎么用](#怎么用)
- [输出怎么读](#输出怎么读)
- [被 AI 当成事实收录，靠的是四件事](#被-ai-当成事实收录靠的是四件事)
- [判据全表](#判据全表)
- [设计纪律](#设计纪律)
- [不做什么](#不做什么)
- [已知边界](#已知边界)

---

## 它解决什么问题

你的产品上线了，功能没毛病，但没人来。

打开任何一个 SEO 工具，它给你一份 80 项的清单，每项都标着红色，你不知道先改哪一个。
问 AI「我的站怎么优化」，它给你一堆放之四海而皆准的建议，没有一条能验证做了有没有用。

UPUP 干三件事：

1. **查地基**，告诉你**第一件**该修什么，并给一条能跑出结果的验证命令
2. **拆竞品**，告诉你该写什么，每条选题挂着对手的那一页地址
3. **写内容**，替你写出草稿，并用 13 项机械判据卡住「写空了」

---

## 工作原理

### 三层结构

```
        ┌─────────────────────────────────────────────┐
   ①    │  采集层   fetch.py / robots.py / sitemap.py │
        │  只发普通 HTTP 请求，只看爬虫能看到的东西     │
        │  每次请求的结果分四类：ok / blocked /        │
        │  dead / unknown                             │
        └────────────────────┬────────────────────────┘
                             │  证据 dict
        ┌────────────────────▼────────────────────────┐
   ②    │  判据层   rubric.json + rubric_check.py     │
        │  33 项判据全写在一个 json 里，代码只负责算   │
        │  每项产出 score + observed + source + fix   │
        └────────────────────┬────────────────────────┘
                             │  逐项结果
        ┌────────────────────▼────────────────────────┐
   ③    │  报告层   report.html + 动作排序            │
        │  整份报告只支撑一个动作，其余全是佐证        │
        └─────────────────────────────────────────────┘
```

### 一、采集层：只看爬虫能看到的东西

采集层只发普通 HTTP 请求，**不跑 JS**。理由很直接：AI 爬虫和搜索爬虫抓你的页面时也不跑 JS。
你的正文如果只在前端渲染后才出现，那对它们来说就是不存在。所以这里故意不用浏览器自动化，
让你看到的和爬虫看到的是同一份东西。

采集层做的最重要的一件事是**把请求结果分成四类**，而不是简单的成功失败：

| 分类 | 什么状态 | 意味着什么 | 动作指向哪 |
|---|---|---|---|
| `ok` | 2xx | 正常拿到 | 继续判 |
| `blocked` | 401 / 403 / 429 / 451 | **站是活的，被防护规则拦了** | CDN 后台放行 UA |
| `dead` | 404 / 5xx | 地址或部署真有问题 | 查地址与部署 |
| `unknown` | 连接层失败 | 既不能说活也不能说死 | 记未观察，不判定 |

**这个分类是整套东西的地基。**独立开发者的站大量挂 CDN 防护，把 403 判成「你的网站下线了」
会大面积误伤，而且会把用户推向完全错误的排查方向（去查部署，其实要去改 CDN 规则）。

### 二、判据层：所有判断集中在一个 json 里

33 项判据全部写在 `skills/_shared/rubric.json`，Python 代码只负责算，不藏任何判断标准。

一条判据长这样：

```json
{
  "id": "T3",
  "name": "sitemap 里的地址真的活着",
  "kind": "score",
  "lanes": ["audit"],
  "machine_locked": true,
  "weight": 3,
  "pass_at": 2,
  "how": "等距抽 5 条真发 HEAD 请求。分开统计死链、重定向、被拦。被拦不计入死链。",
  "anchors": {"3": "抽样全部 200 直达", "2": "有重定向但没有死链",
              "1": "抽样里有 1 条死链", "0": "抽样里有 2 条以上死链"},
  "why": "sitemap 格式全对、里面躺着死链，是最常见的沉默故障：所有检查器都说你有 sitemap，但爬虫按它抓一路撞墙。",
  "fix": {"1": "报告里列了是哪几条。从 sitemap 里删掉，或把页面补回来。"},
  "source": "本套件自定，无公开出处",
  "evidence_level": "Heuristic"
}
```

四个字段值得单独说：

- **`machine_locked`**：这一项的分数由脚本算出，**模型只能引用不能改**。
  防的是「AI 觉得这个站还行，就把分数往上调一调」。
- **`source` 与 `evidence_level`**：每条判据都要交代自己凭什么。
  `Official` 是平台或标准文档明写的，`Research` 有公开研究支撑，
  `Derived` 是本次跑到的对照组现算的，`Heuristic` 是本套件的经验值。
  **Heuristic 就明说是经验值，不冒充平台规则。**当前分布：Official 14、Heuristic 15、Research 3、Derived 1。
- **`fix`**：不过时给什么动作。**按分档给不同动作**，不是所有失分都给同一句废话。
- **`how`**：怎么测。这段文字会被 `--print-table` 生成进 SKILL.md 的判据表，
  `--check-doc` 断言两边一致。**改了判据不同步文档，跑自检当场红。**

### 三、报告层：只给一个动作

一份 30 项全红的报告等于没有报告，用户不知道从哪下手，通常的结果是一项都不改。

所以报告末尾只留一个动作位。哪一项被选中，**排序写死在代码里**，不让模型临场决定：

```
G1 页面取得到  →  G2 爬虫进得来  →  G3 正文在初始 HTML  →  T1 sitemap  →  T5 canonical 可达  →  ……
```

**抓取类永远排在内容类前面。**内容拿不到的时候，改文案的收益是零。

每个动作配一条可复现的验证命令，比如四写法归一那一项给的是：

```bash
for v in http://你的域名 https://你的域名 http://www.你的域名 https://www.你的域名; do
  curl -so /dev/null -w "$v -> %{url_effective}\n" -L $v
done
```

**这条纪律救过一次命。**第一次在真站上跑，四写法归一判了失分，但用它自己给的验证命令跑出来是全对的。
查下去发现是尾部斜杠没归一化，`https://a.com` 和 `https://a.com/` 被当成了两个落点。
如果当时没跑那条验证命令，这个误报会直接进产品，用户照着一个本来就没问题的项改一整天。

### 未观察：这套东西最重要的一条设计

**抓不到的东西标「未观察」，永远不折算成 0 分。**

听起来像个小细节，实际上它决定了这份报告能不能用。举个真实场景：

> 你的站挂在 Cloudflare 后面，robots.txt 对脚本请求返回 403。
>
> 一个把未观察当 0 分的检查器会说：「你的 robots.txt 配置有问题，爬虫全被挡住了，
> 请立刻修改 robots.txt。」你打开一看，robots.txt 明明写着 `Allow: /`。你改了半天，
> 验证命令永远不变绿，因为它从头到尾就没有被观察到过。

UPUP 的做法：

- robots.txt 取不到 → 标未观察，**报告里一个字都不许出现「去改 robots」**
- robots.txt 返回 404 → 这是**合法且正常**的状态，等于全站放行，不扣分不给动作
- 未观察的项**不进分母**。整站抓不到时，满分基数是 0，不产出一份「你 0 分」的报告

同一条纪律的另一面：**没去请求就不许说「可达」**。离线跑机械闸时，来源可达性那一项记未观察，
不判通过也不判失败。

回归测试里有 6 条专门盯这件事，因为它是最容易悄悄退化的地方。

### 判据怎么保证不退化

24 份靶站，**每份只犯一种错**，页头声明它必须触发哪一条：

```
<!-- EXPECT: W5 -->
<!-- WHY: 只犯一种错：来源可达且是一手，但页面里没有这几个数字。 -->
```

回归断言的是「**一个不少，一个不多**」。只断言「该触发的触发了」的话，
一个把所有项都判失败的坏引擎也能全绿。

所有靶站从同一份 `00-pass-baseline` 派生，每份只做一处变异。
这样「多触发」就是真的误伤，不是靶站之间本来就不一样。

来源类判据（要联网核对的那几项）注入 stub 取源函数，让回归**离线可跑**：
依赖真实网络的测试会因为对方站点抽风而红，那种红没有信息量。

---

## 三个 skill

```
site-audit       查地基：sitemap / robots / canonical / 结构化数据，加正文可抽取性
      ↓
rival-teardown   定该写什么：拆竞品，产出带出处的选题清单
      ↓
page-write       写出来：抓对照页当证据，写一段能被整段摘走的内容
```

| skill | 一句话 | 判据数 | 耗时 |
|---|---|---|---|
| `site-audit` | 给个网址，告诉你第一件该修什么 | 21 | 约 1 分钟 |
| `rival-teardown` | 给两三个竞品，告诉你该写什么 | 不打分，出清单 | 2 到 4 分钟 |
| `page-write` | 给个题目，替你写出草稿并跑机械闸 | 13 | 约 3 分钟 |

---

## 安装

```bash
git clone git@github.com:ai798-Lab/UPUP.git ~/upup

ln -s ~/upup/skills/_shared        ~/.claude/skills/_shared
ln -s ~/upup/skills/site-audit     ~/.claude/skills/site-audit
ln -s ~/upup/skills/rival-teardown ~/.claude/skills/rival-teardown
ln -s ~/upup/skills/page-write     ~/.claude/skills/page-write
```

**`_shared` 必须一起链。**三个 skill 共用那一份地基。只链其中一个的话，
跑起来会告诉你「找不到共享地基」并列出它找过哪些路径，不会甩一屏堆栈。

不想用软链的话，设个环境变量也行：

```bash
export UPUP_SHARED=~/upup/skills/_shared
```

装完验一下，两个都该全绿：

```bash
python3 ~/upup/evals/check.py         # 24 份靶站 + 纪律回归
python3 ~/upup/evals/check_index.py   # 文件索引 · 命令 · 章节引用 · 硬编码路径
```

装好之后在 Claude Code 里直接说人话就行（「帮我看看我的站行不行」「我该写什么」），
skill 会自己被调起来。下面的命令是给你想手动跑的时候用的。

---

## 怎么用

### 场景一：刚上线，不知道从哪下手

```bash
python3 ~/upup/skills/site-audit/scripts/audit.py https://你的域名 \
  --json runs/audit.json --html runs/audit.html
```

输出长这样（这是在一个真实站点上跑出来的）：

```
verdict=REWORK  分数=91.1%  下一个动作=可提取证据密度
```

打开 `runs/audit.html`，最上面就是**本周就做这一件**，下面是逐项明细和每项的出处等级。

要顺带查跨页抢词（两页抢同一个关键词是自己打自己），加几个核心页：

```bash
python3 ~/upup/skills/site-audit/scripts/audit.py https://你的域名 \
  --pages https://你的域名/a,https://你的域名/b --json runs/audit.json
```

### 场景二：改完了，想知道有没有变好

```bash
# 改完之后再跑一次
python3 ~/upup/skills/site-audit/scripts/audit.py https://你的域名 --json runs/audit2.json

# 两份做 diff
python3 ~/upup/skills/site-audit/scripts/audit.py --compare runs/audit.json runs/audit2.json
```

只报三件事：**哪几项从红转绿、哪几项退化了、哪几项两次都没观察到**。

它**只对机器能验证的部分负责**，不承诺「AI 会不会引用你」。
那件事没有可靠的免费测法，硬测出来的数字换个问法就变，也归不到你改的哪一行上。

### 场景三：地基没问题了，要开始写内容

第一步，拆竞品定题目：

```bash
python3 ~/upup/skills/rival-teardown/scripts/teardown.py "竞品甲.com,竞品乙.com" \
  --mine 你的域名 --json runs/teardown.json
```

```
拆了 2 家，抓到 12 页

选题清单前 5 条：
  generator                他们 2 页在做 → https://竞品甲.com/de/random-quote-generator
      凭什么：写了 FAQ 结构化数据；写了步骤结构化数据
      你缺：你全站没有 FAQ 结构化数据；你全站没有对比表
```

**`--mine` 一定要带**，不带的话「你缺什么」那一栏是空的。

第二步，抓对照页，算出本次的通过线：

```bash
python3 ~/upup/skills/page-write/scripts/winners.py \
  --question "<从清单里挑一个>" --from-teardown runs/teardown.json --out runs/winners.json
```

```
抓到 4 / 4 个对照页
事实密度中位数 0.35，这就是本次机械闸 W1 的通过线
缝：没有一个对照页给数字标了外部来源
```

最后那行「缝」是重点：**对照组一个都没有的东西，就是你的机会**。

第三步，照骨架写，然后过闸：

```bash
cp ~/upup/skills/page-write/assets/draft-skeleton.md drafts/my-draft.md
# 照着 skills/page-write/references/playbook.md 写完之后

python3 ~/upup/skills/page-write/scripts/gate.py \
  --draft drafts/my-draft.md --question "<同上>" \
  --winners runs/winners.json --self-host 你的域名 --json runs/gate.json
```

```
verdict=REWORK  机械分=76.3%
  未过 W2  来源标注率            挂了来源的数值块 1 / 5，占比 20%
       动作：每个数字后面挂上它的出处链接。自己产品的数据就标明是自测，也算标注。
  未过 W5  数字在来源里查得到      核了 6 个数字，来源页里找不到的 2 个
       动作：报告指出了是哪个数字。核对原文，改数字或改来源。
```

**`--self-host` 记得带**，否则你引自己站的自测数据会被判成二手来源，
逼你去找一个其实不存在的外部出处。

改完再跑，最多三轮。**只改内容，不改评分器**：为了让一份草稿过关去动 `rubric.json`，
等于把尺子锯短。

---

## 输出怎么读

每一项的结果长这样：

```json
{
  "id": "T5",
  "name": "canonical 指向的地址 200 直达",
  "observed": true,
  "score": 0,
  "pass": false,
  "machine_locked": true,
  "detail": "canonical 目标返回 404",
  "fix": "canonical 指的地址是死的。把它改成这一页真实的可访问地址。",
  "source": "Google Search Central 规范化文档",
  "evidence_level": "Official"
}
```

读的时候按这个顺序看：

1. **`observed` 是不是 true**。false 的话后面都不用看了，这项这次没测到。
   **未观察不等于通过，也不等于零分。**
2. **`pass`**。false 才需要动。
3. **`evidence_level`**。`Heuristic` 意味着这是本套件的经验判断，不是谁的官方规则，
   你可以有不同意见。`Official` 有文档撑腰。
4. **`fix`**。这一项具体该做什么。

顶层的 `verdict` 三个值：`PASS`（全过）、`REWORK`（有计分项没到线）、`REJECT`（门槛项没过）。

**百分比只用来排序，不是及格证书。**判据是「哪一项没过」，不是「多少分算及格」。

---

## 被 AI 当成事实收录，靠的是四件事

`page-write` 把这四条做成了可量化的判据，跑一遍就知道差多少：

| 原则 | 判据 | 怎么量 |
|---|---|---|
| **多写事实** | W1 事实密度 | 含带单位数值或日期的段落占比。**通过线取对照组中位数** |
| **引用数据标来源** | W2 来源标注率 | 有数字的段落里，多少条挂了可点的来源 |
| **证据链完整** | W3 来源打得开吗 | 每条来源真发一次请求，死链单列 |
| | W4 来源是不是一手 | 域名分档。**引自己站的自测数据算一手** |
| | **W5 数字在来源里查得到吗** | **抓来源页正文，搜这个数字在不在里面** |
| **有图有视频** | W6 可被引的素材 | alt · 说明文字 · JSON-LD 里的 ImageObject 或 VideoObject |

**W5 是这套判据里最狠的一条。**链接能打开不代表数字对得上，
而一条可达、来源体面、数字却对不上的引用，是最像真的假证据，人工抽查几乎抓不到。
它是证据链上唯一能机器验的最后一环。

**事实密度的通过线不拍脑袋定。**写多少才算够，没有任何公开出处能给这个数，所以这里不编：
抓到 3 个以上对照页时，通过线就是它们的中位数，出处就是那几个页面本身。
抓不到时才回退到经验值，**并且报告里会写明这次用的是回退值**。

---

## 判据全表

### site-audit（21 项）

| 组 | 项 |
|---|---|
| 门槛（一票否决） | G1 页面取得到 · G2 爬虫进得来 · G3 正文在初始 HTML 里 |
| sitemap | T1 可用 · T2 内容卫生 · T3 里面的地址真的活着 |
| canonical | T4 数量与形态 · T5 200 直达 · T6 四种写法归一 |
| 结构化数据 | T7 语法能解析 · T8 类型对得上这一页 · T9 和页面上看得到的一致 |
| 内容可抽取 | C1 H1 · C2 首屏 50 词给答案 · C3 可提取证据密度 · C4 无营销腔 |
| 关键词分布 | K1 一页一主词 · K2 四处一致 |
| 国际化 | I1 title 长度与唯一 · I2 语言标记 · I3 hreflang |

robots 按**四档**分别判，因为后果不是一回事：

| 档 | 代表 UA | 被拦的后果 |
|---|---|---|
| 传统检索 | Googlebot · Bingbot | 搜索收录归零 |
| AI 检索索引 | OAI-SearchBot · Claude-SearchBot · PerplexityBot | AI 的索引里没有你 |
| **AI 实时取页** | ChatGPT-User · Claude-User · Perplexity-User | **AI 当场想引你都取不到页面** |
| 训练抓取 | GPTBot · ClaudeBot · CCBot · Google-Extended | 影响模型记忆里有没有你。**拦不拦是你的选择，只报事实不判对错** |

比 robots.txt 更容易误伤的两处也一起查，因为站主通常看不见它们：
页面级 `<meta name="robots" content="noindex">`，
响应头级 `X-Robots-Tag: noindex`（平台和框架的默认配置最常见）。

### page-write（13 项）

| 组 | 项 |
|---|---|
| 门槛 | WG1 答案前置 · D1 有可复现验证命令 · D2 有待核清单 |
| 证据链 | W1 事实密度 · W2 来源标注率 · W3 来源打得开 · W4 来源一手性 · W5 数字可回溯 |
| 可抽取 | W6 可被引的素材 · W7 段落能单独站住 · W8 Schema · W9 内链 |
| 表达 | C4 无营销腔 |

完整判据（含每项的 how / anchors / why / fix / source）在
[`skills/_shared/rubric.json`](skills/_shared/rubric.json)。

---

## 设计纪律

这几条逐条落成了机器检查，不靠记性：

| 纪律 | 靠什么保证 |
|---|---|
| 没在真实站点跑过的不发 | [`examples/`](examples/) 里放真跑产物 |
| 文件索引里绝不列不存在的文件 | `evals/check_index.py`。这个错在这条工作线上犯过三次，第四次改成机器查 |
| 抓不到标未观察，永不折算成 0 | `evals/check.py` 里 6 条专测这个 |
| 未观察时不给动作 | 同上。robots 取不到时报告一个字都不许提「去改 robots」 |
| 403 是被拦不是下线 | `fetch.py` 的四分类 |
| 机械分模型不许改 | 每项结果都带 `machine_locked: true` |
| 判据改了文档必须同步 | `rubric_check.py --check-doc` 断言 SKILL.md 的表与 rubric.json 一致 |
| 不确定标待核，不替站主拍板 | `page-write` 的 D2 是门槛项 |
| 产草稿绝不自动上线 | 不 push、不改生产分支，产物只落在 `drafts/` 与 `runs/` |
| 零安装零付费 | 只用 python3 标准库，回归测试也不依赖网络 |
| 脚本里不许有作者的机器路径 | `check_index.py` 扫这个。硬编码了作者的家目录，作者就永远复现不了用户的故障 |

---

## 不做什么

| 不做 | 为什么 |
|---|---|
| **改你的代码** | 风险最高，识别错技术栈会往错的文件塞东西。报告里已经给出改法，你本来就在用 AI 写代码，让它照着改即可 |
| **人肉去问 AI 看现状** | 要你自己开浏览器粘五轮问答，换个问法结果就变，**归不到你改的哪一行上**。看效果用 `--compare`，那是可复现的 |
| **外链提交自动化** | 价值在名单不在逻辑。名单在 [`references/directories.md`](references/directories.md)，十个入口人手两小时做完，不值得为它写代码并长期维护 |
| **测「AI 有没有引用你」** | 没有可靠的免费测法。要做只能装浏览器自动化、克隆登录态、人工过验证码，四十分钟起，而且结果不可复现 |

---

## 已知边界

- **不跑 JS。**爬虫看到什么，它就看到什么。纯前端渲染的站会被判成正文为空，那是真实观察不是误判。
- **跨页判据要够多的页才成立。**一页一主词需要至少 3 个页面，拿不到就记未观察，不硬判。
- **sitemap index 只展开前 3 个子文件。**大站的结论只覆盖被展开的部分，报告里会标出来。
- **机械分不证明写得好。**它防的是写空。真正的判据是 `page-write` 最后那两个人工确认：
  这段里有没有一句是别处抄不到的，AI 真会把这段整段摘走吗。
- **判据里有 15 项是经验值。**它们标着 Heuristic，不冒充平台规则。
- **机制层台账里有一条主张标着「出处待补」。**那条被反复引用的
  「只改正文命中率下降、只改结构上升」的数字，目前没有可点的原始出处，
  所以任何判据都不许把 source 指向它，依赖它的三条判据已从 Research 降级为 Heuristic。
  见 [`skills/_shared/references.md`](skills/_shared/references.md) 第 4 节。

---

## 目录

```
upup/
├── README.md
├── skills/
│   ├── _shared/                 三个 skill 共用，必须整个 skills/ 一起拷
│   │   ├── fetch.py             取页面事实，含 ok/blocked/dead/unknown 四分类
│   │   ├── robots.py            robots 取与最长匹配判定，四档 bot 分档
│   │   ├── sitemap.py           sitemap 取、index 递归、抽样实测
│   │   ├── rubric.json          33 项判据的单一真相源，每条带 source 与出处等级
│   │   ├── rubric_check.py      机械分引擎，产出标 machine_locked
│   │   ├── references.md        机制层台账，每条带核实日期与出处
│   │   └── report.html          报告基底
│   ├── site-audit/              查地基
│   ├── rival-teardown/          定该写什么
│   └── page-write/              写出来
├── references/
│   └── directories.md           免费收录名单，带核实日期
├── evals/
│   ├── check.py                 24 份靶站 + 纪律回归
│   ├── check_index.py           文件索引与引用自检
│   └── fixtures/                靶站，每份只犯一种错，从 baseline 派生
└── examples/                    真跑产物
```
