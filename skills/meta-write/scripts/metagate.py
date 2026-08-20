#!/usr/bin/env python3
# metagate.py: meta-write 的机械闸。吃一对 title 与 description，判 9 项。
#
# 这里只负责「去看」和「组装输入」，判据一条都不在这里。
# 判据在 _shared/rubric.json，算分在 _shared/rubric_check.py。
#
# 两种用法：
#   1. --url 线上地址：抓当前的 title 与 description，看现状差在哪
#   2. --title / --description：判你新写的这一对，改完再跑一次
#
# 采集纪律与 audit.py 一致：抓不到就留空让引擎记未观察，这里不许填默认值。
import argparse
import json
import os
import sys

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

多半是只拷了 meta-write 这一个目录，没把它旁边的 _shared/ 一起拷过去。
四个 skill 共用那一份地基，必须整个 skills/ 一起拷。

解法二选一：
  1. 把整个 skills/ 目录完整拷到你放 skill 的位置
  2. 设环境变量 UPUP_SHARED 指向放着 fetch.py 的那个目录

找过这些地方：
""" + "\n".join("  " + (c or "(未设 UPUP_SHARED)") for c in cands))


sys.path.insert(0, _find_shared())
import fetch as F                      # noqa: E402
import rubric_check as R               # noqa: E402


def meta_of(url, timeout=20):
    """抓一页的 title 与 meta description。抓不到就返回 None，不编默认值。"""
    page = F.fetch(url, timeout=timeout)
    if page.get("reach") != "ok" or not page.get("html"):
        return {"url": url, "reach": page.get("reach"), "title": None, "description": None}
    f = F.facts(page["html"], base_url=page.get("final_url") or url)
    return {"url": page.get("final_url") or url, "reach": "ok",
            "title": f.get("title"), "description": f.get("meta_description")}


def render(res, page_type, keyword):
    L = []
    s = res["score"]
    L.append("verdict=%s  分数=%s%%  页型=%s  主词=%s" % (
        res["verdict"], s["percent"], page_type or "未给", keyword or "未给"))
    L.append("")
    for i in res["items"]:
        if not i["observed"]:
            L.append("  未观察  %-4s %-16s %s" % (i["id"], i["name"], i["reason"]))
            continue
        mark = "ok  " if i.get("pass") else "红  "
        sc = "gate" if i["kind"] == "gate" else "%d/3" % i["score"]
        L.append("  %s%-4s %-16s %-5s %s" % (mark, i["id"], i["name"], sc, i["detail"]))
    fails = [i for i in res["items"] if i["observed"] and not i.get("pass") and i.get("fix")]
    if fails:
        L.append("")
        L.append("先改这一个：")
        top = sorted(fails, key=lambda i: (i["kind"] != "gate", -(i.get("weight") or 0)))[0]
        L.append("  [%s] %s" % (top["id"], top["fix"]))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(
        description="判一对 title 与 description。不写内容，只判。写在 references/playbook.md")
    ap.add_argument("--url", help="线上地址，抓它当前的 title 与 description")
    ap.add_argument("--title", help="你新写的 title")
    ap.add_argument("--description", help="你新写的 description")
    ap.add_argument("--page-type", choices=R.PAGE_TYPES,
                    help="home / tool / pricing。不给的话 M6 记未观察")
    ap.add_argument("--keyword", default="", help="这一页的主词。不给的话 M3 记未观察")
    ap.add_argument("--peers", default="",
                    help="逗号分隔的同组页面地址，用来查 title 与 description 是否全组唯一")
    ap.add_argument("--json", help="写到这个文件")
    a = ap.parse_args()

    if not a.url and not (a.title or a.description):
        ap.error("要么给 --url 判现状，要么给 --title 与 --description 判新写的那一对")

    src = "手写"
    title, desc = a.title, a.description
    if a.url:
        got = meta_of(a.url)
        if got["reach"] != "ok":
            raise SystemExit("页面没取到（reach=%s）：%s\n"
                             "这不是 meta 写得不好，是页面本身取不到。先用 site-audit 查 G1 与 G2。"
                             % (got["reach"], a.url))
        src = got["url"]
        if title is None:
            title = got["title"]
        if desc is None:
            desc = got["description"]

    peers = []
    for u in [x.strip() for x in a.peers.split(",") if x.strip()]:
        p = meta_of(u)
        if p["reach"] == "ok":
            peers.append(p)

    res = R.score_meta(title, desc, keyword=a.keyword, page_type=a.page_type, peers=peers)
    res["input"] = {"source": src, "title": title, "description": desc,
                    "page_type": a.page_type, "keyword": a.keyword,
                    "peers_observed": len(peers)}

    print(render(res, a.page_type, a.keyword))
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print("\n写到 %s" % a.json)

    sys.exit(0 if res["verdict"] == "PASS" else (2 if res["verdict"] == "REJECT" else 1))


if __name__ == "__main__":
    main()
