#!/usr/bin/env python3
# rubric_check.py: 机械分引擎。判据全部来自 rubric.json，这里只负责算。
#
# 三条纪律：
#   1. 每项结果都带 machine_locked: true。模型只能引用，不许改分。
#   2. 抓不到的项写 observed: false 加 reason，不进分母，绝不折算成 0。
#   3. 每项结果都带 source 与 evidence_level，让读报告的人知道这条判据凭什么。
#
# 判据分块统计而不是按每百词，是因为 CJK 逐字计词会让中文密度被严重稀释，
# 中英文的每百词基准不可比。块 = 段落级单元（p / li / 表格行 / figcaption / 标题）。
import json
import os
import re
import sys
import urllib.parse

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
try:
    import fetch as F
except ModuleNotFoundError:
    raise SystemExit("""
找不到同目录的 fetch.py。

多半是只拷了一个 skill 目录，没把 skills/_shared/ 一起拷过去。
把整个 skills/ 目录完整拷过去，或设 UPUP_SHARED 指向放着 fetch.py 的目录。
""")

RUBRIC_PATH = os.path.join(_HERE, "rubric.json")

# ── 词表。改这里等于改判据，改完要同步 rubric.json 的 how 字段 ──────────────
UNIT = (r'%|％|percent|个百分点|倍|秒|分钟|小时|天|周|月|年|人|次|条|道|题|项|款|元|美元|'
        r'\$|USD|RMB|GB|MB|KB|TB|ms|px|字|词|分位|名')
NUM_UNIT = re.compile(r'\d[\d,\.]*\s*(?:' + UNIT + r')', re.I)
DATE = re.compile(r'(19|20)\d{2}\s*[-/年]\s*\d{1,2}|(19|20)\d{2}\s*年')
# 区间写法（例如 10 到 20 的西文写法）里那个符号用 re 的 \u2013 转义写，
# 不写字面量：本项目对产物跑「不许出现破折号」的机械自检，字面量会让它在这一行误红。
RANGE = re.compile(r'\d[\d,\.]*\s*(?:到|至|-|~|\u2013)\s*\d')

SOURCE_MARK = re.compile(r'(?i)(来源|出处|据[^，。]{0,8}(称|报道|显示)|引自|source\s*:|'
                         r'according to|per\s+the|<cite[ >])')

MARKETING = re.compile(
    r"(#1\b|\bbest ever\b|\bamazing\b|\bworld.?s best\b|\bnumber one\b|\bfree forever\b|"
    r"\bmost powerful\b|\brevolutionary\b|\bgame.?changer\b|\bcutting.?edge\b|"
    r"\bunleash\b|\bsupercharge\b|\bseamlessly\b|\beffortlessly\b|"
    r"业界领先|颠覆式|一键搞定|最强|极致体验|遥遥领先|全网最)", re.I)

# 段首悬空代词。命中这些开头，段落被单独摘走时读者找不到先行词。
DANGLING = re.compile(r'^\s*(它们|它|他们|该方案|该功能|该产品|这一点|这些|那些|上述|'
                      r'this\b|that\b|these\b|those\b|it\b|they\b)', re.I)

# 一手来源。域名后缀或关键段命中即判一手。
FIRST_PARTY_SUFFIX = ('.gov', '.edu', '.gov.cn', '.edu.cn', '.int', '.mil')
FIRST_PARTY_MARK = ('doi.org', 'arxiv.org', 'pubmed', 'nih.gov', 'who.int', 'oecd.org',
                    'w3.org', 'ietf.org', 'rfc-editor.org', 'schema.org', 'sitemaps.org',
                    'developers.google.com', 'developer.mozilla.org', 'docs.',
                    'nature.com', 'science.org', 'acm.org', 'ieee.org')
WEAK_MARK = ('medium.com', 'zhihu.com', 'jianshu.com', 'csdn.net', 'blogspot.',
             'wordpress.com', 'substack.com', 'x.com', 'twitter.com', 'facebook.com',
             'linkedin.com', 'quora.com', 'reddit.com', 'pinterest.', 'aggregator',
             'weibo.com', 'xiaohongshu.com')

VALID_SCHEMA_TYPES = {"SoftwareApplication", "WebApplication", "HowTo", "FAQPage", "Article",
                      "Product", "ItemList", "BlogPosting", "NewsArticle", "Course", "Recipe",
                      "ImageObject", "VideoObject", "Quiz", "Dataset"}
PAGE_LEVEL_TYPES = {"SoftwareApplication", "WebApplication", "Product", "Article", "FAQPage",
                    "HowTo", "BlogPosting", "NewsArticle", "Course", "Recipe", "Quiz",
                    "Dataset", "ItemList"}

# 目标问题里的通用词，算命中时要先去掉，否则 "best free online" 会把任何页面都判成命中。
STOP = set("the a an and or for of to in on with your you online free best how what is are that "
           "this when which who can do does my me it its from by at as vs 的 了 吗 呢 和 与 "
           "怎么 如何 什么 多久 哪个 是不是".split())

W1_FALLBACK = 0.30      # 取不到对照组时的事实占比回退线。经验值，报告里必须标出来


def load_rubric(path=RUBRIC_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _item(rubric, iid):
    for i in rubric["items"]:
        if i["id"] == iid:
            return i
    raise KeyError("rubric.json 里没有 %s。判据和实现对不上，先修 rubric.json" % iid)


def result(rubric, iid, score=None, detail="", evidence=None, observed=True, reason=None,
           fix_key=None):
    """统一的单项结果。未观察时 score 为 None，且不进分母。"""
    it = _item(rubric, iid)
    out = {
        "id": iid, "name": it["name"], "kind": it["kind"], "machine_locked": True,
        "observed": observed, "score": score, "detail": detail,
        "evidence": evidence or [], "source": it["source"],
        "evidence_level": it["evidence_level"], "why": it["why"],
    }
    if not observed:
        out["reason"] = reason or "未观察"
        out["fix"] = None
        return out
    if it["kind"] == "gate":
        out["pass"] = bool(score)
    else:
        out["weight"] = it["weight"]
        out["pass_at"] = it["pass_at"]
        out["pass"] = score is not None and score >= it["pass_at"]
    fixes = it.get("fix") or {}
    key = fix_key if fix_key is not None else (str(score) if score is not None else "default")
    out["fix"] = fixes.get(key) or fixes.get("default") or (
        fixes.get(str(score)) if score is not None else None)
    if out.get("pass") and out["kind"] == "score":
        out["fix"] = None
    return out


# ── 块级切分 ────────────────────────────────────────────────────────────
BLOCK_RE = re.compile(r'(?is)<(p|li|figcaption|h[1-6]|blockquote|td|th|dd)[^>]*>(.*?)</\1>')


def blocks_of(html):
    """把内容块切成段落级单元。返回 [{tag, html, text}]。

    markdown 表格行也算一块：草稿里大量事实是以表格给出的，漏掉表格会低估事实密度。
    """
    out = []
    for tag, inner in BLOCK_RE.findall(html or ""):
        t = F.clean_text(inner)
        if t:
            out.append({"tag": tag.lower(), "html": inner, "text": t})
    for line in (html or "").splitlines():
        s = line.strip()
        if s.startswith("|") and s.count("|") >= 3 and not re.match(r'^\|[\s\-:|]+\|$', s):
            t = F.clean_text(s.strip("|"))
            if t:
                out.append({"tag": "mdrow", "html": s, "text": t})
    return out


def has_fact(text):
    return bool(NUM_UNIT.search(text) or DATE.search(text))


def links_in(html):
    """块或内容块里的链接。返回 (站内, 站外)。"""
    hrefs = re.findall(r'(?i)<a[^>]+href=["\']([^"\']+)["\']', html or "")
    hrefs += re.findall(r'\]\(([^)\s]+)\)', html or "")          # markdown 链接
    internal = [h for h in hrefs if h.startswith("/")]
    external = [h for h in hrefs if re.match(r'^https?://', h)]
    return internal, external


def question_terms(question):
    """把目标问题切成可比对的词。中文用双字而不是单字：单字匹配下，
    「多久」的「久」会命中「很久以前」，答案前置这一项就形同虚设。"""
    q = (question or "").lower()
    terms = [w for w in re.findall(r'[a-z]{2,}', q) if w not in STOP]
    cjk = re.findall(r'[一-鿿]{2,}', q)
    for run in cjk:
        for i in range(len(run) - 1):
            bg = run[i:i + 2]
            if bg not in STOP:
                terms.append(bg)
    return list(dict.fromkeys(terms))


def norm_url(u):
    """比较两个地址是不是同一个落点时用。

    尾部斜杠、host 大小写、默认端口、fragment 都不改变实际落点，
    不归一化就会把 https://a.com 和 https://a.com/ 判成两个不同的地址，
    在四写法归一那一项上产生误报，而验证命令跑出来是全对的。
    """
    if not u:
        return u
    pr = urllib.parse.urlparse(u)
    host = pr.netloc.lower()
    if (pr.scheme == "https" and host.endswith(":443")) or \
       (pr.scheme == "http" and host.endswith(":80")):
        host = host.rsplit(":", 1)[0]
    path = pr.path.rstrip("/") or "/"
    return urllib.parse.urlunparse((pr.scheme, host, path, "", pr.query, ""))


def source_tier(url, self_host=None):
    host = F.bare_host(url)
    # 引自己站的数据算一手：自测数据的原始出处就是你自己，这是独立开发者最常见的引用形态。
    if self_host and host == F.bare_host(self_host):
        return "first"
    if any(host.endswith(s) for s in FIRST_PARTY_SUFFIX) or any(m in host for m in FIRST_PARTY_MARK):
        return "first"
    if any(m in host for m in WEAK_MARK):
        return "weak"
    return "second"


def numbers_in(text):
    """块里的数字串，用于回来源页核对。去掉纯年份，年份到处都是，核不出信息。"""
    out = []
    for m in re.finditer(r'\d[\d,]*\.?\d*', text or ""):
        s = m.group(0)
        if re.match(r'^(19|20)\d{2}$', s):
            continue
        if len(s.replace(",", "").replace(".", "")) >= 2:
            out.append(s)
    return out


def extract_block(draft_text):
    """从草稿 md 里取那个可上线内容块。取不到返回 None，上层报用法错误，不去猜。"""
    m = re.search(r'(?s)```(?:html|markdown|md)\s*\n(.*?)```', draft_text or "")
    return m.group(1) if m else None


# ── 默认取源函数。测试时注入 stub，让 evals 能离线跑 ──────────────────────
def live_source_fetcher(url, timeout=12):
    p = F.fetch(url, timeout=timeout)
    return {"ok": p["reach"] == "ok", "status": p["status"], "reach": p["reach"],
            "text": F.clean_text(p["html"]) if p["reach"] == "ok" else ""}


# ── write lane ─────────────────────────────────────────────────────────
def score_write(draft_text, question="", fetch_source=None, comparables=None, rubric=None,
                self_host=None):
    """吃一份草稿，出机械分。fetch_source 可注入，便于离线回归。"""
    rubric = rubric or load_rubric()
    fetch_source = fetch_source or live_source_fetcher
    block = extract_block(draft_text)
    if block is None:
        raise ValueError("草稿里找不到 ```html 或 ```markdown 的可上线内容块")

    text = F.clean_text(block)
    bs = blocks_of(block)
    items = []

    # WG1 答案前置
    ws = F.words(text)
    # 两种拼法都要试：CJK 逐字计词后，" ".join 会把「依恋」拆成「依 恋」，
    # 双字词在空格版里永远匹配不到。
    first50 = " ".join(ws[:50]).lower()
    first50_cat = "".join(ws[:50]).lower()
    qw = question_terms(question)
    if not question:
        items.append(result(rubric, "WG1", observed=False, reason="没给目标问题，本项不判定"))
    else:
        hit = [w for w in qw if w in first50 or w in first50_cat]
        need = 2 if len(qw) >= 2 else len(qw)
        ok = len(hit) >= need and len(ws) >= 20
        items.append(result(rubric, "WG1", score=1 if ok else 0,
                            detail="前 50 词命中问题实义词 %d 个（需 %d），内容块 %d 词" % (
                                len(hit), need, len(ws)),
                            evidence=[{"first_50_words": " ".join(ws[:50])[:200],
                                       "hit": hit[:8], "question_words": qw[:8]}]))

    # C4 无营销腔
    hits = []
    for b in bs:
        # 数全部命中而不是每块第一个：一句话里塞四个套话只算一处的话，这一项就废了
        for m in MARKETING.finditer(b["text"]):
            hits.append({"phrase": m.group(0), "sentence": b["text"][:180]})
    n = len(hits)
    items.append(result(rubric, "C4", score=3 if n == 0 else 2 if n == 1 else 1 if n <= 3 else 0,
                        detail="命中营销套话 %d 处" % n, evidence=hits[:5]))

    # W1 事实密度
    fact_blocks = [b for b in bs if has_fact(b["text"])]
    ratio = (len(fact_blocks) / len(bs)) if bs else 0.0
    if comparables:
        vals = sorted(c for c in comparables if isinstance(c, (int, float)))
    else:
        vals = []
    if len(vals) >= 3:
        mid = vals[len(vals) // 2]
        line, line_src = mid, "对照组 %d 个页面的中位数" % len(vals)
    else:
        line, line_src = W1_FALLBACK, "回退经验值（没抓到 ≥3 个对照页，这次用的不是实测线）"
    sc = 3 if ratio >= line else 2 if ratio >= line * 0.6 else 1 if ratio > 0 else 0
    items.append(result(rubric, "W1", score=sc,
                        detail="含事实的块 %d / %d，占比 %.2f，通过线 %.2f（%s）" % (
                            len(fact_blocks), len(bs), ratio, line, line_src),
                        evidence=[{"threshold": line, "threshold_source": line_src,
                                   "sample": [b["text"][:120] for b in fact_blocks[:3]]}]))

    # W2 来源标注率
    num_blocks = [b for b in bs if NUM_UNIT.search(b["text"]) or RANGE.search(b["text"])]
    if not num_blocks:
        items.append(result(rubric, "W2", observed=False,
                            reason="内容块里没有数值块，本项不判定。写不写数字已经由 W1 判过"))
        cited = []
    else:
        cited = [b for b in num_blocks
                 if links_in(b["html"])[1] or SOURCE_MARK.search(b["html"])]
        r2 = len(cited) / len(num_blocks)
        items.append(result(rubric, "W2",
                            score=3 if r2 >= 0.6 else 2 if r2 >= 0.3 else 1 if r2 > 0 else 0,
                            detail="挂了来源的数值块 %d / %d，占比 %.0f%%" % (
                                len(cited), len(num_blocks), r2 * 100),
                            evidence=[{"uncited_sample": [b["text"][:120]
                                                          for b in num_blocks if b not in cited][:3]}]))

    # W3 来源真的打得开 / W4 一手性 / W5 数字可回溯
    _, ext = links_in(block)
    ext = list(dict.fromkeys(ext))[:8]
    if not ext:
        for iid, why in (("W3", "内容块里没有外部来源链接，没有可核的来源"),
                         ("W4", "内容块里没有外部来源链接"),
                         ("W5", "内容块里没有外部来源链接")):
            items.append(result(rubric, iid, observed=False, reason=why))
    else:
        probes = {u: fetch_source(u) for u in ext}
        dead = [u for u, v in probes.items() if v.get("reach") == "dead"]
        blocked = [u for u, v in probes.items() if v.get("reach") == "blocked"]
        unknown = [u for u, v in probes.items() if v.get("reach") == "unknown"]
        if len(unknown) == len(ext):
            # 一条都没真去请求（离线模式或全部连接失败）。没观察就说「全部可达」是假的。
            items.append(result(rubric, "W3", observed=False,
                                reason="%d 条来源一条都没请求到，可达性无从判定" % len(ext)))
        else:
            tail = "；另有 %d 条没请求到，不计入" % len(unknown) if unknown else ""
            items.append(result(
                rubric, "W3",
                score=3 if not dead and not blocked else 2 if not dead else 1 if len(dead) == 1 else 0,
                detail="来源 %d 条：死链 %d，被防护拦住 %d（被拦不算死链）%s" % (
                    len(ext), len(dead), len(blocked), tail),
                evidence=[{"dead": dead, "blocked": blocked, "unobserved": unknown}]))

        tiers = {u: source_tier(u, self_host) for u in ext}
        first = [u for u, t in tiers.items() if t == "first"]
        weak = [u for u, t in tiers.items() if t == "weak"]
        if len(first) >= len(ext) / 2:
            s4 = 3
        elif first:
            s4 = 2
        elif len(weak) == len(ext):
            s4 = 0
        else:
            s4 = 1
        items.append(result(rubric, "W4", score=s4,
                            detail="一手 %d，二手 %d，弱来源 %d" % (
                                len(first), len(ext) - len(first) - len(weak), len(weak)),
                            evidence=[{"tiers": tiers}]))

        # W5：挂了来源的数值块，数字要在来源页里找得到
        checks, unobserved = [], []
        for b in (cited or []):
            b_ext = links_in(b["html"])[1]
            if not b_ext:
                continue
            src = b_ext[0]
            pr = probes.get(src) or fetch_source(src)
            if not pr.get("ok"):
                unobserved.append({"source": src, "why": "来源页取不到（%s）" % pr.get("status")})
                continue
            body = pr.get("text") or ""
            for num in numbers_in(b["text"])[:3]:
                plain = num.replace(",", "")
                found = num in body or plain in body or ("{:,}".format(int(plain))
                                                         if plain.isdigit() else "") in body
                checks.append({"number": num, "source": src, "found": bool(found),
                               "claim": b["text"][:120]})
        miss = [c for c in checks if not c["found"]]
        if not checks:
            items.append(result(rubric, "W5", observed=False,
                                reason="没有「挂了来源的数值块」可核" + (
                                    "；另有 %d 条来源页取不到" % len(unobserved) if unobserved else "")))
        else:
            items.append(result(
                rubric, "W5",
                score=3 if not miss else 2 if len(miss) == 1 else 1 if len(miss) < len(checks) else 0,
                detail="核了 %d 个数字，来源页里找不到的 %d 个" % (len(checks), len(miss)),
                evidence=[{"missing": miss[:4], "unobserved_sources": unobserved[:3]}]))

    # W6 有可被引的图或视频
    imgs = re.findall(r'(?is)<img[^>]*>', block)
    vids = re.findall(r'(?is)<(video|iframe)[^>]*>', block)
    md_imgs = re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', block)
    n_media = len(imgs) + len(vids) + len(md_imgs)
    if n_media == 0:
        items.append(result(rubric, "W6", score=0, detail="内容块里没有图也没有视频"))
    else:
        no_alt = [t for t in imgs if not (re.search(r'(?i)alt=["\']([^"\']+)', t))]
        no_alt += [a for a, _ in md_imgs if not a.strip()]
        has_caption = bool(re.search(r'(?is)<figcaption[^>]*>\s*\S', block))
        ld_types = _block_jsonld_types(block)
        has_media_ld = bool({"ImageObject", "VideoObject"} & set(ld_types))
        if no_alt or not has_caption:
            s6 = 1
        elif not has_media_ld:
            s6 = 2
        else:
            s6 = 3
        items.append(result(rubric, "W6", score=s6,
                            detail="素材 %d 个，缺 alt %d 个，%s说明文字，JSON-LD %s声明 ImageObject/VideoObject" % (
                                n_media, len(no_alt), "有" if has_caption else "无",
                                "有" if has_media_ld else "无"),
                            evidence=[{"missing_alt": no_alt[:3], "jsonld_types": ld_types}]))

    # W7 段落能单独站住
    paras = [b for b in bs if b["tag"] in ("p", "blockquote")]
    dang = [b["text"][:120] for b in paras if DANGLING.match(b["text"])]
    n7 = len(dang)
    items.append(result(rubric, "W7", score=3 if n7 == 0 else 2 if n7 == 1 else 1 if n7 <= 3 else 0,
                        detail="段首悬空代词 %d 段" % n7, evidence=[{"paragraphs": dang[:4]}]))

    # W8 Schema
    types = _block_jsonld_types(block)
    broken = _block_jsonld_broken(block)
    valid = [t for t in types if t in VALID_SCHEMA_TYPES]
    if broken and not valid:
        s8, d8 = 0, "有 %d 个 JSON-LD 块解析不了" % broken
    elif not types:
        s8, d8 = 0, "内容块里没有 JSON-LD"
    elif not valid:
        s8, d8 = 1, "有 JSON-LD 但类型不在有效集里：%s" % types
    elif len(set(valid)) >= 2:
        s8, d8 = 3, "有效类型 %s" % sorted(set(valid))
    else:
        s8, d8 = 2, "有效类型 %s" % sorted(set(valid))
    items.append(result(rubric, "W8", score=s8, detail=d8,
                        evidence=[{"types": types, "broken_blocks": broken}]))

    # W9 内链
    internal = list(dict.fromkeys(links_in(block)[0]))
    n9 = len(internal)
    items.append(result(rubric, "W9", score=3 if n9 >= 5 else 2 if n9 >= 3 else 1 if n9 >= 1 else 0,
                        detail="站内链接 %d 条" % n9, evidence=[{"links": internal[:6]}]))

    # D1 验证命令
    bash = re.findall(r'(?s)```bash\s*\n(.*?)```', draft_text)
    ok1 = any(re.search(r'\b(curl|grep)\b', b) for b in bash)
    items.append(result(rubric, "D1", score=1 if ok1 else 0,
                        detail="bash 块 %d 个，含 curl 或 grep：%s" % (len(bash), "是" if ok1 else "否")))

    # D2 待核清单
    has_sec = bool(re.search(r'(?im)^#{1,4}\s*(待核|需核|needs?[ _-]?review)', draft_text))
    marks = len(re.findall(r'\[(待核|需核|未验证)\]', block))
    listed = len(re.findall(r'(?im)^\s*[-*]\s*.*\[(待核|需核|未验证)\]', draft_text))
    ok2 = has_sec and marks <= listed
    items.append(result(rubric, "D2", score=1 if ok2 else 0,
                        detail="待核小节：%s；内容块标记 %d 处，清单条目 %d 条" % (
                            "有" if has_sec else "无", marks, listed)))

    return finalize(items, lane="write")


def _block_jsonld_types(block):
    types = []
    for raw in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', block):
        try:
            data = json.loads(raw.strip())
        except Exception:
            types += re.findall(r'"@type"\s*:\s*"([^"]+)"', raw)
            continue

        def walk(node):
            if isinstance(node, dict):
                t = node.get("@type")
                if isinstance(t, str):
                    types.append(t)
                elif isinstance(t, list):
                    types.extend([x for x in t if isinstance(x, str)])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(data)
    return sorted(set(types))


def _block_jsonld_broken(block):
    n = 0
    for raw in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', block):
        try:
            json.loads(raw.strip())
        except Exception:
            n += 1
    return n


# ── audit lane ─────────────────────────────────────────────────────────
def nav_words(html):
    """header 与 nav 里出现过的词。用来量首屏 50 词里有多少其实是导航噪声。"""
    ws = set()
    for tag, inner in re.findall(r'(?is)<(header|nav)[^>]*>(.*?)</\1>', html or ""):
        for w in F.words(F.clean_text(inner)):
            ws.add(w.lower())
    return ws


def terms_of(text):
    """一段文字的实义词集合。中文双字，英文整词，去掉通用词。"""
    return set(question_terms(text or ""))


def _walk_jsonld(node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, (str, int, float)):
                out.append((k, str(v)))
            else:
                _walk_jsonld(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_jsonld(v, out)


def score_audit(ev, rubric=None):
    """吃一份观察证据，出机械分。证据由 site-audit/scripts/audit.py 采集。

    ev 的键：url / page / facts / robots / noindex / ua_probe / cdn_blocked /
            sitemap / sample / canonical_target / variants / peers
    任何一处没观察到就记未观察，绝不折算成 0。
    """
    rubric = rubric or load_rubric()
    items = []
    page = ev.get("page") or {}
    facts = ev.get("facts")
    html = page.get("html") or ""
    url = ev.get("url") or ""

    # G1 页面取得到
    reach = page.get("reach") or "unknown"
    if reach == "unknown":
        items.append(result(rubric, "G1", observed=False,
                            reason="连接层就失败了（%s），本次不判定" % (page.get("error") or "无响应")))
    else:
        items.append(result(rubric, "G1", score=1 if reach == "ok" else 0, fix_key=reach,
                            detail="HTTP %s，判为 %s%s" % (
                                page.get("status"), reach,
                                "（站是活的，被防护规则拦了，不是下线）" if reach == "blocked" else ""),
                            evidence=[{"status": page.get("status"), "reach": reach}]))

    # G2 爬虫进得来
    rb = ev.get("robots") or {}
    noindex = ev.get("noindex") or []
    if not rb.get("observed"):
        items.append(result(rubric, "G2", observed=False,
                            reason=rb.get("reason") or "robots.txt 没观察到，本项不判定，也不给改 robots 的动作"))
    else:
        blocked = {}
        for cls, agents in (rb.get("classes") or {}).items():
            if cls in ("training",):
                continue
            hit = [a for a, v in agents.items() if not v["allowed"]]
            if hit:
                blocked[cls] = hit
        ok2 = not blocked and not noindex
        fk = "robots" if blocked else ("header_noindex" if any(
            "X-Robots-Tag" in n["where"] for n in noindex) else "meta_noindex" if noindex else None)
        items.append(result(rubric, "G2", score=1 if ok2 else 0, fix_key=fk,
                            detail="被挡的档：%s；noindex：%s%s" % (
                                blocked or "无", [n["where"] for n in noindex] or "无",
                                "；站上没有 robots.txt，等于全放行" if rb.get("no_robots_file") else ""),
                            evidence=[{"blocked": blocked, "noindex": noindex,
                                       "cdn_blocked": ev.get("cdn_blocked")}]))

    # G3 正文在初始 HTML 里
    if not facts:
        items.append(result(rubric, "G3", observed=False, reason="页面没取到，正文无从判定"))
    else:
        wc = facts["word_count"]
        items.append(result(rubric, "G3", score=1 if wc >= 120 else 0,
                            detail="初始 HTML 正文 %d 词（阈值 120）" % wc))

    # T1 sitemap 可用
    sm = ev.get("sitemap") or {}
    if sm.get("observed"):
        declared = bool(rb.get("sitemap_lines")) and any(
            s.startswith("http") for s in (rb.get("sitemap_lines") or []))
        items.append(result(rubric, "T1", score=3 if declared else 2,
                            detail="找到 %s%s" % (sm.get("source"),
                                                 "，robots.txt 已用绝对地址声明" if declared
                                                 else "，但 robots.txt 里没声明"),
                            evidence=[{"tried": sm.get("tried")}]))
    else:
        tried = sm.get("tried") or []
        soft404 = any(t.get("status") == 200 and not t.get("usable") for t in tried)
        # 「取不到」和「站上确实没有」是两回事。全是 404 才算确实没有；
        # 只要有一个入口是被拦或连接失败，就记未观察，不许判成 0。
        conclusive = bool(tried) and all(t.get("reach") == "dead" for t in tried)
        if soft404:
            items.append(result(rubric, "T1", score=1,
                                detail="返回 200 但不是 XML，是软 404",
                                evidence=[{"tried": tried}]))
        elif conclusive:
            items.append(result(rubric, "T1", score=0,
                                detail="试过的地址全部 404，站上确实没有 sitemap",
                                evidence=[{"tried": tried}]))
        else:
            items.append(result(rubric, "T1", observed=False,
                                reason="sitemap 取不到（%s），不能据此判定站上没有" % (
                                    sm.get("reason") or "未知原因")))

    # T2 sitemap 内容卫生
    if not sm.get("observed"):
        items.append(result(rubric, "T2", observed=False, reason="没有 sitemap 可查"))
    else:
        iss = sm.get("issues") or []
        ids = {i["id"] for i in iss}
        if ids & {"too_many", "size"}:
            s2 = 0
        elif ids & {"relative_urls", "cross_host", "fragment", "mixed_scheme"}:
            s2 = 1
        elif ids & {"lastmod_format", "lastmod_uniform"}:
            s2 = 2
        else:
            s2 = 3
        items.append(result(rubric, "T2", score=s2,
                            detail="共 %d 条地址，问题 %d 项" % (len(sm.get("entries") or []), len(iss)),
                            evidence=iss[:5]))

    # T3 sitemap 里的地址真的活着
    sp = ev.get("sample") or {}
    if not sp.get("observed"):
        items.append(result(rubric, "T3", observed=False,
                            reason=sp.get("reason") or "没有可抽样的地址"))
    else:
        nd, nr = len(sp.get("dead") or []), len(sp.get("redirect") or [])
        s3 = 3 if not nd and not nr else 2 if not nd else 1 if nd == 1 else 0
        items.append(result(rubric, "T3", score=s3,
                            detail="抽了 %d 条：死链 %d，重定向 %d，被拦 %d（被拦不算死链）" % (
                                sp.get("sampled", 0), nd, nr, len(sp.get("blocked") or [])),
                            evidence=[{"dead": sp.get("dead"), "redirect": sp.get("redirect")}]))

    # T4 canonical 数量与形态
    if not facts:
        for iid in ("T4", "T5", "T6"):
            items.append(result(rubric, iid, observed=False, reason="页面没取到"))
    else:
        cans = facts.get("canonical") or []
        if len(cans) != 1:
            items.append(result(rubric, "T4", score=0,
                                detail="canonical 有 %d 个（必须恰好 1 个，多个时会被全部忽略）" % len(cans),
                                evidence=[{"canonical": cans}]))
        else:
            c = cans[0]
            if not re.match(r'^https?://', c):
                s4, d4 = 2, "只有一个但写成了相对路径：%s" % c
            elif "#" in c or urllib.parse.urlparse(norm_url(c)).scheme != urllib.parse.urlparse(
                    norm_url(page.get("final_url") or url)).scheme:
                s4, d4 = 1, "带 fragment 或协议与本页不一致：%s" % c
            else:
                s4, d4 = 3, "恰好一个，绝对地址：%s" % c
            items.append(result(rubric, "T4", score=s4, detail=d4, evidence=[{"canonical": c}]))

        # T5 canonical 可达
        ct = ev.get("canonical_target")
        if not cans:
            items.append(result(rubric, "T5", observed=False, reason="页面没有 canonical，无处可验"))
        elif not ct or ct.get("status") is None:
            items.append(result(rubric, "T5", observed=False,
                                reason="canonical 目标取不到（%s），不判定" % (
                                    (ct or {}).get("error") or "无响应")))
        else:
            st = ct["status"]
            hops = ct.get("hops", 1)
            s5 = 3 if st == 200 else 0 if (st == 404 or st >= 500) else (2 if hops <= 1 else 1)
            items.append(result(rubric, "T5", score=s5,
                                detail="canonical 目标返回 %s%s" % (
                                    st, "，重定向 %d 跳" % hops if 300 <= st < 400 else ""),
                                evidence=[ct]))

        # T6 四写法归一
        var = ev.get("variants") or {}
        seen = [norm_url(v.get("final")) for v in var.values() if v.get("final")]
        unobs = [k for k, v in var.items() if not v.get("final")]
        if len(seen) < 2:
            items.append(result(rubric, "T6", observed=False,
                                reason="四个入口里只观察到 %d 个，样本不足以判归一" % len(seen)))
        else:
            distinct = len(set(seen))
            s6 = 3 if distinct == 1 and not unobs else 2 if distinct == 1 else 1 if distinct == 2 else 0
            items.append(result(rubric, "T6", score=s6,
                                detail="四个入口落到 %d 个不同地址，未观察 %d 个" % (distinct, len(unobs)),
                                evidence=[{"variants": var}]))

    # T7 / T8 / T9 JSON-LD
    if not facts:
        for iid in ("T7", "T8", "T9"):
            items.append(result(rubric, iid, observed=False, reason="页面没取到"))
    else:
        nb, broken = facts["jsonld_blocks"], facts["jsonld_broken"]
        if nb == 0:
            items.append(result(rubric, "T7", score=0, detail="页面没有 JSON-LD"))
        elif broken == 0:
            items.append(result(rubric, "T7", score=3, detail="%d 个块全部能解析" % nb))
        elif broken >= nb:
            items.append(result(rubric, "T7", score=0,
                                detail="%d 个块全部解析失败，等于完全没有 JSON-LD" % nb))
        else:
            items.append(result(rubric, "T7", score=2 if broken == 1 else 1,
                                detail="%d 个块里坏了 %d 个" % (nb, broken)))

        types = facts["jsonld_types"]
        if not types:
            items.append(result(rubric, "T8", score=0, detail="没有可识别的 @type"))
        else:
            pg = [t for t in types if t in PAGE_LEVEL_TYPES]
            site = [t for t in types if t not in PAGE_LEVEL_TYPES]
            s8 = 3 if pg and site else 2 if pg else 1
            note = ("；其中有类型是从解析失败的块里正则兜底提出来的，那些块实际不生效，见 T7"
                    if broken else "")
            items.append(result(rubric, "T8", score=s8,
                                detail="页面级类型 %s；站级类型 %s%s" % (pg or "无", site or "无", note),
                                evidence=[{"types": types, "from_broken_blocks": bool(broken)}]))

        pairs = []
        for b in F.jsonld_blocks(html):
            if b["ok"]:
                _walk_jsonld(b["data"], pairs)
        watch = [(k, v) for k, v in pairs
                 if k in ("price", "ratingValue", "reviewCount", "ratingCount")]
        body = (facts.get("body_text") or "")
        self_rating = any(k == "aggregateRating" for k, _ in pairs) or \
            any(k in ("ratingValue", "reviewCount") for k, _ in pairs)
        if not watch:
            items.append(result(rubric, "T9", observed=False,
                                reason="JSON-LD 里没有 price / rating 这类可与正文比对的字段"))
        else:
            miss = [(k, v) for k, v in watch if v not in body]
            s9 = 3 if not miss else 2 if len(miss) == 1 else 1 if len(miss) == 2 else 0
            items.append(result(rubric, "T9", score=s9,
                                detail="比对 %d 个字段，正文里找不到的 %d 个" % (len(watch), len(miss)),
                                evidence=[{"missing": miss[:4],
                                           "needs_review": ("页面自身写了评分，是不是自评自打分要你自己确认"
                                                            if self_rating else None)}]))

    # C1 / C2 / C3 / C4 内容项
    if not facts:
        for iid in ("C1", "C2", "C3", "C4"):
            items.append(result(rubric, iid, observed=False, reason="页面没取到"))
    else:
        n1 = facts["h1_count"]
        items.append(result(rubric, "C1", score=3 if n1 == 1 else 2 if n1 > 1 else 0,
                            detail="H1 %d 个" % n1, evidence=[{"h1": facts["h1"][:3]}]))

        topic = terms_of((facts.get("title") or "") + " " + (facts.get("meta_description") or ""))
        f50 = facts["first_50_words"]
        f50_terms = terms_of(f50)
        hit = topic & f50_terms
        nav = nav_words(html)
        f50_words = F.words(f50)
        navr = (sum(1 for w in f50_words if w.lower() in nav) / len(f50_words)) if f50_words else 0
        if len(hit) >= 2 and navr < 0.3:
            s2c = 3
        elif len(hit) >= 2:
            s2c = 2 if navr <= 0.6 else 1
        elif len(hit) == 1:
            s2c = 1
        else:
            s2c = 0
        items.append(result(rubric, "C2", score=s2c,
                            detail="首屏命中主题词 %d 个，导航词占比 %.0f%%" % (len(hit), navr * 100),
                            evidence=[{"first_50_words": f50[:180], "hit": sorted(hit)[:6]}]))

        bs = blocks_of(html)
        ev_blocks = [b for b in bs if has_fact(b["text"]) or RANGE.search(b["text"])
                     or links_in(b["html"])[1]]
        ratio = (len(ev_blocks) / len(bs)) if bs else 0
        s3c = 3 if ratio >= 0.3 else 2 if ratio >= 0.15 else 1 if ratio > 0 else 0
        items.append(result(rubric, "C3", score=s3c,
                            detail="含可提取证据的块 %d / %d，占比 %.0f%%" % (
                                len(ev_blocks), len(bs), ratio * 100),
                            evidence=[{"sample": [b["text"][:110] for b in ev_blocks[:3]]}]))

        mk = []
        for b in bs:
            for m in MARKETING.finditer(b["text"]):
                mk.append({"phrase": m.group(0), "sentence": b["text"][:160]})
        nm = len(mk)
        items.append(result(rubric, "C4", score=3 if nm == 0 else 2 if nm == 1 else 1 if nm <= 3 else 0,
                            detail="命中营销套话 %d 处" % nm, evidence=mk[:5]))

    # K1 一页一主词
    peers = ev.get("peers") or []
    if len(peers) < 3:
        items.append(result(rubric, "K1", observed=False,
                            reason="只拿到 %d 个页面，不足以判跨页抢词（需要 3 个以上）" % len(peers)))
    else:
        clash = []
        for i in range(len(peers)):
            for j in range(i + 1, len(peers)):
                a, b = peers[i], peers[j]
                ta = terms_of((a.get("title") or "") + " " + " ".join(a.get("h1") or []))
                tb = terms_of((b.get("title") or "") + " " + " ".join(b.get("h1") or []))
                if not ta or not tb:
                    continue
                jac = len(ta & tb) / len(ta | tb)
                if jac >= 0.6:
                    clash.append({"a": a.get("url"), "b": b.get("url"), "overlap": round(jac, 2)})
        nc = len(clash)
        items.append(result(rubric, "K1", score=3 if nc == 0 else 2 if nc == 1 else 1 if nc <= 3 else 0,
                            detail="标题高度重叠的页面对 %d 组（阈值 0.6）" % nc,
                            evidence=clash[:4]))

    # K2 四处一致
    if not facts:
        items.append(result(rubric, "K2", observed=False, reason="页面没取到"))
    else:
        t_title = terms_of(facts.get("title"))
        t_h1 = terms_of(" ".join(facts.get("h1") or []))
        path = urllib.parse.urlparse(page.get("final_url") or url).path
        t_url = terms_of(re.sub(r'[-_/]+', ' ', path))
        first_sent = (facts.get("sentences") or [""])[0]
        t_first = terms_of(first_sent)
        groups = [t_title, t_h1, t_url, t_first]
        common = set.intersection(*[g for g in groups if g]) if all(groups) else set()
        if not common:
            counts = {}
            for g in groups:
                for w in g:
                    counts[w] = counts.get(w, 0) + 1
            best = max(counts.values()) if counts else 0
        else:
            best = 4
        items.append(result(rubric, "K2", score=3 if best >= 4 else 2 if best == 3 else 1 if best == 2 else 0,
                            detail="四处里最多有 %d 处共用同一个主词" % best,
                            evidence=[{"title": sorted(t_title)[:5], "h1": sorted(t_h1)[:5],
                                       "url": sorted(t_url)[:5], "first_sentence": first_sent[:120]}]))

    # I1 title 长度与唯一
    if not facts:
        for iid in ("I1", "I2", "I3"):
            items.append(result(rubric, iid, observed=False, reason="页面没取到"))
    else:
        title = facts.get("title") or ""
        ln = sum(2 if re.match(r'[一-鿿]', c) else 1 for c in title)
        dup = [p.get("url") for p in peers
               if p.get("title") and title and p.get("title") == title
               and p.get("url") != (page.get("final_url") or url)]
        if not title:
            s_i1 = 0
        elif len(dup) >= 2:
            s_i1 = 0
        elif len(dup) == 1:
            s_i1 = 1
        elif 15 <= ln <= 60:
            s_i1 = 3
        else:
            s_i1 = 2
        items.append(result(rubric, "I1", score=s_i1,
                            detail="title 长度 %d（15 到 60 为宜），与 %d 个其他页重复" % (ln, len(dup)),
                            evidence=[{"title": title[:120], "duplicates": dup[:3]}]))

        lang = facts.get("lang")
        url_lang = re.match(r'^/([a-z]{2}(?:-[a-zA-Z]{2,4})?)(/|$)',
                            urllib.parse.urlparse(page.get("final_url") or url).path or "")
        if not lang:
            s_i2, d_i2 = 0, "html 标签没有 lang"
        elif "_" in lang:
            s_i2, d_i2 = 1, "lang 写成了下划线：%s，应该是连字符" % lang
        elif url_lang and not lang.lower().startswith(url_lang.group(1).lower()[:2]):
            s_i2, d_i2 = 2, "lang=%s 与 URL 语言段 /%s 对不上" % (lang, url_lang.group(1))
        else:
            s_i2, d_i2 = 3, "lang=%s" % lang
        if lang and re.match(r'^(ar|he|fa|ur)', lang, re.I) and not re.search(
                r'(?i)<html[^>]+dir=["\']?rtl', html):
            s_i2, d_i2 = min(s_i2, 2), d_i2 + "；RTL 语言但 html 上没有 dir=rtl"
        items.append(result(rubric, "I2", score=s_i2, detail=d_i2))

        alts = re.findall(r'(?is)<link[^>]+hreflang=["\']([^"\']+)["\'][^>]*>', html)
        alt_pairs = re.findall(
            r'(?is)<link[^>]+rel=["\']alternate["\'][^>]*hreflang=["\']([^"\']+)["\'][^>]*href=["\']([^"\']+)["\']',
            html)
        cur = page.get("final_url") or url
        if not alts and not url_lang:
            items.append(result(rubric, "I3", observed=False,
                                reason="页面没有 hreflang，URL 里也没有语言段，按单语言站处理，不判定"))
        elif not alts:
            items.append(result(rubric, "I3", score=0, detail="URL 有语言段但页面没有 hreflang"))
        else:
            self_ref = any(norm_url(h) == norm_url(cur) for _, h in alt_pairs)
            xd = any(a.lower() == "x-default" for a in alts)
            s_i3 = 3 if self_ref and xd else 2 if self_ref else 1
            items.append(result(rubric, "I3", score=s_i3,
                                detail="hreflang %d 条，自指 %s，x-default %s" % (
                                    len(alts), "有" if self_ref else "无", "有" if xd else "无"),
                                evidence=[{"hreflang": alts[:8]}]))

    return finalize(items, lane="audit")



# ── meta lane：一对 title 与 description ───────────────────────────────
CJK_RE = re.compile(r'[\u4e00-\u9fff]')


def _mlen(s):
    """字符数，CJK 按 2 计。与 audit lane 的 I1 同一套计法。"""
    return sum(2 if CJK_RE.match(c) else 1 for c in (s or ""))


HOOK_PATTERNS = {
    "带单位数值": re.compile(
        r'(?i)\d+\s*(秒|分钟|小时|天|次|个|条|页|张|人|%|percent|sec|second|min|minute|hour|day|x\b)'),
    "价格或币种": re.compile(r'(?i)(\$|¥|€|£|\d+\s*(美元|元|刀)|\b(usd|eur|cny|rmb)\b|/\s*(mo|month|月))'),
    "免费程度": re.compile(
        r'(?i)(免费|不用注册|无需注册|不用登录|\bfree\b|no sign.?up|no account|no credit card)'),
    "产出物或支持范围": re.compile(
        r'(?i)(导出|下载|支持|兼容|\b(mp4|gif|png|jpg|pdf|csv|svg|webp|json)\b|'
        r'\b(instagram|linkedin|tiktok|youtube|twitter|facebook|x)\b|export|download)'),
}

VERB_RE = re.compile(
    r'(?i)(生成|制作|转换|检测|分析|创建|上传|导出|下载|排期|发布|写|做|查|试|'
    r'\bgenerate|\bcreate|\bconvert|\bmake|\bbuild|\bwrite|\bcheck|\bschedule|\bpublish|\bturn\b)')

TOOL_VERB_RE = re.compile(
    r'(?i)(生成器|转换器|检测器|分析器|编辑器|生成|转换|检测|分析|压缩|裁剪|去除|'
    r'\bgenerator\b|\bconverter\b|\bchecker\b|\banalyzer\b|\beditor\b|\bmaker\b|'
    r'\bcreator\b|\bremover\b|\bcompressor\b|\bdetector\b)')

AUDIENCE_RE = re.compile(
    r'(?i)(给|为|适合|面向|团队|个人|创作者|开发者|商家|新手|专业|运营|营销|设计师|'
    r'\bfor\b|\bteams?\b|\bcreators?\b|\bdevelopers?\b|\bmarketers?\b|\bagencies\b|'
    r'\bbeginners?\b|\bfreelancers?\b|\bbusinesses\b)')

PAGE_TYPES = ("home", "tool", "pricing")


def score_meta(title, description, keyword="", page_type=None, peers=None, rubric=None):
    """吃一对 title 与 description。peers 是同组其他页 [{title, description, url}]，用于查唯一性。"""
    rubric = rubric or load_rubric()
    items = []
    title = (title or "").strip()
    desc = (description or "").strip()
    peers = peers or []
    tl, dl = _mlen(title), _mlen(desc)

    # MG1 门槛
    ok_gate = bool(title) and bool(desc) and tl >= 6 and dl >= 20
    items.append(result(rubric, "MG1", score=1 if ok_gate else 0,
                        detail="title %d 字符，description %d 字符" % (tl, dl),
                        evidence=[{"title": title[:120], "description": desc[:200]}]))

    # M1 title 长度
    if not title:
        s = 0
    elif 15 <= tl <= 60:
        s = 3
    elif 10 <= tl < 15 or 60 < tl <= 70:
        s = 2
    else:
        s = 1
    items.append(result(rubric, "M1", score=s, detail="title 长度 %d（15 到 60 为宜）" % tl))

    # M2 description 长度
    if not desc:
        s = 0
    elif 70 <= dl <= 155:
        s = 3
    elif 50 <= dl < 70 or 155 < dl <= 175:
        s = 2
    else:
        s = 1
    items.append(result(rubric, "M2", score=s, detail="description 长度 %d（70 到 155 为宜）" % dl))

    # M3 主词在 title 前半
    kw_terms = sorted(terms_of(keyword)) if keyword else []
    if not kw_terms:
        items.append(result(rubric, "M3", observed=False,
                            reason="没给主词，无法判断它在不在 title 前半"))
    elif not title:
        items.append(result(rubric, "M3", score=0, detail="没有 title"))
    else:
        low = title.lower()
        hits = [low.find(t.lower()) for t in kw_terms if t.lower() in low]
        if not hits:
            items.append(result(rubric, "M3", score=0,
                                detail="title 里找不到主词 %s" % "、".join(kw_terms[:4]),
                                evidence=[{"title": title[:120], "keyword_terms": kw_terms[:6]}]))
        else:
            rel = _mlen(title[:min(hits)]) / max(tl, 1)
            s = 3 if rel <= 1 / 3 else (2 if rel <= 0.5 else 1)
            items.append(result(rubric, "M3", score=s,
                                detail="主词首次出现在 title 的第 %d%% 处" % round(rel * 100),
                                evidence=[{"keyword_terms": kw_terms[:6]}]))

    # M4 description 不复述 title
    a, b = terms_of(title), terms_of(desc)
    if not a or not b:
        items.append(result(rubric, "M4", observed=False, reason="title 或 description 取不到实义词"))
    else:
        j = len(a & b) / len(a | b)
        s = 3 if j <= 0.30 else (2 if j <= 0.50 else (1 if j <= 0.70 else 0))
        items.append(result(rubric, "M4", score=s,
                            detail="与 title 的实义词重叠度 %.2f（越低越好）" % j,
                            evidence=[{"shared_terms": sorted(a & b)[:8]}]))

    # M5 具体钩子
    if not desc:
        items.append(result(rubric, "M5", score=0, detail="没有 description"))
    else:
        hit = [k for k, rx in HOOK_PATTERNS.items() if rx.search(desc)]
        if len(hit) >= 2:
            s = 3
        elif len(hit) == 1:
            s = 2
        elif VERB_RE.search(desc):
            s = 1
        else:
            s = 0
        items.append(result(rubric, "M5", score=s,
                            detail="命中 %d 类具体信息%s" % (
                                len(hit), ("：" + "、".join(hit)) if hit else ""),
                            evidence=[{"hooks": hit}]))

    # M6 页型必答项
    if page_type not in PAGE_TYPES:
        items.append(result(rubric, "M6", observed=False,
                            reason="没给页型（home / tool / pricing），无法判断必答项"))
    else:
        blob = title + " " + desc
        if page_type == "home":
            need = {"品类词": bool(kw_terms) and any(t.lower() in blob.lower() for t in kw_terms),
                    "人群或用途": bool(AUDIENCE_RE.search(blob))}
        elif page_type == "tool":
            need = {"功能动词": bool(TOOL_VERB_RE.search(blob)),
                    "说清输入或产出": bool(HOOK_PATTERNS["产出物或支持范围"].search(blob)
                                           or HOOK_PATTERNS["带单位数值"].search(blob))}
        else:
            need = {"价格数字": bool(re.search(r'\d', blob)),
                    "币种": bool(HOOK_PATTERNS["价格或币种"].search(blob))}
        got = sum(1 for v in need.values() if v)
        s = {2: 3, 1: 2, 0: 0}[got] if len(need) == 2 else (3 if got == len(need) else 1)
        miss = [k for k, v in need.items() if not v]
        items.append(result(rubric, "M6", score=s,
                            detail="页型 %s：%s" % (
                                page_type, ("都齐了" if not miss else "缺 " + "、".join(miss))),
                            evidence=[{"page_type": page_type, "missing": miss}]))

    # M7 同组唯一
    if not peers:
        items.append(result(rubric, "M7", observed=False, reason="只给了一页，没有同组可比"))
    else:
        dup_t = [p.get("url") for p in peers if title and p.get("title") == title]
        dup_d = [p.get("url") for p in peers if desc and p.get("description") == desc]
        if len(dup_t) >= 2:
            s = 0
        elif len(dup_t) == 1:
            s = 1
        elif dup_d:
            s = 2
        else:
            s = 3
        items.append(result(rubric, "M7", score=s,
                            detail="title 与 %d 页重复，description 与 %d 页重复" % (
                                len(dup_t), len(dup_d)),
                            evidence=[{"title_dup": dup_t[:3], "desc_dup": dup_d[:3]}]))

    # C4 无营销腔（与 audit / write 共用同一份词表）
    hits = []
    for m in MARKETING.finditer(title + " " + desc):
        hits.append({"phrase": m.group(0)})
    n = len(hits)
    s = 3 if n == 0 else (2 if n == 1 else (1 if n <= 3 else 0))
    items.append(result(rubric, "C4", score=s,
                        detail="命中营销套话 %d 处" % n, evidence=hits[:5]))

    return finalize(items, lane="meta")

# ── 汇总 ───────────────────────────────────────────────────────────────
def finalize(items, lane):
    gates = [i for i in items if i["kind"] == "gate"]
    scored = [i for i in items if i["kind"] == "score" and i["observed"]]
    unobserved = [i for i in items if not i["observed"]]
    failed_gates = [i for i in gates if i["observed"] and not i["pass"]]
    got = sum(i["score"] * i["weight"] for i in scored)
    full = sum(3 * i["weight"] for i in scored)
    below = [i for i in scored if not i["pass"]]
    verdict = "REJECT" if failed_gates else ("REWORK" if below else "PASS")
    return {
        "lane": lane,
        "verdict": verdict,
        "machine_locked": True,
        "score": {"got": got, "full": full,
                  "percent": round(got / full * 100, 1) if full else None,
                  "note": "百分比只用来排序，不是及格证书。未观察的项不进分母。"},
        "failed_gates": [i["id"] for i in failed_gates],
        "below_floor": [i["id"] for i in below],
        "unobserved": [{"id": i["id"], "reason": i["reason"]} for i in unobserved],
        "items": items,
    }


# ── SKILL.md 里的表由这里生成，不许手改 ────────────────────────────────
def print_table(lane, rubric=None):
    rubric = rubric or load_rubric()
    rows = ["| 项 | 名称 | 怎么测 | 通过判据 | 出处等级 |", "|---|---|---|---|---|"]
    for it in rubric["items"]:
        if lane not in it["lanes"]:
            continue
        a = it["anchors"]
        if it["kind"] == "gate":
            crit = a.get("pass", "")
        else:
            crit = "；".join("%s 分：%s" % (k, v) for k, v in sorted(a.items(), reverse=True))
        rows.append("| %s | %s | %s | %s | %s |" % (
            it["id"], it["name"], it["how"].replace("\n", " "), crit, it["evidence_level"]))
    return "\n".join(rows)


def check_doc(path, rubric=None):
    """断言 SKILL.md 里的表和 rubric.json 一致。不一致当场红，不靠人记得同步。"""
    rubric = rubric or load_rubric()
    txt = open(path, encoding="utf-8").read()
    bad = []
    for lane in rubric["lanes"]:
        m = re.search(r'(?s)<!-- RUBRIC-TABLE:%s START.*?-->\n(.*?)<!-- RUBRIC-TABLE:%s END -->'
                      % (lane, lane), txt)
        if not m:
            continue
        want = print_table(lane, rubric).strip()
        got = m.group(1).strip()
        if want != got:
            bad.append(lane)
    return bad


def selfcheck(rubric=None):
    """判据与实现一一对应。rubric 里有的项，引擎必须真的算过；引擎算的项，rubric 里必须有。"""
    rubric = rubric or load_rubric()
    src = open(__file__, encoding="utf-8").read()
    implemented = set(re.findall(r'result\(rubric,\s*"([A-Z]+\d+)"', src))
    implemented |= set(re.findall(r'\("([A-Z]+\d+)",\s*"[^"]*没有外部来源', src))
    out = {}
    for lane in rubric["lanes"]:
        declared = {i["id"] for i in rubric["items"] if lane in i["lanes"]}
        out[lane] = {"declared": len(declared),
                     "missing": sorted(declared - implemented),
                     "extra": sorted(implemented - {i["id"] for i in rubric["items"]})}
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="UPUP 机械分引擎")
    ap.add_argument("--print-table", metavar="LANE", help="生成 SKILL.md 里的判据表")
    ap.add_argument("--check-doc", metavar="PATH", help="断言某个 SKILL.md 的表与 rubric.json 一致")
    ap.add_argument("--selfcheck", action="store_true", help="判据与实现是否一一对应")
    a = ap.parse_args()
    if a.print_table:
        print(print_table(a.print_table))
    elif a.check_doc:
        bad = check_doc(a.check_doc)
        if bad:
            print("表与 rubric.json 不一致的 lane：%s\n用 --print-table <lane> 重新生成后贴回。" % bad,
                  file=sys.stderr)
            sys.exit(1)
        print("表与 rubric.json 一致")
    elif a.selfcheck:
        r = selfcheck()
        print(json.dumps(r, ensure_ascii=False, indent=2))
        bad = any(v["missing"] or v["extra"] for v in r.values())
        sys.exit(1 if bad else 0)
    else:
        ap.print_help()
