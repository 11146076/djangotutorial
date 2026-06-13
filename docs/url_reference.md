# urlpatterns 與 views 功能對照表

## 全站路由（mysite/urls.py）

| URL Pattern | 名稱 | 說明 |
|-------------|------|------|
| `/admin/` | — | EatWhat 自訂後台 |
| `/captcha/` | — | 圖片驗證碼 |
| `/api/v1/` | `posts_api:*` | RESTful API |
| `/api/v1/auth/` | `accounts_api:*` | JWT Token |
| `/ckeditor/` | — | 富文字編輯器上傳 |
| `/accounts/` | `accounts:*` | 會員系統 |
| `/i18n/setlang/` | `set_language` | 語言切換 |
| `/` | `posts:*` | 貼文與動態牆 |

---

## Web UI — posts（`posts/urls.py`）

| URL | name | View | HTTP | 說明 |
|-----|------|------|------|------|
| `/` | `posts:feed` | `feed` | GET/POST | 動態牆、搜尋、發文 |
| `/collections/` | `posts:collections_list` | `collections_list` | GET | 我的收藏（分類篩選） |
| `/<pk>/` | `posts:post_detail` | `post_detail` | GET | 貼文詳情 |
| `/<pk>/edit/` | `posts:post_edit` | `post_edit` | GET/POST | 編輯貼文 |
| `/<pk>/delete/` | `posts:post_delete` | `post_delete` | GET/POST | 刪除貼文 |
| `/<pk>/like-toggle/` | `posts:like_toggle` | `like_toggle` | POST | 按讚切換 |
| `/<pk>/collect-toggle/` | `posts:collect_toggle` | `collect_toggle` | POST | 收藏切換 |
| `/<pk>/comment/` | `posts:comment_create` | `comment_create` | POST | 新增留言 |
| `/<pk>/comment/<id>/like-toggle/` | `posts:comment_like_toggle` | `comment_like_toggle` | POST | 留言按讚 |
| `/<pk>/comment/<id>/edit/` | `posts:comment_edit` | `comment_edit` | GET/POST | 編輯留言 |
| `/<pk>/comment/<id>/delete/` | `posts:comment_delete` | `comment_delete` | POST | 刪除留言 |
| `/categories/` | `posts:category_manage` | `category_manage` | GET/POST | 分類管理（editor+） |
| `/categories/<pk>/delete/` | `posts:category_delete` | `category_delete` | POST | 刪除分類 |
| `/tags/` | `posts:tag_manage` | `tag_manage` | GET/POST | 標籤管理（editor+） |
| `/tags/<pk>/delete/` | `posts:tag_delete` | `tag_delete` | POST | 刪除標籤 |
| `/ai-chat/` | `posts:ai_chat` | `AiChatAPIView` | POST | AI 助理（DRF，相容舊路徑） |

---

## Web UI — accounts（`accounts/urls.py`）

| URL | name | View | HTTP | 說明 |
|-----|------|------|------|------|
| `/accounts/register/` | `accounts:register` | `register` | GET/POST | 註冊 |
| `/accounts/login/` | `accounts:login` | `LoginView` | GET/POST | 登入（CAPTCHA） |
| `/accounts/logout/` | `accounts:logout` | `LogoutView` | POST | 登出 |
| `/accounts/profile/edit/` | `accounts:profile_edit` | `profile_edit` | GET/POST | 編輯個人檔案 |
| `/accounts/@<user>/` | `accounts:profile_detail` | `profile_detail` | GET | 個人頁 |
| `/accounts/@<user>/follow-toggle/` | `accounts:follow_toggle` | `follow_toggle` | POST | 追蹤切換 |
| `/accounts/@<user>/posts/` | `accounts:profile_posts` | `profile_posts` | GET | 使用者貼文列表 |
| `/accounts/@<user>/comments/` | `accounts:profile_comments` | `profile_comments` | GET | 使用者留言列表 |

---

## RESTful API — 資源規劃

詳見 `docs/rest_api.md`。

| 資源 | Base URL | 認證 |
|------|----------|------|
| Posts | `/api/v1/posts/` | JWT / Session / API Key |
| Categories | `/api/v1/categories/` | 同上 |
| Tags | `/api/v1/tags/` | 同上 |
| AI Chat | `/api/v1/ai-chat/` | 需登入 |
| Auth Token | `/api/v1/auth/token/` | 帳密 |

### Web UI vs REST 設計差異

| 面向 | Web UI | REST API |
|------|--------|----------|
| 呈現 | HTML Template | JSON |
| 認證 | Session Cookie | JWT Bearer / API Key |
| 互動 | 表單 POST + 整頁/片段 | HTTP 動詞 + 狀態碼 |
| 錯誤 | messages 框架 | `{"error": "..."}` |
| 分頁 | Django Paginator | `?page=` PageNumberPagination |
