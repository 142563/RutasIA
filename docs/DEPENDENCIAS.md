# Revisión de dependencias — 2026-10-11

## Frontend: parche de source-map-js (RUT-83)

La instalación desde `origin/main` (`696d02d`) usaba `source-map-js` **1.2.1**, una dependencia de desarrollo indirecta de PostCSS (Vite) y `@tailwindcss/node`. `npm audit` completo detectó **1 aviso alto**; `npm audit --omit=dev` detectó **0**.

El aviso [GHSA-68fv-2mgg-jv7q / CVE-2026-93749](https://github.com/advisories/GHSA-68fv-2mgg-jv7q) describe un bloqueo prolongado del procesamiento al recibir mapas fuente con offsets excesivos. Afecta a versiones `>=1.0.0 <1.2.2`; el parche es **1.2.2**. No se demostró que esa entrada sea alcanzable en la aplicación publicada.

Se ejecutó `npm update source-map-js --package-lock-only` y se revisó el resultado. El cambio final en `frontend/package-lock.json` contiene únicamente la versión, URL del paquete e integridad de `source-map-js`; se descartaron metadatos opcionales de WASM ajenos a la tarjeta. No cambian `package.json`, los rangos existentes, otras versiones ni el código del producto.

Después de instalar con `npm ci`, `source-map-js` queda en **1.2.2**. Ambas auditorías, completa y sin dependencias de desarrollo, reportan **0 avisos**.

Para repetir la verificación, desde `frontend/`:

```powershell
npm ci
npm ls source-map-js
npm audit
npm audit --omit=dev
npx tsc -b
npx vitest run
npm run build
```

Verificación de RUT-83: `npm ci`, ambas auditorías y TypeScript correctos; **70 pruebas Vitest en 17 archivos** y build correctos. El backend de esta rama pasó **241 pruebas en 290.551 s**, con `DATABASE_URL` forzado a vacío antes de cargar Django. No se añade lógica nueva ni una prueba que duplique el cambio del lockfile. Persisten los avisos anteriores de `staticfiles` local inexistente y chunk inicial de **508.23 kB** (>500 kB); no son fallos de la verificación.

## Backend: actualización separada (RUT-66)

La base de esta rama aún fija Django **6.0.4**. La revisión previa de las seis dependencias directas de `requirements.txt` en OSV encontró avisos para esa versión de Django; las otras cinco no tuvieron avisos en esa consulta. GHSA y PYSEC pueden identificar el mismo problema: no se cuentan como vulnerabilidades distintas sin revisar sus alias.

RUT-66 prepara Django **6.0.9** en una rama independiente, `codex/rut-66`, commit local `d33a83b`. La consulta OSV de esa versión no devolvió avisos y su verificación pasó 241 pruebas Django. **Ese parche está pendiente de revisión e integración local por Claude**; esta tarjeta no modifica `requirements.txt` ni afirma que producción ya lo tenga.

## Alcance y límites

- Los resultados reflejan las bases de avisos consultadas el 2026-10-11; cero avisos conocidos no demuestra ausencia de vulnerabilidades.
- La auditoría npm incluye dependencias directas e indirectas del lockfile. La revisión OSV previa del backend cubrió solo las seis dependencias directas; no se auditó todo su árbol transitivo.
- No se hizo una prueba de explotación, una auditoría completa de la aplicación ni una comprobación de las versiones instaladas en Render.
- Las pruebas del backend usan SQLite forzado, nunca la base de la nube; las llamadas Google y Resend de las pruebas se simulan.
- Los commits quedan locales en `codex/rut-<n>`, para revisión de Claude. No hay push, merge a `main` ni despliegue sin autorización de Julio.
