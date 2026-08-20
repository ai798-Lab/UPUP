# 真跑产物

这里放的是**在真实站点上跑出来的**产物，不是构造的样例。

纪律第一条是「没在真实站点跑过的不发」，这个目录就是那条纪律的证据。

| 产物 | 跑的是什么 | 跑的日期 |
|---|---|---|
| `randomhub-2026-08-20/` | `site-audit` 对 randomhub.io | 2026-08-20 |
| `mesonar-2026-08-20/` | `site-audit` 对 mesonar.com | 2026-08-20 |
| `teardown-randomhub-mesonar-2026-08-20.json` | `rival-teardown` 拆这两家 | 2026-08-20 |

`audit.html` 直接用浏览器打开就能看。

## 这两次跑出来的东西说明了什么

**randomhub.io**：91.1 分，唯一失分是可提取证据密度（49 个段落里只有 1 个含具体数字）。
这是工具站首页的典型形态，判定属实。

**mesonar.com**：77.8 分，失分四项，其中三项当场用 curl 复现过：

```bash
curl -s https://mesonar.com | grep -c '<h1'          # 0，页面确实没有 H1
curl -s https://mesonar.com | grep -o '"@type":"[^"]*"' | sort -u
# 只有 ImageObject / Organization / WebSite，确实没有页面级类型
for v in http://mesonar.com https://mesonar.com http://www.mesonar.com https://www.mesonar.com; do
  curl -so /dev/null -w "$v -> %{url_effective}\n" -L $v
done
# www 与非 www 各自停在自己的域名上，确实没有归一
```

## 这个目录也记录了一次真实的误报

第一次跑 randomhub.io 时，四写法归一那一项判了失分，但用它自己给出的验证命令跑出来是全对的：
四个入口都落到 `https://randomhub.io/`。

原因是尾部斜杠没做归一化，`https://randomhub.io` 与 `https://randomhub.io/` 被当成两个落点。

修法是给引擎加 URL 规范化，并在 `evals/check.py` 里钉了一条回归，
断言「四个入口只差尾斜杠与大小写时判为已归一」。

**留着这段是因为它说明了为什么每条动作都必须配一条可复现的验证命令**：
不跑那一步，这个误报会直接进产品，用户照着一个本来就没问题的项改一整天。
