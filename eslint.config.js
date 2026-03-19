// @ts-check
const nextConfig = require("eslint-config-next");

module.exports = [
  ...nextConfig,
  {
    rules: {
      // Ensure no-explicit-any is enforced
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
];
