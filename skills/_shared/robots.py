#!/usr/bin/env python3
# robots.py: 爬虫进不进得来。这是 SEO 和 GEO 真正分道的地方，所以单独一个模块。
#
# 三条判定纪律，每条都是踩过的坑：
#   1. robots.txt 返回 404 是合法且正常的状态，等于全站放行。不扣分、不给动作。
#      判成故障会让用户去「修」一个本来就没问题的东西。
#   2. 只有 403 / 超时 / 5xx 才是「未观察」。未观察时上层一个字都不许说「去改 robots」，
#      否则给出的验证命令永远不会变绿。
#   3. robots 放行不等于请求放行。CDN 的 UA 规则是另一层，要真换 UA 发一次才知道。
#      两者分开报：一个动作指向 robots.txt，另一个指向 CDN 后台。
#
# UA 字符串的出处与复核日期见 references.md §1，此处只放字符串，不复述结论。
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
try:
    import fetch as F
except ModuleNotFoundError:
    raise SystemExit("""
找不到同目录的 fetch.py。

多半是只拷了一个 skill 目录，没把 skills/_shared/ 一起拷过去。

解法二选一：
  1. 把整个 skills/ 目录完整拷到你放 skill 的位置
  2. 设环境变量 UPUP_SHARED 指向放着 fetch.py 的那个目录
""")

# 四档。比三档多分出 ai_search，因为它和 ai_user 的后果不是一回事：
# ai_search 挡住 = AI 的索引里没有你；ai_user 挡住 = AI 当场想引你都取不到页面。
BOTS = {
    "search":    ["Googlebot", "Bingbot"],
    "ai_search": ["OAI-SearchBot", "Claude-SearchBot", "PerplexityBot"],
    "ai_user":   ["ChatGPT-User", "Claude-User", "Perplexity-User"],
    "training":  ["GPTBot", "ClaudeBot", "CCBot", "Google-Extended"],
}

CLASS_LABEL = {
    "search":    "传统检索",
    "ai_search": "AI 检索索引",
    "ai_user":   "AI 实时取页",
    "training":  "训练抓取",
}

# 训练档拦不拦是站主的选择，不判对错，只报事实。其余三档被拦都是要给动作的。
OPTIONAL_CLASSES = {"training"}


def _groups(txt):
    """把 robots.txt 切成组。连续的 User-agent 行共享同一组规则。"""
    groups, cur = [], None
    for raw in txt.splitlines():
        line = raw.split("#")[0].strip()
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            if cur is None or cur["rules"]:
                cur = {"agents": [], "rules": []}
                groups.append(cur)
            cur["agents"].append(v.lower())
        elif k in ("allow", "disallow") and cur is not None:
            cur["rules"].append((k, v))
    return groups


def robots_for(txt, agent, path="/"):
    """返回 (放行?, 命中的组类型, 命中规则原文)。

    按 RFC 9309 的最长匹配：路径最长的规则胜出，同长时 Allow 胜。
    不是字符串包含，那会把 Disallow: /admin 判成挡住了 /admin-guide 之外的一切。
    """
    a = agent.lower()
    chosen, kind = None, "none"
    gs = _groups(txt)
    for g in gs:
        if a in g["agents"]:
            chosen, kind = g, "explicit"
            break
    if chosen is None:
        for g in gs:
            if "*" in g["agents"]:
                chosen, kind = g, "wildcard"
                break
    if chosen is None:
        return True, "none", "robots 里没有适用它的组，默认放行"
    best, best_len = None, -1
    for k, v in chosen["rules"]:
        if v == "":
            continue
        pat = "^" + re.escape(v).replace(r"\*", ".*").replace(r"\$", "$")
        if re.match(pat, path) and (len(v) > best_len or (len(v) == best_len and k == "allow")):
            best, best_len = (k, v), len(v)
    if best is None:
        return True, kind, "%s 组内没有命中 %s 的规则，放行" % (kind, path)
    return best[0] == "allow", kind, "%s: %s" % (best[0].capitalize(), best[1])


def report(origin, path="/", timeout=15):
    """站级 robots 判定。返回 observed / 四档结果 / 声明的 sitemap 地址。"""
    url = origin.rstrip("/") + "/robots.txt"
    r = F.fetch(url, timeout=timeout)
    out = {"url": url, "status": r["status"], "observed": False, "reason": None,
           "no_robots_file": False, "classes": None, "sitemap_lines": [], "raw": None}

    # 404：没有 robots.txt。这是正常状态，等于全站放行，不是故障。
    if r["reach"] == "dead" and r["status"] == 404:
        out.update(observed=True, no_robots_file=True,
                   classes={c: {a: {"allowed": True, "group": "none",
                                    "rule": "站上没有 robots.txt，默认全放行"}
                                for a in ags} for c, ags in BOTS.items()},
                   reason="没有 robots.txt。这是合法状态，等于全站放行，不用改")
        return out

    if r["reach"] != "ok":
        out["reason"] = "robots.txt 取不到（%s，%s）。不判定，也不给改 robots 的动作" % (
            r["status"], r["error"] or r["reach"])
        return out

    txt = r["html"]
    if "<html" in txt[:400].lower():
        out["reason"] = "robots.txt 返回的是 HTML 页面，不是 robots 文本。不判定"
        out["raw"] = txt[:300]
        return out
    if not txt.strip():
        out.update(observed=True, no_robots_file=True,
                   classes={c: {a: {"allowed": True, "group": "none", "rule": "空文件，全放行"}
                                for a in ags} for c, ags in BOTS.items()},
                   reason="robots.txt 是空的，等于全放行")
        return out

    out.update(
        observed=True,
        classes={c: {a: dict(zip(("allowed", "group", "rule"), robots_for(txt, a, path)))
                     for a in ags} for c, ags in BOTS.items()},
        sitemap_lines=re.findall(r"(?im)^\s*sitemap\s*:\s*(\S+)", txt),
        raw=txt[:1500])
    return out


def blocked_classes(rep):
    """哪几档被挡了。未观察时返回 None，让上层知道这不是「没被挡」。"""
    if not rep.get("observed"):
        return None
    out = {}
    for cls, agents in (rep.get("classes") or {}).items():
        blocked = [a for a, v in agents.items() if not v["allowed"]]
        if blocked:
            out[cls] = blocked
    return out


def noindex_signals(page):
    """比 robots.txt 更容易误伤的两处：页面级 meta robots 与响应头 X-Robots-Tag。

    这两处站主通常看不见（框架或平台默认塞的），但效力比 robots.txt 更狠：
    robots.txt 只是不让爬，noindex 是爬到了也不许收录。
    """
    out = []
    html = page.get("html") or ""
    m = re.search(r'(?is)<meta[^>]+name=["\']robots["\'][^>]*content=["\']([^"\']*)', html)
    if m and re.search(r'\bnoindex\b', m.group(1), re.I):
        out.append({"where": "页面 <meta name=robots>", "value": m.group(1).strip(),
                    "fix": "删掉这个 meta 标签里的 noindex"})
    xr = (page.get("headers") or {}).get("x-robots-tag")
    if xr and re.search(r'\bnoindex\b', xr, re.I):
        out.append({"where": "HTTP 响应头 X-Robots-Tag", "value": xr,
                    "fix": "去托管平台或服务端配置里删掉这个响应头。这一处站主通常不知道自己带着"})
    return out


def robots_txt_noindex(rep):
    """robots.txt 里写 noindex。这个写法早已不被支持，写了等于没写，
    但站主以为生效了，所以要单独点名，不然他会一直以为那几页没被收录。"""
    raw = rep.get("raw") or ""
    hits = re.findall(r"(?im)^\s*noindex\s*:\s*(\S+)", raw)
    return hits


def ua_probe(url, agents=("OAI-SearchBot", "PerplexityBot", "ChatGPT-User"), timeout=15):
    """robots 放行不等于请求放行。真换 UA 各发一次，看 CDN 放不放。

    这一层和 robots.txt 是两回事：robots 写着放行、实际 403，动作是去 CDN 放行 UA，
    不是去改 robots。判错方向会让用户改一整天都不见效。
    """
    out = {}
    for a in agents:
        r = F.fetch(url, ua="%s/1.0" % a, timeout=timeout)
        out[a] = {"status": r["status"], "reach": r["reach"],
                  "bytes": len(r["html"] or ""), "error": r["error"]}
    return out


def cdn_blocks(probe, baseline_reach="ok"):
    """浏览器 UA 拿得到、爬虫 UA 拿不到，就是 CDN 层在挡。"""
    if baseline_reach != "ok":
        return None
    return [a for a, v in probe.items() if v["reach"] == "blocked"]


if __name__ == "__main__":
    import json
    if len(sys.argv) < 2:
        print("用法: python3 robots.py <origin> [path]", file=sys.stderr)
        sys.exit(2)
    origin = sys.argv[1]
    if not origin.startswith("http"):
        origin = "https://" + origin
    rep = report(origin, sys.argv[2] if len(sys.argv) > 2 else "/")
    rep.pop("raw", None)
    print(json.dumps({"robots": rep, "blocked": blocked_classes(rep)},
                     ensure_ascii=False, indent=2))
