"""
watchlist.py
------------
بيقرأ قائمة أصناف من ملف watchlist.txt (صنف في كل سطر)، يدور على كل واحد
فيهم في موقع مناقصات قطر، ولو لقى مناقصات ممنوحة جديدة (مش موجودة قبل كده
في القاعدة المحلية) بيكتبها في تقرير reports/new_matches.md.

الفايدة: تحط فيه الأصناف اللي بتتعامل معاها كتير، وتخلي GitHub Actions
يشغله يوميًا تلقائيًا (شوف .github/workflows/scheduled-watchlist.yml)
فتلاقي تقرير جاهز بأي مناقصة جديدة اتمنحت لصنف بتتابعه.
"""

import os
import db
import search_tender

WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "watchlist.txt")
REPORT_FILE = os.path.join(os.path.dirname(__file__), "reports", "new_matches.md")


def load_watchlist():
    if not os.path.exists(WATCHLIST_FILE):
        return []
    with open(WATCHLIST_FILE, encoding="utf-8") as f:
        items = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
    return items


def main():
    db.init_db()
    items = load_watchlist()

    if not items:
        print("مفيش أصناف في watchlist.txt. ضيف كل صنف في سطر منفصل.")
        os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write("# تقرير مناقصات جديدة\n\nمفيش أصناف مضافة في watchlist.txt للمتابعة حاليًا.\n")
        return

    report_lines = ["# تقرير مناقصات جديدة\n"]
    any_new = False

    for term in items:
        print(f"\n--- بحث عن: {term} ---")

        # نجيب الـ tender_ids الموجودة قبل البحث عشان نعرف الجديد إيه بعد كده
        before = {t["tender_id"] for t in db.search_local(term)}

        results, _approx = search_tender.run_search(term)

        after = {t["tender_id"] for t in results}
        new_ids = after - before

        if new_ids:
            any_new = True
            report_lines.append(f"## صنف: {term}\n")
            for t in results:
                if t["tender_id"] in new_ids:
                    report_lines.append(
                        f"- **{t.get('tender_number')}** - {t.get('subject')} "
                        f"(منحت في {t.get('award_date')}) - الجهة: {t.get('ministry')}\n"
                        f"  [رابط التفاصيل]({t.get('details_url')})\n"
                    )

    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    if any_new:
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        print(f"\n✅ فيه مناقصات جديدة! اتكتبت في {REPORT_FILE}")
    else:
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write("# تقرير مناقصات جديدة\n\nمفيش مناقصات جديدة اتمنحت للأصناف المتابعة من آخر تشغيل.\n")
        print("\nمفيش جديد النهاردة.")


if __name__ == "__main__":
    main()
