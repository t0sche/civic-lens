// @ts-check
import { FlatCompat } from "@eslint/eslintrc";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

export default [
  // Use legacy .eslintrc.* configuration as the base, converted to flat config.
  ...compat.config(),
  {
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
];
