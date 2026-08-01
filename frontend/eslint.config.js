import eslint from "@eslint/js";
import lit from "eslint-plugin-lit";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["coverage", "dist"] },
  eslint.configs.recommended,
  ...tseslint.configs.strictTypeChecked.map((config) => ({
    ...config,
    files: ["src/**/*.ts", "test/**/*.ts", "browser/**/*.ts", "*.config.ts"],
  })),
  ...tseslint.configs.stylisticTypeChecked.map((config) => ({
    ...config,
    files: ["src/**/*.ts", "test/**/*.ts", "browser/**/*.ts", "*.config.ts"],
  })),
  {
    files: ["src/**/*.ts", "test/**/*.ts", "browser/**/*.ts", "*.config.ts"],
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: { lit },
    rules: {
      ...lit.configs.recommended.rules,
      "@typescript-eslint/consistent-type-definitions": ["error", "interface"],
      "@typescript-eslint/no-confusing-void-expression": "off",
      "@typescript-eslint/no-unsafe-type-assertion": "off",
    },
  },
);
