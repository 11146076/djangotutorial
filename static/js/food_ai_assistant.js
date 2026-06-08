/**
 * 等等吃啥 · AI 美食助理（前端）
 */
document.addEventListener("alpine:init", () => {
  Alpine.data("foodAiAssistant", () => ({
    open: false,
    messages: [],
    input: "",
    sending: false,
    pendingFile: null,
    pendingPreview: null,
    quickPrompts: [],

    i18n() {
      return window.FOOD_AI_I18N || {};
    },

    init() {
      const t = this.i18n();
      this.quickPrompts = [t.quick1, t.quick2, t.quick3, t.quick4].filter(Boolean);
      if (!this.quickPrompts.length) {
        this.quickPrompts = [
          "今天吃什麼？",
          "等等吃啥？",
          "月底吃土只有預算 100 怎麼吃？",
          "少油少鹽可以怎麼吃？",
        ];
      }
      this.resetWelcome();
    },

    resetWelcome() {
      const welcomeText =
        this.i18n().welcome ||
        "嗨，我是等等吃啥的美食助理。可以問我聚餐、口味、預算，或上傳食物照片一起討論。";
      // 預先算好 html：在 x-for 子作用域內若直接呼叫 renderMessageHtml 可能解析失敗
      this.messages = [
        {
          role: "assistant",
          text: welcomeText,
          html: this.renderMessageHtml(welcomeText),
          isWelcome: true,
        },
      ];
    },

    toggle() {
      this.open = !this.open;
      if (this.open) {
        queueMicrotask(() => this.scrollToBottom());
      }
    },

    clearConversation() {
      if (this.sending) return;
      this.resetWelcome();
      this.clearImage();
      this.input = "";
      queueMicrotask(() => this.scrollToBottom());
    },

    useQuick(text) {
      this.input = text;
      queueMicrotask(() => {
        const ta = document.querySelector("[data-food-ai-input]");
        if (ta) ta.focus();
      });
    },

    clearImage() {
      // 僅 blob: 預覽網址需要 revoke；data: URL 不必釋放
      if (this.pendingPreview && String(this.pendingPreview).startsWith("blob:")) {
        URL.revokeObjectURL(this.pendingPreview);
      }
      this.pendingFile = null;
      this.pendingPreview = null;
      const el = document.getElementById("food-ai-file");
      if (el) el.value = "";
    },

    /**
     * 用 Canvas 將圖片等比例縮放（長邊 ≤800px）、再匯出為 JPEG（品質 0.7）。
     * 解碼時優先使用 createImageBitmap(..., { imageOrientation: "from-image" })，
     * 讓瀏覽器依 EXIF 轉成正確方向，避免手機直拍在畫布上橫倒；失敗則降級為一般載入。
     */
    async compressImage(file) {
      let bitmapOrImg = null;
      let tempObjectUrl = null;

      const decodeWithExif = async () => {
        if (typeof createImageBitmap !== "function") return null;
        try {
          return await createImageBitmap(file, { imageOrientation: "from-image" });
        } catch {
          return null;
        }
      };

      try {
        bitmapOrImg = await decodeWithExif();
        if (!bitmapOrImg) {
          tempObjectUrl = URL.createObjectURL(file);
          const img = new Image();
          await new Promise((resolve, reject) => {
            img.onload = () => resolve();
            img.onerror = () => reject(new Error("無法載入圖片"));
            img.src = tempObjectUrl;
          });
          if (typeof createImageBitmap === "function") {
            bitmapOrImg = await createImageBitmap(img);
          } else {
            bitmapOrImg = img;
          }
        }

        const w = bitmapOrImg.width;
        const h = bitmapOrImg.height;
        const maxSide = 800;
        const longSide = Math.max(w, h);
        // 長邊大於 800 才縮小；否則維持原尺寸（仍轉成 JPEG 以統一格式）
        const scale = longSide <= maxSide ? 1 : maxSide / longSide;
        const targetW = Math.max(1, Math.round(w * scale));
        const targetH = Math.max(1, Math.round(h * scale));

        const canvas = document.createElement("canvas");
        canvas.width = targetW;
        canvas.height = targetH;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          throw new Error("無法取得 Canvas 2D 內容");
        }
        ctx.drawImage(bitmapOrImg, 0, 0, targetW, targetH);

        // 須 await toBlob 完成後再釋放 bitmap，否則匯出可能讀到已關閉的來源
        const blob = await new Promise((resolve, reject) => {
          canvas.toBlob(
            (b) => {
              if (b) resolve(b);
              else reject(new Error("圖片匯出失敗"));
            },
            "image/jpeg",
            0.7
          );
        });
        return blob;
      } finally {
        if (bitmapOrImg && typeof bitmapOrImg.close === "function") {
          bitmapOrImg.close();
        }
        if (tempObjectUrl) {
          URL.revokeObjectURL(tempObjectUrl);
        }
      }
    },

    /**
     * 選圖後先壓縮再存入 pendingFile（JPEG Blob 包成 File）；
     * pendingPreview 使用壓縮後 Blob 的 Object URL。
     */
    async pickImage(event) {
      const f = event.target.files && event.target.files[0];
      if (!f) return;
      if (!f.type || !f.type.startsWith("image/")) {
        window.alert(this.i18n().pickImageOnly || "請選擇圖片檔案");
        event.target.value = "";
        return;
      }
      if (f.size > 5 * 1024 * 1024) {
        window.alert(this.i18n().imageTooLarge || "圖片請小於 5MB");
        event.target.value = "";
        return;
      }
      this.clearImage();
      try {
        const blob = await this.compressImage(f);
        if (blob.size > 5 * 1024 * 1024) {
          window.alert(this.i18n().compressStillLarge || "壓縮後仍超過 5MB，請換一張較小的圖");
          event.target.value = "";
          return;
        }
        const stem = (f.name && f.name.replace(/\.[^/.]+$/, "")) || "image";
        this.pendingFile = new File([blob], `${stem}.jpg`, {
          type: "image/jpeg",
          lastModified: Date.now(),
        });
        this.pendingPreview = URL.createObjectURL(blob);
      } catch (err) {
        console.error(err);
        window.alert(this.i18n().compressFailed || "圖片壓縮失敗，請換一張圖片再試。");
        event.target.value = "";
      }
    },

    getCookie(name) {
      if (!document.cookie) return null;
      const parts = document.cookie.split(";");
      for (let i = 0; i < parts.length; i++) {
        const c = parts[i].trim();
        if (c.startsWith(name + "=")) {
          return decodeURIComponent(c.slice(name.length + 1));
        }
      }
      return null;
    },

    /** 跳脫 HTML，避免搭配 x-html 時被插入腳本。 */
    escapeHtml(s) {
      return String(s ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    },

    /**
     * 把 **粗體** 轉成 <strong>；換行轉 <br>。先 escapeHtml，輸出可安全用於 x-html。
     */
    renderMessageHtml(text) {
      let s = this.escapeHtml(text ?? "");
      s = s.replace(/\*\*([\s\S]+?)\*\*/g, "<strong>$1</strong>");
      s = s.replace(/\n/g, "<br>");
      return s == null ? "" : String(s);
    },

    /**
     * 用 FileReader 把檔案讀成 Data URL（內含 Base64），供 JSON 傳給後端。
     */
    fileToDataURL(file) {
      return new Promise((resolve, reject) => {
        const fr = new FileReader();
        fr.onload = () => resolve(fr.result);
        fr.onerror = () => reject(fr.error || new Error("讀取圖片失敗"));
        fr.readAsDataURL(file);
      });
    },

    historyForApi() {
      return this.messages
        .filter((m) => !m.isWelcome && (m.role === "user" || m.role === "assistant"))
        .map((m) => ({
          role: m.role,
          content: (m.text || "").slice(0, 4000),
        }))
        .filter((m) => m.content.length > 0);
    },

    scrollToBottom() {
      const el = document.getElementById("food-ai-scroll");
      if (el) el.scrollTop = el.scrollHeight;
    },

    feedSuggestionUrl(s) {
      const base = document.body.getAttribute("data-feed-list-url") || "/";
      const u = new URL(base.replace(/\/?$/, "/"), window.location.origin);
      if (s && s.type === "tag" && s.id) {
        u.searchParams.set("tag", String(s.id));
      } else {
        u.searchParams.set("q", (s && (s.query || s.name)) || "");
      }
      return u.pathname + u.search;
    },

    suggestionLabel(s) {
      const name = (s && (s.name || s.query)) || "";
      const tpl = this.i18n().viewRelatedPosts || "查看「{name}」相關貼文";
      return tpl.replace("{name}", name);
    },

    withRetryHint(message) {
      const text = String(message || "");
      const isTransient = /(timeout|逾時|429|502|503|504|上游暫時性錯誤)/i.test(text);
      if (!isTransient) return text;
      return `${text}\n\n小提醒：這通常是上游服務暫時忙碌或網路波動，請等 30-60 秒後再問一次。`;
    },

    async sendMessage() {
      if (this.sending) return;
      const text = (this.input || "").trim();
      if (!text && !this.pendingFile) return;

      const endpoint = document.body.getAttribute("data-ai-chat-url");
      if (!endpoint) {
        const t = this.i18n().loginRequired || "請先登入後再使用 AI 助理。";
        this.messages.push({
          role: "assistant",
          text: t,
          html: this.renderMessageHtml(t),
        });
        return;
      }

      this.sending = true;
      const fileCopy = this.pendingFile;
      const previewCopy = this.pendingPreview;

      let imageBase64 = null;
      let displayImage = previewCopy || null;
      if (fileCopy) {
        try {
          imageBase64 = await this.fileToDataURL(fileCopy);
          displayImage = imageBase64;
        } catch (e) {
          this.sending = false;
          const t = this.i18n().imageReadError || "抱歉：無法讀取圖片，請換一張再試。";
          this.messages.push({
            role: "assistant",
            text: t,
            html: this.renderMessageHtml(t),
          });
          queueMicrotask(() => this.scrollToBottom());
          return;
        }
      }

      const userText = text || (fileCopy ? this.i18n().uploadedImage || "（已上傳圖片）" : "");
      this.messages.push({
        role: "user",
        text: userText,
        image: displayImage || null,
        html: this.renderMessageHtml(userText),
      });
      this.input = "";
      this.pendingFile = null;
      this.pendingPreview = null;
      const fileInput = document.getElementById("food-ai-file");
      if (fileInput) fileInput.value = "";

      const token = this.getCookie("csrftoken");
      const imageTurnId =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : String(Date.now());
      const body = {
        // 只傳圖片時：避免每次送完全相同的文字，導致模型重複同一套回答
        message:
          text ||
          (fileCopy
            ? `請分析這張食物照片（請求編號：${imageTurnId}）。先列出你看得見的 3 個具體線索，再推測料理/份量，最後才估熱量並清楚寫出假設。`
            : ""),
        history: this.historyForApi(),
      };
      if (imageBase64) {
        body.image_base64 = imageBase64;
      }

      try {
        const res = await fetch(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { "X-CSRFToken": token } : {}),
          },
          body: JSON.stringify(body),
          credentials: "same-origin",
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data.error || res.statusText || "請求失敗");
        }
        const replyText = this.withRetryHint(data.reply || this.i18n().emptyReply || "（沒有回覆內容）");
        const suggestions = Array.isArray(data.suggestions) ? data.suggestions : [];
        this.messages.push({
          role: "assistant",
          text: replyText,
          html: this.renderMessageHtml(replyText),
          suggestions,
        });
      } catch (e) {
        const errText = this.withRetryHint(
          (this.i18n().sorryPrefix || "抱歉：") + (e.message || this.i18n().tryLater || "請稍後再試")
        );
        this.messages.push({
          role: "assistant",
          text: errText,
          html: this.renderMessageHtml(errText),
        });
      } finally {
        this.sending = false;
        queueMicrotask(() => this.scrollToBottom());
      }
    },
  }));
});
