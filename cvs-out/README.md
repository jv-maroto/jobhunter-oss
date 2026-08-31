# cvs-out — CVs y cover letters generados

Cada vez que le das a "Prepare application" a una oferta desde el dashboard,
el backend deposita AQUÍ una copia con nombre humano de los PDFs:

```
{Empresa}_{YYYY-MM-DD}_job{id}_cv.pdf
{Empresa}_{YYYY-MM-DD}_job{id}_cover.pdf
```

Formato pensado para copia-pega rápida al correo del reclutador o al form
del ATS. Los originales siguen en `backend/data/applications/{slug}/`.

Esta carpeta está en `.gitignore` — nunca se subirá al repo.
