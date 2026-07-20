const assert = require("node:assert/strict");
const ImageUploadApp = require("./app.js");

global.confirm = () => true;
let logoutCalled = false;
global.auth = {
  logout() {
    logoutCalled = true;
  },
};

const app = Object.create(ImageUploadApp.prototype);
app.history = [{ image_id: "user-a-scan" }];
app.selectedFiles = [{ name: "user-a.jpg" }];
app.resendTimer = null;
app.resultsContent = { replaceChildren() {} };
app.resultsSection = { classList: { add() {} } };
app.updatePreview = () => {};
app.renderHistory = () => {};
app.showAuth = () => {};
app.showToast = () => {};
app.handleLogout();

assert.equal(logoutCalled, true);
assert.deepEqual(app.history, []);
assert.deepEqual(app.selectedFiles, []);
console.log("logout clears the previous user's UI history");
