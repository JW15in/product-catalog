# KiWAV Product Catalog Generator

此 generator 將 KiWAV 搜尋結果 MHTML 轉成固定格式的繁體中文 GitHub Pages 型錄。

## 輸入

- 一個或多個 KiWAV 搜尋結果 `.mhtml`（有分頁時依頁碼全部提供）
- 型錄顯示名稱 / fitment，例如：`Ninja 650 EX650（2006–2016）`
- 新子目錄 slug，例如：`ninja-650-ex650-2006-2016`

## 固定輸出

每份新型錄固定產生：

- `index.html`
- `product.html`
- `products.json`
- `config.json`

並在 `catalogs.json` 加入該型錄，讓 `/manage/` 可以切換管理。

## 固定規則

- 搜尋結果 MHTML 決定產品名單，不加入搜尋結果不存在的產品
- 不猜 SKU；只有從 MHTML 內已出現的 KiWAV CDN 圖片網址確認到數字識別碼時才保存
- 排除已確認的 mirror / adapter 混色組合（black + chrome adapter / chrome + black adapter）
- 圖片直接引用 KiWAV CDN，不另存圖片
- NTD = USD × 30 × 0.8
- 繁體中文呈現
- short name 用於首頁、detail 與型錄管理，例如 BLOK、WISP、WISP RH
- Sold Out 保留在資料中，由各型錄的 `showSoldOut` 開關決定是否顯示
- 每一產品可在各型錄的 `config.json` 獨立顯示 / 隱藏
- Detail 圖片張數可設為全部或 1–10 張
- 更新既有 generated catalog 時保留其 config 選擇

## Production protection

以下路徑禁止 generator 寫入：

- `1986-1992-suzuki-gsx-r`
- 根目錄 `index.html`
- 舊 `admin.html`
- `manage/`
- `generator/`

`1986-1992-suzuki-gsx-r` 是 locked production catalog。

## 執行範例

```bash
python generator/generate_catalog.py \
  --fitment "2011 Kawasaki Ninja 650" \
  --slug "2011-kawasaki-ninja-650" \
  --mhtml page1.mhtml page2.mhtml page3.mhtml
```

新型錄完成後會在：

```
/2011-kawasaki-ninja-650/
```

如果要更新一份已由 generator 建立的型錄：

```bash
python generator/generate_catalog.py \
  --fitment "2011 Kawasaki Ninja 650" \
  --slug "2011-kawasaki-ninja-650" \
  --mhtml page1.mhtml page2.mhtml page3.mhtml \
  --update
```

`--update` 會保留原本的產品顯示、Sold Out、zoom、重量與 Detail 圖片張數設定。

## 日常 ChatGPT workflow

在 KiWAV Product Catalog Generator Project 中只需要提供：

1. MHTML 檔
2. 子目錄 / 車型名稱

其餘使用本 generator 的固定模板與規則產生，不重新設計 HTML。
