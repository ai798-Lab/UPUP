#!/usr/bin/env python3
# gate.py: page-write 的机械闸入口。判据一条都不在这里。
#
# 判据在 _shared/rubric.json，算分在 _shared/rubric_check.py。
# 这里只做三件事：找到共享地基、把草稿和对照组喂进去、把结果印出来。
#
# 改的永远是内容，不是评分器。为了让一份草稿过关去动 rubric.json，等于把尺子锯短。
import argparse
import json
import os
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

多半是只拷了 page-write 这一个目录，没把它旁边的 _shared/ 一起拷过去。
三个 skill 共用那一份地基，必须整个 skills/ 一起拷。

解法二选一：
  1. 把整个 skills/ 目录完整拷到你放 skill 的位置
  2. 设环境变量 UPUP_SHARED 指向放着 fetch.py 的那个目录

找过这些地方：
  %s
""" % "\n  ".join(str(c) for c in cands))


sys.path.insert(0, _find_shared())
import rubric_check as RC   # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="page-write 机械闸")
    ap.add_argument("--draft", required=True, help="草稿 md")
    ap.add_argument("--question", required=True, help="目标问题")
    ap.add_argument("--winners", help="winners.py 的产物，用它的事实密度中位数当通过线")
    ap.add_argument("--self-host", help="你自己的域名。引自己站的数据算一手来源")
    ap.add_argument("--json", help="把结果写到这个文件")
    ap.add_argument("--offline", action="store_true",
                    help="不去请求来源页。W3 / W5 会记未观察，不判失败")
    a = ap.parse_args()

    with open(a.draft, encoding="utf-8") as f:
        draft = f.read()

    comparables = None
    if a.winners:
        with open(a.winners, encoding="utf-8") as f:
            w = json.load(f)
        b = w.get("bench") or {}
        if b.get("usable_as_threshold"):
            comparables = b.get("fact_density_list")

    fetcher = None
    if a.offline:
        def fetcher(url, timeout=12):
            return {"ok": False, "status": None, "reach": "unknown", "text": "",
                    "note": "--offline，没有去请求"}

    try:
        res = RC.score_write(draft, question=a.question, fetch_source=fetcher,
                             comparables=comparables, self_host=a.self_host)
    except ValueError as e:
        raise SystemExit("用法错误：%s\n草稿里必须有一个 ```html 或 ```markdown 的可上线内容块。" % e)

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)

    print("verdict=%s  机械分=%s%%" % (res["verdict"], res["score"]["percent"]))
    if res["failed_gates"]:
        print("门槛未过：%s" % ", ".join(res["failed_gates"]))
    for i in res["items"]:
        if i["observed"] and not i["pass"]:
            print("  未过 %-3s %-16s %s" % (i["id"], i["name"], i["detail"]))
            if i.get("fix"):
                print("       动作：%s" % i["fix"])
    for u in res["unobserved"]:
        print("  未观察 %-3s %s" % (u["id"], u["reason"]))
    if res["unobserved"]:
        print("\n未观察不等于通过，也不等于零分。上面这几项这次没测到，别当成过了。")
    return {"PASS": 0, "REWORK": 1, "REJECT": 2}[res["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
