# -*- coding: utf-8 -*-
from docx import Document

checks = {
    "猎人指令公式.docx": [
        "猎人Y被使用静止卡 [获得线索N] [获得露水M]",
        "猎人Y被使用护盾卡",
        "不再支持获得线索",
        "X组XXX被XXX淘汰",
        "召唤机动人员",
    ],
    "任务点NPC指令公式.docx": [
        "任务点N 完成 线索X 露水Y 金露水Z 护盾卡Z 静止卡Z",
        "任务点N 接收 线索X 露水Y 金露水Z 护盾卡Z 静止卡Z",
        "全局免疫 15 秒",
    ],
}

ok = True
for fn, subs in checks.items():
    d = Document(fn)
    txt = "\n".join(p.text for p in d.paragraphs if p.text.strip())
    for s in subs:
        if s not in txt:
            print("MISSING in", fn, ":", s)
            ok = False
    print(fn, "OK" if ok else "FAIL")

print("ALL DOCX VERIFIED" if ok else "VERIFY FAILED")
