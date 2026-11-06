# Monitor INAMHI en Mac: instalación (unos 20 minutos)

Esta carpeta hace tres cosas: recopila noticias del INAMHI cada día, las clasifica
y las publica en una página web que cualquier persona abre con un enlace, sin cuenta.

```
monitor-inamhi/
  monitor_inamhi.py   ← el recolector
  docs/index.html     ← la página pública
  docs/reports.json   ← los datos (ya trae los reportes del 3 oct al 5 nov)
```

## 1. Probar el script
1. Descomprime la carpeta en tu Mac, por ejemplo en `~/monitor-inamhi`.
2. Abre **Terminal** y ejecuta:
   ```
   cd ~/monitor-inamhi
   python3 monitor_inamhi.py
   ```
   Si macOS ofrece instalar las "herramientas de línea de comandos", acepta y repite el comando.
3. Debe imprimir algo como `noticias nuevas: 12`. Para ver la página en tu computadora:
   ```
   cd docs && python3 -m http.server 8000
   ```
   y abre http://localhost:8000 en el navegador (Ctrl+C para detenerlo).

## 2. Publicar con enlace público (GitHub Pages, gratis)
1. Crea una cuenta en https://github.com y un repositorio **público** llamado `monitor-inamhi`.
2. En Terminal, dentro de la carpeta:
   ```
   git init
   git add -A
   git commit -m "Primera versión"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/monitor-inamhi.git
   git push -u origin main
   ```
   Cuando pida contraseña, usa un **token de acceso personal** (GitHub → Settings →
   Developer settings → Personal access tokens). El Mac lo recuerda y el script
   podrá publicar solo.
3. En GitHub: **Settings → Pages → Deploy from a branch → main → carpeta /docs → Save**.
4. En un par de minutos tu enlace será: `https://TU_USUARIO.github.io/monitor-inamhi/`
   Ese enlace es el que compartes. Cualquiera puede elegir fecha y descargar PDF, Word o CSV.

## 3. Que corra solo cada día
1. Guarda esto como `~/Library/LaunchAgents/com.monitor.inamhi.plist`
   (cambia `TUUSUARIO` por tu nombre de usuario del Mac):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.monitor.inamhi</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string>
    <string>/Users/TUUSUARIO/monitor-inamhi/monitor_inamhi.py</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/TUUSUARIO/monitor-inamhi</string>
  <key>StartCalendarInterval</key><array>
    <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>13</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>19</integer><key>Minute</key><integer>0</integer></dict>
  </array>
  <key>StandardOutPath</key><string>/Users/TUUSUARIO/monitor-inamhi/log.txt</string>
  <key>StandardErrorPath</key><string>/Users/TUUSUARIO/monitor-inamhi/log.txt</string>
</dict></plist>
```
2. Actívalo en Terminal:
   ```
   launchctl load ~/Library/LaunchAgents/com.monitor.inamhi.plist
   ```
   Corre a las 07:00, 13:00 y 19:00. Si el Mac está dormido a esa hora, lo hace al despertar.
   Para ver si funcionó, abre `log.txt` en la carpeta.

## 4. (Opcional) Mejorar la recolección con Google Alerts
1. En https://www.google.com/alerts crea alertas con "INAMHI", "INAMHI alerta",
   "INAMHI advertencia" y elige **Entregar a: feed RSS**.
2. Copia el enlace de cada feed y pégalo en `ALERT_FEEDS` dentro de `monitor_inamhi.py`.

## 5. Capturas de pantalla de cada noticia
El script abre cada nota en un navegador invisible (Chromium) y guarda una captura en
`docs/capturas/`. La página las muestra como miniatura en la columna "Captura".
1. Instala una sola vez, en Terminal:
   ```
   pip3 install playwright
   python3 -m playwright install chromium
   ```
2. Ejecuta `python3 monitor_inamhi.py` como siempre. Para capturar también las noticias
   antiguas que ya están en `reports.json`: `python3 monitor_inamhi.py --todo`
   (hace hasta 40 por vez; repite el comando para completar las demás).
3. Si no quieres capturas, pon `CAPTURAS = False` en el script.

Cosas que debes saber:
- Es la parte más frágil: sitios con muro de pago, ventanas emergentes o bloqueo a
  navegadores automáticos pueden dar una captura tapada o ninguna. El script intenta cerrar
  los avisos de cookies, pero no siempre lo logra.
- Con Google Noticias, el script toma la captura y además reemplaza el enlace de Google
  por el enlace directo de la nota.
- Cada captura pesa unos 100 a 200 KB. Con tres ejecuciones al día el repositorio crece
  rápido; GitHub recomienda no pasar de 1 GB. Si se llena, borra capturas antiguas.
- Las capturas se muestran en un sitio público. Publicar imágenes de páginas de medios
  puede infringir sus derechos de autor. Si el uso es solo de archivo interno, usa un
  repositorio privado o deja `CAPTURAS = False` en la versión pública.
- Los PDF y Word aún no incluyen las capturas; el CSV sí trae el enlace de cada una.

## Límites que conviene conocer
- El tema, el tipo y la ciudad se deducen por palabras clave del titular y de la descripción
  de la nota; a veces se equivocan. Cada fila lleva el enlace para verificar.
- Los enlaces de Google Noticias son redirecciones: abren la nota, pero no permiten leer
  su descripción. Con Google Alerts los enlaces son directos y el detalle suele ser mejor.
- Google puede tardar o dejar pasar medios pequeños. Para un reporte formal, revisa de vez
  en cuando las páginas de los medios principales y el sitio oficial servicios.inamhi.gob.ec.
- Si falta algún día o una nota, puedes pedirme aquí que prepare ese reporte a mano.
