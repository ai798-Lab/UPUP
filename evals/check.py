#!/usr/bin/env python3
# check.py: 反面靶站回归。断言每份靶子触发的项与它页头声明的一个不少、一个不多。
#
# 为什么要「一个不多」：只断言「该触发的触发了」时，一个把所有项都判失败的坏引擎也能全绿。
# 靶站从 00-pass-baseline.md 派生，每份只做一处变异，所以「多触发」就是真的误伤。
#
# 来源类判据（W3 来源可达 / W5 数字可回溯）注入 stub 取源函数，让回归离线可跑：
# 依赖真实网络的测试会因为对方站点抽风而红，那种红没有信息量。
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.join(os.path.dirname(HERE), "skills", "_shared")
sys.path.insert(0, SHARED)

import rubric_check as R  # noqa: E402

FIX = os.path.join(HERE, "fixtures", "write")

# stub 语料。数字要和 baseline 里的对得上，否则 W5 会在正面对照上误红。
SOURCES = {
    "https://doi.org/10.1037/ecr-1998": {
        "ok": True, "status": 200, "reach": "ok",
        "text": "ECR 量表说明。本量表共 36 项，采用 7 点计分，1998 年发表。"},
    "https://example-source.test/timing": {
        "ok": True, "status": 200, "reach": "ok",
        "text": "2026 年 7 月计时数据：样本 1200 名用户，中位数 9.4 分钟，第 90 百分位 14 分钟。"},
    "https://example-source.test/mismatch": {
        "ok": True, "status": 200, "reach": "ok",
        "text": "这一页讲的是别的事情，没有任何用时统计，也没有样本量。"},
    "https://doi.org/10.1037/dead": {"ok": False, "status": 404, "reach": "dead", "text": ""},
    "https://example-source.test/dead2": {"ok": False, "status": 404, "reach": "dead", "text": ""},
    "https://weak-aggregator.test/ecr-copy": {
        "ok": True, "status": 200, "reach": "ok",
        "text": "转载：该量表共 36 项，7 点计分。"},
    "https://weak-aggregator.test/timing-copy": {
        "ok": True, "status": 200, "reach": "ok",
        "text": "转载：中位数 9.4 分钟，样本 1200 人，第 90 百分位 14 分钟。"},
}


def stub_fetch(url, timeout=12):
    if url in SOURCES:
        return SOURCES[url]
    return {"ok": False, "status": None, "reach": "unknown",
            "text": "", "note": "stub 里没有登记这个地址"}


QUESTION = "依恋类型测试要多久"

_ok, _bad = [], []


def ok(m):
    _ok.append(m)
    print("  ok   %s" % m)


def bad(m):
    _bad.append(m)
    print("  FAIL %s" % m)


def failing_ids(res):
    """本次真正失分的项。未观察不算失分，那是纪律，不是漏判。"""
    out = []
    for i in res["items"]:
        if not i["observed"]:
            continue
        if i["kind"] == "gate" and not i["pass"]:
            out.append(i["id"])
        elif i["kind"] == "score" and not i["pass"]:
            out.append(i["id"])
    return sorted(out)


def run_one(path):
    txt = open(path, encoding="utf-8").read()
    m = re.search(r'<!--\s*EXPECT:\s*(.*?)\s*-->', txt)
    if not m:
        bad("%s 缺 EXPECT 声明" % os.path.basename(path))
        return
    want = sorted([x for x in re.split(r'[,\s]+', m.group(1)) if x and x != "none"])
    res = R.score_write(txt, question=QUESTION, fetch_source=stub_fetch)
    got = failing_ids(res)
    name = os.path.basename(path)
    if got == want:
        ok("%s 触发 %s" % (name, got or "无"))
        return
    missing = [x for x in want if x not in got]
    extra = [x for x in got if x not in want]
    detail = []
    if missing:
        detail.append("该触发没触发：%s" % missing)
    if extra:
        detail.append("误伤：%s" % extra)
        for i in res["items"]:
            if i["id"] in extra:
                detail.append("    %s → %s" % (i["id"], i["detail"]))
    bad("%s %s" % (name, "；".join(detail)))


def run_unobserved_semantics():
    """13-W2-no-source 那份把来源全删了。W3/W4/W5 必须是未观察，不许判成 0 分。
    这一条单独测，因为「未观察折算成 0」是这套东西最容易悄悄退化的地方。"""
    p = os.path.join(FIX, "13-W2-no-source.md")
    res = R.score_write(open(p, encoding="utf-8").read(), question=QUESTION, fetch_source=stub_fetch)
    by = {i["id"]: i for i in res["items"]}
    for iid in ("W3", "W4", "W5"):
        if by[iid]["observed"]:
            bad("13-W2-no-source：%s 应记未观察，实际判了 %s 分" % (iid, by[iid]["score"]))
        else:
            ok("13-W2-no-source：%s 记未观察（%s）" % (iid, by[iid]["reason"][:28]))
    if res["score"]["full"] and any(i["id"] in ("W3", "W4", "W5")
                                    for i in res["items"] if i["observed"]):
        bad("未观察的项进了分母")


def run_offline_not_pass():
    """离线跑闸时 W3 必须记未观察，不许判成「来源全部可达」。
    没去请求就说可达，是把未观察偷换成通过，性质和折算成 0 一样坏。"""
    def dead_air(url, timeout=12):
        return {"ok": False, "status": None, "reach": "unknown", "text": ""}
    p = os.path.join(FIX, "00-pass-baseline.md")
    res = R.score_write(open(p, encoding="utf-8").read(), question=QUESTION, fetch_source=dead_air)
    w3 = [i for i in res["items"] if i["id"] == "W3"][0]
    if not w3["observed"]:
        ok("一条来源都没请求到时 W3 记未观察，不判成全部可达")
    else:
        bad("W3 在没请求到任何来源的情况下判了 %s 分" % w3["score"])


def run_machine_locked():
    """每项都必须带 machine_locked。模型改分的口子从这里堵死。"""
    p = os.path.join(FIX, "00-pass-baseline.md")
    res = R.score_write(open(p, encoding="utf-8").read(), question=QUESTION, fetch_source=stub_fetch)
    if all(i.get("machine_locked") for i in res["items"]) and res["machine_locked"]:
        ok("每项都带 machine_locked")
    else:
        bad("有项没带 machine_locked")


def run_rubric_selfcheck():
    r = R.selfcheck()
    for lane, v in r.items():
        if v["missing"] or v["extra"]:
            bad("%s lane 判据与实现对不上：声明了没实现 %s；实现了没声明 %s"
                % (lane, v["missing"], v["extra"]))
        else:
            ok("%s lane 判据与实现一一对应（%d 项）" % (lane, v["declared"]))


def run_self_host_is_first_party():
    """引自己站的自测数据算一手。这是独立开发者最常见的引用形态，
    判成二手会逼他们去找一个其实没有的外部出处。"""
    p = os.path.join(FIX, "00-pass-baseline.md")
    txt = open(p, encoding="utf-8").read()
    a = R.score_write(txt, question=QUESTION, fetch_source=stub_fetch)
    b = R.score_write(txt, question=QUESTION, fetch_source=stub_fetch,
                      self_host="example-source.test")
    def tier_of(res, host_part):
        w4 = [i for i in res["items"] if i["id"] == "W4"][0]
        tiers = w4["evidence"][0]["tiers"]
        for u, t in tiers.items():
            if host_part in u:
                return t
        return None
    before, after = tier_of(a, "example-source.test"), tier_of(b, "example-source.test")
    if before == "second" and after == "first":
        ok("self_host 传入后自测来源从二手改判一手")
    else:
        bad("self_host 没生效：传入前 %s，传入后 %s（应为 second → first）" % (before, after))


def run_threshold_honesty():
    """没给对照组时，W1 必须在报告里标明用的是回退值，不许假装是实测线。"""
    p = os.path.join(FIX, "00-pass-baseline.md")
    res = R.score_write(open(p, encoding="utf-8").read(), question=QUESTION, fetch_source=stub_fetch)
    w1 = [i for i in res["items"] if i["id"] == "W1"][0]
    if "回退" in w1["detail"]:
        ok("W1 标明了这次用的是回退值")
    else:
        bad("W1 没标明阈值来源")
    res2 = R.score_write(open(p, encoding="utf-8").read(), question=QUESTION,
                         fetch_source=stub_fetch, comparables=[0.2, 0.3, 0.5])
    w1b = [i for i in res2["items"] if i["id"] == "W1"][0]
    if "对照组" in w1b["detail"]:
        ok("给了对照组时 W1 改用对照组中位数")
    else:
        bad("给了对照组，W1 仍在用回退值")




# ── audit lane ─────────────────────────────────────────────────────────
AFIX = os.path.join(HERE, "fixtures", "audit")
BASE_URL = "https://example.test/attachment-style-test"


def audit_evidence(html, url=BASE_URL, **over):
    """构造一份「站级全好」的证据，页面部分用真实 HTML。

    站级项（robots / sitemap / 抽样 / 四写法）在靶站 HTML 里表达不出来，
    所以用覆盖参数直接构造。这样每个站级判据也能被单独打靶，不用真的去架一个坏站。
    """
    import fetch as FF
    page = {"reach": "ok", "status": 200, "final_url": url, "html": html,
            "headers": {}, "error": None}
    ev = {
        "url": url,
        "page": page,
        "facts": FF.facts(html, base_url=url),
        "robots": {"observed": True, "no_robots_file": False, "reason": None,
                   "sitemap_lines": ["https://example.test/sitemap.xml"],
                   "classes": {c: {a: {"allowed": True, "group": "wildcard", "rule": "Allow: /"}
                                   for a in ags}
                               for c, ags in __import__("robots").BOTS.items()}},
        "noindex": [],
        "cdn_blocked": [],
        "sitemap": {"observed": True, "source": "https://example.test/sitemap.xml",
                    "entries": [{"loc": "https://example.test/p%d" % i, "lastmod": "2026-08-%02d" % (i + 1)}
                                for i in range(6)],
                    "issues": [], "tried": []},
        "sample": {"observed": True, "sampled": 5, "dead": [], "redirect": [], "blocked": [],
                   "checked": []},
        "canonical_target": {"status": 200, "hops": 0, "error": None},
        "variants": {k: {"final": url} for k in
                     ("http://example.test", "http://www.example.test",
                      "https://example.test", "https://www.example.test")},
        "peers": [{"url": BASE_URL, "title": "Attachment Style Test: 36 Questions, 9 Minutes",
                   "h1": ["Attachment Style Test"]},
                  {"url": "https://example.test/scoring", "title": "How Scoring Works",
                   "h1": ["Scoring Guide"]},
                  {"url": "https://example.test/sample-questions", "title": "Sample Questions",
                   "h1": ["Sample Questions"]},
                  {"url": "https://example.test/start", "title": "Start The Test",
                   "h1": ["Start"]}],
    }
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(ev.get(k), dict):
            ev[k] = dict(ev[k], **v)
        else:
            ev[k] = v
    if "html" in (over.get("page") or {}):
        ev["facts"] = FF.facts(over["page"]["html"], base_url=url)
    return ev


def run_audit_fixture(path):
    html = open(path, encoding="utf-8").read()
    m = re.search(r'<!--\s*EXPECT:\s*(.*?)\s*-->', html)
    want = sorted([x for x in re.split(r'[,\s]+', m.group(1)) if x and x != "none"])
    res = R.score_audit(audit_evidence(html))
    got = failing_ids(res)
    name = os.path.basename(path)
    if got == want:
        ok("%s 触发 %s" % (name, got or "无"))
        return
    missing = [x for x in want if x not in got]
    extra = [x for x in got if x not in want]
    d = []
    if missing:
        d.append("该触发没触发：%s" % missing)
    if extra:
        d.append("误伤：%s" % extra)
        for i in res["items"]:
            if i["id"] in extra:
                d.append("    %s → %s" % (i["id"], i["detail"]))
    bad("%s %s" % (name, "；".join(d)))


def item_of(res, iid):
    return [i for i in res["items"] if i["id"] == iid][0]


def run_site_level_cases():
    """站级判据的靶标。每条只动证据里的一处。"""
    baseline = open(os.path.join(AFIX, "00-pass-baseline.html"), encoding="utf-8").read()

    def case(label, checker, **over):
        res = R.score_audit(audit_evidence(baseline, **over))
        try:
            msg = checker(res)
        except Exception as e:
            bad("%s：判定时抛错 %s" % (label, e))
            return
        (ok if msg is True else bad)(label if msg is True else "%s：%s" % (label, msg))

    # G1：403 是被拦不是下线，动作要指向 CDN
    case("403 判成 blocked 而不是 dead，动作指向 CDN",
         lambda r: True if (item_of(r, "G1")["detail"].find("blocked") >= 0
                            and "CDN" in (item_of(r, "G1")["fix"] or "")
                            and "部署" not in (item_of(r, "G1")["fix"] or "")[:12])
         else "fix 是 %r" % item_of(r, "G1")["fix"],
         page={"reach": "blocked", "status": 403})

    # G1：连接层失败要记未观察
    case("连接层失败记未观察，不判死",
         lambda r: True if not item_of(r, "G1")["observed"] else "被判成了 %s" % item_of(r, "G1")["score"],
         page={"reach": "unknown", "status": None, "error": "timeout"})

    # G2：robots 取不到时必须未观察，且不给任何动作
    def g2_unobs(r):
        it = item_of(r, "G2")
        if it["observed"]:
            return "robots 未观察却判了分"
        if it["fix"]:
            return "未观察却给了动作：%r" % it["fix"]
        return True
    case("robots 取不到：未观察且不给改 robots 的动作", g2_unobs,
         robots={"observed": False, "classes": None,
                 "reason": "robots.txt 取不到（403），不判定，也不给改 robots 的动作"})

    # G2：只挡训练 bot 不算失败
    def only_training(ev_classes):
        c = {k: {a: {"allowed": True, "group": "w", "rule": "Allow: /"} for a in v}
             for k, v in __import__("robots").BOTS.items()}
        for a in c["training"]:
            c["training"][a] = {"allowed": False, "group": "explicit", "rule": "Disallow: /"}
        return c
    case("只挡训练 bot 不算 G2 失败（拦不拦是站主的选择）",
         lambda r: True if item_of(r, "G2")["pass"] else "被判成了失败",
         robots={"classes": only_training(None)})

    # G2：挡住 AI 实时取页要失败
    def block_ai_user(_):
        c = {k: {a: {"allowed": True, "group": "w", "rule": "Allow: /"} for a in v}
             for k, v in __import__("robots").BOTS.items()}
        for a in c["ai_user"]:
            c["ai_user"][a] = {"allowed": False, "group": "explicit", "rule": "Disallow: /"}
        return c
    case("挡住 AI 实时取页时 G2 失败",
         lambda r: True if not item_of(r, "G2")["pass"] else "没判失败",
         robots={"classes": block_ai_user(None)})

    # G2：响应头 noindex 要抓到，且动作指向响应头
    case("X-Robots-Tag: noindex 被抓到，动作指向响应头",
         lambda r: True if (not item_of(r, "G2")["pass"]
                            and "响应头" in (item_of(r, "G2")["fix"] or "")) else
         "fix 是 %r" % item_of(r, "G2")["fix"],
         noindex=[{"where": "HTTP 响应头 X-Robots-Tag", "value": "noindex", "fix": "x"}])

    # T1：软 404
    case("sitemap 软 404 判 1 分，不判成「有」",
         lambda r: True if item_of(r, "T1")["score"] == 1 else "判了 %s 分" % item_of(r, "T1")["score"],
         sitemap={"observed": False, "entries": None, "issues": [], "reason": "软 404",
                  "tried": [{"url": "https://example.test/sitemap.xml", "status": 200,
                             "usable": False, "why": "返回的是 HTML"}]})

    # T3：被拦不算死链
    case("抽样被防护拦住不算死链",
         lambda r: True if item_of(r, "T3")["score"] == 3 else
         "判了 %s 分：%s" % (item_of(r, "T3")["score"], item_of(r, "T3")["detail"]),
         sample={"observed": True, "sampled": 5, "dead": [], "redirect": [],
                 "blocked": [{"url": "https://example.test/p1", "status": 403}] * 3})

    # T3：真死链要罚
    case("抽样有 2 条死链判 0 分",
         lambda r: True if item_of(r, "T3")["score"] == 0 else "判了 %s 分" % item_of(r, "T3")["score"],
         sample={"observed": True, "sampled": 5, "redirect": [], "blocked": [],
                 "dead": [{"url": "https://example.test/p1", "status": 404},
                          {"url": "https://example.test/p2", "status": 404}]})

    # T5：canonical 指向死页
    case("canonical 指向 404 判 0 分",
         lambda r: True if item_of(r, "T5")["score"] == 0 else "判了 %s 分" % item_of(r, "T5")["score"],
         canonical_target={"status": 404, "hops": 0})

    # T5：canonical 目标取不到 → 未观察
    case("canonical 目标取不到记未观察",
         lambda r: True if not item_of(r, "T5")["observed"] else "判了分",
         canonical_target={"status": None, "error": "timeout"})

    # T6：尾斜杠不算不同落点。这条是真站上抓出来的误报，必须钉死
    case("四个入口只差尾斜杠与大小写时判为已归一",
         lambda r: True if item_of(r, "T6")["score"] == 3 else
         "判了 %s 分：%s" % (item_of(r, "T6")["score"], item_of(r, "T6")["detail"]),
         variants={"http://example.test": {"final": "https://example.test/attachment-style-test/"},
                   "http://www.example.test": {"final": "https://Example.test/attachment-style-test"},
                   "https://example.test": {"final": "https://example.test:443/attachment-style-test"},
                   "https://www.example.test": {"final": BASE_URL}})

    # T6：四写法不归一
    case("四个入口落到 3 个地址判 0 分",
         lambda r: True if item_of(r, "T6")["score"] == 0 else "判了 %s 分" % item_of(r, "T6")["score"],
         variants={"http://example.test": {"final": "https://example.test/a"},
                   "http://www.example.test": {"final": "https://www.example.test/a"},
                   "https://example.test": {"final": "https://example.test/b"},
                   "https://www.example.test": {"final": BASE_URL}})

    # T6：观察不到足够入口 → 未观察
    case("四写法只观察到 1 个入口时记未观察",
         lambda r: True if not item_of(r, "T6")["observed"] else "判了分",
         variants={"http://example.test": {"final": None}, "http://www.example.test": {"final": None},
                   "https://example.test": {"final": BASE_URL}, "https://www.example.test": {"final": None}})

    # K1：跨页抢词
    case("两页标题高度重叠时 K1 检测得到并扣一档（1 组重叠仍算通过，2 组以上才失分）",
         lambda r: True if item_of(r, "K1")["score"] == 2 and item_of(r, "K1")["evidence"]
         else "判了 %s 分，证据 %s" % (item_of(r, "K1")["score"], item_of(r, "K1")["evidence"]),
         peers=[{"url": BASE_URL, "title": "Attachment Style Test Free", "h1": ["Attachment Style Test"]},
                {"url": "https://example.test/attachment-test", "title": "Free Attachment Style Test",
                 "h1": ["Attachment Style Test"]},
                {"url": "https://example.test/scoring", "title": "How Scoring Works", "h1": ["Scoring"]},
                {"url": "https://example.test/start", "title": "Start The Test", "h1": ["Start"]}])

    # K1：页面数不够时不判
    case("只拿到 2 个页面时 K1 记未观察",
         lambda r: True if not item_of(r, "K1")["observed"] else "样本不足却判了分",
         peers=[{"url": BASE_URL, "title": "A", "h1": ["A"]},
                {"url": "https://example.test/b", "title": "B", "h1": ["B"]}])

    # I1：title 重复
    case("title 与两个页面重复时 I1 判 0 分",
         lambda r: True if item_of(r, "I1")["score"] == 0 else "判了 %s 分" % item_of(r, "I1")["score"],
         peers=[{"url": BASE_URL, "title": "Attachment Style Test: 36 Questions, 9 Minutes", "h1": []},
                {"url": "https://example.test/x", "title": "Attachment Style Test: 36 Questions, 9 Minutes", "h1": []},
                {"url": "https://example.test/y", "title": "Attachment Style Test: 36 Questions, 9 Minutes", "h1": []},
                {"url": "https://example.test/z", "title": "Other", "h1": []}])


def run_audit_unobserved_not_zero():
    """整站取不到时，未观察的项不许进分母。这是「不给站主一份全红报告」的底线。"""
    ev = audit_evidence("", page={"reach": "blocked", "status": 403, "html": ""})
    ev["facts"] = None
    ev["sitemap"] = {"observed": False, "entries": None, "issues": [], "reason": "取不到", "tried": []}
    ev["sample"] = {"observed": False, "reason": "没有可抽样的地址"}
    ev["robots"] = {"observed": False, "classes": None, "reason": "robots.txt 取不到（403）"}
    ev["peers"] = []          # 整站取不到时不可能有别的页面
    ev["canonical_target"] = {"status": None, "error": "整站取不到"}
    ev["variants"] = {k: {"final": None} for k in ev["variants"]}
    res = R.score_audit(ev)
    unobs = {u["id"] for u in res["unobserved"]}
    scored = {i["id"] for i in res["items"] if i["observed"] and i["kind"] == "score"}
    if unobs & scored:
        bad("同一项既记未观察又参与了计分：%s" % (unobs & scored))
    elif len(unobs) < 10:
        bad("整站抓不到时只有 %d 项记未观察，其余被折算了" % len(unobs))
    else:
        ok("整站抓不到时 %d 项记未观察，不折算成 0" % len(unobs))
    if res["score"]["full"] == 0:
        ok("未观察项不进分母（满分基数为 0，不产出一份全红报告）")
    else:
        bad("未观察项进了分母，满分基数 %s" % res["score"]["full"])



# ── meta lane ──────────────────────────────────────────────────────────
def run_meta_cases():
    """每条靶标只钉一项：改坏那一处，必须且只必须让对应判据掉下来。"""
    GOOD = dict(
        title="Free AI Caption Generator: Social Media Captions in Seconds",
        description=("Generate on-brand social media captions instantly with our free "
                     "AI caption generator. For Instagram, Facebook, LinkedIn, and more."),
        keyword="AI caption generator", page_type="tool")

    def case(label, checker, **over):
        kw = dict(GOOD)
        kw.update(over)
        res = R.score_meta(**kw)
        m = checker(res)
        (ok if m is True else bad)(label if m is True else "%s：%s" % (label, m))

    def it(res, iid):
        for i in res["items"]:
            if i["id"] == iid:
                return i
        return None

    # 基线必须全绿，否则后面每一条靶标都说明不了问题
    case("真实工具页做基线时 meta lane 判 PASS",
         lambda r: True if r["verdict"] == "PASS" else "verdict=%s 失分=%s" % (
             r["verdict"], r["below_floor"]))

    case("缺 description 时 MG1 门槛未过，判 REJECT",
         lambda r: True if (r["verdict"] == "REJECT" and "MG1" in r["failed_gates"])
         else "verdict=%s gates=%s" % (r["verdict"], r["failed_gates"]),
         description="")

    case("title 落在 60 到 70 时 M1 掉一档到 2",
         lambda r: True if it(r, "M1")["score"] == 2 else "M1=%s" % it(r, "M1")["score"],
         title="Free AI Caption Generator: Social Media Captions in Seconds Today")

    case("title 超过 70 时 M1 判 1，但仍不判 0",
         lambda r: True if it(r, "M1")["score"] == 1 else "M1=%s" % it(r, "M1")["score"],
         title="Free AI Caption Generator for Social Media Posts and Captions in Seconds Today")

    case("title 里没有主词时 M3 判 0",
         lambda r: True if it(r, "M3")["score"] == 0 else "M3=%s" % it(r, "M3")["score"],
         title="The Ultimate Toolkit for Modern Social Teams Everywhere")

    case("没给主词时 M3 记未观察，不折算成 0",
         lambda r: True if it(r, "M3")["observed"] is False and it(r, "M3")["score"] is None
         else "observed=%s score=%s" % (it(r, "M3")["observed"], it(r, "M3")["score"]),
         keyword="")

    case("description 复述 title 时 M4 判 0",
         lambda r: True if it(r, "M4")["score"] == 0 else "M4=%s" % it(r, "M4")["score"],
         description=("Free AI caption generator: social media captions in seconds, "
                      "a free AI caption generator for social media captions."))

    case("description 通篇形容词时 M5 判 0",
         lambda r: True if it(r, "M5")["score"] == 0 else "M5=%s" % it(r, "M5")["score"],
         description=("The most thoughtfully designed companion for modern teams who care "
                      "about how their voice comes across, crafted with real attention."))

    case("定价页不写价格与币种时 M6 判 0",
         lambda r: True if it(r, "M6")["score"] == 0 else "M6=%s" % it(r, "M6")["score"],
         page_type="pricing", keyword="pricing",
         title="Pricing plans for every team size",
         description=("Flexible plans designed to meet the needs of every team, "
                      "whatever your size or stage of growth today."))

    case("没给页型时 M6 记未观察，不折算成 0",
         lambda r: True if it(r, "M6")["observed"] is False
         else "observed=%s" % it(r, "M6")["observed"],
         page_type=None)

    case("只给一页时 M7 记未观察，不折算成 0",
         lambda r: True if it(r, "M7")["observed"] is False
         else "observed=%s" % it(r, "M7")["observed"])

    case("title 与两页重复时 M7 判 0",
         lambda r: True if it(r, "M7")["score"] == 0 else "M7=%s" % it(r, "M7")["score"],
         peers=[{"url": "/a", "title": GOOD["title"], "description": "x"},
                {"url": "/b", "title": GOOD["title"], "description": "y"}])

    case("只有 description 重复时 M7 掉到 2，title 唯一不判 0",
         lambda r: True if it(r, "M7")["score"] == 2 else "M7=%s" % it(r, "M7")["score"],
         peers=[{"url": "/a", "title": "别的标题", "description": GOOD["description"]}])

    case("meta lane 里营销腔由 C4 抓到",
         lambda r: True if it(r, "C4")["score"] == 0 else "C4=%s" % it(r, "C4")["score"],
         title="世界最强的 AI caption generator，业界领先",
         description="全网最好用的一键搞定方案，遥遥领先，为您提供极致体验，最强体验。")

    # 未观察不进分母：三项全未观察时，满分基数不应把它们算进去
    r_all = R.score_meta(GOOD["title"], GOOD["description"], keyword="", page_type=None)
    scored = [i for i in r_all["items"] if i["kind"] == "score" and i["observed"]]
    expect_full = sum(3 * i["weight"] for i in scored)
    if r_all["score"]["full"] == expect_full and len(r_all["unobserved"]) == 3:
        ok("meta lane 未观察的 3 项不进分母")
    else:
        bad("meta lane 未观察项进了分母：full=%s 期望=%s 未观察=%d"
            % (r_all["score"]["full"], expect_full, len(r_all["unobserved"])))

if __name__ == "__main__":
    print("write lane 靶站：")
    for f in sorted(os.listdir(FIX)):
        if f.endswith(".md"):
            run_one(os.path.join(FIX, f))
    print("\n纪律回归：")
    run_unobserved_semantics()
    run_machine_locked()
    run_offline_not_pass()
    run_threshold_honesty()
    run_self_host_is_first_party()

    print("\naudit lane 靶站：")
    for f in sorted(os.listdir(AFIX)):
        if f.endswith(".html"):
            run_audit_fixture(os.path.join(AFIX, f))

    print("\nmeta lane 靶标：")
    run_meta_cases()

    print("\naudit lane 站级靶标：")
    run_site_level_cases()
    run_audit_unobserved_not_zero()

    print("\n判据与实现：")
    run_rubric_selfcheck()
    print("\n%d 过，%d 红" % (len(_ok), len(_bad)))
    sys.exit(1 if _bad else 0)
