# 🍴 等等吃啥（EatWhat）

美食社群平台：發文、互動、搜尋靈感，並整合 **AI 美食助理**、**健康達人模式**、**個人化推薦**、**通知中心**、**Google OAuth** 與 **RESTful API（Swagger）**。

- **GitHub（繳交用）**：<https://github.com/11146076/djangotutorial>（`main` 分支）
- **本機開發**：WSL Ubuntu + Apache + MariaDB，或 `runserver` 快速開發

---

## 主要功能

| 模組 | 說明 | 狀態 |
| --- | --- | :---: |
| 會員 | 註冊、登入/登出、CAPTCHA、個人檔案（頭像、簡介、飲食偏好） |
| Google OAuth | 第三方登入、個人頁連結/解除 Google 帳號 |
| 貼文 | 富文字發文、最多 3 張圖、公開/私密、動態牆、單篇瀏覽 |
| 互動 | 按讚、留言/回覆、留言按讚、收藏、追蹤 |
| 搜尋篩選 | 關鍵字、分類多選、標籤多選、搜尋紀錄 |
| 個人化推薦 | 首頁「今天吃什麼？」Top 3 美食靈感 |
| 通知中心 | 按讚、留言、回覆、追蹤者發文等站內通知 |
| AI 助理 | 美食對話助手（文字/圖片），浮動視窗 |
| 健康達人 | AI 健康分析 + 動態牆/詳情頁對話框顯示 |
| REST API | DRF ViewSets + OpenAPI（Swagger / ReDoc） |
| 後台管理 | 會員/貼文/留言/分類/標籤、CSV 匯出、重算讚數 |

---

## 重要網址（本機 Apache）

| 功能 | 路徑 |
| --- | --- |
| 動態牆（含推薦） | `/` |
| 登入 / 註冊 | `/accounts/login/`、`/accounts/register/` |
| Google OAuth | `/oauth/` |
| 通知中心 | `/notifications/` |
| 收藏列表 | `/collections/` |
| 個人頁 | `/@<username>/` |
| 個人檔案編輯 | `/accounts/profile/edit/` |
| Swagger API 文件 | `/api/docs/` |
| ReDoc API 文件 | `/api/redoc/` |
| OpenAPI Schema | `/api/schema/` |
| REST API v1 | `/api/v1/` |
| AI Chat API | `/api/v1/ai-chat/` |
| Django 後台 | `/admin/` |

---

## 個人化推薦（今天吃什麼？）

登入後於首頁（無搜尋/分類/標籤篩選、第 1 頁）顯示 **3 篇推薦貼文**。

排序依據：收藏、按讚、自己的發文、搜尋紀錄、飲食偏好、追蹤對象、健康等級與互動熱度。若個人化候選不足，會以熱門公開貼文補滿 3 篇。

相關程式：`posts/recommendations.py`、`posts/templates/posts/feed.html`

---

## 健康達人模式

- 發文後由 Celery 背景任務觸發 AI 分析（非同步）
- 資料表：`post_health_insights`；前端透過 `posts.latest_health_insight` 讀取
- 動態牆可一鍵切換健康模式，顯示熱量、A–D 等級與短評氣泡

| 欄位 | 說明 |
| --- | --- |
| `calories` | 熱量估算（kcal） |
| `health_rank` | 健康等級（A / B / C / D） |
| `reason` | 一句話短評 |
| `status` | `pending` / `completed` / `failed` |

歷史貼文回填：

```bash
python manage.py backfill_health_insights --sync
```

---

## 報告圖檔與文件

| 文件 | 說明 |
|------|------|
| [`docs/report_diagrams.md`](docs/report_diagrams.md) | 用例圖、ERD、部署圖、狀態圖、活動圖、類別圖 |
| [`docs/url_reference.md`](docs/url_reference.md) | urlpatterns 與 views 對照表 |
| [`docs/rest_api.md`](docs/rest_api.md) | REST 端點與資源規劃 |
| [`docs/database.md`](docs/database.md) | MariaDB 設定 |
| [`docs/logging.md`](docs/logging.md) | 後端日誌 |
| [`docs/i18n.md`](docs/i18n.md) | 多國語言 |
| [`docs/parallel_auth.md`](docs/parallel_auth.md) | 並存認證與角色授權 |
| [`docs/jwt.md`](docs/jwt.md) | JWT 認證 |
| [`deploy/README.md`](deploy/README.md) | Linux + Nginx + Gunicorn 部署 |

---

## 安全與注意事項

- `.env`、API Key、資料庫密碼、GitHub PAT **請勿**提交到 Git
- `DEBUG=true` 僅供開發；上線請關閉並設定 `ALLOWED_HOSTS`
- 本專案使用 `django-ckeditor`（CKEditor 4），上線前建議評估升級方案
- Google OAuth 需在 Google Cloud Console 設定正確的 Redirect URI

---

## 授權

本專題為課程作業用途；原始教學基底來自 Django Tutorial，並擴充為 EatWhat 美食社群平台。
