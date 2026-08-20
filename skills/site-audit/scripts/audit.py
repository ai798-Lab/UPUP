#!/usr/bin/env python3
# audit.py: site-audit 的入口。采集观察证据，交给共享引擎打分，产报告。
#
# 这里只负责「去看」，判据一条都不在这里。判据在 _shared/rubric.json，算分在 _shared/rubric_check.py。
# 分开的理由：判据要能被 evals 单独打靶，采集要能被换掉（比如离线重放）。
#
# 采集纪律：
#   1. 每一次请求的结果都要能分类成 ok / blocked / dead / unknown，不许只记「失败」。
#   2. 采不到就把那一处留空，让引擎记未观察。这里不许填默认值，填了就等于把未观察偷换成 0。
#   3. 不登录、不跑 JS、不用第三方库。爬虫看到什么，这里就看什么。
import argparse
import json
import os
import re
import sys
import urllib.parse

_HERE = os.path.dirname(os.path.abspath(__file__))


def _find_shared():
    """找共享地基。找不到就报人话，不甩 ModuleNotFoundError 堆栈。"""
    cands = [os.environ.get("UPUP_SHARED"),
             os.path.join(os.path.dirname(_HERE), "_shared"),
             os.path.join(os.path.dirname(os.path.dirname(_HERE)), "_shared"),
             os.path.expanduser("~/.claude/skills/_shared")]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "fetch.py")):
            return c
    raise SystemExit("""
找不到共享地基 _shared/fetch.py。

多半是只拷了 site-audit 这一个目录，没把它旁边的 _shared/ 一起拷过去。
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

MAX_PEERS = 6               # 抓多少个同站页面用来判跨页抢词。再多就把体检拖长了


def origin_of(url):
    u = urllib.parse.urlparse(url if "://" in url else "https://" + url)
    return "%s://%s" % (u.scheme or "https", u.netloc)


def canonical_target(canonical, timeout=12):
    """跟着 canonical 走，最多 4 跳，记录跳数。不用递归，链路要能被人看懂。"""
    if not canonical:
        return None
    url, hops = canonical, 0
    while hops <= 4:
        r = F.status_only(url, timeout=timeout)
        if r["status"] is None:
            return {"status": None, "hops": hops, "error": r["error"], "final": url}
        if 300 <= r["status"] < 400 and r["location"]:
            url = urllib.parse.urljoin(url, r["location"])
            hops += 1
            continue
        return {"status": r["status"], "hops": hops, "error": None, "final": url}
    return {"status": None, "hops": hops, "error": "重定向超过 4 跳", "final": url}


def variant_landings(origin, timeout=12):
    """http/https 乘带不带 www 四个入口各请求一次，看落到哪。取不到的记 None，不猜。"""
    host = F.bare_host(origin)
    out = {}
    for scheme in ("http", "https"):
        for prefix in ("", "www."):
            u = "%s://%s%s" % (scheme, prefix, host)
            p = F.fetch(u, timeout=timeout)
            out[u] = {"final": (p["final_url"] if p["reach"] == "ok" else None),
                      "status": p["status"], "reach": p["reach"]}
    return out


def collect_peers(entries, self_url, timeout=12, limit=MAX_PEERS):
    """从 sitemap 里等距取几页，抓 title 与 h1，用于判跨页抢词与 title 重复。

    等距而不是取前 N 个：sitemap 前几条通常是首页和导航页，彼此本来就像，
    取前 N 会造出一堆假的「抢词」。
    """
    locs = [e["loc"] for e in (entries or [])]
    if self_url not in locs:
        locs = [self_url] + locs
    step = max(1, len(locs) // limit)
    picked = [locs[i] for i in range(0, len(locs), step)][:limit]
    peers = []
    for u in picked:
        p = F.extract(u, timeout=timeout)
        if not p["observed"]:
            continue
        peers.append({"url": p["final_url"] or u, "title": p["facts"]["title"],
                      "h1": p["facts"]["h1"][:2]})
    return peers


def run(url, extra_pages=None, timeout=15):
    url = url if "://" in url else "https://" + url
    origin = origin_of(url)

    page = F.fetch(url, timeout=timeout)
    facts = F.facts(page["html"], base_url=page["final_url"] or url) if page["reach"] == "ok" else None

    rb = RB.report(origin, path=urllib.parse.urlparse(url).path or "/", timeout=timeout)
    noindex = RB.noindex_signals(page) if page["reach"] == "ok" else []
    probe = RB.ua_probe(url, timeout=timeout) if page["reach"] == "ok" else {}
    cdn = RB.cdn_blocks(probe, page["reach"]) if probe else None

    sm = SM.collect(origin, rb.get("sitemap_lines"), timeout=timeout)
    sample = SM.sample_check(sm.get("entries") or [], timeout=timeout) if sm.get("observed") else {
        "observed": False, "reason": "没有 sitemap，无处抽样"}

    canon = (facts or {}).get("canonical") or []
    ct = canonical_target(urllib.parse.urljoin(page["final_url"] or url, canon[0]),
                          timeout=timeout) if canon else None

    variants = variant_landings(origin, timeout=timeout)

    peers = []
    if sm.get("observed") or extra_pages:
        peers = collect_peers(sm.get("entries"), page["final_url"] or url, timeout=timeout)
    for e in (extra_pages or []):
        p = F.extract(e, timeout=timeout)
        if p["observed"]:
            peers.append({"url": p["final_url"] or e, "title": p["facts"]["title"],
                          "h1": p["facts"]["h1"][:2]})

    ev = {"url": url, "origin": origin, "page": page, "facts": facts, "robots": rb,
          "noindex": noindex, "ua_probe": probe, "cdn_blocked": cdn, "sitemap": sm,
          "sample": sample, "canonical_target": ct, "variants": variants, "peers": peers}
    res = RC.score_audit(ev)
    res["url"] = url
    res["origin"] = origin
    res["evidence_digest"] = {
        "status": page["status"], "reach": page["reach"],
        "robots_observed": rb.get("observed"), "no_robots_file": rb.get("no_robots_file"),
        "sitemap_source": sm.get("source"), "sitemap_count": len(sm.get("entries") or []),
        "peers": len(peers), "cdn_blocked": cdn,
        "ua_probe": {k: v["status"] for k, v in (probe or {}).items()},
    }
    res["next_action"] = pick_action(res)
    return res


def pick_action(res):
    """整份报告只支撑一个动作。

    排序写死在这里，不让模型临场决定：抓取类门槛永远排在内容类前面，
    因为内容拿不到时改文案的收益是零。
    """
    order = ["G1", "G2", "G3", "T1", "T5", "T4", "T7", "T3", "T2", "T6", "T8", "T9",
             "C1", "C2", "K2", "C3", "C4", "K1", "I1", "I2", "I3", "W6"]
    by = {i["id"]: i for i in res["items"]}
    for iid in order:
        it = by.get(iid)
        if not it or not it["observed"]:
            continue
        failed = (not it["pass"]) if it["kind"] == "gate" else (not it["pass"])
        if failed and it.get("fix"):
            return {"id": iid, "name": it["name"], "why": it["detail"], "do": it["fix"],
                    "verify": verify_cmd(iid, res)}
    return {"id": None, "name": "机械项没有失分",
            "do": "机械层查得到的都过了。下一步不是继续查，是去写内容：跑 rival-teardown 定题目，"
                  "再用 page-write 写第一篇。",
            "verify": None}


def verify_cmd(iid, res):
    """给一条能复现的验证命令。未观察的项不给命令，因为它永远不会变绿。"""
    u, o = res["url"], res["origin"]
    return {
        "G1": "curl -sI %s | head -1" % u,
        "G2": "curl -s %s/robots.txt | head -40" % o,
        "G3": "curl -s %s | python3 -c \"import sys,re;h=sys.stdin.read();"
              "print(len(re.sub(r'<[^>]+>',' ',re.sub(r'(?is)<(script|style)[^>]*>.*?</\\\\1>',' ',h)).split()))\"" % u,
        "T1": "curl -sI %s/sitemap.xml | head -3" % o,
        "T2": "curl -s %s/sitemap.xml | grep -c '<loc>'" % o,
        "T3": "curl -s %s/sitemap.xml | grep -o '<loc>[^<]*' | head -5 | "
              "sed 's|<loc>||' | xargs -I{} curl -sI -o /dev/null -w '%%{http_code} {}\\n' {}" % o,
        "T4": "curl -s %s | grep -o '<link[^>]*canonical[^>]*>'" % u,
        "T5": "curl -sI \"$(curl -s %s | grep -o 'rel=\"canonical\"[^>]*href=\"[^\"]*' | "
              "sed 's|.*href=\"||')\" | head -1" % u,
        "T6": "for v in http://%s https://%s http://www.%s https://www.%s; do "
              "curl -so /dev/null -w \"$v -> %%{url_effective}\\n\" -L $v; done" % (
                  F.bare_host(o), F.bare_host(o), F.bare_host(o), F.bare_host(o)),
        "T7": "curl -s %s | python3 -c \"import sys,re,json;"
              "[print('OK' if _try(b) else 'BROKEN') for b in re.findall(r'(?is)<script[^>]+ld\\\\+json[^>]*>(.*?)</script>',sys.stdin.read())]\" "
              "# 或直接把每段贴进 json.loads" % u,
        "T8": "curl -s %s | grep -o '\"@type\"[^,]*'" % u,
        "T9": "curl -s %s | grep -o '\"price\"[^,]*\\|\"ratingValue\"[^,]*'" % u,
        "C1": "curl -s %s | grep -c '<h1'" % u,
        "C2": "curl -s %s | python3 -c \"import sys,re;h=sys.stdin.read();"
              "t=re.sub(r'<[^>]+>',' ',re.sub(r'(?is)<(script|style|head|nav|header)[^>]*>.*?</\\\\1>',' ',h));"
              "print(' '.join(t.split()[:50]))\"" % u,
        "I1": "curl -s %s | grep -o '<title>[^<]*'" % u,
        "I2": "curl -s %s | grep -o '<html[^>]*lang=\"[^\"]*'" % u,
        "I3": "curl -s %s | grep -o 'hreflang=\"[^\"]*'" % u,
    }.get(iid)


# ── compare ────────────────────────────────────────────────────────────
def compare(old, new):
    """两次体检做机器 diff。只报三件事，不承诺任何 AI 侧的效果。"""
    ob = {i["id"]: i for i in old["items"]}
    nb = {i["id"]: i for i in new["items"]}
    fixed, worse, still_unobserved, changed = [], [], [], []
    for iid, n in nb.items():
        o = ob.get(iid)
        if not o:
            continue
        if not o["observed"] and not n["observed"]:
            still_unobserved.append({"id": iid, "name": n["name"], "reason": n["reason"]})
            continue
        if not o["observed"] or not n["observed"]:
            changed.append({"id": iid, "name": n["name"],
                            "from": "未观察" if not o["observed"] else o["score"],
                            "to": "未观察" if not n["observed"] else n["score"]})
            continue
        if o["score"] == n["score"]:
            continue
        rec = {"id": iid, "name": n["name"], "from": o["score"], "to": n["score"],
               "detail": n["detail"]}
        (fixed if (n["score"] or 0) > (o["score"] or 0) else worse).append(rec)
    return {
        "from": {"url": old.get("url"), "verdict": old.get("verdict"),
                 "percent": old.get("score", {}).get("percent")},
        "to": {"url": new.get("url"), "verdict": new.get("verdict"),
               "percent": new.get("score", {}).get("percent")},
        "fixed": fixed, "worse": worse, "still_unobserved": still_unobserved,
        "observability_changed": changed,
        "note": "只对机器能验证的部分负责。这里不承诺 AI 有没有引用你，"
                "那件事没有可靠的免费测法，硬测出来的数字换个问法就变。",
    }


# ── 报告 ───────────────────────────────────────────────────────────────
def render_html(res, template_path=None):
    tpl = template_path or os.path.join(_find_shared(), "report.html")
    with open(tpl, encoding="utf-8") as f:
        html = f.read()
    rows = []
    for i in res["items"]:
        if not i["observed"]:
            rows.append('<tr class="unobs"><td>%s</td><td>%s</td><td colspan="2">未观察：%s</td>'
                        '<td>%s</td></tr>' % (i["id"], _esc(i["name"]), _esc(i["reason"]),
                                              i["evidence_level"]))
            continue
        mark = "过" if i["pass"] else "未过"
        score = "门槛" if i["kind"] == "gate" else "%s / 3" % i["score"]
        rows.append('<tr class="%s"><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                    '<tr class="d"><td></td><td colspan="4">%s%s</td></tr>' % (
                        "ok" if i["pass"] else "no", i["id"], _esc(i["name"]), score, mark,
                        i["evidence_level"], _esc(i["detail"]),
                        ("<br><b>动作</b>：" + _esc(i["fix"])) if i.get("fix") else ""))
    act = res["next_action"]
    act_html = "<p><b>%s</b></p><p>%s</p>" % (_esc(act.get("name") or ""), _esc(act.get("do") or ""))
    if act.get("verify"):
        act_html += "<pre>%s</pre>" % _esc(act["verify"])
    dig = res["evidence_digest"]
    return (html.replace("{{URL}}", _esc(res["url"]))
                .replace("{{VERDICT}}", res["verdict"])
                .replace("{{PERCENT}}", str(res["score"]["percent"]))
                .replace("{{ACTION}}", act_html)
                .replace("{{ROWS}}", "\n".join(rows))
                .replace("{{DIGEST}}", _esc(json.dumps(dig, ensure_ascii=False))))


def _esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def main():
    ap = argparse.ArgumentParser(description="site-audit：一次查完搜索和 AI 的地基")
    ap.add_argument("url", nargs="?", help="要体检的网址")
    ap.add_argument("--pages", help="逗号分隔的额外页面，用来判跨页抢词")
    ap.add_argument("--json", help="把结果写到这个 JSON 文件")
    ap.add_argument("--html", help="把报告写到这个 HTML 文件")
    ap.add_argument("--compare", nargs=2, metavar=("OLD.json", "NEW.json"),
                    help="两份体检结果做 diff")
    a = ap.parse_args()

    if a.compare:
        old = json.load(open(a.compare[0], encoding="utf-8"))
        new = json.load(open(a.compare[1], encoding="utf-8"))
        print(json.dumps(compare(old, new), ensure_ascii=False, indent=2))
        return 0

    if not a.url:
        ap.error("要给一个网址，或者用 --compare 比两份结果")

    res = run(a.url, extra_pages=[x.strip() for x in (a.pages or "").split(",") if x.strip()])
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
    if a.html:
        with open(a.html, "w", encoding="utf-8") as f:
            f.write(render_html(res))
    if not a.json and not a.html:
        slim = dict(res)
        slim["items"] = [{k: v for k, v in i.items() if k not in ("why", "evidence")}
                         for i in res["items"]]
        print(json.dumps(slim, ensure_ascii=False, indent=2))
    else:
        print("verdict=%s  分数=%s%%  下一个动作=%s" % (
            res["verdict"], res["score"]["percent"], res["next_action"]["name"]))
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
