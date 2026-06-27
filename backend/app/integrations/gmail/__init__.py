"""Gmail tracking (Pilar 4): detecta rechazos/respuestas y mueve el pipeline.

Opcional y SOLO LECTURA. Local-first: las credenciales del usuario viven en
`data/integrations/`. Nunca borra ni modifica correo. No persiste el cuerpo del
correo (solo un snippet corto + la salida del clasificador).
"""
