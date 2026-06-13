# 🍴 等等吃啥（EatWhat）

美食社群平台：發文、看文、用分類/標籤找靈感，並可按讚、留言、收藏、追蹤。  
目前已加入 **健康達人模式**：可在貼文上顯示 AI 估算熱量、A-D 健康等級與一句話短評。

---

## 主要功能

| 模組 | 說明 | 狀態 |
| --- | --- | :---: |
| 會員 | 註冊、登入/登出、個人檔案（頭像、簡介、飲食偏好） | 已完成 |
| 貼文 | 富文字發文、最多 3 張圖、公開/私密、動態牆、單篇瀏覽 | 已完成 |
| 互動 | 按讚、留言/回覆、留言按讚、收藏、追蹤 | 已完成 |
| 搜尋篩選 | 關鍵字、分類多選、標籤多選、搜尋紀錄 | 已完成 |
| AI 助理 | 美食對話助手（文字/圖片） | 已完成 |
| 健康達人 | AI 健康分析 + 卡片/詳情頁對話框顯示 | 已完成 |
| 後台管理 | 會員/貼文/留言/分類/標籤、CSV 匯出、重算讚數 | 已完成 |

---

## 健康達人模式（本次重點）

- 發文後由背景任務觸發 AI 分析（非同步，避免發文等待）
- 儲存於 `post_health_insights`（關聯表）
- `posts.latest_health_insight` 作為前端快速讀取入口
- 前端可一鍵切換健康模式，顯示 AI 對話氣泡

### 分析欄位

- `calories`：熱量估算（kcal）
- `health_rank`：健康等級（A/B/C/D）
- `reason`：一句話短評
- `status`：`pending` / `completed` / `failed`

---

## 技術棧

- **後端**：Django 5.x（Python）
- **資料庫**：MariaDB
- **快取/任務佇列**：Redis + Celery
- **畫面**：Django Template + Tailwind + Alpine.js（部分互動）
- **編輯器**：django-ckeditor
- **後台匯出**：django-import-export

---

## 本機開發

### 1) 安裝套件

```powershell
pip install -r requirements.txt
```

### 2) 設定資料庫與環境變數

- 建立 DB：`eat_what`
- `.env` 至少需包含 DB 連線資訊、AI key（若要啟用 AI）
- Celery/Redis 可用預設值：
  - `CELERY_BROKER_URL=redis://127.0.0.1:6379/0`
  - `CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/1`

### 3) 套用 migration

```powershell
python manage.py migrate
```

### 4) 建立管理員（可選）

```powershell
python manage.py createsuperuser
```

### 5) 啟動服務

**終端 A（Celery）**
```powershell
celery -A mysite worker -l info -P solo
```


**終端 B（Django）**
```powershell
python manage.py runserver
```

---

## 舊貼文健康分析回填

已提供管理指令可一次補跑歷史貼文：

```powershell
python manage.py backfill_health_insights
```

- 預設：丟進 Celery 非同步處理
- 若要同步執行：

```powershell
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

- `.env`、API key、資料庫密碼請勿提交到 Git。
- 本專案使用 `django-ckeditor`（CKEditor 4），若上線建議評估升級方案。
