<!-- EXPECT: W6 -->
<!-- WHY: 只犯一种错：一张图一个视频都没有。W8 应降到 2 分但仍通过。 -->
# 依恋类型测试要多久

```html
<section>
<h2>依恋类型测试要多久</h2>
<p>这份测试有 36 道题，多数人 8 到 12 分钟做完。题目来自 1998 年发表的 ECR 量表，
共 36 项，采用 7 点计分（<a href="https://doi.org/10.1037/ecr-1998">来源：ECR 原始量表说明</a>）。</p>
<p>题量和时间的关系是线性的：题目每减少 12 道，平均用时下降约 3 分钟。我们在 2026 年 7 月
对 1200 名用户计时，中位数为 9.4 分钟，第 90 百分位为 14 分钟
（<a href="https://example-source.test/timing">来源：本站 2026 年 7 月计时数据</a>）。</p>
<p>结果页会给出四种类型的得分。四种类型的划分沿用同一份量表，不做自定义改动。</p>
<p>想先看题目样例，见<a href="/sample-questions">样题页</a>；想直接开始，见<a href="/start">测试入口</a>，
也可以先读<a href="/scoring">计分说明</a>。</p>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question",
"name":"依恋类型测试要多久","acceptedAnswer":{"@type":"Answer","text":"36 道题，多数人 8 到 12 分钟完成，中位数 9.4 分钟。"}}]}
</script>
</section>
```

## 验证

```bash
curl -s https://example.test/how-long | grep -c "9.4 分钟"
```

## 待核

- [待核] 1200 这个样本量要你自己核对后台导出的数字
