# -*- coding: utf-8 -*-
"""只读探查 营员名单(1).xlsx 的结构：sheet名、表头、前若干行、总行数。"""
import os, sys, openpyxl
sys.stdout.reconfigure(encoding="utf-8")

SRC = r"D:/Program Files (x86)/weixinDownload/xwechat_files/wxid_1370353703312_ac1b/msg/file/2026-08/营员名单(1).xlsx"

wb = openpyxl.load_workbook(SRC, read_only=True)
for sn in wb.sheetnames:
    ws = wb[sn]
    print("==== SHEET:", sn, "| rows:", ws.max_row, "| cols:", ws.max_column)
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 20:
            print(i, list(row))
    print("... (total %d rows)" % ws.max_row)
wb.close()
