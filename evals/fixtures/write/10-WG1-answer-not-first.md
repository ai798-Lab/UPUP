<!-- EXPECT: WG1 -->
<!-- WHY: 只犯一种错：前 50 词全是背景铺垫，不出现目标问题的主词。 -->
# 依恋类型测试要多久

```html
<section>
<p>很久以前，心理学家们围坐在一起，讨论人与人之间的关系应该如何被理解和归类，这个话题在学术圈里被反复争论了几十年，不同学派各执一词，谁也说服不了谁，直到后来量表这种工具出现，情况才开始慢慢发生一些变化，研究者终于有了可以互相比较的尺子，于是这件事才算有了一个可以往下走的起点。</p>
<p>这份测试有 36 道题，多数人 8 到 12 分钟做完。题目来自 1998 年发表的 ECR 量表，
共 36 项，采用 7 点计分（<a href="https://doi.org/10.1037/ecr-1998">来源：ECR 原始量表说明</a>）。</p>
<p>题量和时间的关系是线性的：题目每减少 12 道，平均用时下降约 3 分钟。我们在 2026 年 7 月
对 1200 名用户计时，中位数为 9.4 分钟，第 90 百分位为 14 分钟
（<a href="https://example-source.test/timing">来源：本站 2026 年 7 月计时数据</a>）。</p>
<p>结果页会给出四种类型的得分。四种类型的划分沿用同一份量表，不做自定义改动。</p>
<figure>
  <img src="/img/ecr-timing.png" alt="1200 名用户完成 36 题测试的用时分布，中位数 9.4 分钟">
  <figcaption>2026 年 7 月的用时分布。横轴为分钟，纵轴为人数。</figcaption>
</figure>
<p>想先看题目样例，见<a href="/sample-questions">样题页</a>；想直接开始，见<a href="/start">测试入口</a>，
也可以先读<a href="/scoring">计分说明</a>。</p>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question",
"name":"依恋类型测试要多久","acceptedAnswer":{"@type":"Answer","text":"36 道题，多数人 8 到 12 分钟完成，中位数 9.4 分钟。"}}]}
</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"ImageObject","name":"用时分布图",
"description":"1200 名用户完成 36 题测试的用时分布","contentUrl":"/img/ecr-timing.png","uploadDate":"2026-07-31"}
</script>
</section>
```

## 验证

```bash
curl -s https://example.test/how-long | grep -c "9.4 分钟"
```

## 待核

- [待核] 1200 这个样本量要你自己核对后台导出的数字
