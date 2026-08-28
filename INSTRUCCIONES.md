# Instrucciones de implementación — Dashboard PMO Fundición

## Paso 1 · Crear la fuente de datos en Google Drive

1. Sube `Plantilla_Control_Proyectos_EJEMPLO.xlsx` a Google Drive y ábrelo con Google Sheets
   (clic derecho → Abrir con → Google Sheets). Esto lo convierte a un Google Sheet nativo.
2. Verifica que el libro tenga exactamente 4 hojas, con estos nombres exactos:
   `Proyectos`, `Costos`, `Cronograma`, `Riesgos` (respeta mayúsculas/minúsculas).
3. Copia el **ID del Sheet** desde la URL:
   `https://docs.google.com/spreadsheets/d/`**`ESTE_ES_EL_ID`**`/edit`
4. A partir de ahora, el Gerente de Ingeniería y sus PMs solo editan este Sheet —
   nadie toca código para actualizar el dashboard.

## Paso 2 · Crear la cuenta de servicio de Google (para que el dashboard pueda leer el Sheet)

1. Entra a [Google Cloud Console](https://console.cloud.google.com/) y crea un proyecto
   (o usa uno existente).
2. Habilita las APIs: **Google Sheets API** y **Google Drive API**
   (menú "APIs y servicios" → "Habilitar APIs y servicios").
3. Ve a "APIs y servicios" → "Credenciales" → "Crear credenciales" → **Cuenta de servicio**.
   Dale un nombre, por ejemplo `pmo-dashboard`.
4. Dentro de la cuenta de servicio creada, ve a la pestaña "Claves" → "Agregar clave" →
   "Crear clave nueva" → tipo **JSON**. Se descargará un archivo `.json` — guárdalo, es tu
   credencial.
5. Copia el correo de la cuenta de servicio (termina en `.iam.gserviceaccount.com`).
6. Regresa a tu Google Sheet → botón **Compartir** → pega ese correo y dale permiso de
   **Lector**. Sin este paso, el dashboard no podrá leer los datos.

## Paso 3 · Configurar las credenciales en Streamlit

1. En la carpeta del proyecto, copia `secrets_ejemplo.toml` a `.streamlit/secrets.toml`.
2. Abre el `.json` descargado en el paso 2 y copia cada campo a `secrets.toml`:
   `sheet_id` (del Paso 1) y todos los campos del bloque `[google_service_account]`.
3. **Importante:** agrega `.streamlit/secrets.toml` a tu `.gitignore` — nunca debe
   subirse a un repositorio ni compartirse.

## Paso 4 · Probar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Si aún no tienes el Google Sheet conectado, usa la opción **"Subir archivo Excel/CSV"**
del panel lateral y carga `Plantilla_Control_Proyectos_EJEMPLO.xlsx` para validar que
todo funciona con datos de muestra.

## Paso 5 · Publicar el dashboard (gratis, sin servidor propio)

Dado que solo cuentan con Google Drive como infraestructura, la opción más simple y sin
costo es **Streamlit Community Cloud**, que se conecta a un repositorio de GitHub:

1. Crea un repositorio en GitHub y sube `app.py`, `data_sources.py`, `evm.py` y
   `requirements.txt` (**NO subas `secrets.toml`**).
2. Entra a [share.streamlit.io](https://share.streamlit.io), conecta tu cuenta de GitHub
   y selecciona el repositorio.
3. En la configuración de la app, en la sección **"Secrets"**, pega el contenido completo
   de tu `secrets.toml` (la plataforma lo cifra; es el equivalente en la nube al archivo local).
4. Despliega. Obtendrás una URL pública tipo `tuapp.streamlit.app` que el Gerente de
   Ingeniería puede abrir desde cualquier navegador, sin instalar nada.

> Si prefieren no usar GitHub, otra alternativa dentro de Google es publicar la misma
> lógica como **Google Apps Script + Looker Studio** conectado directamente al Sheet,
> pero se pierde el control fino de EVM/Gantt que este código ya resuelve — la ruta
> con Streamlit Cloud es la recomendada.

## Paso 6 · Operación diaria (para los PMs, sin tocar código)

- **Actualizar avance de un proyecto:** editar la columna `avance_fisico_pct` en la hoja
  `Proyectos`.
- **Registrar un gasto:** agregar una fila en la hoja `Costos`.
- **Actualizar el cronograma:** editar fechas reales y `avance_pct` en `Cronograma`.
- **Agregar un riesgo:** agregar fila en `Riesgos`.
- El dashboard refleja los cambios en un máximo de 10 minutos (caché), o de inmediato
  usando el botón de "Rerun" (tecla `R`) en la esquina superior derecha de Streamlit.

## Extensión futura (no requerida ahora, pero contemplada en el diseño)

`data_sources.py` usa un patrón adaptador: si en el futuro quieren leer directo desde
el ERP (Odoo/SQL) en lugar de Google Sheets, solo se agrega una clase nueva
`class OdooSource(DataSource): ...` con su propio `load_all()` — el resto del
dashboard (`app.py`, `evm.py`) no cambia.
