# JobHunter Assistant (extensión Chrome)

Extensión Chrome (Manifest V3) que conecta tu dashboard local
(`http://localhost:8000`) con LinkedIn y con los formularios de aplicación de
los ATS más comunes. Actúa dentro de tu sesión, en tu navegador: no es un
scraper headless ni usa APIs privadas.

## Qué hace

| Flujo | Dónde | Estado |
| --- | --- | --- |
| Autorrelleno de formularios de aplicación | Wellfound, Lever, Greenhouse, Ashby, Workable, Indeed, Workday, iCIMS, BambooHR, Teamtailor, SmartRecruiters, Recruitee, Personio… | Funcional (solo al pulsar el botón) |
| Respuestas a preguntas de cribado | ídem | Funcional (`/ext/answer-question`, con caché) |
| Reportar "aplicado" al backend | ídem | Funcional (`/ext/applied`) |
| Importar tu propio perfil de LinkedIn al onboarding | `linkedin.com/in/tu-perfil` | Funcional |
| Conectar + nota personalizada | `linkedin.com/in/*` | Funcional |
| Programar publicación | `linkedin.com/feed` | Funcional, sin imagen |
| Sugerencias de comentarios en el feed | `linkedin.com/*` | Funcional |
| Detección de mensajes + respuestas sugeridas | `linkedin.com/messaging` | Funcional |

## Build

```bash
cd linkedin-ext
npm install
npm run build         # genera dist/ (carga descomprimida)
npm run watch         # recompila al detectar cambios
npm run typecheck     # solo tipos
```

El build copia `manifest.json`, HTML, CSS e iconos a `dist/`.

## Cargar la extensión en Chrome

1. Abre `chrome://extensions/`.
2. Activa **Modo desarrollador** (arriba a la derecha).
3. **Cargar descomprimida** → selecciona la carpeta `dist/`.
4. Fija la extensión en la barra para acceso rápido.
5. (Recomendado) Copia el ID de la extensión y ponlo en `backend/.env` como
   `CHROME_EXTENSION_ID` para que solo esta extensión pueda hablar con la API.

## Configuración

En el popup ves el estado de conexión con el backend. **Opciones** permite:

- **Backend URL** (`http://localhost:8000` por defecto).
- **Velocidad de simulación**: slow / normal / fast.
- **Intervalo de polling**: mínimo 30 s (límite de `chrome.alarms`).
- **Auto-ejecutar**: apagado por defecto; si está apagado solo se ejecutan
  tareas al pulsar "Forzar sincronización".

## Contrato con el backend

Endpoints consumidos (ver `src/lib/api.ts` y `src/background/service-worker.ts`):

- `GET /health`, `GET /ext/tasks`, `GET /ext/profile`, `GET /ext/apply-queue`
- `POST /ext/connect-result`, `/ext/inbox-messages`, `/ext/post-result`,
  `/ext/applied`, `/ext/answer-question`
- `POST /onboarding/linkedin/from-extension`
- `POST /comments/manual-post`, `/comments/feed-posts`

Tipos compartidos en `src/lib/types.ts`; mantenerlos sincronizados con los
modelos Pydantic del backend.

## Comportamiento "humano"

- Delays aleatorios entre 200-800 ms (`humanDelay()`).
- Tecleo carácter a carácter usando el setter nativo de React.
- `scrollIntoView` antes de cada clic; máximo 1 tarea por tick.
- Nada se envía ni se publica sin una acción tuya.

## Pendiente

- Subida de imágenes al programar un post.
- Selectores de respaldo cuando LinkedIn cambie clases.
- Modo "review" que resalta los botones sin clicarlos.
- Localización: la extensión asume LinkedIn en ES o EN según
  `document.documentElement.lang`.
