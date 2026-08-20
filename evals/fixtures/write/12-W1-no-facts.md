<!-- EXPECT: W1 -->
<!-- WHY: 只犯一种错：全篇没有一个带单位的数字，事实密度为 0。 -->
# 依恋类型测试要多久

```html
<section>
<h2>依恋类型测试要多久</h2>
<p>这份测试题目不多，多数人很快就能做完。题目来自经典的 ECR 量表，采用多点计分（<a href="https://doi.org/10.1037/ecr-1998">来源：ECR 原始量表说明</a>）。</p>
<p>题量和时间大致成正比：题目变少，平均用时也会跟着下降。我们对不少用户计时，多数人用时都在可接受范围内
（<a href="https://example-source.test/timing">来源：本站 2026 年 7 月计时数据</a>）。</p>
<p>结果页会给出四种类型的得分。四种类型的划分沿用同一份量表，不做自定义改动。</p>
<figure>
  <img src="/img/ecr-timing.png" alt="用户完成测试的用时分布">
  <figcaption>用时分布。横轴为分钟，纵轴为人数。</figcaption>
</figure>
<p>想先看题目样例，见<a href="/sample-questions">样题页</a>；想直接开始，见<a href="/start">测试入口</a>，
也可以先读<a href="/scoring">计分说明</a>。</p>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question",
"name":"依恋类型测试要多久","acceptedAnswer":{"@type":"Answer","text":"题目不多，多数人很快能做完。"}}]}
</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"ImageObject","name":"用时分布图",
"description":"用户完成测试的用时分布","contentUrl":"/img/ecr-timing.png","uploadDate":"2026-07-31"}
</script>
</section>
```

## 验证

```bash
curl -s https://example.test/how-long | grep -c "用时"
```

## 待核

- [待核] 样本量要你自己核对后台导出的数字
