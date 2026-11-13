#!/usr/bin/env python3
"""Fill assets/index.template.html from config.json.  Usage: build_page.py TEMPLATE CONFIG OUT_HTML"""
import html, json, sys
tpl, cfg, out = sys.argv[1:4]
c = json.load(open(cfg))
e = html.escape
cats = [n for n, _ in c.get("categories", [])] + ["Other"]
vals = {
    "QUEUE_TITLE": e(c["queue_title"]),
    "EYEBROW": e(c["eyebrow"]),
    "LEDE_EXTRA": (" " + e(c["lede_extra"])) if c.get("lede_extra") else "",
    "TOPIC_OPTIONS": "\n        ".join(f"<option>{e(n)}</option>" for n in cats),
    "EXCLUSION_NOTE": e(c.get("exclusion_note", "")),
}
t = open(tpl).read()
for k, v in vals.items(): t = t.replace("{{" + k + "}}", v)
assert "{{" not in t, "unfilled placeholder"
open(out, "w").write(t)
print(f"wrote {out} ({len(t)} bytes)")
