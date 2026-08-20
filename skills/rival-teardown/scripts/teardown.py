#!/usr/bin/env python3
# teardown.py: 拆竞品，产出「该写什么」。
#
# 它回答两个问题：
#   1. 对手靠哪些词拿量：跨页统计标题里的实义词。一个词被多页覆盖，说明他们在系统性地做它，
#      不是随手写了一篇。只出现一次的词是噪声，不进清单。
#   2. 你缺哪几样：把对手覆盖的词和你自己站覆盖的词做差集，得到选题清单。
#
# 三条纪律：
#   1. 抓不到的页记未观察，不进任何统计，也不当成「他们没有」。
#   2. 每条选题都要挂着对手的那一页地址，让你能自己去看。没有出处的选题不产出。
#   3. 只读公开页面，不登录、不跑 JS、不用第三方库。
import argparse
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


def _find_shared():
    cands = [os.environ.get("UPUP_SHARED"),
             os.path.join(os.path.dirname(_HERE), "_shared"),
             os.path.join(os.path.dirname(os.path.dirname(_HERE)), "_shared"),
             os.path.expanduser("~/.claude/skills/_shared")]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "fetch.py")):
            return c
    raise SystemExit("""
找不到共享地基 _shared/fetch.py。

多半是只拷了 rival-teardown 这一个目录，没把它旁边的 _shared/ 一起拷过去。
三个 skill 共用那一份地基，必须整个 skills/ 一起拷。

解法二选一：
  1. 把整个 skills/ 目录完整拷到你放 skill 的位置
  2. 设环境变量 UPUP_SHARED 指向放着 fetch.py 的那个目录

找过这些地方：
  %s
""" % "\n  ".join(str(c) for c in cands))


sys.path.insert(0, _find_shared())
import fetch as F           # noqa: E402
import robots as RB         # noqa: E402
import sitemap as SM        # noqa: E402
import rubric_check as RC   # noqa: E402

PAGES_PER_SITE = 12         # 每家抓多少页。再多就慢，且边际信息很小
MIN_PAGES_FOR_TERM = 2      # 一个词至少被这么多页覆盖，才算「他们在做这个词」

# 选题噪声。这三类词会在每一份标题里出现，但都不是你能去争的词：
#   1. 语言代码：多语言站的 title 或 URL 段里到处都是
#   2. 品牌名：对手的名字，你抢不走也不该抢
#   3. 计量与通用词：min、sec 这类从「9 min」里切出来的碎片
LANG_CODES = set("""ar bg bn cs da de el en es et fa fi fr gu he hi hr hu id it iw ja jp kn ko
lt lv ml mr ms nb nl no pl pt ro ru sk sl sr sv sw ta te th tr uk ur vi zh
cn tw hant hans br mx us gb ca au""".split())
UNIT_WORDS = set("""min mins sec secs hr hrs kb mb gb ms px pcs pct num no yes new top all
free best online tool tools app apps site web page""".split())


def origin_of(u):
    u = u if "://" in u else "https://" + u
    m = re.match(r'(https?://[^/]+)', u)
    return m.group(1)


def scan_site(target, timeout=15, limit=PAGES_PER_SITE):
    """抓一个站的若干页，产出它的词覆盖与页面特征。"""
    origin = origin_of(target)
    rb = RB.report(origin, timeout=timeout)
    sm = SM.collect(origin, rb.get("sitemap_lines"), timeout=timeout)
    entries = [e["loc"] for e in (sm.get("entries") or [])]
    if not entries:
        entries = [origin]
    step = max(1, len(entries) // limit)
    picked = [entries[i] for i in range(0, len(entries), step)][:limit]

    pages, skipped = [], []
    for u in picked:
        p = F.extract(u, timeout=timeout)
        if not p["observed"]:
            skipped.append({"url": u, "status": p["status"], "reach": p["reach"],
                            "note": "被防护规则拦住，不是这页不存在" if p["reach"] == "blocked" else None})
            continue
        f = p["facts"]
        bs = RC.blocks_of(p["html"])
        facts_blocks = [b for b in bs if RC.has_fact(b["text"])]
        pages.append({
            "url": p["final_url"] or u,
            "title": f["title"],
            "h1": f["h1"][:1],
            "terms": sorted(RC.terms_of((f["title"] or "") + " " + " ".join(f["h1"][:1]))),
            "word_count": f["word_count"],
            "fact_density": round(len(facts_blocks) / len(bs), 3) if bs else 0.0,
            "jsonld_types": f["jsonld_types"],
            "tables": f["table_count"],
            "images": f["img_count"],
            "cited_blocks": sum(1 for b in bs if RC.links_in(b["html"])[1]),
        })

    cover = {}
    for p in pages:
        for t in set(p["terms"]):
            cover.setdefault(t, []).append(p["url"])
    return {
        "target": target, "origin": origin,
        "sitemap": sm.get("source"), "sitemap_count": len(entries),
        "observed_pages": len(pages), "skipped": skipped,
        "pages": pages,
        "term_coverage": {t: urls for t, urls in cover.items() if len(urls) >= MIN_PAGES_FOR_TERM},
        "note": ("一页都没抓到，这一家的结论不成立，别拿它当对照" if not pages else None),
    }


def best_page_for(term, sites):
    """这个词上，谁那一页最值得你去看。按事实密度排，密度相同看结构件数量。"""
    cands = []
    for s in sites:
        for p in s["pages"]:
            if term in p["terms"]:
                cands.append((p, s["origin"]))
    if not cands:
        return None
    cands.sort(key=lambda x: (x[0]["fact_density"],
                              x[0]["tables"] + len(x[0]["jsonld_types"]) + x[0]["cited_blocks"]),
               reverse=True)
    p, origin = cands[0]
    why = []
    if p["fact_density"] >= 0.3:
        why.append("每 3 段里至少 1 段有具体数字（密度 %.2f）" % p["fact_density"])
    if p["tables"]:
        why.append("有 %d 个对比表" % p["tables"])
    if p["cited_blocks"]:
        why.append("%d 段挂了外部来源" % p["cited_blocks"])
    if "FAQPage" in (p["jsonld_types"] or []):
        why.append("写了 FAQ 结构化数据")
    if "HowTo" in (p["jsonld_types"] or []):
        why.append("写了步骤结构化数据")
    if p["images"]:
        why.append("配了 %d 张图" % p["images"])
    if not why:
        why.append("结构上没有特别之处，只是他们占了这个词")
    return {"page": p["url"], "from": origin, "why": why, "fact_density": p["fact_density"],
            "word_count": p["word_count"]}


def brand_words(sites):
    """把对手和你自己的品牌名收集起来。品牌名在每个 title 里都有，
    但它不是可争的词：你抢不走对手的名字，也不该把它写进自己的选题清单。"""
    out = set()
    for s in sites:
        if not s:
            continue
        host = F.bare_host(s.get("origin") or "")
        for part in host.split("."):
            if len(part) > 2:
                out.add(part.lower())
                # 复合品牌名（randomhub）也把可能的组成部分挡掉，避免变成半个选题
                for sub in re.findall(r'[a-z]{4,}', part.lower()):
                    out.add(sub)
    return out


def is_noise(term, brands):
    if term in brands:
        return True
    if re.match(r'^[a-z]+$', term):
        if term in LANG_CODES or term in UNIT_WORDS:
            return True
        if len(term) < 3:
            return True
    return False


def gaps(mine, rivals):
    """对手系统性在做、你没有的词。每条挂着对手的页面地址。"""
    brands = brand_words(list(rivals) + ([mine] if mine else []))
    mine_terms = set((mine or {}).get("term_coverage") or {})
    if mine:
        for p in mine.get("pages", []):
            mine_terms |= set(p["terms"])
    out = []
    seen = set()
    for s in rivals:
        for term, urls in (s["term_coverage"] or {}).items():
            if term in mine_terms or term in seen or is_noise(term, brands):
                continue
            seen.add(term)
            b = best_page_for(term, rivals)
            if not b:
                continue
            out.append({
                "topic": term,
                "rival_pages": len(urls),
                "page": b["page"],
                "from": b["from"],
                "fact_density": b["fact_density"],
                "why_it_works": b["why"],
                "you_lack": you_lack(b, mine),
            })
    out.sort(key=lambda x: (x["rival_pages"], x["fact_density"]), reverse=True)
    return out


def you_lack(best, mine):
    """你现在缺哪几样。只列机器看得出来的差距，不替你判断内容好坏。"""
    lack = []
    if not mine or not mine.get("pages"):
        return ["还没抓到你自己的站，这一栏留空。加 --mine 你的域名再跑一次"]
    my_max_density = max((p["fact_density"] for p in mine["pages"]), default=0)
    my_types = set(t for p in mine["pages"] for t in (p["jsonld_types"] or []))
    my_tables = max((p["tables"] for p in mine["pages"]), default=0)
    my_cited = max((p["cited_blocks"] for p in mine["pages"]), default=0)
    if best["fact_density"] > my_max_density:
        lack.append("事实密度：他 %.2f，你最高 %.2f" % (best["fact_density"], my_max_density))
    if "FAQPage" not in my_types:
        lack.append("你全站没有 FAQ 结构化数据")
    if my_tables == 0:
        lack.append("你全站没有对比表")
    if my_cited == 0:
        lack.append("你全站没有一段给数字挂外部来源")
    return lack or ["机器层面看不出差距，差别在内容本身，去打开他那一页读一遍"]


def main():
    ap = argparse.ArgumentParser(description="拆竞品，产出该写什么")
    ap.add_argument("rivals", help="逗号分隔的竞品域名，2 到 3 个")
    ap.add_argument("--mine", help="你自己的域名。给了才能算出你缺什么")
    ap.add_argument("--json", help="写到这个文件")
    ap.add_argument("--limit", type=int, default=PAGES_PER_SITE, help="每家抓多少页")
    a = ap.parse_args()

    rv = [x.strip() for x in a.rivals.split(",") if x.strip()]
    if not rv:
        raise SystemExit("至少给一个竞品域名。")
    if len(rv) > 4:
        print("给了 %d 家，只拆前 4 家，再多这份报告就没人看得完了" % len(rv), file=sys.stderr)
        rv = rv[:4]

    sites = [scan_site(u, limit=a.limit) for u in rv]
    mine = scan_site(a.mine, limit=a.limit) if a.mine else None
    usable = [s for s in sites if s["pages"]]
    topics = gaps(mine, usable) if usable else []

    out = {"rivals": sites, "mine": mine, "topics": topics[:20],
           "coverage_note": "每家最多抓 %d 页，等距取样。结论只覆盖抓到的这些页，不是全站结论。"
                            % a.limit}
    if len(usable) < len(sites):
        out["warning"] = "有 %d 家一页都没抓到，它们没有进入对照" % (len(sites) - len(usable))

    js = json.dumps(out, ensure_ascii=False, indent=2)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            f.write(js)
        print("拆了 %d 家，抓到 %d 页" % (len(usable), sum(s["observed_pages"] for s in usable)))
        for s in sites:
            if s["skipped"]:
                print("  %s 有 %d 页没抓到（被拦或取不到），不计入统计" % (s["origin"], len(s["skipped"])))
        print("\n选题清单前 5 条：")
        for t in topics[:5]:
            print("  %-24s 他们 %d 页在做 → %s" % (t["topic"], t["rival_pages"], t["page"]))
            print("      凭什么：%s" % "；".join(t["why_it_works"][:2]))
            print("      你缺：%s" % "；".join(t["you_lack"][:2]))
        if not topics:
            print("  没有产出选题：可能是没抓到对手的页，也可能是你已经覆盖了他们的词。")
    else:
        print(js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
