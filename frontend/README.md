# JobHunter — Frontend Dashboard

Dashboard que Javier abre cada mañana para gestionar la búsqueda de empleo
automatizada: ofertas detectadas, preparación de aplicaciones, lista de
personas a conectar en LinkedIn, posts programados, pipeline kanban y
métricas.

## Stack

- Next.js 16 (App Router, Turbopack por defecto) + React 19.2
- TypeScript estricto
- Tailwind CSS v4 con tokens HSL en CSS y variantes `dark`
- shadcn/ui — componentes locales en `components/ui/` construidos sobre Radix
- TanStack Query v5
- Recharts (gráficas en `/metrics`)
- @dnd-kit (drag & drop en `/pipeline`)
- next-themes (dark mode por defecto)
- sonner (toasts)
- date-fns (locale `es`)

## Arrancar

```bash
cd jobhunter/frontend
npm install            # ya hecho durante el scaffolding
cp .env.local.example .env.local
npm run dev            # puerto 3000
```

El dashboard escucha el backend en `NEXT_PUBLIC_API_URL`
(`http://localhost:8000` por defecto). Si el backend no está corriendo,
las páginas siguen funcionando con datos **mock** (`lib/mock.ts`) y el
indicador de la sidebar muestra "Backend: offline".

### Build de producción

```bash
npm run build
npm run start
```

## Rutas

| Ruta          | Página                                                                                          |
| ------------- | ----------------------------------------------------------------------------------------------- |
| `/`           | Redirige a `/today`                                                                             |
| `/today`      | Jobs nuevas + personas a conectar + post del día                                                |
| `/pipeline`   | Kanban con drag & drop entre estados                                                            |
| `/metrics`    | KPIs + 4 charts (line / bar / pie / bar horizontal)                                              |
| `/companies`  | Tabla agregada por empresa                                                                      |
| `/linkedin`   | Tabs: Posts (week scheduler con modal) / Connections / Comments (10 sugerencias)                 |
| `/settings`   | API key (placeholder), editor JSON `cv_master`, toggle dark/light                               |

## Estructura

```
frontend/
├── app/                         # App Router pages
├── components/
│   ├── ui/                      # Botones, cards, table, dialog, etc. (shadcn-style)
│   ├── layout/                  # Sidebar, TopBar, ThemeToggle
│   ├── jobs/                    # JobCard, JobTable, ScoreBadge, PrepareApplicationButton
│   ├── persons/                 # PersonCard, ConnectButton
│   ├── posts/                   # PostCard, WeekScheduler
│   ├── kanban/                  # KanbanBoard, KanbanColumn
│   ├── metrics/                 # MetricCard + charts
│   └── providers.tsx            # ThemeProvider + QueryClientProvider + Toaster
├── hooks/                       # useJobs, usePersons, usePosts, useMetrics, useBackendStatus
└── lib/
    ├── api.ts                   # fetch wrapper + apiOrMock fallback
    ├── types.ts                 # Contrato API (sincronizado con ARCHITECTURE.md)
    ├── mock.ts                  # Seeds offline
    └── utils.ts                 # cn(), formatSalary(), scoreTone(), initials()
```

## Score badges

| Score    | Color           |
| -------- | --------------- |
| 90–100   | Verde fuerte    |
| 70–89    | Verde claro     |
| 50–69    | Amarillo        |
| 0–49     | Rojo            |

## Notas técnicas

- **Next.js 16** convierte `params` y `searchParams` en `Promise<>`; las
  páginas de este dashboard no dependen de params dinámicos, así que no se
  ven afectadas.
- **shadcn CLI no se ejecutó** (requiere init interactivo). En su lugar,
  los componentes de `components/ui/` están escritos a mano siguiendo el
  patrón shadcn (Radix + CVA + Tailwind v4 + tokens HSL en CSS).
- **Fallback a mock**: `apiOrMock()` intercepta errores de red y devuelve
  data de `lib/mock.ts`. Permite trabajar sin tener el backend corriendo.
- **Dark mode** activado por defecto (`defaultTheme="dark"`).

## Próximos pasos

- Cuando el backend exponga endpoints reales (`/jobs`, `/persons`, `/posts`,
  `/metrics/*`), el dashboard los consumirá automáticamente — sin cambios.
- Endpoints aún sin definir formalmente pero ya usados desde el frontend:
  - `POST /scrape/trigger`
  - `POST /posts/generate-week`
  - `GET /settings/cv_master` / `PUT /settings/cv_master`
  - `GET /metrics/companies` (lista de `CompanyAggregate`)
- Falta cablear: filtro de `/pipeline` por `?company=`, métricas reales de
  jobs-per-day (ahora usa mock), respuestas LinkedIn vía la extensión.
- `npx shadcn@latest init` formal si se quiere usar el CLI para añadir
  más componentes en el futuro.
