#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
from email import policy
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import urlparse

PROTECTED_PATHS = {
    "1986-1992-suzuki-gsx-r",
    "admin.html",
    "index.html",
    "manage",
    "generator",
}

KNOWN_FAMILIES = [
    "Classic Plus", "Mamba Round", "Viper II", "Palm II", "Cleaver II",
    "MambaX", "Blackline", "Emperor", "Eclipse", "Lucifer", "Classic",
    "Orbii", "Orbix", "Wisp", "Blok", "Mamba", "Viper", "Horus", "OJO",
    "Shield", "4Rizz", "Stan", "Missie", "Zipper", "Oval", "Retro", "Modern",
    "Stark", "Panther", "Venom", "Redline", "Hawk", "Bob", "Leap", "Aura", "Blade",
]

COLOR_RULES = [
    ("glossy carbon fiber", "亮面碳纖維"),
    ("glossy carbon", "亮面碳纖維"),
    ("matte carbon fiber", "霧面碳纖維"),
    ("matte carbon", "霧面碳纖維"),
    ("chrome", "鍍鉻"),
    ("black", "黑色"),
    ("blue", "藍色"),
    ("red", "紅色"),
    ("green", "綠色"),
    ("silver", "銀色"),
    ("gold", "金色"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate a KiWAV customer catalog from saved search-result MHTML files.")
    p.add_argument("--fitment", required=True, help="Display name, e.g. '2011 Kawasaki Ninja 650'")
    p.add_argument("--slug", required=True, help="Output subdirectory, e.g. '2011-kawasaki-ninja-650'")
    p.add_argument("--mhtml", nargs="+", required=True, help="One or more KiWAV search-result MHTML files in page order")
    p.add_argument("--repo-root", default=".", help="Repository root (default: current directory)")
    p.add_argument("--template-dir", default=None, help="Template directory (default: <repo>/generator/templates)")
    p.add_argument("--catalog-name", default=None, help="Name shown in Catalog Manager; defaults to fitment")
    p.add_argument("--footer-note", default=None, help="Optional footer note, e.g. test-page note")
    p.add_argument("--update", action="store_true", help="Update an existing generated catalog while preserving its config choices")
    p.add_argument("--no-register", action="store_true", help="Do not update catalogs.json")
    p.add_argument("--exchange-rate", type=float, default=30.0)
    p.add_argument("--discount", type=float, default=0.8)
    return p.parse_args()


def read_mhtml_html(path: Path) -> str:
    with path.open("rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)
    html_parts = []
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            try:
                html_parts.append(part.get_content())
            except Exception:
                payload = part.get_payload(decode=True) or b""
                html_parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
    if not html_parts:
        raise ValueError(f"No text/html part found in {path}")
    return html_parts[0]


def strip_tags(s: str) -> str:
    s = re.sub(r"<script\b[\s\S]*?</script>", " ", s, flags=re.I)
    s = re.sub(r"<style\b[\s\S]*?</style>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html_lib.unescape(s)).strip()


def split_product_cards(page_html: str) -> list[str]:
    return re.split(r'<div[^>]*class="[^"]*\bproduct\s+product-item\b[^"]*"[^>]*>', page_html, flags=re.I)[1:]


def extract_product(card: str, rate: float, discount: float) -> dict | None:
    next_pos = re.search(r'<div[^>]*class="[^"]*\bproduct\s+product-item\b', card, flags=re.I)
    if next_pos:
        card = card[:next_pos.start()]

    href_match = re.search(r'href="(https://kiwavmotors\.com/en/[^"]+-detail)"', card, flags=re.I)
    if not href_match:
        return None
    url = html_lib.unescape(href_match.group(1))

    text = strip_tags(card)
    name_price = re.search(r"Quick View\s+(.+?)\s+\$([0-9]+(?:\.[0-9]+)?)\s*USD\b", text, flags=re.I)
    if not name_price:
        return None
    name = name_price.group(1).strip()
    usd = float(name_price.group(2))

    low = name.lower()
    if "adapter" in low and (("black" in low and "chrome adapter" in low) or ("chrome" in low and "black adapter" in low)):
        return None

    img_urls = []
    for m in re.finditer(r'(?:src|data-src)="(https://cdn\.kiwavmotors\.com/products/images/main/resized/[^"]+)"', card, flags=re.I):
        u = html_lib.unescape(m.group(1))
        if u not in img_urls:
            img_urls.append(u)

    sku = ""
    for u in img_urls:
        m = re.search(r"/([0-9]+)__[^/]+$", urlparse(u).path)
        if m:
            sku = m.group(1)
            break

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    p = {
        "id": slug,
        "name": name,
        "url": url,
        "usd": int(usd) if usd.is_integer() else usd,
        "ntd": round(usd * rate * discount),
        "soldOut": bool(re.search(r"\bSold out\b", text, flags=re.I)),
        "images": img_urls[:2],
    }
    if sku:
        p["sku"] = sku
    return enrich_product(p)


def family_name(name: str) -> str:
    low = name.lower()
    for family in sorted(KNOWN_FAMILIES, key=len, reverse=True):
        if low.startswith(family.lower() + " ") or low == family.lower():
            return family.upper()
    token = re.match(r"[A-Za-z0-9+.-]+", name)
    return (token.group(0) if token else "PRODUCT").upper()


def detect_package(low: str) -> str:
    if re.search(r"\bRH\b", low, flags=re.I):
        return "右側單支"
    if re.search(r"\bLH\b", low, flags=re.I):
        return "左側單支"
    if "a pair" in low or re.search(r"\bmirrors\b", low):
        return "左右一對"
    if "one piece" in low or "a piece" in low or re.search(r"\bmirror\b", low):
        return "單支"
    return ""


def detect_finish(low: str) -> str:
    for needle, zh in COLOR_RULES:
        if needle in low:
            return zh
    return ""


def detect_install(low: str) -> tuple[str, str, str]:
    if "fairing mount" in low or "fairing-mount" in low:
        return "整流罩固定式", "依商品頁確認", "整流罩後視鏡"
    m = re.search(r"\bM(\d+)\s+threaded\s+handlebars?\b", low, flags=re.I)
    if m:
        thread = f"M{m.group(1)}"
        variant = "重型配重款" if "heavy weight" in low else ("配重款" if "weight" in low else "標準車把端款")
        return f"{thread} 內牙車把端", thread, variant
    if "bar end" in low:
        variant = "重型配重款" if "heavy weight" in low else ("配重款" if "weight" in low else "標準車把端款")
        return "車把端", "依商品頁確認", variant
    return "依商品名稱確認", "依商品頁確認", "一般款"


def zh_variant(v: str) -> str:
    return {
        "重型配重款": "重型配重",
        "配重款": "配重款",
        "整流罩後視鏡": "整流罩款",
        "標準車把端款": "標準車把端",
    }.get(v, v)


def enrich_product(p: dict) -> dict:
    name = p["name"]
    low = name.lower()
    family = family_name(name)
    package = detect_package(low)
    finish = detect_finish(low)
    install, thread, variant = detect_install(low)

    short_name = family
    if package == "右側單支":
        short_name += " RH"
    elif package == "左側單支":
        short_name += " LH"

    display_parts = [family]
    if finish:
        display_parts.append(finish)
    if install.startswith("M"):
        display_parts.append(f"{thread} 車把端後視鏡")
    elif install == "整流罩固定式":
        display_parts.append("整流罩後視鏡")
    else:
        display_parts.append("後視鏡")
    if package:
        suffix = "一對" if package == "左右一對" else package
        display_parts[-1] = display_parts[-1] + f"（{suffix}）"

    chips = []
    if install.startswith("M"):
        chips.append(thread)
    elif install == "整流罩固定式":
        chips.append("整流罩款")
    chips.append(zh_variant(variant))
    if finish:
        chips.append(finish)
    if package == "左右一對":
        chips.append("一對")
    elif package:
        chips.append(package)
    chips = list(dict.fromkeys(chips))[:4]

    summary_parts = []
    if finish:
        summary_parts.append(finish)
    summary_parts.append(zh_variant(variant))
    if install.startswith("M"):
        summary_parts.append(f"{thread} 車把端安裝")
    elif install == "整流罩固定式":
        summary_parts.append("整流罩安裝")
    if package:
        summary_parts.append(package)

    specs = []
    if install.startswith("M"):
        specs.extend([["安裝", install], ["固定螺牙", thread]])
    elif install == "整流罩固定式":
        specs.extend([["安裝", "整流罩固定式"], ["固定方式", "雙孔整流罩"]])
    else:
        specs.append(["安裝", install])
    if finish:
        specs.append(["顏色 / 表面", finish])
    specs.append(["款式", zh_variant(variant)])
    if package:
        specs.append(["包裝", package])

    points = []
    if install.startswith("M"):
        points.append(f"使用 {thread} 內牙車把端安裝。")
    elif install == "整流罩固定式":
        points.append("此版本為整流罩固定式後視鏡。")
    else:
        points.append("安裝方式請依商品頁確認。")
    if variant == "重型配重款":
        points.append("重型配重版本，適合希望增加車把端重量感的配置。")
    elif variant == "配重款":
        points.append("車把端配重版本。")
    elif variant == "整流罩後視鏡":
        points.append("使用整流罩固定方式。")
    elif variant == "標準車把端款":
        points.append("標準車把端版本。")
    if finish:
        points.append(f"{finish}版本。")
    if package:
        points.append(f"包裝為{package}。")

    p.update({
        "displayName": " ".join(display_parts),
        "install": install,
        "package": package,
        "finish": finish,
        "variant": variant,
        "thread": thread,
        "points": points,
        "shortName": short_name,
        "chips": chips,
        "summary": "・".join(summary_parts),
        "specs": specs,
    })
    return p


def collect_products(mhtml_paths: list[Path], rate: float, discount: float) -> list[dict]:
    products = []
    seen = set()
    for path in mhtml_paths:
        page = read_mhtml_html(path)
        for card in split_product_cards(page):
            p = extract_product(card, rate, discount)
            if not p or p["id"] in seen:
                continue
            seen.add(p["id"])
            products.append(p)
    if not products:
        raise ValueError("No KiWAV product cards were found in the supplied MHTML files.")
    return products


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def build_config(products: list[dict], existing: dict | None) -> dict:
    existing = existing or {}
    existing_products = existing.get("products") or {}
    return {
        "products": {p["id"]: existing_products.get(p["id"], True) for p in products},
        "showSoldOut": existing.get("showSoldOut", True),
        "enableZoom": existing.get("enableZoom", True),
        "showWeight": existing.get("showWeight", False),
        "detailImageLimit": existing.get("detailImageLimit", 0),
    }


def render_template(template: str, values: dict[str, str]) -> str:
    for k, v in values.items():
        template = template.replace("{{" + k + "}}", v)
    unreplaced = re.findall(r"{{[A-Z0-9_]+}}", template)
    if unreplaced:
        raise ValueError(f"Unreplaced template variables: {', '.join(sorted(set(unreplaced)))}")
    return template


def update_registry(path: Path, slug: str, name: str) -> None:
    data = load_json(path, [])
    for row in data:
        if row.get("path") == slug or row.get("id") == slug:
            if row.get("locked"):
                raise ValueError(f"Catalog registry entry {slug} is locked")
            row.update({"id": slug, "name": name, "path": slug, "locked": False, "legacy": False})
            break
    else:
        data.append({"id": slug, "name": name, "path": slug, "locked": False, "legacy": False})
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo = Path(args.repo_root).resolve()
    slug = args.slug.strip("/")
    if not slug or "/" in slug or "\\" in slug:
        raise ValueError("--slug must be one direct child directory name")
    if slug in PROTECTED_PATHS:
        raise ValueError(f"Protected path: {slug}. Generation aborted.")
    target = repo / slug
    if target.exists() and not args.update:
        raise ValueError(f"Target already exists: {target}. Use --update only for an intentional generated-catalog refresh.")

    template_dir = Path(args.template_dir).resolve() if args.template_dir else repo / "generator" / "templates"
    index_template = (template_dir / "index.html").read_text(encoding="utf-8")
    product_template = (template_dir / "product.html").read_text(encoding="utf-8")

    mhtmls = [Path(x).resolve() for x in args.mhtml]
    products = collect_products(mhtmls, args.exchange_rate, args.discount)

    existing_cfg = load_json(target / "config.json", {}) if target.exists() else {}
    config = build_config(products, existing_cfg)

    target.mkdir(parents=True, exist_ok=True)
    fitment = args.fitment
    footer = args.footer_note if args.footer_note is not None else f"{fitment} mirror catalog"
    values = {
        "FITMENT": fitment,
        "PAGE_TITLE": f"{fitment}後視鏡款式型錄",
        "PAGE_DESCRIPTION": f"{fitment}後視鏡款式參考",
        "FOOTER": footer,
    }
    (target / "index.html").write_text(render_template(index_template, values), encoding="utf-8")
    (target / "product.html").write_text(render_template(product_template, values), encoding="utf-8")
    (target / "products.json").write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    (target / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.no_register:
        registry = repo / "catalogs.json"
        if registry.exists():
            update_registry(registry, slug, args.catalog_name or fitment)

    sold = sum(1 for p in products if p.get("soldOut"))
    print(f"Generated: {target}")
    print(f"Products: {len(products)} (sold out: {sold})")
    print(f"Price formula: USD × {args.exchange_rate:g} × {args.discount:g} → NTD")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
