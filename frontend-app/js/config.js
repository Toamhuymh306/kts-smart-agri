const AWS_CONFIG = {
  // ✅ Cognito User Pool - Thực tế
  cognito: {
    region: "ap-southeast-1",
    userPoolId: "ap-southeast-1_UHScPNky5",
    clientId: "71e13g3a44uveseil0f0030bv1",
  },

  // ✅ API Gateway - Thực tế
  apiGateway: {
    endpoint: "https://zmdoxc27gg.execute-api.ap-southeast-1.amazonaws.com/dev",
    presignUrl: "/presign",
    inferenceUrl: "/inference",
    resultsUrl: "/results",
  },

  // Cấu hình S3
  s3: {
    bucket: "kts-smartagri-dev-raw-images",
    region: "ap-southeast-1",
    outputBucket: "kts-smartagri-dev-results",
  },

  // PlantVillage Dataset
  plantVillage: {
    crops: [
      "Apple",
      "Blueberry",
      "Cherry",
      "Corn",
      "Grape",
      "Orange",
      "Peach",
      "Pepper",
      "Potato",
      "Raspberry",
      "Soybean",
      "Squash",
      "Strawberry",
      "Tomato",
    ],
  },

  // Lambda Container Inference
  inference: {
    type: "lambda",
    lambdaFunction: "kts-smartagri-inference",
    timeout: 120,
  },

  // App settings
  app: {
    name: "KTs Smart Agriculture",
    version: "2.0.0",
    maxFileSize: 10 * 1024 * 1024, // 10MB
    confidenceThreshold: 0.75,
  },
};

// Export
if (typeof module !== "undefined" && module.exports) {
  module.exports = AWS_CONFIG;
}
