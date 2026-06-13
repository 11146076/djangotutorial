# REST API 端點說明

Base URL：`/api/v1/`

## 認證方式（並存）

1. **JWT**：`Authorization: Bearer <access_token>`
2. **Session**：瀏覽器 Cookie（同站請求）
3. **API Key**：`X-API-Key: <key>`

取得 JWT：見 `docs/jwt.md`  
API Key：見 `docs/parallel_auth.md`

---

## Auth

| Method | Endpoint | 說明 | Auth |
|--------|----------|------|------|
| POST | `/api/v1/auth/token/` | 取得 access + refresh token | 帳密 JSON |
| POST | `/api/v1/auth/token/refresh/` | 刷新 access token | refresh token |

**Request（token）**

```json
{"username": "demo", "password": "secret"}
```

**Response**

```json
{
  "access": "...",
  "refresh": "...",
  "username": "demo",
  "role": "member"
}
```

---

## Posts 資源

| Method | Endpoint | 說明 | Auth |
|--------|----------|------|------|
| GET | `/api/v1/posts/` | 列表（公開 + 自己的私密） | 可選 |
| POST | `/api/v1/posts/` | 建立貼文 | 必填 |
| GET | `/api/v1/posts/{id}/` | 單篇詳情 | 可選 |
| PUT/PATCH | `/api/v1/posts/{id}/` | 更新（作者） | 必填 |
| DELETE | `/api/v1/posts/{id}/` | 刪除（作者或 staff） | 必填 |
| GET | `/api/v1/posts/mine/` | 目前使用者全部貼文 | 必填 |

**Query**

- `?page=2` — 分頁（每頁 20 筆）

**Create body**

```json
{
  "title": "午餐推薦",
  "content": "<p>牛肉麵</p>",
  "category": 1,
  "tag_ids": [2, 3],
  "visibility": "public"
}
```

---

## Categories 資源

| Method | Endpoint | 說明 |
|--------|----------|------|
| GET | `/api/v1/categories/` | 分類列表 |
| GET | `/api/v1/categories/{id}/` | 單一分類 |

---

## Tags 資源

| Method | Endpoint | 說明 |
|--------|----------|------|
| GET | `/api/v1/tags/` | 標籤列表 |
| GET | `/api/v1/tags/{id}/` | 單一標籤 |

---

## AI Chat

| Method | Endpoint | 說明 | Auth |
|--------|----------|------|------|
| POST | `/api/v1/ai-chat/` | 美食 AI 對話 | 必填 |

**JSON body**

```json
{
  "message": "這道料理健康嗎？",
  "history": [{"role": "user", "content": "你好"}],
  "image_base64": "data:image/jpeg;base64,..."
}
```

**Multipart**：`message`、`history`（JSON 字串）、`image`（檔案）

---

## HTTP 狀態碼慣例

| 狀態碼 | 情境 |
|--------|------|
| 200 | 成功 |
| 201 | 建立成功 |
| 400 | 驗證錯誤 |
| 401 | 未認證 |
| 403 | 權限不足 |
| 404 | 資源不存在 |
| 500 | 伺服器錯誤 |

錯誤回應格式：`{"error": "訊息"}`

---

## 資源命名原則

- 名詞複數：`/posts/`、`/categories/`
- 巢狀動作以子路徑：`/posts/mine/`
- 版本前綴：`/api/v1/` 利於日後 v2 並存
- Web UI 路徑（`/accounts/login/`）與 API 路徑分離，避免混淆 HTML 與 JSON 回應
