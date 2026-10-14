# Seguridad

El repositorio contiene recursos gráficos y un verificador local que utiliza la biblioteca estándar de Python. No incorpora dependencias externas, credenciales, servicios de red ni workflows de GitHub Actions.

## Antes de subir cambios

1. Añade solo los archivos necesarios. Revisa `git diff --cached --name-status` y `git diff --cached`.
2. Ejecuta `python3 scripts/verificar.py`. Si cambias un recurso, revisa su contenido y actualiza su suma SHA-256 de forma deliberada.
3. Confirma que no se incluyan archivos de sesión, rutas personales, enlaces de subida o descarga temporales, tokens, claves o datos de cuenta.
4. Mantén el repositorio privado mientras decides qué contenido deseas hacer público.

El verificador detecta patrones comunes y valida el atlas; no sustituye una revisión completa de secretos ni un análisis de seguridad de software.

## Si encuentras un dato sensible

Evita incluirlo en una issue pública. Contacta al propietario por un canal privado que ya tengas disponible. Si se expuso una credencial, revócala antes de limpiar el historial.
