# meta-write 招式库

机械闸只判「有没有写空」。真正决定这两行字好不好的，是下面这些，机器判不了。

## 通用四条

1. **主词放前面。**结果页从尾部截断，放后面的就是被切掉的那个。
2. **title 60 以内，description 155 以内**（CJK 按 2 计）。超了不是判死刑，但钩子必须落在前半段。
3. **description 不复述 title。**它是第二次机会，用来给点击理由，不是把标题再说一遍。
4. **每页都不一样。**全站一套复制粘贴的 description，等于没写。批量模板要把主词写进变量。

## 三种页型各自要回答什么

来的人带着完全不同的问题，写法也就不同。

### 首页 · 让一个完全没听说过你的人 3 秒内知道你是干什么的

**必须出现：品类词 + 人群或用途。**

结构上多数是同一个形状：`品牌名，冒号或竖线，品类词，再加一个具体的东西`（承诺 / 差异点 / 人群）。

三个真实写法，字符数是实测的：

```
Taplio    (50)  Taplio | AI tool to grow on LinkedIn in 10 min/day
                品类词加一个具体承诺「每天 10 分钟」

Postiz    (59)  Postiz: The All-in-One agentic social media scheduling tool
                品类词写死，加一个差异点

Supergrow (64)  Supergrow: LinkedIn Content Platform for Teams & Individuals
                品类词加人群，一眼知道给谁用
```

**首页最常见的坑是品牌调性压过品类。**有个测评站首页写的是 `Sonar your self`，很有格调，
但拿工具去读它的首页，只能猜出品类是「测试」，猜不出是性格测试。
**AI 读你的首页时面临一模一样的问题。**

自检：把 title 加 description 念给一个完全不了解你产品的人听，他能不能说出你是干什么的。

### 工具页 · 让人马上开始用

**必须出现：功能动词 + 说清输入或产出。**

和首页不同，**这里不需要品牌名**。用户搜什么，这页就叫什么。

```
T (60)  Free AI Caption Generator: Social Media Captions in Seconds
D (130) Generate on-brand social media captions instantly with our free
        AI caption generator. For Instagram, Facebook, LinkedIn, and more.
```

看三处：
- title 里没有品牌名，全是用户会搜的词：free、AI caption generator、social media
- **免费的话就把「免费」写进 title**，这个词本身就是点击率
- description 末尾列出支持的平台，**因为用户会搜「Instagram caption generator」这种带平台名的词**

网址也直接用功能词（`/caption-generator`），不要用 `/tool-1`。

### 定价页 · 让人掏钱，或者至少知道自己该选哪档

**必须出现：价格数字 + 币种。**

title 就是 `品牌名 + Pricing`，不要玩花的。搜这个词的人目的极明确。

description 里直接写价格。写「免费开始，Pro 每月 9 美元」比写
「灵活的定价方案满足不同需求」有用一百倍，**用户在结果页就想知道多少钱**。

## 钩子写什么

description 里放具体信息，四类任选两类以上：

| 类别 | 例子 |
|---|---|
| 带单位的数值 | 30 秒出结果 · 每天 3 次 · 10 min/day |
| 价格或币种 | $9/mo · 免费开始 |
| 免费程度 | 免费 · 不用注册 · no credit card |
| 产出物或支持范围 | 导出 MP4 和 GIF · 支持 Instagram、LinkedIn |

**不要写**「行业领先」「专业团队」「值得信赖」「灵活的解决方案」。
这类词占的是本可以放事实的位置，而且机械闸的 C4 会直接抓出来。

## 写完之后

机械闸过了只说明没写空。最后自己答两问：

1. **这两行字换成竞品的名字，还成立吗？**成立的话，说明你写的是品类通用话术，不是你这一页。
2. **用户看到这一条，知道点进去会发生什么吗？**答不上来，就是钩子还不够具体。
