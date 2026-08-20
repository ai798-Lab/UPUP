#!/usr/bin/env python3
# check_index.py: 文件索引与引用的机械自检。
#
# 存在的理由很具体：这条工作线上「文档里列了一个不存在的文件」这个错犯过三次。
# 三次都是靠人肉复查发现的，所以第四次改成机器查。
#
# 它断言四件事：
#   1. 文档里列出的每一个仓库内文件路径，真实存在
#   2. 文档里写的每一条 python3 命令，指向的脚本真实存在
#   3. references.md 的每一处 §N 引用，指向真实存在的小节
#   4. rubric.json 里每条 source 提到的 §N，同上
#
# 第 3 第 4 条是因为前身犯过「最吃重的主张挂在一个指向空处的引用上」。
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFS = os.path.join(ROOT, "skills", "_shared", "references.md")

_bad = []


def bad(m):
    _bad.append(m)
    print("  FAIL %s" % m)


def ok(m):
    print("  ok   %s" % m)


def md_files():
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in (".git", "__pycache__", "runs", "drafts")]
        for f in fn:
            if f.endswith(".md"):
                yield os.path.join(dp, f)


def _bases(doc_path):
    """一条路径可能相对哪些目录。文档里写 `rubric.json` 时指的是 _shared 里那份，
    写 `../_shared/fetch.py` 时相对文档自己的目录，都要认。"""
    b = [os.path.dirname(doc_path), ROOT, os.path.join(ROOT, "skills"),
         os.path.join(ROOT, "skills", "_shared")]
    sk = os.path.join(ROOT, "skills")
    if os.path.isdir(sk):
        b += [os.path.join(sk, d) for d in os.listdir(sk)
              if os.path.isdir(os.path.join(sk, d))]
    return b


def check_listed_paths():
    """**文件索引表格**第一列里的路径，必须真实存在。

    只查表格第一列，不查正文里的每一处反引号：正文里提到一个文件名多半是指代
    （「判据请改 rubric.json」），不是在给你一份索引。犯过三次的那个错发生在索引表里，
    所以这里就只钉索引表。

    运行产物（runs/ 与 drafts/ 下的东西）跳过：它们在跑之前本来就不存在。
    """
    n = 0
    for p in md_files():
        txt = open(p, encoding="utf-8").read()
        for line in txt.splitlines():
            line = line.strip()
            if not line.startswith("|") or line.count("|") < 3:
                continue
            first = line.split("|")[1].strip()
            m = re.match(r'^`([^`]+)`$', first)
            if not m:
                continue
            ref = m.group(1).strip()
            if ref.startswith(("http", "<", "runs/", "drafts/")) or " " in ref:
                continue
            if not re.search(r'\.(py|md|json|html)$', ref):
                continue
            if any(os.path.exists(os.path.normpath(os.path.join(b, ref))) for b in _bases(p)):
                n += 1
            else:
                bad("%s 的文件索引里列了不存在的 %s" % (os.path.relpath(p, ROOT), ref))
    ok("文件索引里的 %d 处路径全部存在" % n)


def check_commands():
    """文档里的 python3 命令，脚本必须存在。<skills> 与 <repo> 是占位符，按仓库根解析。"""
    n = 0
    for p in md_files():
        txt = open(p, encoding="utf-8").read()
        for m in re.finditer(r'python3\s+([^\s\\]+\.py)', txt):
            ref = m.group(1)
            real = (ref.replace("<skills>", os.path.join(ROOT, "skills"))
                       .replace("<repo>", ROOT))
            # README 里按「装在 ~/upup」写命令，检查时把它解析到本仓库根
            for home_form in ("~/upup", os.path.expanduser("~/upup")):
                if real.startswith(home_form):
                    real = ROOT + real[len(home_form):]
            if not os.path.isabs(real):
                real = os.path.normpath(os.path.join(os.path.dirname(p), real))
            if os.path.exists(real):
                n += 1
            else:
                bad("%s 里的命令指向不存在的脚本：%s" % (os.path.relpath(p, ROOT), ref))
    ok("文档里的 %d 条命令指向的脚本都存在" % n)


def refs_sections():
    txt = open(REFS, encoding="utf-8").read()
    return set(re.findall(r'(?m)^##\s+(\d+)\.', txt))


def check_section_refs():
    """每一处 §N 引用都要指向 references.md 里真实存在的小节。"""
    have = refs_sections()
    if not have:
        bad("references.md 里一个编号小节都没解析到，自检本身失效了")
        return
    n = 0
    targets = list(md_files()) + [os.path.join(ROOT, "skills", "_shared", "rubric.json")]
    for p in targets:
        txt = open(p, encoding="utf-8").read()
        for m in re.finditer(r'references\.md\s*§\s*(\d+)', txt):
            sec = m.group(1)
            if sec in have:
                n += 1
            else:
                bad("%s 引用了 references.md §%s，但那一节不存在" % (os.path.relpath(p, ROOT), sec))
    ok("%d 处 §N 引用全部指向真实存在的小节（现有小节：%s）"
       % (n, ",".join(sorted(have, key=int))))


def check_skill_frontmatter():
    """每个 SKILL.md 的 frontmatter 只能有 name 与 description，且 name 要和目录名一致。"""
    for dp in sorted(os.listdir(os.path.join(ROOT, "skills"))):
        d = os.path.join(ROOT, "skills", dp)
        if not os.path.isdir(d) or dp.startswith("_"):
            continue
        f = os.path.join(d, "SKILL.md")
        if not os.path.exists(f):
            bad("skills/%s 没有 SKILL.md" % dp)
            continue
        txt = open(f, encoding="utf-8").read()
        m = re.match(r'(?s)^---\n(.*?)\n---\n', txt)
        if not m:
            bad("skills/%s/SKILL.md 没有 frontmatter" % dp)
            continue
        keys = set(re.findall(r'(?m)^([a-z_]+):', m.group(1)))
        if keys - {"name", "description"}:
            bad("skills/%s/SKILL.md 的 frontmatter 有多余字段：%s" % (dp, keys - {"name", "description"}))
        name = re.search(r'(?m)^name:\s*(\S+)', m.group(1))
        if not name or name.group(1) != dp:
            bad("skills/%s/SKILL.md 的 name 与目录名不一致" % dp)
        else:
            ok("skills/%s/SKILL.md frontmatter 合规" % dp)


def check_no_hardcoded_home():
    """脚本里不许硬编码作者自己的机器路径。

    这条也是踩过的：作者的机器上永远复现不了用户的故障，因为路径写死在他自己家目录。
    """
    home = os.path.expanduser("~")
    user = os.path.basename(home)
    n = 0
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in (".git", "__pycache__")]
        for f in fn:
            if not f.endswith((".py", ".md", ".json", ".html")):
                continue
            p = os.path.join(dp, f)
            txt = open(p, encoding="utf-8", errors="replace").read()
            for pat in ("/Users/%s" % user, "/home/%s" % user):
                if pat in txt:
                    bad("%s 里硬编码了作者的机器路径 %s" % (os.path.relpath(p, ROOT), pat))
                    n += 1
    if n == 0:
        ok("没有任何文件硬编码作者的机器路径")


if __name__ == "__main__":
    print("文件索引与引用自检：")
    check_listed_paths()
    check_commands()
    check_section_refs()
    check_skill_frontmatter()
    check_no_hardcoded_home()
    print("\n%s" % ("全部通过" if not _bad else "%d 处不一致" % len(_bad)))
    sys.exit(1 if _bad else 0)
