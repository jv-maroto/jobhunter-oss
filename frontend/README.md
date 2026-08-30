# JobHunter — Frontend Dashboard

Dashboard local para gestionar la búsqueda de empleo: onboarding, ofertas
detectadas, preparación de aplicaciones, pipeline kanban, networking,
posts de LinkedIn, integraciones y métricas.

## Stack

- Next.js 16 (App Router, Turbopack) + React 19
- TypeScript estricto
- Tailwind CSS v4 con tokens HSL y tema oscuro/claro (next-themes)
- Componentes estilo shadcn/ui en `components/ui/` (Radix + CVA)
- TanStack Query v5, Recharts, @dnd-kit, sonner, date-fns
- i18n propio (`lib/i18n.tsx`): español/inglés, sigue el idioma del navegador

## Arrancar

```bash
cd frontend
npm install
cp .env.local.example .env.local    # opcional; por defecto http://localhost:8000
npm run dev                         # http://localhost:3000
```

El dashboard habla con el backend en `NEXT_PUBLIC_API_URL`. **No hay datos de
relleno**: si el backend no responde, las páginas muestran el error y la
sidebar marca "Backend: offline". En una instalación nueva, `OnboardingGate`
redirige a `/onboarding` hasta completar el wizard.

### Build de producción

```bash
npm run lint
npm run build
npm run start
```

## Rutas

| Ruta                     | Página                                                        |
| ------------------------ | ------------------------------------------------------------- |
| `/`                      | Redirige a `/today`                                           |
| `/onboarding`            | Wizard: IA → GitHub → LinkedIn → CV → países → roles → revisión |
| `/today`                 | Resumen del día: ofertas nuevas, personas a contactar          |
| `/jobs`                  | Tabla de ofertas con filtros y "buscar ahora"                  |
| `/swipe`                 | Cola de decisión rápida por track                              |
| `/pipeline`              | Kanban con drag & drop entre estados                           |
| `/applications`          | Aplicaciones preparadas (CV/carta)                             |
| `/companies`             | Agregado por empresa                                           |
| `/networking`            | Personas y mensajes de conexión                                |
| `/linkedin`              | Posts semanales, programación, comentarios sugeridos           |
| `/metrics`               | KPIs y gráficas                                                |
| `/settings`              | Perfil (`cv_master.json`), rehacer onboarding, tema            |
| `/settings/ai`           | Modo de IA (local / cloud / off), claves, prueba               |
| `/settings/search`       | Países, plataformas, queries, "buscar ahora"                   |
| `/settings/integrations` | Gmail (solo lectura)                                           |

## Estructura

```
frontend/
├── app/                 # App Router pages
├── components/
│   ├── ui/              # Botones, cards, dialog, tabs... (estilo shadcn)
│   ├── layout/          # Sidebar, TopBar, CommandPalette, ThemeToggle
│   ├── onboarding/      # OnboardingGate
│   ├── jobs/ persons/ posts/ kanban/ metrics/
│   └── providers.tsx    # Theme + QueryClient + i18n + Toaster
├── hooks/               # useJobs, useOnboarding, useAiSettings, useSearchProfile...
└── lib/
    ├── api.ts           # fetch wrapper (sin fallback a mocks)
    ├── i18n.tsx         # diccionario es/en + LanguageProvider
    ├── onboarding.ts, aiSettings.ts, searchProfile.ts, integrations.ts
    ├── types.ts         # contrato con la API
    └── utils.ts
```

## Score badges

| Score  | Color        |
| ------ | ------------ |
| 90–100 | Verde fuerte |
| 70–89  | Verde claro  |
| 50–69  | Amarillo     |
| 0–49   | Rojo         |

## Notas

- Next.js 16 convierte `params`/`searchParams` en `Promise<>`; estas páginas
  no dependen de params dinámicos.
- Los componentes de `components/ui/` están escritos a mano siguiendo el
  patrón shadcn (no se usó el CLI).
