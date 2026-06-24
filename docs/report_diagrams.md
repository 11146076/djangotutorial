# EatWhat 報告用圖表（Mermaid）

可直接複製到支援 Mermaid 的編輯器（GitHub、Typora、VS Code 外掛），或匯出成 PNG 貼進 Word / PowerPoint。

---

## 1. 系統架構（部署）

```mermaid
flowchart LR
    U[使用者瀏覽器] --> A[Apache + mod_wsgi]
    A --> D[Django 應用]
    D --> M[(MariaDB)]
    D --> R[(Redis)]
    R --> C[Celery Worker]
    C --> D
    D --> AI[NVIDIA / Gemini API]
    D --> G[Google OAuth]
```

---

## 2. 用例圖（Use Case）

```mermaid
flowchart TB
    subgraph Actors
        V[訪客]
        M[會員]
        AD[管理員]
    end

    subgraph EatWhat
        UC1[瀏覽動態牆]
        UC2[註冊 / 登入 / CAPTCHA]
        UC3[Google OAuth 登入]
        UC4[發文 / 編輯 / 刪除]
        UC5[按讚 / 留言 / 收藏 / 追蹤]
        UC6[搜尋與篩選]
        UC7[個人化推薦 Top 3]
        UC8[通知中心]
        UC9[AI 美食助理]
        UC10[健康達人模式]
        UC11[REST API / Swagger]
        UC12[後台管理]
    end

    V --> UC1
    V --> UC2
    V --> UC3
    M --> UC1
    M --> UC4
    M --> UC5
    M --> UC6
    M --> UC7
    M --> UC8
    M --> UC9
    M --> UC10
    M --> UC11
    AD --> UC12
```

---

## 3. ERD（實體關聯圖）

```mermaid
erDiagram
    USER ||--o| PROFILE : has
    USER ||--o{ POST : authors
    USER ||--o{ LIKE : gives
    USER ||--o{ COLLECTION : saves
    USER ||--o{ FOLLOW : follows
    USER ||--o{ NOTIFICATION : receives
    USER ||--o{ SEARCH_LOG : logs
    USER ||--o{ AI_CHAT_LOG : chats

    POST ||--o{ LIKE : has
    POST ||--o{ POST_COMMENT : has
    POST ||--o{ COLLECTION : collected_in
    POST }o--o{ TAG : tagged
    POST }o--o| CATEGORY : belongs_to
    POST ||--o| POST_HEALTH_INSIGHT : has
    POST ||--o{ NOTIFICATION : relates

    POST_COMMENT ||--o{ COMMENT_LIKE : has
    POST_COMMENT ||--o{ POST_COMMENT : replies_to

    USER {
        int id PK
        string username
        string email
    }

    PROFILE {
        int id PK
        int user_id FK
        string dietary_preference
        string bio
    }

    POST {
        int id PK
        int author_id FK
        int category_id FK
        string title
        text content
        string visibility
    }

    POST_HEALTH_INSIGHT {
        int id PK
        int post_id FK
        int calories
        string health_rank
        string reason
        string status
    }

    NOTIFICATION {
        int id PK
        int recipient_id FK
        int actor_id FK
        string notification_type
        bool is_read
    }

    CATEGORY {
        int id PK
        string name
    }

    TAG {
        int id PK
        string name
    }
```

---

## 4. 發文與健康分析流程

```mermaid
sequenceDiagram
    participant U as 會員
    participant W as Django Web
    participant Q as Celery / Redis
    participant AI as AI API
    participant DB as MariaDB

    U->>W: 提交新貼文
    W->>DB: 儲存 Post
    W->>Q: 排程健康分析任務
    W-->>U: 立即回應（不等待 AI）

    Q->>AI: 分析圖文內容
    AI-->>Q: 熱量 / 等級 / 短評
    Q->>DB: 寫入 PostHealthInsight
    U->>W: 重新整理動態牆
    W->>DB: 讀取 latest_health_insight
    W-->>U: 顯示健康達人氣泡
```

---

## 5. 個人化推薦流程

```mermaid
flowchart TD
    A[登入會員進入首頁] --> B{無搜尋/篩選且第 1 頁?}
    B -- 否 --> Z[不顯示推薦區]
    B -- 是 --> C[建立偏好檔案]
    C --> D[收藏 / 按讚 / 發文 / 搜尋 / 追蹤 / 飲食偏好]
    D --> E[篩選公開貼文候選]
    E --> F[評分排序]
    F --> G{不足 3 篇?}
    G -- 是 --> H[以熱門公開貼文補滿]
    G -- 否 --> I[取 Top 3]
    H --> I
    I --> J[顯示「今天吃什麼？」區塊]
```

---

## 匯出成圖片的方式

1. **GitHub**：將本檔 push 後在 repo 內預覽，截圖 Mermaid 區塊
2. **Mermaid Live Editor**：<https://mermaid.live/> 貼上程式碼後 Export PNG/SVG
3. **VS Code**：安裝 Mermaid 外掛後預覽並匯出
