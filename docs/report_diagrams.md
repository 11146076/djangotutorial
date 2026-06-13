# 等等吃啥 — 系統圖表（報告用）

本文件包含用例圖、ERD、部署圖；加分項目含狀態圖與活動圖。  
可在 [Mermaid Live Editor](https://mermaid.live) 或支援 Mermaid 的 Markdown 編輯器預覽。

---

## 1. 用例圖（Use Case Diagram）

```mermaid
flowchart LR
    subgraph Actors
        Guest((訪客))
        Member((會員))
        Editor((編輯))
        Admin((管理員))
        External((外部系統))
    end

    subgraph EatWhat["等等吃啥平台"]
        UC1[瀏覽動態牆]
        UC2[註冊/登入]
        UC3[發文/編輯貼文]
        UC4[按讚/留言/收藏]
        UC5[追蹤使用者]
        UC6[AI 美食助理]
        UC7[健康達人分析]
        UC8[管理分類/標籤]
        UC9[後台管理]
        UC10[REST API 呼叫]
        UC11[切換語言]
    end

    Guest --> UC1
    Guest --> UC2
    Guest --> UC11
    Member --> UC3
    Member --> UC4
    Member --> UC5
    Member --> UC6
    Member --> UC7
    Editor --> UC8
    Admin --> UC9
    External --> UC10
    Member --> UC10
```

---

## 2. ERD（實體關係模型）

```mermaid
erDiagram
    USERS ||--|| PROFILES : has
    USERS ||--o{ API_KEYS : owns
    USERS ||--o{ POSTS : authors
    USERS ||--o{ LIKES : gives
    USERS ||--o{ COLLECTIONS : saves
    USERS ||--o{ FOLLOWS : follows
    USERS ||--o{ POST_COMMENT : writes
    USERS ||--o{ AI_CHAT_LOGS : chats

    CATEGORIES ||--o{ POSTS : categorizes
    TAGS }o--o{ POSTS : tags

    POSTS ||--o{ LIKES : receives
    POSTS ||--o{ COLLECTIONS : collected_in
    POSTS ||--o{ POST_COMMENT : has
    POSTS ||--o| POST_HEALTH_INSIGHTS : latest_insight

    POST_COMMENT ||--o{ POST_COMMENT_LIKES : receives
    POST_COMMENT ||--o| POST_COMMENT : replies_to

    USERS {
        bigint id PK
        varchar username UK
        varchar email UK
        varchar password
        varchar role
        datetime created_at
    }

    PROFILES {
        bigint user_id PK,FK
        varchar avatar
        text bio
        varchar dietary_preference
    }

    API_KEYS {
        bigint id PK
        bigint user_id FK
        varchar key UK
        varchar role
        bool is_active
    }

    POSTS {
        bigint id PK
        bigint user_id FK
        bigint category_id FK
        text content
        varchar visibility
        int like_count
        datetime created_at
    }

    CATEGORIES {
        bigint id PK
        varchar name
    }

    TAGS {
        bigint id PK
        varchar name
    }

    POST_HEALTH_INSIGHTS {
        bigint id PK
        bigint post_id FK
        int calories
        char health_rank
        varchar status
    }
```

---

## 3. 部署圖（Deployment Diagram）

```mermaid
flowchart TB
    subgraph Client["使用者端"]
        Browser[Web Browser]
        APIClient[外部 API Client]
    end

    subgraph LinuxServer["Linux Server"]
        subgraph Nginx["Nginx Virtual Host"]
            Static[/static/]
            Media[/media/]
            Proxy[Reverse Proxy]
        end

        subgraph AppTier["Application Tier"]
            Gunicorn[Gunicorn WSGI]
            Django[Django Application\nmysite.wsgi]
            Celery[Celery Worker]
        end

        subgraph DataTier["Data Tier"]
            MariaDB[(MariaDB / MySQL)]
            Redis[(Redis)]
            LogFiles[logs/*.log]
        end
    end

    Browser --> Nginx
    APIClient --> Nginx
    Nginx --> Static
    Nginx --> Media
    Nginx --> Proxy
    Proxy --> Gunicorn
    Gunicorn --> Django
    Django --> MariaDB
    Django --> Redis
    Django --> LogFiles
    Celery --> Redis
    Celery --> MariaDB
    Celery --> Django
```

---

## 4. 狀態圖 — 貼文健康分析（加分）

```mermaid
stateDiagram-v2
    [*] --> pending: 發文觸發 Celery 任務
    pending --> completed: AI 分析成功
    pending --> failed: AI 逾時/錯誤
    failed --> pending: 管理員重試
    completed --> pending: 內容更新重分析
    completed --> [*]
    failed --> [*]
```

---

## 5. 活動圖 — 使用者登入（加分）

```mermaid
flowchart TD
    A[開啟登入頁] --> B[輸入帳號/密碼]
    B --> C[輸入 CAPTCHA]
    C --> D{勾選我不是機器人?}
    D -- 否 --> E[顯示錯誤]
    E --> B
    D -- 是 --> F{驗證碼正確?}
    F -- 否 --> G[Refresh CAPTCHA]
    G --> C
    F -- 是 --> H{帳密正確?}
    H -- 否 --> I[寫入 security.log]
    I --> E
    H -- 是 --> J[建立 Session]
    J --> K[導向動態牆]
    K --> [*]
```

---

## 6. 類別圖（ORM 對映摘要）

```mermaid
classDiagram
    class User {
        +username
        +email
        +role
        +authenticate()
    }
    class Profile {
        +avatar
        +bio
    }
    class ApiKey {
        +key
        +role
        +effective_role()
    }
    class Post {
        +title
        +content
        +visibility
        +gallery_images()
    }
    class Category
    class Tag
    class Collection
    class Like

    User "1" --> "1" Profile
    User "1" --> "*" ApiKey
    User "1" --> "*" Post
    Post "*" --> "0..1" Category
    Post "*" --> "*" Tag
    User "*" --> "*" Post : Collection
```
