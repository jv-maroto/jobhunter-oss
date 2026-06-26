# Deploy backend en Hugging Face Spaces (GRATIS, sin tarjeta)

Hugging Face Spaces es lo único realmente gratis sin tarjeta para FastAPI con Docker.

- Free tier: 2 vCPU + 16GB RAM (¡mejor que Fly.io free!)
- Sin tarjeta de crédito
- Auto-sleep tras inactividad (cold start ~30s)
- URL pública: `https://<usuario>-<space-name>.hf.space`

---

## PASO 1 — Crear cuenta y Space (3 min)

1. Ve a https://huggingface.co/join
2. Crea cuenta con tu email (NO pide tarjeta, NO pide nada raro).
3. Una vez dentro, abre https://huggingface.co/new-space
4. Configura el nuevo Space:
   - **Space name**: `jobhunter-backend`
   - **License**: MIT
   - **Select the Space SDK**: marca **Docker** (no Gradio, no Streamlit)
   - **Docker template**: deja **"Blank"**
   - **Space hardware**: deja **CPU basic (free)**
   - **Visibility**: Public (Private en plan gratis no permite Docker)
5. Click **Create Space**.

Te lleva a la página del Space. Verás un mensaje tipo "This Space is awaiting your code".

---

## PASO 2 — Push del código

Hugging Face usa git para los Spaces (igual que GitHub). Hay que añadirlo como remote.

Abre Terminal y ejecuta:

```bash
cd ~/Documentos/job-automation/jobhunter/backend

# Configurar credenciales HF (te abrirá navegador la primera vez)
# Tu username es el que pusiste al registrarte en HF
HF_USER=your-huggingface-username   # change to your HF username

# Añadir el remote
git remote add huggingface https://huggingface.co/spaces/$HF_USER/jobhunter-backend

# Renombrar el README de HF para que sea el principal del space
cp README_HF.md README.md

# Crear branch dedicada al deploy (para no confundir con el repo de GitHub)
git checkout -b hf-deploy
git add README.md
git commit -m "feat: HF Space config"
git push huggingface hf-deploy:main
```

⚠️ HF te pedirá usuario+password.
- Username: tu username de HF.
- Password: NO uses tu contraseña real. Usa un **Access Token**.
  Lo creas en https://huggingface.co/settings/tokens → New token → permisos "write".
  Copia el token (empieza por `hf_...`) y úsalo como password al hacer push.

---

## PASO 3 — Configurar API key

En la página de tu Space:

1. Pestaña **Settings**.
2. Sección **Variables and secrets** → **New secret**.
3. Name: `ANTHROPIC_API_KEY`. Value: tu key real.
4. **Save**.

HF rebuildea automáticamente con la nueva env var.

---

## PASO 4 — Build y verificar

En la pestaña **Logs** verás el build de Docker. Tarda ~5-7 minutos.

Cuando termine, prueba:
```
https://<TU_USER>-jobhunter-backend.hf.space/health
```
Debería responder `{"status":"ok"}`.

**Pégame esa URL** y yo termino el frontend en Vercel.

---

## Cosas a saber

- **Auto-sleep**: si nadie usa el Space en ~48h, se duerme. Primer request despierta en 30-60s.
- **Persistencia**: HF Spaces tier gratis **NO persiste** datos entre reinicios. La DB SQLite se resetea cuando rebuildea.
  - Para producción real necesitas un Postgres externo (Supabase / Neon free tier son gratis sin tarjeta).
  - Para empezar y probar, la DB efímera vale.
- **HTTPS**: HF te lo da gratis con su dominio.
