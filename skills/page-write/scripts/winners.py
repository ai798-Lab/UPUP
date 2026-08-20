#!/usr/bin/env python3
# winners.py: 抓对照页，产出两样东西。
#
#   1. 写作证据：对手在这个题目上给了什么事实、什么结构。每条主张日后都要挂在这上面。
#   2. 通过线：对照组的事实密度中位数。page-write 的 W1 用它当通过线，
#      而不是用一个拍脑袋的数字。你的竞品写到什么密度，你的线就在哪。
#
# 抓不到的页记 observed: false，不进任何统计，也不当成「它们没有」。
# 三个来源一个都没给时直接报错退出，不去猜对照页是谁。
import argparse
import json
import os
import re
import statistics
import sys
import urllib.parse

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

多半是只拷了 page-write 这一个目录，没把它旁边的 _shared/ 一起拷过去。
三个 skill 共用那一份地基，必须整个 skills/ 一起拷。

解法二选一：
  1. 把整个 skills/ 目录完整拷到你放 skill 的位置
  2. 设环境变量 UPUP_SHARED 指向放着 fetch.py 的那个目录

找过这些地方：
  %s
""" % "\n  ".join(str(c) for c in cands))


sys.path.insert(0, _find_shared())
import fetch as F           # noqa: E402
import rubric_check as RC   # noqa: E402


def analyze(url, timeout=15):
    p = F.extract(url, timeout=timeout)
    if not p["observed"]:
        return {"url": url, "observed": False,
                "reason": "取不到（%s / %s）" % (p["status"], p["reach"]),
                "note": ("被防护规则拦住，不是这一页不存在"
                         if p["reach"] == "blocked" else None)}
    f = p["facts"]
    html = p["html"]
    bs = RC.blocks_of(html)
    fact_blocks = [b for b in bs if RC.has_fact(b["text"])]
    density = (len(fact_blocks) / len(bs)) if bs else 0.0
    ext_cited = [b for b in bs if RC.links_in(b["html"])[1]]
    quotes = [b["text"][:220] for b in fact_blocks[:6]]
    return {
        "url": p["final_url"] or url, "observed": True,
        "title": f["title"], "h1": f["h1"][:2], "h2": f["h2"][:12],
        "word_count": f["word_count"],
        "blocks": len(bs),
        "fact_blocks": len(fact_blocks),
        "fact_density": round(density, 3),
        "cited_blocks": len(ext_cited),
        "jsonld_types": f["jsonld_types"],
        "jsonld_broken": f["jsonld_broken"],
        "tables": f["table_count"], "lists": f["list_count"],
        "images": f["img_count"], "images_with_alt": f["img_with_alt"],
        "has_video": bool(re.search(r'(?is)<(video|iframe)[^>]*>', html)),
        "external_domains": f["external_domains"][:10],
        "quotable_facts": quotes,
        "questions_answered": [s for s in f["sentences"] if s.rstrip().endswith(("?", "？"))][:6],
    }


def bench(pages):
    """把对照组压成几个可比的数。取不到的页不进统计。"""
    obs = [p for p in pages if p.get("observed")]
    if not obs:
        return {"observed": 0, "note": "一个对照页都没抓到，这次没有实测通过线可用"}
    dens = sorted(p["fact_density"] for p in obs)
    out = {
        "observed": len(obs),
        "fact_density_list": dens,
        "fact_density_median": round(statistics.median(dens), 3),
        "word_count_median": int(statistics.median([p["word_count"] for p in obs])),
        "with_table": sum(1 for p in obs if p["tables"]),
        "with_faq": sum(1 for p in obs if "FAQPage" in (p["jsonld_types"] or [])),
        "with_image": sum(1 for p in obs if p["images"]),
        "with_video": sum(1 for p in obs if p["has_video"]),
        "with_citation": sum(1 for p in obs if p["cited_blocks"]),
    }
    gaps = []
    if out["with_table"] == 0:
        gaps.append("没有一个对照页做了对比表")
    if out["with_faq"] == 0:
        gaps.append("没有一个对照页写了 FAQ 结构化数据")
    if out["with_video"] == 0:
        gaps.append("没有一个对照页配了视频")
    if out["with_citation"] == 0:
        gaps.append("没有一个对照页给数字标了外部来源")
    out["gaps"] = gaps
    out["usable_as_threshold"] = len(obs) >= 3
    if not out["usable_as_threshold"]:
        out["note"] = ("只抓到 %d 个对照页，不足 3 个，机械闸会回退到经验值，"
                       "报告里会标出来" % len(obs))
    return out


def main():
    ap = argparse.ArgumentParser(description="抓对照页，产写作证据与通过线")
    ap.add_argument("--question", required=True, help="目标问题")
    ap.add_argument("--rivals", help="逗号分隔的对照页地址")
    ap.add_argument("--from-teardown", help="rival-teardown 产出的 JSON，从里面取选题对应的页面")
    ap.add_argument("--out", help="写到这个 JSON 文件")
    a = ap.parse_args()

    urls = [u.strip() for u in (a.rivals or "").split(",") if u.strip()]
    if a.from_teardown:
        with open(a.from_teardown, encoding="utf-8") as f:
            td = json.load(f)
        for t in td.get("topics", []):
            if a.question.lower() in (t.get("topic") or "").lower() and t.get("page"):
                urls.append(t["page"])
        if not urls:
            for r in td.get("rivals", []):
                if r.get("observed") and r.get("url"):
                    urls.append(r["url"])
    urls = list(dict.fromkeys(urls))
    if not urls:
        raise SystemExit(
            "没有对照页可抓。\n"
            "给 --rivals 逗号分隔的地址，或给 --from-teardown 指向 rival-teardown 的产物。\n"
            "这一步不去猜对照页是谁：猜错了，后面每一条主张挂的证据都是错的。")

    pages = [analyze(u) for u in urls]
    out = {"question": a.question, "rivals": pages, "bench": bench(pages)}
    js = json.dumps(out, ensure_ascii=False, indent=2)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(js)
        b = out["bench"]
        print("抓到 %s / %s 个对照页" % (b.get("observed", 0), len(urls)))
        if b.get("usable_as_threshold"):
            print("事实密度中位数 %.2f，这就是本次机械闸 W1 的通过线" % b["fact_density_median"])
        else:
            print(b.get("note", ""))
        for g in b.get("gaps", []):
            print("缝：%s" % g)
    else:
        print(js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
