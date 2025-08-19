# -*- coding: utf-8 -*-
"""
하나투어 패키지(예: 일본 관동)
- 목록 페이지: 동적(Playwright) → 상세 링크 "최대 10개"만 수집하면 즉시 중단
- 상세 페이지: 정적(requests+BeautifulSoup) → 필드 파싱
저장: products.csv
"""
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin, urlparse, parse_qs
import re, csv, time, requests, sys
from bs4 import BeautifulSoup

# ===================== 설정 =====================
BASE = "https://hope.hanatour.com"
MAX_ITEMS = 10  # ★ 최대 10개만 수집

# ▶ 수집할 목록 URL들 (원하는 나라/도시 URL을 추가해도 됨)
LIST_URLS = [
    "https://hope.hanatour.com/package/major-products?cntryCd=JP&areaCd=JT&cityCdNm=%EC%9D%BC%EB%B3%B8%EA%B4%80%EB%8F%99",  # 일본 관동
]

# ▶ 선택자: 페이지가 바뀌면 여기만 손보면 됨
SEL_BTN_MORE        = "button:has-text('더보기'), a:has-text('더보기'), button:has-text('더 보기'), a:has-text('더 보기')"

# 카드 컨테이너는 넓게 두되, 너무 많으면 나중에 좁히자 (ex. '.pkg-list article')
SEL_CARD_CONTAINER  = "article, li"

# 판매상품보기 문구가 '판매 상품 보기' / 링크 <a>일 수도 있음
SEL_BTN_SEE_SALES   = "button:has-text('판매상품보기'), button:has-text('판매 상품 보기'), a:has-text('판매상품보기'), a:has-text('판매 상품 보기')"

# 상세 라벨이 '상세일정보기' / '상세 일정 보기' / '상세보기' 등으로 섞일 수 있음
SEL_LINK_DETAIL     = "a:has-text('상세일정보기'), a:has-text('상세 일정'), a:has-text('상세보기')"

# URL 패턴(최후의 안전핀)
SEL_DETAIL_FALLBACK = "a[href*='CHPC0PKG0200M200'][href*='pkgCd=']"

# ▶ 디버그: 너무 빠르면 차단/로딩 문제 생길 수 있음
SLOW_MO_MS          = 120
DEFAULT_TIMEOUT_MS  = 45000
CLICK_RETRY         = 12

# ===================== 유틸 =====================
HDR = {"User-Agent": "Mozilla/5.0"}

def pkgcd_from_url(u: str) -> str:
    return parse_qs(urlparse(u).query).get("pkgCd", [""])[0]

def extract_price(text: str) -> str:
    m = re.search(r"(\d{1,3}(?:,\d{3})+)\s*원", text)
    return m.group(1) if m else ""

def clean_hashtags(tags):
    out = []
    for t in tags:
        t = (t or "").strip().replace(" ", "")
        if not t:
            continue
        if not t.startswith("#"):
            t = "#" + t
        if len(t) <= 25:
            out.append(t)
    # 중복 제거
    return list(dict.fromkeys(out))

# ===================== 목록 열기 =====================
def open_list_page(list_url):
    """접속 안정화: headful + UA/locale 지정 + DOMContentLoaded + 핵심 요소 대기"""
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=False, slow_mo=SLOW_MO_MS,
        args=[
            "--disable-gpu",
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    ctx = browser.new_context(
        locale="ko-KR",
        user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"),
        extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7"},
        viewport={"width": 1360, "height": 900},
    )
    page = ctx.new_page()
    page.set_default_timeout(DEFAULT_TIMEOUT_MS)
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    page.on("console", lambda m: print("[console]", m.type, m.text))
    page.on("requestfailed", lambda r: print("[reqfail]", r.url, getattr(r.failure, "error_text", "")))

    # 접속 + 핵심 요소 대기
    last_err = None
    for attempt in range(3):
        try:
            page.goto(list_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
            # 카드/버튼 중 하나가 보일 때까지
            page.wait_for_selector(f"{SEL_BTN_SEE_SALES}, {SEL_CARD_CONTAINER}", timeout=30000)
            break
        except Exception as e:
            last_err = e
            print(f"[goto retry {attempt+1}] {e}")
            time.sleep(1.0)
    else:
        page.screenshot(path="goto_fail.png", full_page=True)
        with open("goto_fail.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        raise last_err

    return pw, browser, page

# ===================== 목록 → 상세 링크 수집 (10개 채우면 즉시 중단) =====================
def collect_detail_urls_from_list(page):
    detail_urls = []

    # 1) 더보기 여러 번 (필요시)
    for _ in range(50):
        if len(detail_urls) >= MAX_ITEMS:
            break
        btn = page.locator(SEL_BTN_MORE)
        if not btn.count():
            break
        before = page.locator(SEL_CARD_CONTAINER).count()
        btn.first.click()
        ok = False
        for _ in range(CLICK_RETRY):
            page.wait_for_timeout(500)
            if page.locator(SEL_CARD_CONTAINER).count() > before:
                ok = True
                break
        if not ok:
            break

    # 2) 무한 스크롤 보조
    last = -1
    for _ in range(80):
        if len(detail_urls) >= MAX_ITEMS:
            break
        curr = page.locator(SEL_CARD_CONTAINER).count()
        if curr == last:
            break
        last = curr
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(700)

    # 3) 카드 돌면서 판매상품보기 → 상세일정보기 링크 수집
    cards = page.locator(SEL_CARD_CONTAINER)
    print("카드 수:", cards.count())
    stop_all = False

    def add_links_from(loc):
        nonlocal detail_urls, stop_all
        # 상세일정보기 텍스트 기반
        for a in loc.locator(SEL_LINK_DETAIL).all():
            if len(detail_urls) >= MAX_ITEMS:
                stop_all = True; return
            href = a.get_attribute("href")
            if href:
                u = href if href.startswith("http") else urljoin(BASE, href)
                if "pkgCd=" in u and u not in detail_urls:
                    detail_urls.append(u)
                    if len(detail_urls) >= MAX_ITEMS:
                        stop_all = True; return
        # URL 패턴 기반(백업)
        for a in loc.locator(SEL_DETAIL_FALLBACK).all():
            if len(detail_urls) >= MAX_ITEMS:
                stop_all = True; return
            href = a.get_attribute("href")
            if href:
                u = href if href.startswith("http") else urljoin(BASE, href)
                if "pkgCd=" in u and u not in detail_urls:
                    detail_urls.append(u)
                    if len(detail_urls) >= MAX_ITEMS:
                        stop_all = True; return

    for i in range(cards.count()):
        if stop_all or len(detail_urls) >= MAX_ITEMS:
            break
        card = cards.nth(i)
        try:
            card.scroll_into_view_if_needed()
            # 판매상품보기 클릭(있으면)
            if card.locator(SEL_BTN_SEE_SALES).count():
                card.locator(SEL_BTN_SEE_SALES).first.click()
                # 펼쳐질 때까지 대기
                for _ in range(CLICK_RETRY):
                    if card.locator(SEL_LINK_DETAIL).count() or card.locator(SEL_DETAIL_FALLBACK).count():
                        break
                    page.wait_for_timeout(300)

            add_links_from(card)

        except Exception as e:
            print("card error:", i, e)

    # 최후 수단: 페이지 전체에서 패턴 스캔(아직 0개일 때만)
    if not detail_urls:
        add_links_from(page)

    # 중복/필터 + 안전 슬라이스
    detail_urls = [u for u in dict.fromkeys(detail_urls) if "pkgCd=" in u][:MAX_ITEMS]
    print("상세 URL 수집:", len(detail_urls))
    return detail_urls

# ===================== 상세 파싱 =====================
def parse_detail(u: str) -> dict:
    """상세 페이지는 정적 파싱 (빠르고 튼튼)"""
    try:
        r = requests.get(u, headers=HDR, timeout=20)
    except Exception as e:
        return {"pkgCd": pkgcd_from_url(u), "url": u, "error": f"request_fail: {e}"}

    s = BeautifulSoup(r.text, "lxml")
    title_el    = s.select_one("h1, .prd-title, .title")
    subtitle_el = s.select_one(".desc, .prd-summary, .subtitle")
    title       = title_el.get_text(strip=True) if title_el else ""
    subtitle    = subtitle_el.get_text(strip=True) if subtitle_el else ""

    raw_tags = [e.get_text(strip=True) for e in s.select("[class*='tag'] a, [class*='tag'] .tag, .hashtag a, .hashtag .tag")]
    hashtags = clean_hashtags(raw_tags)

    features = [li.get_text(" ", strip=True) for li in s.select(".benefit-wrap li, .feature li, .ico-list li, [class*='icon'] li")]
    features = [re.sub(r"\s+", " ", f) for f in features]

    price = extract_price(s.get_text(" ", strip=True))

    return {
        "pkgCd": pkgcd_from_url(u),
        "url": u,
        "title": title,
        "subtitle": subtitle,
        "hashtags": "|".join(hashtags),
        "features": "|".join(features),
        "price_krw": price
    }

# ===================== 메인 =====================
def main():
    all_rows = []
    for list_url in LIST_URLS:
        print("\n=== 목록 진입:", list_url)
        pw, browser, page = open_list_page(list_url)
        try:
            detail_urls = collect_detail_urls_from_list(page)
        finally:
            browser.close()
            pw.stop()

        if not detail_urls:
            print("❗ 상세 URL 0개. goto_fail.html 확인해서 선택자 수정 필요.")
            continue

        # 상세 파싱 (이미 10개 제한된 상태)
        for u in detail_urls:
            row = parse_detail(u)
            all_rows.append(row)
            time.sleep(0.2)  # 과도 요청 방지

    if not all_rows:
        print("수집 결과가 없습니다.")
        return

    # CSV 저장
    with open("products.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["pkgCd","url","title","subtitle","hashtags","features","price_krw"])
        w.writeheader(); w.writerows(all_rows)
    print("\n✅ 저장 완료 → products.csv  (행 수:", len(all_rows), ")")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단됨")
        sys.exit(1)
