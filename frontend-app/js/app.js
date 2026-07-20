class ImageUploadApp {
  constructor() {
    if (typeof auth === "undefined") throw new Error("Cognito auth is not initialized");
    this.selectedFiles = [];
    this.history = [];
    this.isUploading = false;
    this.resendTimer = null;
    this.cacheElements();
    this.attachEventListeners();
    this.checkAuthStatus();
  }

  cacheElements() {
    const byId = (id) => document.getElementById(id);
    this.authContainer = byId("auth-container");
    this.appContainer = byId("app-container");
    this.loginForm = byId("login-form");
    this.signupForm = byId("signup-form");
    this.confirmForm = byId("confirm-form");
    this.confirmEmail = byId("confirm-email");
    this.resendCodeBtn = byId("resend-code-btn");
    this.resendStatus = byId("resend-status");
    this.authError = byId("auth-error");
    this.authSuccess = byId("auth-success");
    this.dropZone = byId("drop-zone");
    this.imageInput = byId("imageFile");
    this.previewSection = byId("preview-section");
    this.previewGrid = byId("preview-grid");
    this.uploadBtn = byId("upload-btn");
    this.clearImagesBtn = byId("clear-images-btn");
    this.logoutBtn = byId("logout-btn");
    this.userName = byId("user-name");
    this.progressContainer = byId("progress-container");
    this.progressFill = byId("progress-fill");
    this.progressPercent = byId("progress-percent");
    this.progressText = byId("progress-text");
    this.resultsSection = byId("results-section");
    this.resultsContent = byId("results-content");
    this.historyList = byId("history-list");
    this.clearHistoryBtn = byId("clear-history-btn");
    this.toast = byId("toast");
  }

  attachEventListeners() {
    this.loginForm.addEventListener("submit", (event) => this.handleLogin(event));
    this.signupForm.addEventListener("submit", (event) => this.handleSignup(event));
    this.confirmForm.addEventListener("submit", (event) => this.handleConfirmSignup(event));
    this.resendCodeBtn.addEventListener("click", () => this.handleResendCode());
    document.getElementById("back-to-signup").addEventListener("click", (event) => {
      event.preventDefault();
      this.showAuthForm("signup");
    });
    document.querySelectorAll(".auth-tab").forEach((tab) => {
      tab.addEventListener("click", () => this.switchAuthTab(tab));
    });
    this.logoutBtn.addEventListener("click", () => this.handleLogout());
    this.dropZone.addEventListener("click", () => this.imageInput.click());
    this.imageInput.addEventListener("change", (event) => this.addFiles(Array.from(event.target.files)));
    this.uploadBtn.addEventListener("click", () => this.handleUpload());
    this.clearImagesBtn.addEventListener("click", () => this.clearSelectedImages());
    this.clearHistoryBtn.addEventListener("click", () => this.clearHistory());
    this.dropZone.addEventListener("dragover", (event) => {
      event.preventDefault();
      this.dropZone.classList.add("dragover");
    });
    this.dropZone.addEventListener("dragleave", () => this.dropZone.classList.remove("dragover"));
    this.dropZone.addEventListener("drop", (event) => {
      event.preventDefault();
      this.dropZone.classList.remove("dragover");
      this.addFiles(Array.from(event.dataTransfer.files).filter((file) => file.type.startsWith("image/")));
    });
  }

  checkAuthStatus() {
    if (auth.isLoggedIn()) {
      this.showApp();
      this.userName.textContent = auth.getUserEmail() || "User";
      this.loadHistory();
    } else {
      this.showAuth();
      this.renderHistory();
    }
  }

  async handleLogin(event) {
    event.preventDefault();
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    const button = this.loginForm.querySelector('button[type="submit"]');
    this.setLoading(button, "login-text", "login-spinner", true);
    try {
      const result = await auth.login(email, password);
      this.userName.textContent = result.email;
      this.showApp();
      await this.loadHistory();
      this.showToast("Đăng nhập thành công", "success");
    } catch (error) {
      if (error.code === "UserNotConfirmedException") {
        this.showConfirmationForm(email);
        this.showAuthError("Vui lòng nhập mã xác nhận đã gửi tới email của bạn.");
      } else {
        this.showAuthError(error.message);
      }
    } finally {
      this.setLoading(button, "login-text", "login-spinner", false);
    }
  }

  async handleSignup(event) {
    event.preventDefault();
    const name = document.getElementById("signup-name").value.trim();
    const email = document.getElementById("signup-email").value.trim();
    const password = document.getElementById("signup-password").value;
    const passwordConfirm = document.getElementById("signup-password-confirm").value;
    if (password !== passwordConfirm) {
      this.showAuthError("Mật khẩu xác nhận không khớp.");
      return;
    }
    const button = this.signupForm.querySelector('button[type="submit"]');
    this.setLoading(button, "signup-text", "signup-spinner", true);
    try {
      const result = await auth.signup(email, password, name);
      this.showAuthSuccess(result.message);
      this.showConfirmationForm(email);
    } catch (error) {
      this.showAuthError(error.message);
    } finally {
      this.setLoading(button, "signup-text", "signup-spinner", false);
    }
  }

  async handleConfirmSignup(event) {
    event.preventDefault();
    const code = document.getElementById("confirm-code").value.trim();
    const button = this.confirmForm.querySelector('button[type="submit"]');
    this.setLoading(button, "confirm-text", "confirm-spinner", true);
    try {
      const result = await auth.confirmSignup(this.confirmEmail.value, code);
      document.getElementById("login-email").value = this.confirmEmail.value;
      this.showAuthForm("login");
      this.showAuthSuccess(result.message);
    } catch (error) {
      if (error.code === "NotAuthorizedException") {
        document.getElementById("login-email").value = this.confirmEmail.value;
        this.showAuthForm("login");
        this.showAuthSuccess("Tài khoản đã được xác nhận. Bạn có thể đăng nhập.");
      } else {
        this.showAuthError(error.message);
      }
    } finally {
      this.setLoading(button, "confirm-text", "confirm-spinner", false);
    }
  }

  async handleResendCode() {
    this.resendCodeBtn.disabled = true;
    try {
      const result = await auth.resendConfirmationCode(this.confirmEmail.value);
      this.showAuthSuccess(result.message);
      this.startResendCooldown(30);
    } catch (error) {
      this.showAuthError(error.message);
      this.resendCodeBtn.disabled = false;
    }
  }

  showConfirmationForm(email) {
    this.confirmEmail.value = email;
    this.showAuthForm("confirm");
    document.getElementById("confirm-code").focus();
    this.startResendCooldown(30);
  }

  startResendCooldown(seconds) {
    clearInterval(this.resendTimer);
    let remaining = seconds;
    this.resendCodeBtn.disabled = true;
    this.resendStatus.textContent = `Có thể gửi lại sau ${remaining} giây`;
    this.resendTimer = setInterval(() => {
      remaining -= 1;
      this.resendStatus.textContent = remaining > 0 ? `Có thể gửi lại sau ${remaining} giây` : "";
      if (remaining <= 0) {
        clearInterval(this.resendTimer);
        this.resendCodeBtn.disabled = false;
      }
    }, 1000);
  }

  setLoading(button, textId, spinnerId, loading) {
    button.disabled = loading;
    document.getElementById(textId)?.classList.toggle("hidden", loading);
    document.getElementById(spinnerId)?.classList.toggle("hidden", !loading);
  }

  switchAuthTab(tab) {
    document.querySelectorAll(".auth-tab").forEach((item) => item.classList.remove("active"));
    tab.classList.add("active");
    this.showAuthForm(tab.dataset.tab);
    this.authError.classList.add("hidden");
    this.authSuccess.classList.add("hidden");
  }

  showAuthForm(name) {
    document.querySelectorAll(".auth-form").forEach((form) => form.classList.remove("active-form"));
    document.getElementById(`${name}-form`)?.classList.add("active-form");
  }

  showAuthError(message) {
    this.authError.textContent = message;
    this.authError.classList.remove("hidden");
    this.authSuccess.classList.add("hidden");
  }

  showAuthSuccess(message) {
    this.authSuccess.textContent = message;
    this.authSuccess.classList.remove("hidden");
    this.authError.classList.add("hidden");
  }

  showAuth() {
    this.authContainer.style.display = "flex";
    this.appContainer.classList.add("hidden");
  }

  showApp() {
    this.authContainer.style.display = "none";
    this.appContainer.classList.remove("hidden");
  }

  handleLogout() {
    if (!confirm("Bạn có chắc muốn đăng xuất?")) return;
    auth.logout();
    clearInterval(this.resendTimer);
    this.history = [];
    this.selectedFiles = [];
    this.resultsContent.replaceChildren();
    this.resultsSection.classList.add("hidden");
    this.updatePreview();
    this.renderHistory();
    this.showAuth();
    this.showToast("Đã đăng xuất", "success");
  }

  addFiles(files) {
    const maxSize = AWS_CONFIG.app.maxFileSize || 10 * 1024 * 1024;
    files.forEach((file) => {
      if (!file.type.startsWith("image/")) return;
      if (file.size > maxSize) {
        this.showToast(`${file.name} quá lớn (tối đa 10MB)`, "error");
      } else if (!this.selectedFiles.some((item) => item.name === file.name && item.size === file.size)) {
        this.selectedFiles.push(file);
      }
    });
    this.updatePreview();
  }

  updatePreview() {
    this.previewSection.classList.toggle("hidden", this.selectedFiles.length === 0);
    this.previewGrid.replaceChildren();
    this.selectedFiles.forEach((file, index) => {
      const reader = new FileReader();
      reader.onload = (event) => {
        const item = document.createElement("div");
        item.className = "preview-item";
        const image = document.createElement("img");
        image.src = event.target.result;
        image.alt = file.name;
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "preview-item-remove";
        remove.textContent = "×";
        remove.addEventListener("click", () => {
          this.selectedFiles.splice(index, 1);
          this.updatePreview();
        });
        item.append(image, remove);
        this.previewGrid.appendChild(item);
      };
      reader.readAsDataURL(file);
    });
  }

  clearSelectedImages() {
    if (confirm("Xóa tất cả ảnh đã chọn?")) {
      this.selectedFiles = [];
      this.updatePreview();
    }
  }

  async handleUpload() {
    if (!this.selectedFiles.length || this.isUploading) return;
    this.isUploading = true;
    this.uploadBtn.disabled = true;
    this.progressContainer.classList.remove("hidden");
    const results = [];
    for (let index = 0; index < this.selectedFiles.length; index += 1) {
      const file = this.selectedFiles[index];
      this.updateProgress(Math.round(((index + 1) / this.selectedFiles.length) * 100), `Đang xử lý ${file.name}...`);
      try {
        const upload = await this.uploadFile(file);
        const inference = await this.waitForInference(upload.image_id);
        results.push({ file: file.name, status: "success", inference });
      } catch (error) {
        results.push({ file: file.name, status: "error", error: error.message });
      }
    }
    this.displayResults(results);
    await this.loadHistory();
    this.selectedFiles = [];
    this.updatePreview();
    this.progressContainer.classList.add("hidden");
    this.isUploading = false;
    this.uploadBtn.disabled = false;
  }

  async uploadFile(file) {
    const response = await this.authorizedFetch(`${AWS_CONFIG.apiGateway.endpoint}${AWS_CONFIG.apiGateway.presignUrl}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, contentType: file.type }),
    });
    if (!response.ok) throw new Error(await this.apiError(response, "Lấy pre-signed URL thất bại"));
    const upload = await response.json();
    const putResponse = await fetch(upload.upload_url, {
      method: "PUT",
      headers: {
        "Content-Type": file.type,
        "x-amz-meta-user-id": upload.metadata["user-id"],
        "x-amz-meta-upload-time": upload.metadata["upload-time"],
        "x-amz-meta-original-name": upload.metadata["original-name"],
      },
      body: file,
    });
    if (!putResponse.ok) throw new Error("Tải ảnh lên S3 thất bại");
    return upload;
  }

  async waitForInference(scanId) {
    for (let attempt = 0; attempt < 30; attempt += 1) {
      const response = await this.authorizedFetch(
        `${AWS_CONFIG.apiGateway.endpoint}${AWS_CONFIG.apiGateway.resultsUrl}?image_id=${encodeURIComponent(scanId)}`,
      );
      if (response.ok) {
        const result = (await response.json()).results;
        if (result.status === "REJECTED") {
          throw new Error(result.message || "Ảnh không hợp lệ, vui lòng chọn ảnh lá cây rõ nét.");
        }
        return result.predictions || result;
      }
      if (response.status !== 404) throw new Error(await this.apiError(response, "Không thể lấy kết quả AI"));
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
    throw new Error("AI chưa xử lý xong trong thời gian cho phép");
  }

  updateProgress(percent, text) {
    this.progressFill.style.width = `${percent}%`;
    this.progressPercent.textContent = `${percent}%`;
    this.progressText.textContent = text;
  }

  displayResults(results) {
    this.resultsSection.classList.remove("hidden");
    this.resultsContent.replaceChildren();
    results.forEach((result) => {
      const item = document.createElement("div");
      item.className = "result-item";
      if (result.status === "success") {
        const confidence = Number(result.inference.confidence || 0);
        item.textContent = `${result.file}: ${result.inference.crop || "Không xác định"} - ${result.inference.disease || result.inference.prediction || "Không xác định"} (${(confidence * 100).toFixed(1)}%)`;
      } else {
        item.textContent = `${result.file}: ${result.error}`;
      }
      this.resultsContent.appendChild(item);
    });
  }

  async authorizedFetch(url, options = {}) {
    return fetch(url, {
      ...options,
      headers: { ...(options.headers || {}), Authorization: auth.getIdToken() },
    });
  }

  async apiError(response, fallback) {
    try {
      return (await response.json()).error || fallback;
    } catch (_) {
      return fallback;
    }
  }

  async loadHistory() {
    if (!auth.isLoggedIn()) {
      this.history = [];
      this.renderHistory();
      return;
    }
    try {
      const response = await this.authorizedFetch(`${AWS_CONFIG.apiGateway.endpoint}${AWS_CONFIG.apiGateway.resultsUrl}`);
      if (!response.ok) throw new Error(await this.apiError(response, "Không thể tải lịch sử"));
      this.history = (await response.json()).results || [];
      this.renderHistory();
    } catch (error) {
      this.history = [];
      this.renderHistory();
      this.showToast(error.message, "error");
    }
  }

  renderHistory() {
    this.historyList.replaceChildren();
    if (!this.history.length) {
      const empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = "Chưa có lịch sử tải lên";
      this.historyList.appendChild(empty);
      return;
    }
    this.history.forEach((item) => {
      const row = document.createElement("div");
      row.className = "history-item";
      const details = document.createElement("div");
      details.textContent = item.status === "REJECTED"
        ? "Ảnh không hợp lệ"
        : item.prediction || item.predicted_class || item.rawImageKey || item.s3_key || item.image_id;
      const time = document.createElement("div");
      time.className = "history-item-time";
      time.textContent = new Date(item.createdAt || item.processed_at).toLocaleString("vi-VN");
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "btn btn-danger btn-sm history-delete";
      remove.textContent = "Xóa";
      remove.addEventListener("click", () => this.deleteHistoryItem(item.scanId || item.image_id));
      row.append(details, time, remove);
      this.historyList.appendChild(row);
    });
  }

  async deleteHistoryItem(scanId, confirmed = false) {
    if (!confirmed && !confirm("Xóa lịch sử này và các ảnh liên quan?")) return false;
    const response = await this.authorizedFetch(
      `${AWS_CONFIG.apiGateway.endpoint}${AWS_CONFIG.apiGateway.resultsUrl}/${encodeURIComponent(scanId)}`,
      { method: "DELETE" },
    );
    if (!response.ok) {
      this.showToast(await this.apiError(response, "Xóa lịch sử thất bại"), "error");
      return false;
    }
    this.history = this.history.filter((item) => (item.scanId || item.image_id) !== scanId);
    this.renderHistory();
    this.showToast("Đã xóa lịch sử", "success");
    return true;
  }

  async clearHistory() {
    if (!this.history.length || !confirm("Xóa toàn bộ lịch sử và ảnh liên quan của bạn?")) return;
    for (const item of [...this.history]) {
      await this.deleteHistoryItem(item.scanId || item.image_id, true);
    }
  }

  showToast(message, type = "info") {
    this.toast.textContent = message;
    this.toast.className = `toast ${type}`;
    setTimeout(() => this.toast.classList.add("hidden"), 3000);
  }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = ImageUploadApp;
}
