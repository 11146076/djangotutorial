# EatWhat 繳交整理清單

本文件協助一次收齊 **報告、截圖、示範影片** 等繳交材料。

- **原始碼**：<https://github.com/11146076/djangotutorial>（`main` 分支）
- **本機站台**：<http://localhost/>（WSL + Apache + MariaDB）

---

## 建議資料夾結構

```
EatWhat_繳交/
├── 01_報告.pdf
├── 02_簡報.pptx          # 若老師要求
├── 03_截圖/
├── 04_示範影片.mp4
└── 05_附錄/
    └── GitHub網址.txt
```

---

## 建議執行順序

1. 啟動服務（`mariadb`、`apache2`）
2. **錄示範影片**（邊錄邊用 `Win + Shift + S` 截圖）
3. 補缺截圖
4. 撰寫報告 / 簡報
5. 最後檢查清單

---

## 錄影前準備

```bash
sudo service mariadb start
sudo service apache2 restart
```

確認：

- [ ] 已登入主要測試帳號
- [ ] 首頁可見「今天吃什麼？」推薦 3 篇
- [ ] 至少有 2～3 篇公開貼文（建議含圖片）
- [ ] 通知鈴鐺有未讀通知（可互按讚/留言產生）
- [ ] 瀏覽器 100% 縮放、視窗最大化

健康分析若未顯示：

```bash
cd ~/projects/eatwhat
source .venv/bin/activate
python manage.py backfill_health_insights --sync
```

---

## 示範影片腳本（約 5～8 分鐘）

| 時間 | 畫面 | 說明重點 |
| --- | --- | --- |
| 0:00 | Apache / MariaDB 狀態 | 部署環境已啟動 |
| 0:30 | 首頁動態牆 + 推薦區 | 個人化 Top 3 |
| 1:00 | 登入頁 | CAPTCHA、帳密登入 |
| 1:30 | Google 登入按鈕 | OAuth 整合 |
| 2:00 | 發文流程 | 富文字、分類、標籤、圖片 |
| 3:00 | 健康達人模式 ON | 熱量 / 等級氣泡 |
| 3:30 | 按讚、留言、收藏 | 社群互動 |
| 4:00 | 通知中心 | 站內通知 |
| 4:30 | 搜尋與篩選 | 關鍵字、分類、標籤 |
| 5:00 | AI 美食助理 | 對話示範 |
| 5:30 | `/api/docs/` | Swagger API |
| 6:00 | 試執行一個 API | RESTful 端點 |
| 6:30 | 個人檔案編輯 | 飲食偏好 |
| 7:00 | `/admin/` | 後台管理 |
| 7:30 | GitHub `main` 分支 | 原始碼倉庫 |

---

## 截圖清單（建議至少 15 張）

檔名範例：`01_首頁推薦.png`

### 環境與版本

| # | 內容 |
| --- | --- |
| 1 | `apache2` / `mariadb` 服務狀態 |
| 2 | `git log --oneline -3` + GitHub main 頁面 |

### 會員與 OAuth

| # | URL | 內容 |
| --- | --- | --- |
| 3 | `/accounts/login/` | 登入 + CAPTCHA |
| 4 | `/accounts/login/` | Google 登入按鈕 |
| 5 | `/accounts/profile/edit/` | 個人檔案、飲食偏好 |

### 核心功能

| # | URL | 內容 |
| --- | --- | --- |
| 6 | `/` | 動態牆 +「今天吃什麼？」 |
| 7 | 發文頁 | CKEditor + 上傳圖片 |
| 8 | `/posts/<id>/` | 貼文詳情 + 留言 |
| 9 | `/` | 健康達人模式開啟 |
| 10 | `/notifications/` | 通知列表 |
| 11 | `/` | 搜尋 / 篩選結果 |

### AI 與 API

| # | URL | 內容 |
| --- | --- | --- |
| 12 | AI 助理視窗 | 問答畫面 |
| 13 | `/api/docs/` | Swagger 總覽 |
| 14 | `/api/docs/` 或 `/api/redoc/` | API 端點展開 |

### 後台

| # | URL | 內容 |
| --- | --- | --- |
| 15 | `/admin/` | 後台列表 |

---

## 報告章節建議

1. 專題名稱與動機
2. 系統需求（功能 / 非功能）
3. 系統架構（見 `docs/report_diagrams.md`）
4. 資料庫設計（ERD）
5. 功能說明（每項附截圖）
6. 部署說明（WSL、Apache、MariaDB、`.env`）
7. 測試與成果
8. 結論與未來改進

附錄：GitHub 網址、示範影片檔名

---

## 功能完成對照表

| 功能 | 狀態 | 證明 |
| --- | :---: | --- |
| 會員註冊登入 + CAPTCHA | ✅ | 截圖 3 |
| Google OAuth | ✅ | 截圖 4、5 |
| 貼文發佈 | ✅ | 截圖 7、8 |
| 互動（讚/留言/收藏/追蹤） | ✅ | 截圖 8、影片 |
| 搜尋篩選 | ✅ | 截圖 11 |
| 個人化推薦 Top 3 | ✅ | 截圖 6 |
| 健康達人模式 | ✅ | 截圖 9 |
| 通知中心 | ✅ | 截圖 10 |
| AI 美食助理 | ✅ | 截圖 12 |
| REST API + Swagger | ✅ | 截圖 13、14 |
| Apache + MariaDB | ✅ | 截圖 1 |
| GitHub 原始碼 | ✅ | main 分支 |

---

## 繳交前檢查

- [ ] GitHub `main` 為最新程式
- [ ] 報告 PDF 可開啟、截圖清晰
- [ ] 影片 5～8 分鐘
- [ ] 報告內含 repo 網址與分支名稱
- [ ] 截圖 / 報告中**無** `.env`、密碼、API Key、PAT
- [ ] 檔名符合老師規定（學號_姓名_專題名稱 等）
