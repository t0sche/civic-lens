// @ts-check
import config from "eslint-config-next";

export default [
  ...config,
  {
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
];
