import csv, io
from openpyxl import Workbook


def to_csv(rows):
    out = io.StringIO()
    if rows:
        w = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return out.getvalue().encode("utf-8-sig")  # BOM so Excel reads Arabic/UTF-8


def to_xlsx(rows):
    wb = Workbook()
    ws = wb.active
    if rows:
        keys = list(rows[0].keys())
        ws.append(keys)
        for r in rows:
            ws.append([r.get(k) for k in keys])
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(60, max(len(str(c.value or "")) for c in col) + 2)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
