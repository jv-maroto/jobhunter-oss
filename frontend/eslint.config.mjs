import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // Varias paginas siembran estado local UNA vez a partir de datos del
      // backend (guardado con un flag `seeded`). Es el patron documentado para
      // evitar desajustes de hidratacion; lo dejamos como aviso, no como error.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
]);

export default eslintConfig;
