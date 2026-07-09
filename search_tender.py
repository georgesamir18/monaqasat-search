"""
search_tender.py
----------------
الأداة الرئيسية: بتاخد اسم الصنف من الطرفية (command line)، تدور في موقع
مناقصات قطر عن كل المناقصات الممنوحة اللي فيها الصنف ده، تجيب تفاصيلها
كاملة، وتحفظها في قاعدة بيانات محلية عشان تقدر تدور فيها تاني بسرعة.

الاستخدام:
    python search_tender.py "اسم الصنف أو جزء من موضوع المناقصة"

مثال:
    python search_tender.py "Medical Consumables"
"""

import sys
import re
import db
import scraper


def normalize(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def is_exact_match(subject: str, term: str) -> bool:
    """تطابق دقيق: الكلمة/الجملة اللي بحثنا عنها موجودة بالظبط كجزء متكامل من الموضوع."""
    n_subject = normalize(subject)
    n_term = normalize(term)
    if not n_term:
        return False
    # تطابق كحدود كلمات كاملة (مش مجرد substring عشوائي)
    pattern = r"(?<!\w)" + re.escape(n_term) + r"(?!\w)"
    return re.search(pattern, n_subject) is not None


def run_search(term: str, max_pages: int = 20, fetch_details: bool = True):
    db.init_db()

    print(f"🔎 بحث في موقع مناقصات قطر عن: \"{term}\" ...")
    cards, session = scraper.search_awarded_tenders(term, max_pages=max_pages)
    print(f"   لقيت {len(cards)} نتيجة من بحث الموقع (قبل الفلترة الدقيقة).")

    exact_matches = []
    approx_matches = []

    for card in cards:
        if is_exact_match(card.get("subject", ""), term):
            exact_matches.append(card)
        else:
            approx_matches.append(card)

    print(f"   ✅ منها {len(exact_matches)} تطابق دقيق، و {len(approx_matches)} تطابق تقريبي.")

    saved_tenders = []

    if fetch_details:
        for card in exact_matches:
            tender_id = card.get("tender_id")
            if not tender_id:
                continue

            if db.tender_exists(tender_id):
                print(f"   ↺ المناقصة {card.get('tender_number')} موجودة بالفعل في القاعدة المحلية، هنجيبها من هناك.")
                continue

            print(f"   📄 بجيب تفاصيل المناقصة {card.get('tender_number')} - {card.get('subject')[:60]}...")
            tender, awarded_companies, tech_companies = scraper.fetch_tender_details(session, card)
            if tender:
                db.save_tender(tender, awarded_companies, tech_companies, term)
                saved_tenders.append(tender)

    db.log_search(term, len(exact_matches))

    # نجيب كل النتائج (القديمة المحفوظة + الجديدة) من القاعدة المحلية عشان نعرضها كاملة
    all_local_results = db.search_local(term)

    return all_local_results, approx_matches


def print_results(results: list, approx_matches: list):
    print("\n" + "=" * 70)
    print(f"النتائج المطابقة تمامًا ({len(results)}):")
    print("=" * 70)

    if not results:
        print("مفيش أي مناقصة ممنوحة سابقًا بنفس الصنف ده بالظبط.")
    else:
        for t in results:
            print(f"\n🔹 رقم المناقصة: {t.get('tender_number')}   (رقم عند الجهة: {t.get('tender_number_at_ministry')})")
            print(f"   الموضوع: {t.get('subject')}")
            print(f"   الجهة: {t.get('ministry')}")
            print(f"   نوع المناقصة: {t.get('tender_type')}   |   القطاع: {t.get('sector_type')}")
            print(f"   تاريخ المنح: {t.get('award_date')}   |   القيمة الممنوحة: {t.get('awarded_amount')}")
            print(f"   رابط التفاصيل: {t.get('details_url')}")
            companies = t.get("awarded_companies", [])
            if companies:
                print("   الشركات الفايزة:")
                for c in companies:
                    print(f"      - {c.get('company_name')}  |  سجل تجاري: {c.get('cr_number')}  |  "
                          f"القيمة المعتمدة: {c.get('approved_value')}  |  الأصناف المعتمدة: {c.get('approved_items') or '—'}")

    if approx_matches:
        print("\n" + "-" * 70)
        print(f"نتائج تقريبية إضافية من الموقع (مش تطابق دقيق - {len(approx_matches)}):")
        print("-" * 70)
        for c in approx_matches[:15]:
            print(f"   - [{c.get('tender_number')}] {c.get('subject')}")
        if len(approx_matches) > 15:
            print(f"   ... و {len(approx_matches) - 15} نتيجة تانية")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("الاستخدام: python search_tender.py \"اسم الصنف\"")
        sys.exit(1)

    search_term = " ".join(sys.argv[1:])
    results, approx = run_search(search_term)
    print_results(results, approx)
