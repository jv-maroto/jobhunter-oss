# JobHunter LinkedIn Assistant

Extensión Chrome (Manifest V3) que actúa como puente entre tu dashboard local
(`http://localhost:8000`) y LinkedIn, simulando interacciones humanas con la
sesión legítima del usuario. No es un scraper headless ni utiliza la API
privada de LinkedIn: el navegador del propio usuario hace los clics.

## Estructura

```
linkedin-ext/
├── manifest.json
├── esbuild.config.mjs
├── package.json
├── tsconfig.json
├── public/icons/                # 16/48/128 PNG (placeholder "JH")
└── src/
    ├── background/service-worker.ts   # Polling al backend + orquestación
    ├── content/
    │   ├── linkedin-profile.ts        # Conectar + nota personalizada
    │   ├── linkedin-feed.ts           # Programar post + overlay sugerencias
    │   ├── linkedin-messaging.ts      # Detectar mensajes + overlay respuestas
    │   └── overlay.css
    ├── popup/                         # Acción de la extensión
    ├── options/                       # Página de configuración
    └── lib/                           # api, dom, storage, logger, types
```

## Build

```bash
cd ~/Documentos/job-automation/jobhunter/linkedin-ext
npm install
npm run build         # Genera dist/ (carga descomprimida)
npm run watch         # Recompila al detectar cambios
npm run typecheck     # Sólo chequeo de tipos
```

El build copia `manifest.json`, HTML, CSS e iconos a `dist/`.

## Cargar la extensión en Chrome

1. Visita `chrome://extensions/`.
2. Activa el toggle **Modo desarrollador** (arriba a la derecha).
3. Click **Cargar descomprimida** y selecciona la carpeta `dist/`.
4. Fija la extensión en la barra (icono "JH") para acceso rápido.

## Configuración

Al abrir el popup verás el estado de conexión con el backend. Pulsa
**Opciones** para configurar:

- **Backend URL** (`http://localhost:8000` por defecto).
- **Velocidad de simulación**: slow / normal / fast.
- **Intervalo de polling**: mínimo 30 s (límite de `chrome.alarms`).
- **Auto-ejecutar**: si está apagado, sólo se ejecutan tareas al pulsar
  "Forzar sincronización" desde el popup.

## Flujos implementados

| Flujo | Estado | Detalles |
| --- | --- | --- |
| Conectar + nota (linkedin.com/in/*) | **Funcional** | Botón directo o vía menú "Más" + modal "Añadir nota" |
| Programar publicación (linkedin.com/feed/*) | **Funcional, sin imagen** | Click "Empezar publicación" → contenteditable → reloj → fecha/hora → Programar |
| Adjuntar imagen al post | **Stub** | Detectado pero no implementado |
| Detección de mensajes no leídos | **Funcional** | Lectura DOM con varios selectores fallback; reporta a `/ext/inbox-messages` |
| Overlay de respuestas sugeridas | **Funcional** | Muestra hasta N sugerencias; click pega texto en editor |
| Overlay de comentarios en feed | **Stub** | Observer listo, sin endpoint de comentarios todavía |

## Contrato con el backend

Endpoints consumidos (ver `src/lib/api.ts`):

- `GET /health` (opcional, fallback a `/ext/tasks`)
- `GET /ext/tasks`
- `POST /ext/connect-result`
- `POST /ext/inbox-messages`

Tipos compartidos en `src/lib/types.ts`. Mantener sincronizados con los
modelos Pydantic del backend.

## Anti-detección

- Delays aleatorios entre 200-800 ms con `humanDelay()`.
- Tecleo carácter a carácter (20-100 ms) usando el setter nativo de React.
- `scrollIntoView` antes de cada clic.
- Máximo 1 tarea activa por tick.
- `auto_execute` apagado por defecto (requiere acción del usuario).

## Próximos pasos

- Subida de imágenes en `schedule_post` (descargar URL → DataTransfer → input).
- Endpoint `/ext/comments` + activar overlay del feed.
- Selectores de respaldo cuando LinkedIn cambie clases (test E2E con Playwright).
- Reporte de `schedule_post_result` y `comment_used` al backend.
- Telemetría local de errores (chrome.storage circular log).
- Modo "review" donde la extensión sólo abre la pestaña y resalta los botones
  sin clicarlos (usuario confirma).
- Localización completa (la extensión asume LinkedIn en ES o EN según
  `document.documentElement.lang`).

## Notas

- Sin emojis intencionalmente (preferencia del propietario).
- `chrome.alarms` exige `periodInMinutes >= 0.5` en versiones recientes; el
  service worker normaliza el valor.
