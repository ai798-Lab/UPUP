---
name: site-audit
description: 给一个网址，一次查完搜索引擎和 AI 两侧的地基：sitemap、robots、canonical、结构化数据这四项技术基建，加上正文可抽取性与关键词分布，共 21 项机械判据，末尾只给一个本周做得完的动作和一条可复现的验证命令。成本：零安装、零付费、约 1 分钟，只发普通 HTTP 请求，不开浏览器、不登录任何账号。Use when 用户说「帮我看看我的站行不行」「我的网站 SEO 怎么样」「AI 抓不抓得到我」「为什么搜不到我」「刚上线该先做什么」「该先改哪一处」「体检一下」，或者要对比两次改动之间有没有变好。不要用于写内容（那是 page-write）、拆竞品定选题（那是 rival-teardown）。
---

# site-audit · 一次查完搜索和 AI 的地基

给一个网址，告诉你这站在搜索引擎和 AI 面前长什么样，以及**第一件该修什么**。

它不产出一份 50 项的清单让你自己挑。整份报告只支撑一个动作，其余全是佐证。

## 什么时候用它

| 你会这么说 | 就是这个 skill |
|---|---|
| 帮我看看我的站行不行 | 是 |
| 我的网站 SEO 怎么样 / AI 抓得到我吗 | 是 |
| 为什么搜不到我 / 刚上线先做什么 | 是 |
| 我改完了，有没有变好 | 是，用 `--compare` |
| 帮我写第一篇 / 补个 FAQ | 不是，用 page-write |
| 竞品靠什么赢的 / 我该写什么 | 不是，用 rival-teardown |
| AI 到底有没有推荐我 | 本套件不做这件事，理由见 README |

## 成本，先说清楚

- **零安装**：只用 python3 标准库，不装任何第三方包，不装 npm，不用浏览器自动化
- **零付费**：不调任何 API，不需要注册任何账号
- **会联网**：发几十个普通 HTTP 请求，只读公开页面
- **约 1 分钟**：站大、sitemap 长的话到 2 到 3 分钟

## 怎么跑

```bash
python3 <skills>/site-audit/scripts/audit.py https://你的域名 \
  --json runs/audit.json --html runs/audit.html
```

改完之后想知道有没有变好：

```bash
python3 <skills>/site-audit/scripts/audit.py https://你的域名 --json runs/audit-new.json
python3 <skills>/site-audit/scripts/audit.py --compare runs/audit.json runs/audit-new.json
```

`--compare` 只报三件事：哪几项从红转绿、哪几项退化了、哪几项两次都没观察到。
**它只对机器能验证的部分负责**，不承诺「AI 会不会引用你」，那件事没有可靠的免费测法。

退出码：`0` 全过，`1` 有项没过。

## 四项技术基建，SEO 和 GEO 共用的地基

任何一项配错，上面写多好的内容都传不出去。同一项在两侧关心的不是一件事：

| 项 | SEO 侧关心 | GEO 侧关心 |
|---|---|---|
| sitemap | 收录入口，新页多久被发现 | 没有外链时，AI 爬虫唯一的发现路径 |
| robots.txt | Googlebot / Bingbot 进不进得来 | **AI 的两档 bot 分别进不进得来，被拦就是零** |
| canonical | 权重归一，防同站页面自相残杀 | AI 引用时给出的，是不是你能追踪到的那个地址 |
| JSON-LD | 富结果展示 | **机器无歧义拿到「这是什么、谁做的、多少钱」的唯一通道** |

robots 按四档分别判，因为后果不是一回事：

| 档 | 代表 UA | 被拦的后果 |
|---|---|---|
| 传统检索 | Googlebot · Bingbot | 搜索收录归零 |
| AI 检索索引 | OAI-SearchBot · Claude-SearchBot · PerplexityBot | AI 的索引里没有你 |
| **AI 实时取页** | ChatGPT-User · Claude-User · Perplexity-User | **AI 当场想引你都取不到页面** |
| 训练抓取 | GPTBot · ClaudeBot · CCBot · Google-Extended | 影响模型记忆里有没有你。**拦不拦是你的选择，本 skill 只报事实不判对错** |

## 判据表

下面这张表由 `_shared/rubric.json` 生成，**不要手改**。改判据请改 `rubric.json` 再重新生成，
`python3 ../_shared/rubric_check.py --check-doc SKILL.md` 会断言两边一致。

<!-- RUBRIC-TABLE:audit START 由 rubric_check.py --print-table 生成，勿手改 -->
| 项 | 名称 | 怎么测 | 通过判据 | 出处等级 |
|---|---|---|---|---|
| G1 | 页面取得到 | 看 HTTP 状态码分类：2xx 为 ok；401/403/429/451 为 blocked（站活着，被防护规则拦了）；404 与 5xx 为 dead；连接层失败为 unknown。 | reach = ok | Official |
| G2 | 爬虫进得来 | robots.txt 按 RFC 9309 最长匹配规则，对四档 bot 分别判：search（Googlebot/Bingbot）、ai_search（OAI-SearchBot/Claude-SearchBot/PerplexityBot）、ai_user（ChatGPT-User/Claude-User/Perplexity-User）、training（GPTBot/ClaudeBot/CCBot/Google-Extended）。另查页面 meta robots 与响应头 X-Robots-Tag 的 noindex。robots.txt 返回 404 = 全放行，正常状态。403 或超时 = 未观察，此时不给任何改 robots 的动作。 | search / ai_search / ai_user 三档全放行，且无 noindex | Official |
| G3 | 正文在初始 HTML 里 | 剥掉 script/style/head/noscript/svg 后数正文词数，CJK 逐字计一词。 | ≥ 120 词 | Heuristic |
| T1 | sitemap 可用 | 按三个来源找：robots.txt 里声明的地址、/sitemap.xml 等常见路径、/sitemap。取到后判根元素必须是 urlset 或 sitemapindex，且首 400 字符里不含 <html。 | 3 分：找得到且是合法 XML，robots.txt 里也用绝对地址声明了；2 分：找得到且合法，但 robots.txt 里没声明；1 分：找得到但是软 404：返回 200 却是一页 HTML；0 分：三个来源都没有 | Official |
| T2 | sitemap 内容卫生 | 查五项：单文件不超 5 万条、不超 50MB、全绝对路径、同 host、无 fragment、协议统一；另查 lastmod 格式是否合法、是否全站同一个日期。 | 3 分：五项全过且 lastmod 可信；2 分：只有 lastmod 问题（格式或全站同日）；1 分：有相对路径、跨 host 或 fragment；0 分：超过条数或体积硬上限 | Official |
| T3 | sitemap 里的地址真的活着 | 等距抽 5 条真发 HEAD 请求。分开统计死链（404/5xx）、重定向（3xx）、被拦（401/403/429）。被拦不计入死链。 | 3 分：抽样全部 200 直达；2 分：有重定向但没有死链；1 分：抽样里有 1 条死链；0 分：抽样里有 2 条以上死链 | Heuristic |
| T4 | canonical 数量与形态 | 数页面里 rel=canonical 的标签数，查是否绝对 URL、是否带 fragment、host 与协议是否与本页一致。 | 3 分：恰好一个，绝对 URL，无 fragment；2 分：恰好一个但是相对路径；1 分：恰好一个但带 fragment 或跨了协议；0 分：0 个，或 2 个以上 | Official |
| T5 | canonical 指向的地址 200 直达 | 对 canonical 目标发不跟随重定向的 HEAD 请求。 | 3 分：200 直达；2 分：一次 301 到 200；1 分：多跳重定向；0 分：404 或 5xx | Official |
| T6 | 四种写法归一 | 对 http/https 乘带不带 www 四个入口分别请求，看最终落点与 canonical 是不是同一个地址。取不到的入口记未观察，不算失败。 | 3 分：四个入口全部归到同一个地址；2 分：三个归一，一个未观察；1 分：有两个不同的落点；0 分：四个入口落到三个以上不同的地址 | Official |
| T7 | JSON-LD 语法能解析 | 对每个 application/ld+json 块跑 json.loads，统计坏块数。 | 3 分：有 JSON-LD 且全部能解析；2 分：有多个块，坏了 1 个；1 分：有多个块，坏了 2 个以上；0 分：有 JSON-LD 但一个都解析不了；或页面完全没有 JSON-LD | Official |
| T8 | JSON-LD 类型对得上这一页 | 取全部 @type，判断是否含至少一个页面级类型（SoftwareApplication / WebApplication / Product / Article / FAQPage / HowTo / BlogPosting / Course / Recipe 等），而不是只有站级类型（Organization / WebSite / BreadcrumbList）。 | 3 分：有页面级类型且有站级类型；2 分：只有页面级类型；1 分：只有站级类型；0 分：有 JSON-LD 但没有可识别的 @type | Official |
| T9 | JSON-LD 写的和页面上看得到的一致 | 取 JSON-LD 里的 price、ratingValue、reviewCount、name 等可见字段值，在页面正文里搜同一个值。另单独标记自评自打分（页面自身给自己写 aggregateRating）。 | 3 分：抽到的字段值在正文里都能找到；2 分：有 1 个字段对不上；1 分：有 2 个以上对不上；0 分：存在自评自打分的 aggregateRating | Official |
| C1 | H1 存在且唯一 | 数初始 HTML 里非空 h1 标签的个数（不按文本去重，两个一样的也算两个）。 | 3 分：恰好 1 个；2 分：多于 1 个；0 分：一个都没有 | Heuristic |
| C2 | 首屏 50 词直接给答案 | 取正文前 50 词，① 数其中落在 title 与 meta description 实义词集合里的词；② 算其中有多少词来自 header/nav 的导航文本。 | 3 分：实义词命中 ≥2 且导航词占比 <30%；2 分：实义词命中 ≥2 但导航词占比 30% 到 60%；1 分：实义词命中 1，或导航词占比 >60%；0 分：实义词命中 0 | Heuristic |
| C3 | 可提取证据密度 | 按块统计：含可提取证据的块 / 总块数。可提取证据 = 带单位的数值、可归属引语、带来源链接的断言、明确的上下界或区间。用占比不用每百词，理由同 W1。 | 3 分：占比 ≥30%；2 分：≥15%；1 分：> 0 但不足 15%；0 分：一个都没有 | Research |
| C4 | 无营销腔 | 在正文里搜营销套话（#1 / best ever / amazing / world's best / free forever / revolutionary / 业界领先 / 遥遥领先 / 一键搞定 之类），命中就把原句抄出来。 | 3 分：0 处；2 分：1 处；1 分：2 到 3 处；0 分：4 处以上 | Research |
| K1 | 一页一主词 | 取 sitemap 里的页面，两两算 title 与 H1 的实义词重叠度（Jaccard），列出重叠 ≥0.6 的页面对。只在拿到 ≥3 个页面时才判定，否则记未观察。 | 3 分：没有重叠 ≥0.6 的页面对；2 分：有 1 对；1 分：有 2 到 3 对；0 分：有 4 对以上 | Heuristic |
| K2 | 四处一致 | 取 title、H1、URL 路径、正文第一句四处的实义词集合，算两两交集里是否存在至少一个共同的主词。 | 3 分：四处都含同一个主词；2 分：三处含；1 分：两处含；0 分：四处对不上同一个词 | Heuristic |
| I1 | title 长度与全站唯一 | 本页 title 字符数（CJK 按 2 计），并在抓到的多页之间查完全相同的 title。 | 3 分：长度在 15 到 60 之间且全站唯一；2 分：长度越界但唯一；1 分：与另外 1 页重复；0 分：与 2 页以上重复，或没有 title | Heuristic |
| I2 | 语言标记 | 查 html 标签的 lang 属性：存在、用连字符不用下划线、与 URL 里的语言段一致；RTL 语言（ar/he/fa/ur）另查 dir=rtl。 | 3 分：全部满足；2 分：有 lang 但与 URL 语言段对不上；1 分：写成了下划线（zh_CN）；0 分：没有 lang | Official |
| I3 | hreflang 自指与互指 | 取页面 hreflang 集合，查是否包含指向自己的那一条、是否有 x-default。只在页面存在 hreflang 或 URL 含语言段时判定，单语言站记未观察。 | 3 分：有自指且有 x-default；2 分：有自指但没有 x-default；1 分：有 hreflang 但没有自指；0 分：多语言站但完全没有 hreflang | Official |
<!-- RUBRIC-TABLE:audit END -->

## 四条硬纪律

1. **抓不到的标「未观察」，永不折算成 0。**否则你会拿到一份把自己站说得一无是处的报告，然后照着乱改。
   报告里未观察的项不进分母。
2. **403 不等于网站下线。**独立开发者的站大量挂 CDN 防护。被拦时动作指向 CDN 放行 UA，
   不指向部署。判错方向会让你查一整天部署。
3. **robots.txt 取不到时，报告里一个字都不许出现「去改 robots」。**没观察到就不给动作，
   否则给出的验证命令永远不会变绿。robots.txt 返回 404 是正常状态，等于全放行，不扣分。
4. **整份报告只支撑一个动作。**多个门槛同时未过时，抓取类永远排在内容类前面：
   内容拿不到时，改文案的收益是零。

## 每条判据都带出处

报告里每一项都标了出处等级，读的人一眼知道这条凭什么：

| 等级 | 意思 |
|---|---|
| Official | 有平台或标准的公开文档明写，数字直接来自出处 |
| Research | 有公开研究或公开基准的实测支撑 |
| Derived | 阈值由本次跑到的对照组现算，不是预设值 |
| Heuristic | 本套件自定的经验值，没有公开出处，**不冒充平台规则** |

机制层的事实台账在 `../_shared/references.md`，每条带核实日期与出处。本文件不复述结论，只指过去。

## 文件

| 路径 | 作用 |
|---|---|
| `SKILL.md` | 本文件 |
| `scripts/audit.py` | 采集观察证据、调共享引擎打分、产报告。判据一条都不在这里 |

共享地基（与本 skill 目录同级，三个 skill 共用，必须整个 `skills/` 一起拷）：

| 路径 | 作用 |
|---|---|
| `../_shared/fetch.py` | 页面事实的唯一提取口，含 ok / blocked / dead / unknown 四分类 |
| `../_shared/robots.py` | robots 取与最长匹配判定，四档 bot 分档，404 判全放行 |
| `../_shared/sitemap.py` | sitemap 取、index 递归、抽样实测 |
| `../_shared/rubric.json` | 机械检查项的单一真相源 |
| `../_shared/rubric_check.py` | 机械分引擎，判据全部来自 rubric.json |
| `../_shared/references.md` | 机制层事实台账 |
| `../_shared/report.html` | 报告基底 |

## 自检

```bash
python3 <repo>/evals/check.py                                  # 靶站与纪律回归全绿
python3 ../_shared/rubric_check.py --selfcheck                 # 判据与实现一一对应
python3 ../_shared/rubric_check.py --check-doc SKILL.md        # 本文件的表与 rubric.json 同步
python3 <repo>/evals/check_index.py                            # 本文件列的文件真实存在
```

## 已知边界（用之前先知道）

- **不跑 JS。**爬虫看到什么，它就看到什么。纯前端渲染的站会在 G3 上判失败，那是真实观察，不是误判。
- **跨页判据要够多的页才成立。**K1 一页一主词需要至少 3 个页面，拿不到就记未观察，不硬判。
- **sitemap index 只展开前 3 个子文件。**大站的结论只覆盖被展开的部分，报告里会标出来。
- **百分比只用来排序，不是及格证书。**判据是「哪一项没过」，不是「多少分及格」。
- **它查不出内容好不好。**机械层只能查到结构和事实密度。写得好不好，最终要人读。
