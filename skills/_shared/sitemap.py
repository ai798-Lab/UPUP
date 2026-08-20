#!/usr/bin/env python3
# sitemap.py: sitemap 取、解析、抽样实测。
#
# 三个容易骗过检查器的地方，这里都堵了：
#   1. 软 404。很多站的 /sitemap.xml 不存在时返回 200 加一页 HTML。只看状态码会判成「有」，
#      得看 content-type 与根元素。
#   2. sitemap 里躺死链。文件本身格式全对，里面的地址一半是 404，这是最常见的沉默故障，
#      所以要抽几条真去请求。
#   3. 全站 lastmod 同一个日期。等于没有信息，会被直接忽略，但看起来像「每页都有 lastmod」。
#
# 抓不到一律记未观察，绝不返回空列表冒充「一条都没有」。
import datetime
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

# 出处：sitemaps.org 协议。两个都是硬上限，超了整份文件不被接受。
MAX_URLS_PER_FILE = 50000
MAX_BYTES_PER_FILE = 50 * 1024 * 1024
MAX_CHILD_SITEMAPS = 3          # 递归上限。大站的 index 能挂上百个子表，全跟进会把体检拖成十分钟
CANDIDATES = ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml", "/sitemap")


def _looks_like_xml(page):
    """判 sitemap 是不是真的 sitemap，不是伪装成 200 的 404 页。"""
    ctype = (page.get("headers") or {}).get("content-type", "")
    head = (page.get("html") or "")[:3000].lower()
    if "<html" in head[:400]:
        return False, "返回的是 HTML 页面，不是 XML。多半是软 404：地址不存在但服务器回了 200"
    if "<urlset" not in head and "<sitemapindex" not in head:
        return False, "根元素既不是 urlset 也不是 sitemapindex（content-type: %s）" % (ctype or "无")
    return True, None


def _parse_urlset(xml):
    """返回 [{loc, lastmod}]。"""
    out = []
    for blk in re.findall(r"(?is)<url>(.*?)</url>", xml) or []:
        loc = re.search(r"(?is)<loc>\s*([^<]+?)\s*</loc>", blk)
        if not loc:
            continue
        lm = re.search(r"(?is)<lastmod>\s*([^<]+?)\s*</lastmod>", blk)
        out.append({"loc": loc.group(1).strip(), "lastmod": lm.group(1).strip() if lm else None})
    if not out:
        out = [{"loc": x.strip(), "lastmod": None}
               for x in re.findall(r"(?is)<loc>\s*([^<]+?)\s*</loc>", xml)]
    return out


def _valid_lastmod(s):
    """W3C Datetime。只认日期与常见带时区的完整写法。"""
    if not s:
        return False
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            datetime.datetime.strptime(s.strip(), fmt)
            return True
        except ValueError:
            continue
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?([+-]\d{2}:\d{2}|Z)$", s.strip()))


def discover(origin, robots_sitemap_lines=None, timeout=15):
    """按三个来源找 sitemap：robots 里声明的、常见路径、根路径。

    返回 dict：observed 为 False 时表示一处都没找到或全取不到，
    上层要区分「站上确实没有 sitemap」与「有但我们取不到」，两者动作不同。
    """
    tried = []
    base = origin.rstrip("/")
    urls = []
    for line in (robots_sitemap_lines or []):
        urls.append(urllib.parse.urljoin(base + "/", line.strip()))
    urls += [base + c for c in CANDIDATES]

    seen = set()
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        p = F.fetch(u, timeout=timeout)
        ok_xml, why = (_looks_like_xml(p) if p["reach"] == "ok" else (False, "取不到（%s）" % (p["status"] or p["error"])))
        tried.append({"url": u, "status": p["status"], "reach": p["reach"], "usable": ok_xml,
                      "why": why})
        if ok_xml:
            return {"observed": True, "url": u, "page": p, "tried": tried, "reason": None}
    return {"observed": False, "url": None, "page": None, "tried": tried,
            "reason": "试了 %d 个地址，没有一个返回可解析的 sitemap XML" % len(tried)}


def collect(origin, robots_sitemap_lines=None, timeout=15, max_urls=2000):
    """取 sitemap 并展开 index。返回全部条目与格式问题清单。"""
    d = discover(origin, robots_sitemap_lines, timeout=timeout)
    out = {"observed": d["observed"], "source": d["url"], "tried": d["tried"],
           "reason": d["reason"], "entries": None, "issues": [], "children": [],
           "truncated": False}
    if not d["observed"]:
        return out

    page = d["page"]
    xml = page["html"]
    size = len((page["html"] or "").encode("utf-8", "replace"))
    if size > MAX_BYTES_PER_FILE:
        out["issues"].append({"id": "size", "detail": "单文件 %d 字节，超过 50MB 上限" % size,
                              "fix": "拆成 sitemap index"})

    if "<sitemapindex" in xml[:3000].lower():
        child_urls = [m.strip() for m in re.findall(r"(?is)<sitemap>.*?<loc>\s*([^<\s]+)\s*</loc>", xml)]
        out["children"] = child_urls
        entries = []
        for cu in child_urls[:MAX_CHILD_SITEMAPS]:
            cp = F.fetch(cu, timeout=timeout)
            if cp["reach"] != "ok":
                out["issues"].append({"id": "child_unreachable",
                                      "detail": "子 sitemap 取不到：%s（%s）" % (cu, cp["status"]),
                                      "fix": "确认这个地址能公开访问"})
                continue
            entries += _parse_urlset(cp["html"])
            if len(entries) >= max_urls:
                break
        if len(child_urls) > MAX_CHILD_SITEMAPS:
            out["truncated"] = True
            out["issues"].append({
                "id": "index_truncated",
                "detail": "index 里有 %d 个子 sitemap，只展开了前 %d 个" % (
                    len(child_urls), MAX_CHILD_SITEMAPS),
                "fix": "本次结论只覆盖被展开的部分，不要当成全站结论"})
        out["entries"] = entries[:max_urls]
    else:
        entries = _parse_urlset(xml)
        if len(entries) > MAX_URLS_PER_FILE:
            out["issues"].append({"id": "too_many",
                                  "detail": "单文件 %d 条，超过 5 万条上限" % len(entries),
                                  "fix": "拆成 sitemap index"})
        out["entries"] = entries[:max_urls]

    if out["entries"] is not None:
        out["issues"] += hygiene(out["entries"], origin)
    return out


def hygiene(entries, origin):
    """URL 卫生与 lastmod 可信度。每条问题都带示例，不给「有些 URL 有问题」这种话。"""
    issues = []
    host = F.bare_host(origin)
    rel = [e["loc"] for e in entries if not re.match(r"^https?://", e["loc"])]
    other = [e["loc"] for e in entries
             if re.match(r"^https?://", e["loc"]) and F.bare_host(e["loc"]) != host]
    frag = [e["loc"] for e in entries if "#" in e["loc"]]
    schemes = set(urllib.parse.urlparse(e["loc"]).scheme
                  for e in entries if re.match(r"^https?://", e["loc"]))

    if rel:
        issues.append({"id": "relative_urls", "detail": "%d 条是相对路径，示例 %s" % (len(rel), rel[:2]),
                       "fix": "sitemap 里必须写完整的绝对地址"})
    if other:
        issues.append({"id": "cross_host", "detail": "%d 条指向别的域名，示例 %s" % (len(other), other[:2]),
                       "fix": "一个 sitemap 只能装同一个 host 的地址"})
    if frag:
        issues.append({"id": "fragment", "detail": "%d 条带 # 锚点，示例 %s" % (len(frag), frag[:2]),
                       "fix": "去掉 # 后面的部分"})
    if len(schemes) > 1:
        issues.append({"id": "mixed_scheme", "detail": "同时有 http 和 https 两种协议",
                       "fix": "统一成 https"})

    lms = [e["lastmod"] for e in entries if e["lastmod"]]
    if lms:
        bad = [x for x in lms if not _valid_lastmod(x)]
        if bad:
            issues.append({"id": "lastmod_format",
                           "detail": "%d 条 lastmod 格式不合法，示例 %s" % (len(bad), bad[:2]),
                           "fix": "改成 W3C Datetime，例如 2026-08-20 或 2026-08-20T10:00:00+08:00"})
        if len(entries) >= 5 and len(set(lms)) == 1 and len(lms) == len(entries):
            issues.append({"id": "lastmod_uniform",
                           "detail": "全站 %d 条 lastmod 都是同一个日期 %s" % (len(entries), lms[0]),
                           "fix": "全站同日等于没有信息，会被直接忽略。让它反映每页真实的更新时间，"
                                  "或者干脆不写"})
    return issues


def sample_check(entries, n=5, timeout=12):
    """抽 n 条真去请求。分开报「死链」与「被拦」，被拦不算死链。

    取样用等距抽样而不是随机：随机数会让同一个站两次体检结果不可比，
    而这个 skill 的 --compare 模式要求两次跑出来的东西能对得上。
    """
    if not entries:
        return {"observed": False, "reason": "sitemap 里没有条目", "checked": []}
    step = max(1, len(entries) // n)
    picked = [entries[i]["loc"] for i in range(0, len(entries), step)][:n]
    checked = []
    for u in picked:
        r = F.status_only(u, timeout=timeout)
        cls = F.reach(r["status"], r["error"])
        checked.append({"url": u, "status": r["status"], "reach": cls,
                        "redirect_to": r["location"]})
    dead = [c for c in checked if c["reach"] == "dead"]
    blocked = [c for c in checked if c["reach"] == "blocked"]
    redirect = [c for c in checked if c["status"] and 300 <= c["status"] < 400]
    return {"observed": True, "checked": checked, "sampled": len(checked),
            "dead": dead, "blocked": blocked, "redirect": redirect,
            "note": ("抽样里有 %d 条被防护规则拦住，那不是死链，不计入死链数" % len(blocked))
                    if blocked else None}


if __name__ == "__main__":
    import json
    if len(sys.argv) < 2:
        print("用法: python3 sitemap.py <origin>", file=sys.stderr)
        sys.exit(2)
    origin = sys.argv[1] if sys.argv[1].startswith("http") else "https://" + sys.argv[1]
    c = collect(origin)
    s = sample_check(c["entries"] or [])
    print(json.dumps({"source": c["source"], "count": len(c["entries"] or []),
                      "issues": c["issues"], "sample": s.get("checked")},
                     ensure_ascii=False, indent=2))
