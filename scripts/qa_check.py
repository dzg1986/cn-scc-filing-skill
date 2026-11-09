#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布前自检：结构完整性、规范合规、敏感信息、典型问题覆盖度。

用法： python3 scripts/qa_check.py
退出码：0 通过；1 有 error
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(ROOT, "skills", "cn-scc-filing")
REQUIRED = [
    "SKILL.md",
    "references/01-routing.md",
    "references/02-thresholds-and-exemptions.md",
    "references/03-scc-general.md",
    "references/04-scc-gba.md",
    "references/05-timeline.md",
    "references/06-faq.md",
    "references/07-rejected-and-boundary.md",
    "references/08-law-index.md",
]
ALLOWED_FM = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
CASES = [
    ("深圳→香港 员工信息 300 人", ["大湾区", "无数量限制", "集体合同", "分别备案"]),
    ("内地→新加坡 员工信息", ["跨境人力资源管理", "集体合同"]),
    ("当年累计 50 万人", ["10 万人以上、不满 100 万人", "标准合同", "认证"]),
    ("敏感个人信息 1.2 万人", ["1 万人以上敏感", "安全评估"]),
    ("材料被退回怎么补", ["PIA", "必要性", "退回"]),
    ("海南与内地之间", ["海南", "境内"]),
    ("与境外机构签不了合同", ["无法与境外机构", "说明情况"]),
    ("要求拆分数量少报", ["数量拆分", "不得"]),
]
# 敏感信息正则：手机号 / 固话 / 邮箱 / 企业名（写法已避免误伤规则文档自身）
SENSITIVE = r"1[3-9]\d{9}|0\d{2,3}[-—]?\d{7,8}|[\w.\-]+@[\w.\-]+\.\w+|有限(公司|责任公司)|股份有限(公司)"

# 有意公开的商务邮箱白名单：出现在 README 的公开联系方式，不属于"泄露"
PUBLIC_EMAILS = ("ding.zhengan@ghlawyer.net",)


def main():
    errors, warns = [], []

    for f in REQUIRED:
        if not os.path.exists(os.path.join(SKILL_DIR, f)):
            errors.append(f"缺文件：{f}")

    skill_path = os.path.join(SKILL_DIR, "SKILL.md")
    text = open(skill_path, encoding="utf-8").read()

    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        errors.append("SKILL.md 缺 front matter")
        return report(errors, warns)

    fm = m.group(1)
    get = lambda k: (re.search(rf"^{k}:\s*(.*)$", fm, re.M) or [None, None])[1]
    name, desc = get("name"), get("description")

    if name != os.path.basename(SKILL_DIR):
        errors.append(f"name({name}) 与目录名不一致")
    if not name or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
        errors.append("name 须为小写字母/数字/连字符，且无连续连字符")
    if len(name or "") > 64:
        errors.append("name 超过 64 字符")
    if not desc:
        errors.append("缺 description")
    elif len(desc) > 1024:
        errors.append(f"description 长度 {len(desc)} 超过 1024")

    keys = {x.group(1) for x in re.finditer(r"^([a-z\-]+):", fm, re.M)}
    if keys - ALLOWED_FM:
        warns.append(f"非标准 front matter 字段：{sorted(keys - ALLOWED_FM)}（投 claude.ai 可能报错）")

    body = text[m.end():]
    if len(body.split("\n")) > 500:
        warns.append("正文超过 500 行，建议拆分到 references/")

    for ref in set(re.findall(r"references/([0-9a-z\-]+\.md)", text)):
        if not os.path.exists(os.path.join(SKILL_DIR, "references", ref)):
            errors.append(f"引用了不存在的文件：references/{ref}")

    corpus = []
    for dp, _, fs in os.walk(SKILL_DIR):
        for fn in fs:
            if fn.endswith(".md"):
                corpus.append(open(os.path.join(dp, fn), encoding="utf-8").read())
    allt = "\n".join(corpus)

    for q, keys_ in CASES:
        miss = [k for k in keys_ if k not in allt]
        if miss:
            errors.append(f"覆盖度不足：{q} 缺 {miss}")

    # 占位符守卫：发布前必须把 {{...}} 全部替换
    for dp, _, fs in os.walk(ROOT):
        if ".git" in dp:
            continue
        for fn in fs:
            if not fn.endswith((".md", ".txt", ".json", ".yml", ".yaml")):
                continue
            fp = os.path.join(dp, fn)
            txt = open(fp, encoding="utf-8").read()
            if "{{" in txt and "qa_check.py" not in fp:
                ph = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", txt)))
                errors.append(f"未替换的占位符：{os.path.relpath(fp, ROOT)} {ph}")

    hits = []
    for dp, _, fs in os.walk(ROOT):
        if ".git" in dp:
            continue
        for fn in fs:
            if not fn.endswith((".md", ".txt", ".json", ".yml", ".yaml")):
                continue
            fp = os.path.join(dp, fn)
            for i, line in enumerate(open(fp, encoding="utf-8"), 1):
                scan = line
                for e in PUBLIC_EMAILS:
                    scan = scan.replace(e, "<public-email>")
                if re.search(SENSITIVE, scan):
                    hits.append(f"{os.path.relpath(fp, ROOT)}:{i}")
    if hits:
        errors.append(f"疑似敏感信息：{hits[:5]}")

    return report(errors, warns)


def report(errors, warns):
    print("=" * 46)
    for w in warns:
        print("[warn ]", w)
    for e in errors:
        print("[ERROR]", e)
    if not errors:
        print("[ OK  ] 结构、规范、覆盖度、脱敏四项检查通过")
    print("=" * 46)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
