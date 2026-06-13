# MariaDB / MySQL 資料庫設定

本專案**不使用 SQLite**，預設以 **MariaDB** 或 **MySQL** 作為資料庫。

## 建立資料庫

```sql
CREATE DATABASE eat_what CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'eatwhat'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON eat_what.* TO 'eatwhat'@'localhost';
FLUSH PRIVILEGES;
```

## 環境變數（`.env`）

```env
DB_ENGINE=django.db.backends.mysql
DB_NAME=eat_what
DB_USER=eatwhat
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

## Windows 開發（PyMySQL）

若無法安裝 `mysqlclient`，可改用 PyMySQL：

```env
USE_MYSQL=1
```

`mysite/__init__.py` 會在 `USE_MYSQL=1` 時自動載入 PyMySQL shim。

## 套用 Schema

```bash
python manage.py migrate
```

## 主要資料表

| 資料表 | 說明 |
|--------|------|
| `users` | 自訂使用者 |
| `profiles` | 個人資料 |
| `posts` | 貼文 |
| `categories` / `tags` | 分類與標籤 |
| `likes` / `collections` / `follows` | 互動 |
| `post_comment` | 留言 |
| `django_session` | Session |

完整 ERD 見 `docs/report_diagrams.md`。
