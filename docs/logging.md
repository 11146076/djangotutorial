# 後端日誌說明

專案使用 Python 內建 `logging` module，日誌寫入專案根目錄 `logs/`（已加入 `.gitignore`）。

## 日誌檔案

| 檔案 | 內容 |
|------|------|
| `logs/app.log` | 應用程式一般事件（posts、accounts、API） |
| `logs/django.log` | Django 框架與 HTTP 錯誤（4xx/5xx） |
| `logs/security.log` | 登入失敗、安全相關事件 |
| `logs/ai.log` | AI 助理與 API 呼叫 |

## 設定位置

`mysite/settings.py` → `LOGGING`

## 環境變數

```env
LOG_LEVEL=INFO   # DEBUG / INFO / WARNING / ERROR
```

## 輪替策略

採 `RotatingFileHandler`，單檔上限 2–5 MB，保留 3–5 個備份。

## 維運建議

```bash
tail -f logs/app.log
tail -f logs/security.log
grep ERROR logs/django.log
```
