#!/usr/bin/env python3
# fetch.py: 页面事实的唯一提取口。三个 skill 只从这里拿页面事实。
#
# 约束（写死，不许放宽）：
#   1. 纯 python3 标准库，零第三方依赖，零安装。
#   2. 只取「初始 HTML」，即爬虫不跑 JS 时看到的东西。JS 渲染后才出现的正文，这里就是拿不到，
#      拿不到如实报，不去猜、不折算。
#   3. 抓失败一律返回 error 并把正文类字段置 None，绝不返回 0。上层报「未观察」，
#      永远不要把「没抓到」写成「没有」。
#   4. 403 不等于站下线。独立开发者的站大量挂 CDN 防护，把「被拦」判成「你的网站挂了」
#      会大面积误伤，所以 reach 把状态码分成 ok / blocked / dead 三类，上层照类给动作。
import gzip
import io
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

DEFAULT_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

_BLOCK_TAGS = r'(?is)<(script|style|head|noscript|svg|template)[^>]*>.*?</\1>'
_CJK = r'一-鿿぀-ヿ가-힯'

# 被拦：站是活的，是防护规则挡住了这次请求。动作指向 CDN，不指向部署。
BLOCKED_STATUS = {401, 403, 429, 451}


def words(text):
    """中英混排的词表。CJK 逐字一词，拉丁按词。"""
    if not text:
        return []
    return re.findall(r'[A-Za-z0-9][A-Za-z0-9\'’\-]*|[' + _CJK + r']', text)


def clean_text(html):
    """剥掉 script/style/head/noscript/svg 后的纯正文。"""
    if not html:
        return ""
    h = re.sub(_BLOCK_TAGS, ' ', html)
    h = re.sub(r'(?s)<!--.*?-->', ' ', h)
    h = re.sub(r'(?s)<[^>]+>', ' ', h)
    h = re.sub(r'&nbsp;|&#160;', ' ', h)
    h = re.sub(r'&amp;', '&', h)
    h = re.sub(r'&[a-zA-Z#0-9]{2,8};', ' ', h)
    return re.sub(r'\s+', ' ', h).strip()


def bare_host(url):
    """域名去掉 www. 前缀。注意不能用 lstrip('www.')，那是按字符集剥离，
    会把 wallet.com 剥成 allet.com。"""
    netloc = urllib.parse.urlparse(url if '://' in url else 'https://' + url).netloc.lower()
    return re.sub(r'^www\.', '', netloc.split(':')[0])


def _decode(raw, headers):
    enc = (headers.get('Content-Encoding') or '').lower()
    if 'gzip' in enc:
        try:
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        except Exception:
            pass
    elif 'deflate' in enc:
        try:
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        except Exception:
            pass
    charset = None
    ctype = headers.get('Content-Type') or ''
    m = re.search(r'charset=["\']?([\w\-]+)', ctype, re.I)
    if m:
        charset = m.group(1)
    if not charset:
        m = re.search(rb'<meta[^>]+charset=["\']?([\w\-]+)', raw[:4096], re.I)
        if m:
            charset = m.group(1).decode('ascii', 'replace')
    try:
        return raw.decode(charset or 'utf-8', 'replace')
    except (LookupError, TypeError):
        return raw.decode('utf-8', 'replace')


def reach(status, error):
    """把这次请求的结果分三类。判据只看状态码，不看内容。

    ok       正常拿到
    blocked  站活着，被防护规则拦了。动作：去 CDN 放行 UA。不许说成「网站下线」
    dead     地址或部署真有问题。动作：查地址与部署
    unknown  连接层就失败（超时 / DNS / TLS），既不能说活也不能说死，标未观察
    """
    if status is None:
        return "unknown"
    if 200 <= status < 300:
        return "ok"
    if status in BLOCKED_STATUS:
        return "blocked"
    if status == 404 or status >= 500:
        return "dead"
    return "unknown"


def fetch(url, timeout=20, ua=DEFAULT_UA, method="GET", headers=None):
    """取初始 HTML。返回 dict，永远带 error 键（None 表示成功）与 reach 分类。"""
    out = {"url": url, "final_url": None, "status": None, "html": "", "headers": {},
           "elapsed_ms": None, "error": None, "fetched_with_ua": ua, "reach": "unknown"}
    if not re.match(r'^https?://', url):
        url = "https://" + url
        out["url"] = url
    hdr = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    hdr.update(headers or {})
    req = urllib.request.Request(url, headers=hdr, method=method)
    t0 = time.time()
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            raw = r.read()
            out["status"] = r.status
            out["final_url"] = r.geturl()
            out["headers"] = {k.lower(): v for k, v in r.headers.items()}
            out["html"] = _decode(raw, r.headers)
    except urllib.error.HTTPError as e:
        out["status"] = e.code
        out["final_url"] = url
        out["headers"] = {k.lower(): v for k, v in (e.headers or {}).items()}
        try:
            out["html"] = _decode(e.read(), e.headers)
        except Exception:
            pass
        out["error"] = "http_%s" % e.code
    except Exception as e:
        out["error"] = "%s: %s" % (type(e).__name__, e)
    out["elapsed_ms"] = int((time.time() - t0) * 1000)
    out["reach"] = reach(out["status"], out["error"])
    return out


def status_only(url, timeout=12, ua=DEFAULT_UA):
    """不跟随重定向拿状态码与 Location。用来验 canonical 是不是 200 直达。"""
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    op = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": ua}, method="HEAD")
    try:
        with op.open(req, timeout=timeout) as r:
            return {"status": r.status, "location": r.headers.get("Location"), "error": None}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "location": (e.headers or {}).get("Location"), "error": None}
    except Exception as e:
        return {"status": None, "location": None, "error": "%s: %s" % (type(e).__name__, e)}


def _tags(html, name, limit=40):
    raw = re.findall(r'(?is)<%s[^>]*>(.*?)</%s>' % (name, name), html)
    seen, res = set(), []
    for x in raw:
        t = clean_text(x)
        if t and t not in seen:
            seen.add(t)
            res.append(t[:200])
        if len(res) >= limit:
            break
    return res


def sentences(text):
    """按中英句末标点切句，只留够长的。"""
    parts = re.split(r'(?<=[.!?。！？])\s+|(?<=[。！？])', text or "")
    return [p.strip() for p in parts if len(p.strip()) >= 20]


def jsonld_blocks(html):
    """返回每个 JSON-LD 块的解析结果，坏块单独标出来。

    坏掉的 JSON-LD 等于完全不存在，但站主以为自己做了，所以 parse 失败要单独可见，
    不能像取 @type 那样用正则兜底糊过去。
    """
    out = []
    for raw in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html or ""):
        item = {"raw": raw.strip()[:2000], "ok": False, "data": None, "error": None}
        try:
            item["data"] = json.loads(raw.strip())
            item["ok"] = True
        except Exception as e:
            item["error"] = "%s: %s" % (type(e).__name__, e)
        out.append(item)
    return out


def jsonld_types(html):
    """返回 (类型列表, 块数, 坏块数)。坏块的类型用正则兜底，但坏块数照报。"""
    blocks = jsonld_blocks(html)
    types, broken = [], 0

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

    for b in blocks:
        if b["ok"]:
            walk(b["data"])
        else:
            broken += 1
            types += re.findall(r'"@type"\s*:\s*"([^"]+)"', b["raw"])
    return sorted(set(types)), len(blocks), broken


def facts(html, base_url=""):
    """从 HTML 提出全部页面事实。纯函数，不联网。"""
    html = html or ""
    body = clean_text(html)
    ws = words(body)
    host = bare_host(base_url) if base_url else ""

    hrefs = re.findall(r'(?i)<a[^>]+href=["\']([^"\'#][^"\']*)["\']', html)
    internal, external = [], []
    for h in hrefs:
        if h.startswith('/') or (host and host in h):
            internal.append(h)
        elif re.match(r'^https?://', h):
            external.append(h)
    ext_domains = sorted(set(bare_host(u) for u in external if urllib.parse.urlparse(u).netloc))

    imgs = []
    for tag in re.findall(r'(?is)<img[^>]*>', html):
        src_m = re.search(r'(?i)src=["\']([^"\']+)', tag)
        alt_m = re.search(r'(?i)alt=["\']([^"\']*)', tag)
        imgs.append({"src": (src_m.group(1)[:200] if src_m else ""),
                     "alt": (alt_m.group(1) if alt_m else None)})

    ld_types, ld_blocks, ld_broken = jsonld_types(html)
    sents = sentences(body)
    title_m = re.search(r'(?is)<title[^>]*>(.*?)</title>', html)
    desc_m = re.search(r'(?is)<meta[^>]+name=["\']description["\'][^>]*content=["\']([^"\']*)', html)
    lang_m = re.search(r'(?is)<html[^>]*\blang=["\']([\w\-]+)', html)
    canon = re.findall(r'(?is)<link[^>]+rel=["\']canonical["\'][^>]*>', html)
    canon_hrefs = [(re.search(r'(?i)href=["\']([^"\']+)', c) or [None, None])[1]
                   if re.search(r'(?i)href=["\']([^"\']+)', c) else None for c in canon]
    meta_robots = re.search(
        r'(?is)<meta[^>]+name=["\']robots["\'][^>]*content=["\']([^"\']*)', html)

    return {
        "title": clean_text(title_m.group(1)) if title_m else None,
        "meta_description": desc_m.group(1)[:300] if desc_m else None,
        "meta_robots": meta_robots.group(1).strip().lower() if meta_robots else None,
        "lang": lang_m.group(1) if lang_m else None,
        "canonical": [c for c in canon_hrefs if c],
        "h1": _tags(html, "h1"),
        "h1_count": len([x for x in re.findall(r'(?is)<h1[^>]*>(.*?)</h1>', html) if clean_text(x)]),
        "h2": _tags(html, "h2"),
        "h3": _tags(html, "h3"),
        "body_text": body,
        "word_count": len(ws),
        "first_50_words": " ".join(ws[:50]),
        "jsonld_types": ld_types,
        "jsonld_blocks": ld_blocks,
        "jsonld_broken": ld_broken,
        "internal_link_count": len(set(internal)),
        "external_link_count": len(set(external)),
        "external_domains": ext_domains[:30],
        "img_count": len(imgs),
        "img_with_alt": sum(1 for i in imgs if i["alt"]),
        "images": imgs[:30],
        "table_count": len(re.findall(r'(?i)<table[ >]', html)),
        "list_count": len(re.findall(r'(?i)<(ul|ol)[ >]', html)),
        "sentences": sents,
        "sentences_with_number": [s for s in sents if re.search(r'\d', s)],
    }


def extract(url, timeout=20, ua=DEFAULT_UA):
    """fetch + facts。抓失败时 facts 为 None，绝不返回一堆 0。"""
    page = fetch(url, timeout=timeout, ua=ua)
    if page["reach"] != "ok" or not page["html"]:
        page["facts"] = None
        page["observed"] = False
        return page
    page["facts"] = facts(page["html"], base_url=page["final_url"] or url)
    page["observed"] = True
    return page


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 fetch.py <url>  # 打印该页可提取事实的 JSON", file=sys.stderr)
        sys.exit(2)
    p = extract(sys.argv[1])
    if p["facts"]:
        p["facts"].pop("body_text", None)
        p["facts"]["sentences"] = p["facts"]["sentences"][:5]
        p["facts"]["sentences_with_number"] = p["facts"]["sentences_with_number"][:5]
    p.pop("html", None)
    print(json.dumps(p, ensure_ascii=False, indent=2))
