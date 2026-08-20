# <目标问题原样写在这里>

> 目标页：<这段内容要贴到哪一页>
> 对照页：<winners.json 的路径>
> 本次通过线：<对照组事实密度中位数，或标明用的是回退值>

## 可上线内容块

下面这一块是要贴进页面的东西。JSON-LD 写在同一块里，不要留到以后再配。

```html
<section>
  <h2><这一页要回答的那个问题，原样写>< /h2>

  <!-- 第一段就给答案。前 50 词里要出现问题的主词（判据 WG1） -->
  <p>……结论一句话说完。带一个具体数字（<a href="https://…">来源：…</a>）。</p>

  <!-- 每段至少一个带单位的事实，分散写不要堆一段（判据 W1） -->
  <p>……机制或原因。数字后面挂来源，写之前先去来源页把数字复制出来（判据 W2 / W5）。</p>

  <!-- 能做成表就别写成段落，表格比段落好摘 -->
  <table>
    <tr><th>项</th><th>本产品</th><th>常见做法</th></tr>
    <tr><td>……</td><td>…… 36 项</td><td>…… 12 项</td></tr>
  </table>

  <!-- 配一张能独立说明问题的图。alt 写这张图在说明什么（判据 W6） -->
  <figure>
    <img src="/img/xxx.png" alt="<这张图在说明的那件事，带数字>">
    <figcaption>……这张图怎么读。</figcaption>
  </figure>

  <!-- 站内链到相关的两三页（判据 W9） -->
  <p>另见<a href="/xxx">……</a>、<a href="/yyy">……</a>。</p>

  <script type="application/ld+json">
  {"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question",
   "name":"<问题>","acceptedAnswer":{"@type":"Answer","text":"<答案，和正文一致>"}}]}
  </script>

  <script type="application/ld+json">
  {"@context":"https://schema.org","@type":"ImageObject","name":"<图名>",
   "description":"<这张图在说明什么>","contentUrl":"https://<域名>/img/xxx.png",
   "uploadDate":"<YYYY-MM-DD>"}
  </script>
</section>
```

## 每条主张挂的证据

| 主张 | 证据 | 出处 |
|---|---|---|
| …… | 对照页原句或自测数据 | <URL 或 winners.json 字段> |

## 验证

贴上去之后跑这个，看它变绿：

```bash
curl -s https://<你的域名>/<路径> | grep -c "<刚写进去的那个数字>"
```

## 待核

内容块里每一处 [待核] 标记，这里都要有一条对应的：

- [待核] <要核什么，去哪核>

## 两个人工确认

1. 这段里有没有一句是别处抄不到的？
   凭什么这么答：……
   答：

2. AI 真会把这段整段摘走吗？把最关键那段单独复制出来能不能独立回答问题？
   凭什么这么答：……
   答：
