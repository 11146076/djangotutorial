# JWT 認證（DRF）

採用 `djangorestframework-simplejwt`，與 Session、API Key 並存。

## 取得 Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"your_user","password":"your_password"}'
```

回應：

```json
{
  "refresh": "<refresh_token>",
  "access": "<access_token>",
  "username": "your_user",
  "role": "member"
}
```

## 刷新 Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh":"<refresh_token>"}'
```

## 呼叫 API

```bash
curl http://localhost:8000/api/v1/posts/ \
  -H "Authorization: Bearer <access_token>"
```

## 環境變數

```env
JWT_ACCESS_MINUTES=60
JWT_REFRESH_DAYS=7
```

## 認證優先順序（DRF）

1. JWT Bearer Token
2. Session Cookie
3. X-API-Key
