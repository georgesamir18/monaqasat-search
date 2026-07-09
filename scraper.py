"""
scraper.py
----------
بيدخل على موقع مناقصات قطر (monaqasat.mof.gov.qa) ويستخدم خانة البحث
الموجودة فعليًا في صفحة "Awarded Tenders" عشان يجيب المناقصات الممنوحة
اللي فيها صنف/موضوع معين، وبعدين يدخل على كل مناقصة يجيب تفاصيلها كاملة.

مهم: السكريبت بيبعت طلبات بسرعة معقولة (فيه تأخير بين كل طلب) احترامًا
لسيرفر الموقع، ومفيش أي تجاوز لأي حماية أو تسجيل دخول - كل البيانات دي
منشورة وعامة للجميع أصلاً على الموقع.
"""

import time
import re
from bs4 import BeautifulSoup
import requests

BASE_URL = "https://monaqasat.mof.gov.qa"
SEARCH_PAGE_URL = f"{BASE_URL}/TendersOnlineServices/AwardedTenders/1"
REQUEST_DELAY_SECONDS = 1.5  # تأخير مهذب بين كل طلب وطلب

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}


def _get_session_and_token():
    """يفتح جلسة، يجيب الكوكيز وتوكن الحماية (__RequestVerificationToken) من الصفحة."""
    session = requests.Session()
    session.headers.update(HEADERS)
    resp = session.get(SEARCH_PAGE_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    token_input = soup.find("input", {"name": "__RequestVerificationToken"})
    token = token_input["value"] if token_input else None
    return session, token


def _parse_cards(html: str):
    """يستخرج بيانات كل كارت مناقصة من صفحة نتائج."""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    cards = soup.find_all("div", class_="row custom-cards")
    for card in cards:
        try:
            tender_number = card.select_one(".col-header .card-label label")
            tender_number = tender_number.get_text(strip=True) if tender_number else None

            title_link = card.select_one(".col-header .card-title a")
            subject = title_link.get_text(strip=True) if title_link else None
            details_url = title_link["href"] if title_link else None
            tender_id = None
            if details_url:
                m = re.search(r"/TenderDetails/(\d+)", details_url)
                if m:
                    tender_id = m.group(1)

            companies_link = card.find("a", class_="btn-primary")
            companies_url = companies_link["href"] if companies_link else None

            # الصفوف اللي فيها Award date / Sector / Bond / Documents value
            info = {}
            for row in card.select(".cards-row"):
                label = row.select_one(".card-label")
                value = row.select_one(".card-title")
                if label and value:
                    info[label.get_text(strip=True)] = value.get_text(strip=True)

            ministry = None
            tender_type = None
            ministry_col = card.find_all("div", class_="cards-col")
            if len(ministry_col) > 1:
                ministry_label = ministry_col[1].select_one(".col-header .card-label label")
                ministry_value = ministry_col[1].select_one(".col-header .card-title")
                if ministry_value:
                    ministry = ministry_value.get_text(strip=True)
                type_row = ministry_col[1].select_one(".cards-row .card-title")
                if type_row:
                    tender_type = type_row.get_text(strip=True)

            results.append({
                "tender_id": tender_id,
                "tender_number": tender_number,
                "subject": subject,
                "details_url": details_url,
                "companies_url": companies_url,
                "award_date": info.get("Award date"),
                "sector_type": info.get("Requested Sector Type"),
                "tender_bond": info.get("Tender Bond (QAR)"),
                "document_value": info.get("Documents value (QR)"),
                "ministry": ministry,
                "tender_type": tender_type,
            })
        except Exception as e:
            print(f"تحذير: مشكلة في قراءة كارت مناقصة - {e}")
            continue

    # رابط الصفحة التالية لو موجود (نتايج البحث ممكن تتقسم على أكتر من صفحة)
    next_page_url = None
    pagination = soup.find("ul", class_="pagination")
    if pagination:
        active = pagination.find("li", class_="page-item disabled")
        # نحاول نلاقي رقم الصفحة الحالية والصفحة اللي بعدها
        links = pagination.find_all("a", class_="page-link")
        for link in links:
            text = link.get_text(strip=True)
            if text.isdigit():
                pass
        # أبسط طريقة: لو فيه رابط بيحمل كلمة "Next" أو سهم، ناخده
        next_link = pagination.find("a", string=re.compile("Next|»|›"))
        if next_link:
            next_page_url = next_link["href"]

    return results, next_page_url


def _parse_tender_details(html: str, fallback: dict):
    """يستخرج تفاصيل مناقصة كاملة + الشركات الفايزة من صفحة Tender & its Companies' Details."""
    soup = BeautifulSoup(html, "html.parser")

    def get_text(id_):
        el = soup.find(id=id_)
        return el.get_text(strip=True) if el else None

    tender = {
        "tender_id": fallback.get("tender_id"),
        "tender_number": get_text("lbl_num") or fallback.get("tender_number"),
        "tender_number_at_ministry": get_text("lblEntityTenderNumber"),
        "subject": get_text("lbl_subject") or fallback.get("subject"),
        "ministry": get_text("lblRequesterEntity") or fallback.get("ministry"),
        "sector_type": get_text("lblTenderClassification") or fallback.get("sector_type"),
        "tender_type": get_text("lbl_type") or fallback.get("tender_type"),
        "envelopes_system": get_text("lblTenderEnvSystem"),
        "publish_date": get_text("lblTenderAnnouncementDate"),
        "closing_date": get_text("lbltenderClosingDate"),
        "technical_open_date": get_text("lblTechnicalOpenDate"),
        "financial_open_date": get_text("lblFinancialOpenDate"),
        "award_date": get_text("lblAwardedDate") or fallback.get("award_date"),
        "document_value": get_text("lbltenderDocumentValue") or fallback.get("document_value"),
        "tender_bond": get_text("lblTenderInsurance") or fallback.get("tender_bond"),
        "awarded_amount": get_text("lbl_award"),
        "details_url": fallback.get("details_url"),
        "companies_url": fallback.get("companies_url"),
    }

    # جدول "Awarded companies data"
    awarded_companies = []
    for h3 in soup.find_all("h3"):
        if "Awarded companies" in h3.get_text():
            table = h3.find_next("table")
            if table:
                for tr in table.select("tbody tr"):
                    tds = tr.find_all("td")
                    if len(tds) >= 5:
                        awarded_companies.append({
                            "company_name": tds[0].get_text(strip=True),
                            "cr_number": tds[1].get_text(strip=True),
                            "approved_value": tds[2].get_text(strip=True),
                            "financial_result": tds[3].get_text(strip=True),
                            "approved_items": tds[4].get_text(strip=True),
                        })
            break

    # جدول "Technically opened companies data"
    tech_companies = []
    for h3 in soup.find_all("h3"):
        if "Technically opened" in h3.get_text():
            table = h3.find_next("table")
            if table:
                for tr in table.select("tbody tr"):
                    tds = tr.find_all("td")
                    if len(tds) >= 2:
                        tech_companies.append({
                            "company_name": tds[0].get_text(strip=True),
                            "cr_number": tds[1].get_text(strip=True),
                        })
            break

    return tender, awarded_companies, tech_companies


def search_awarded_tenders(subject_term: str, max_pages: int = 20):
    """
    بيبحث في صفحة المناقصات الممنوحة عن كلمة معينة في الصنف (subject)،
    ويرجع ليستة بكل المناقصات اللي طلعت (كروت الملخص بس، من غير تفاصيل الشركات).
    """
    session, token = _get_session_and_token()

    payload = {
        "SearchCriteriaKey": "",
        "SearchData.ClassId": "0",
        "SearchData.Year": "0",
        "SearchData.FKTenderTypeId": "0",
        "SearchData.FKRequesterId": "0",
        "SearchData.TenderSubject": subject_term,
        "SearchData.TenderNumber": "",
        "SearchData.CompanySizeId": "0",
    }
    if token:
        payload["__RequestVerificationToken"] = token

    all_results = []
    url = SEARCH_PAGE_URL

    for page_num in range(1, max_pages + 1):
        resp = session.post(url, data=payload, timeout=30)
        resp.raise_for_status()
        results, next_page_url = _parse_cards(resp.text)

        if not results:
            break

        all_results.extend(results)

        if not next_page_url:
            break
        url = next_page_url if next_page_url.startswith("http") else BASE_URL + next_page_url
        time.sleep(REQUEST_DELAY_SECONDS)

    return all_results, session


def fetch_tender_details(session: requests.Session, card: dict):
    """يدخل على صفحة تفاصيل مناقصة واحدة ويرجع كل بياناتها + الشركات الفايزة."""
    if not card.get("companies_url"):
        return None, [], []

    time.sleep(REQUEST_DELAY_SECONDS)
    resp = session.get(card["companies_url"], timeout=30)
    resp.raise_for_status()
    tender, awarded_companies, tech_companies = _parse_tender_details(resp.text, card)
    return tender, awarded_companies, tech_companies
