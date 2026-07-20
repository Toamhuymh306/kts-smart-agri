// ===== AWS Cognito Authentication =====

if (typeof AmazonCognitoIdentity === "undefined") {
  console.error("❌ AWS Cognito SDK not loaded! Check script tags in HTML.");
  throw new Error(
    "AWS Cognito SDK not loaded. Load amazon-cognito-identity-js before auth.js",
  );
}

class CognitoAuth {
  constructor(config) {
    this.config = config;
    this.userPool = new AmazonCognitoIdentity.CognitoUserPool({
      UserPoolId: config.cognito.userPoolId,
      ClientId: config.cognito.clientId,
    });
    this.currentUser = null;
    this.idToken = null;
  }

  /**
   * Đăng nhập
   */
  async login(email, password) {
    return new Promise((resolve, reject) => {
      const authenticationDetails =
        new AmazonCognitoIdentity.AuthenticationDetails({
          Username: email,
          Password: password,
        });

      const cognitoUser = new AmazonCognitoIdentity.CognitoUser({
        Username: email,
        Pool: this.userPool,
      });

      cognitoUser.authenticateUser(authenticationDetails, {
        onSuccess: (session) => {
          this.currentUser = cognitoUser;
          this.idToken = session.getIdToken().getJwtToken();

          localStorage.setItem("idToken", this.idToken);
          localStorage.setItem("userEmail", email);

          resolve({
            success: true,
            idToken: this.idToken,
            email: email,
            message: "Đăng nhập thành công",
          });
        },
        onFailure: (err) => {
          reject({
            success: false,
            code: err.code,
            message: this.getErrorMessage(err),
          });
        },
        newPasswordRequired: (userAttributes, requiredAttributes) => {
          reject({
            success: false,
            message: "Yêu cầu đổi mật khẩu lần đầu",
            newPasswordRequired: true,
          });
        },
      });
    });
  }

  /**
   * Đăng ký tài khoản mới
   */
  async signup(email, password, name) {
    return new Promise((resolve, reject) => {
      const attributeList = [
        new AmazonCognitoIdentity.CognitoUserAttribute({
          Name: "email",
          Value: email,
        }),
        new AmazonCognitoIdentity.CognitoUserAttribute({
          Name: "name",
          Value: name,
        }),
      ];

      this.userPool.signUp(
        email,
        password,
        attributeList,
        null,
        (err, result) => {
          if (err) {
            reject({ success: false, code: err.code, message: this.getErrorMessage(err) });
            return;
          }
          resolve({
            success: true,
            email,
            userSub: result.userSub,
            message:
              "Tài khoản đã được tạo. Vui lòng kiểm tra email để xác nhận.",
          });
        },
      );
    });
  }

  /**
   * Xác nhận email
   */
  async confirmSignup(email, code) {
    return new Promise((resolve, reject) => {
      const cognitoUser = new AmazonCognitoIdentity.CognitoUser({
        Username: email,
        Pool: this.userPool,
      });

      cognitoUser.confirmRegistration(code, true, (err, result) => {
        if (err)
          return reject({ success: false, code: err.code, message: this.getErrorMessage(err) });
        resolve({
          success: true,
          message: "Xác nhận email thành công. Bạn có thể đăng nhập.",
        });
      });
    });
  }

  /**
   * Gửi lại mã xác nhận
   */
  async resendConfirmationCode(email) {
    return new Promise((resolve, reject) => {
      const cognitoUser = new AmazonCognitoIdentity.CognitoUser({
        Username: email,
        Pool: this.userPool,
      });

      cognitoUser.resendConfirmationCode((err) => {
        if (err)
          return reject({ success: false, code: err.code, message: this.getErrorMessage(err) });
        resolve({ success: true, message: "Mã xác nhận đã được gửi lại." });
      });
    });
  }

  logout() {
    if (this.currentUser) this.currentUser.signOut();
    localStorage.removeItem("idToken");
    localStorage.removeItem("userEmail");
    localStorage.removeItem("uploadHistory");
    sessionStorage.clear();
    this.idToken = null;
    this.currentUser = null;
  }

  isLoggedIn() {
    return !!this.getIdToken();
  }

  getIdToken() {
    return this.idToken || localStorage.getItem("idToken");
  }

  getUserEmail() {
    return localStorage.getItem("userEmail");
  }

  async refreshIdToken() {
    return new Promise((resolve, reject) => {
      if (!this.currentUser) this.currentUser = this.userPool.getCurrentUser();
      if (!this.currentUser) return reject({ message: "Không tìm thấy user" });

      this.currentUser.getSession((err, session) => {
        if (err || !session.isValid()) {
          return reject({ message: "Không thể refresh token" });
        }
        this.idToken = session.getIdToken().getJwtToken();
        localStorage.setItem("idToken", this.idToken);
        resolve(this.idToken);
      });
    });
  }

  getErrorMessage(error) {
    const messages = {
      ExpiredCodeException: "Mã xác nhận đã hết hạn. Vui lòng gửi lại mã mới",
      LimitExceededException: "Đã vượt giới hạn gửi mã. Vui lòng thử lại sau",
      NotAuthorizedException: "Email hoặc mật khẩu không đúng",
      UserNotFoundException: "Người dùng không tồn tại",
      UserNotConfirmedException: "Vui lòng xác nhận email trước khi đăng nhập",
      UsernameExistsException: "Email này đã được sử dụng",
      InvalidPasswordException: "Mật khẩu không đủ mạnh",
      CodeMismatchException: "Mã xác nhận không đúng",
      TooManyRequestsException: "Thử quá nhiều lần. Vui lòng chờ một lúc",
    };
    return messages[error.code] || error.message || "Đã có lỗi xảy ra";
  }
}

// ====================== KHỞI TẠO ======================
const auth = new CognitoAuth(AWS_CONFIG);

// Làm auth khả dụng toàn cầu (quan trọng cho HTML)
window.auth = auth;

console.log("✅ Cognito Auth đã được khởi tạo thành công");
