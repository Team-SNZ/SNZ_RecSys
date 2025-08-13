# pip install playwright bs4 lxml pandas tqdm
# playwright install

import re, csv, time, urllib.parse
from playwright.sync_api import sync_playwright
import pandas as pd
from tqdm import tqdm

URLS = ["https://hope.hanatour.com/trp/pkg/CHPC0PKG0200M200?pkgCd=AVP231250901LJE&prePage=major-products",
        "https://hope.hanatour.com/trp/pkg/CHPC0PKG0200M200?pkgCd=AKP230250816ZEG&prePage=major-products",
        "https://hope.hanatour.com/trp/pkg/CHPC0PKG0200M200?pkgCd=PGB275250901LJ1&prePage=major-products"]

def norm(t: str) -> str:
    if not t:
        return ""
    return re.sub(r"\s+", " ", t).strip()

def get_pkgcd(url: str) -> str:
    q = urllib.parse.urlparse(url).query
    return urllib.parse.parse_qs(q).get("pkgCd", [""])[0]

def get_text_first(pg, selectors, timeout=1500):
    """여러 CSS 중 먼저 잡히는 것의 textContent 반환(없으면 '')"""
    if isinstance(selectors, str):
        selectors = [selectors]
    for sel in selectors:
        try:
            loc = pg.locator(sel).first
            txt = loc.text_content(timeout=timeout)
            if txt and norm(txt):
                return norm(txt)
        except Exception:
            continue
    return ""

def get_all_texts(pg, selector, timeout=1500, limit=None):
    """여러 요소 텍스트 리스트로(없으면 [])"""
    out = []
    try:
        locs = pg.locator(selector).all()
        for i, el in enumerate(locs):
            if limit and i >= limit:
                break
            try:
                txt = el.text_content(timeout=timeout)
                if txt and norm(txt):
                    out.append(norm(txt))
            except Exception:
                continue
    except Exception:
        pass
    return out

def scrape_one(pg, url: str) -> dict:
    # 페이지 열기
    for attempt in range(2):
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                pg.wait_for_selector(
                    "#contents .ly_wrap.prod_brief, .prod_brief .text_wrap, .prod_brief .price_group",
                    timeout=3000
                )
            except Exception:
                pass
            break
        except Exception as e:
            if attempt == 1:
                print(f"[goto fail] {url} -> {e}")
            else:
                time.sleep(0.5)

    # ---- 타이틀 ----
    title = get_text_first(pg, [
        "#contents > div > div > div.ly_wrap.prod_brief > div.inr.right > div.text_wrap > strong",
        ".prod_brief .text_wrap > strong",
        "strong.item_title"
    ])

    # ---- 설명 ----
    description = get_text_first(pg, [
        "#contents > div > div > div.ly_wrap.prod_brief > div.inr.right > div.text_wrap > p",
        ".prod_brief .text_wrap > p",
        "p.txt.exclam"
    ])

    # ---- 상품코드 ----
    product_code = get_pkgcd(url)
    if not product_code:
        product_code = get_text_first(pg, [
            "#contents > div > div > div.ly_wrap.prod_brief > div:nth-child(1) > div.option_wrap > span > strong",
            ".prod_brief .option_wrap span strong"
        ])

    # ---- 해시태그(= nth-child(4) 전체 텍스트, 특정 영역 제외) ----
    try:
        target_sel = "#contents > div > div > div.ly_wrap.prod_brief > div.inr.right > div:nth-child(4)"
        exclude_sels = [
            f"{target_sel} > div.ai_hash_wrap > div.ai_hash_detail > p",
            f"{target_sel} > div.ai_hash_wrap > div.ai_hash_detail > span",
            "#sticky06-top"
        ]

        # 전체 텍스트 요소
        target_el = pg.locator(target_sel).first
        full_text = target_el.inner_text() if target_el.count() > 0 else ""

        # 제외할 영역 텍스트들
        for sel in exclude_sels:
            try:
                exclude_texts = pg.locator(sel).all_inner_texts()
                for et in exclude_texts:
                    if et and et.strip():
                        full_text = full_text.replace(et.strip(), "")
            except Exception:
                continue

        tag_texts = norm(full_text)
    except Exception:
        tag_texts = ""

    # ---- 기타정보 ----
    features = get_all_texts(pg,
        "#contents > div > div > div.ly_wrap.prod_brief > div.inr.right > div.package_info_list .tit, "
        ".prod_brief .package_info_list .tit",
        timeout=1200
    )

    # ---- 가격 ----
    price = get_text_first(pg, [
        "#contents > div > div > div.ly_wrap.prod_brief > div.inr.right > div.price_group > strong:nth-child(2)",
        ".prod_brief .price_group strong.price",
        ".prod_brief .price_group strong"
    ], timeout=1200)
    if not price:
        try:
            alltxt = pg.inner_text("body", timeout=1000)
        except Exception:
            alltxt = ""
        m = re.search(r"(\d{1,3}(?:,\d{3})+)\s*원?", alltxt)
        if m:
            price = m.group(1)

    return {
        "product_code": product_code,
        "title": title,
        "description": description,
        "hashtags": tag_texts,
        "features": ", ".join(features),
        "price": price,
        "url": url
    }

def main():
    rows = []
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True, args=["--disable-gpu", "--no-sandbox"])
        ctx = br.new_context(
            locale="ko-KR",
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"),
            extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7"},
            viewport={"width": 1280, "height": 900},
        )
        pg = ctx.new_page()
        pg.set_default_timeout(15000)

        for i, u in tqdm(enumerate(URLS, 1), total=len(URLS)):
            data = scrape_one(pg, u)
            rows.append(data)
            print(f"[{i}/{len(URLS)}] {data['product_code']} | {data['title'][:40]} | ₩{data['price']}")
            # if len(rows) >= 10:  # 10개 채우면 중단
            #     break
            time.sleep(0.2)

        br.close()

    # 비어 있어도 전부 저장
    cols = ["product_code", "title", "description", "hashtags", "features", "price", "url"]
    with open("final_travel2.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    print(f"✅ 저장 완료 → final_travel.csv (행 수: {len(rows)})")

if __name__ == "__main__":
    main()
