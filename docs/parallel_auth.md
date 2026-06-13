# 並存認證與角色授權

本專案在 Django 預設 Auth 之外，實作**第二套並存認證**與**角色分級授權**。

## 認證方式（並存）

| 方式 | 用途 | 機制 |
|------|------|------|
| **Session 帳密** | Web UI 登入 | `EmailUsernameModelBackend` + 登入表單 |
| **API Key** | 外部系統 / 腳本呼叫 API | Header `X-API-Key` + `ApiKeyBackend` |

兩者可並存：Web 使用者用帳密；整合系統用 API Key。

## 角色分級

| 角色 | 代碼 | 權限 |
|------|------|------|
| 一般會員 | `member` | 發文、互動 |
| 編輯 | `editor` | 管理分類/標籤 |
| 版主 | `moderator` | 內容審核（預留） |
| 管理員 | `admin` | 完整後台權限 |

`users.role` 欄位儲存角色；API Key 可設定獨立 `role`（取較高者為 effective role）。

## API Key 資料表

`api_keys`：user、name、key、role、is_active、last_used_at

建立金鑰：

```bash
python manage.py create_api_key <username> --name integration --role editor
```

## 使用範例

```bash
curl -H "X-API-Key: <your-key>" https://your.domain.com/api/v1/posts/
```

## 相關程式

- `accounts/auth_backends.py`
- `accounts/middleware.py`
- `accounts/api_auth.py`
- `accounts/permissions.py`
- `accounts/roles.py`
