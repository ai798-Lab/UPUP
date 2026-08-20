# 免费收录入口名单

> **本次核实日期 2026-08-20。**核实方式：对每个地址发一次普通 HTTP 请求，记录状态码。
>
> **这份名单只验证了「域名当天可达」，没有逐个走完提交流程，也没有验证提交后多久被收录。**
> 判断值不值得做那一栏是编辑判断，不是实测排名。用之前知道这个边界。

## 怎么用

从上往下做。**做完前两个再看后面的**，它们是唯二能给你真实数据的地方，其余都是单向提交。

不要一天之内把十个都提交一遍。多数入口对「刚上线、内容为零」的站没有耐心，
先有两三篇能站住的内容再去提交，通过率完全不同。

## 名单

| 入口 | 值不值得 | 状态 | 为什么 |
|---|---|---|---|
| [Google Search Console](https://search.google.com/search-console/about) | **必做** | 200 | 提交 sitemap，看真实收录与查询词。需要 Google 账号并验证域名所有权 |
| [Bing Webmaster Tools](https://www.bing.com/webmasters/about) | **必做** | 200 | Bing 与 Copilot 侧的入口。可从 GSC 一键导入，省一次域名验证 |
| [IndexNow](https://www.indexnow.org/) | 值得 | 200 | 推送新页地址给 Bing 与 Yandex。一个 HTTP 请求的事，不用注册 |
| [AlternativeTo](https://alternativeto.net/) | 值得 | 403 | 对比型站点，被 AI 引用的频率不低。收录后你会出现在竞品的替代品列表里 |
| [Product Hunt](https://www.producthunt.com/) | 值得 | 403 | 发布日流量集中，页面本身权重高。要挑日子、备素材，不是随手提交 |
| [Hacker News](https://news.ycombinator.com/showhn.html) | 值得 | 200 | Show HN。成不成看运气与东西本身，成本只有一条链接 |
| [Indie Hackers](https://www.indiehackers.com/) | 值得 | 200 | 同类人群密度高。适合长期发进展，不适合一次性提交完就走 |
| [BetaList](https://betalist.com/) | 看情况 | 200 | 早期产品目录。免费排队慢，付费插队 |
| [SaaSHub](https://www.saashub.com/) | 看情况 | 200 | 与 AlternativeTo 同类，体量小一些 |
| [Awesome 类仓库](https://github.com/topics/awesome) | 看情况 | 200 | 找你所在领域的 awesome 列表提 PR。质量参差，挑维护活跃的 |

## 那两个 403 是什么意思

`AlternativeTo` 与 `Product Hunt` 对脚本发出的请求返回 403，**但站是活的，浏览器能正常打开**。
这是它们的防护规则在挡自动请求，不是站点下线。

这正好是本套件贯穿始终的那条判据：**403 是被拦，不是死。**
site-audit 遇到 403 时给的动作是「去 CDN 放行 UA」，不是「查你的部署」。

## 不在这份名单里的东西

- **付费收录目录。**花钱买一条外链这件事，价值波动太大，这里不推荐也不评价。
- **批量提交工具。**一次提交到 200 个目录的那类服务，多数目录本身没有真实流量。
- **自动化提交脚本。**UPUP 不做这件事：价值在名单本身，不在自动化。
  十个入口，人手做一遍两小时，做完就完了，不值得为它写代码并长期维护。

## 复核

这份名单会过期。重新核一遍很便宜：

```bash
python3 -c "
import sys; sys.path.insert(0, 'skills/_shared')
import fetch as F
for u in ['https://search.google.com/search-console/about',
          'https://www.bing.com/webmasters/about',
          'https://www.indexnow.org/']:
    p = F.fetch(u, timeout=20); print(p['status'], p['reach'], u)
"
```
