#!/usr/bin/env python3
"""Monitor de noticias INAMHI.

Recolecta noticias (Google Noticias + feeds RSS de Google Alerts opcionales),
las clasifica por tema, tipo y ciudad, las guarda en docs/reports.json
y, si la carpeta es un repositorio git, las publica en GitHub Pages.
Solo usa la biblioteca estándar de Python 3.
"""
import hashlib, html, json, re, subprocess, sys, unicodedata
import urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "docs" / "reports.json"
EC = timezone(timedelta(hours=-5))  # hora de Ecuador continental

# Pega aquí los enlaces RSS de tus Google Alerts (opcional, uno por línea):
ALERT_FEEDS = [
    # "https://www.google.com/alerts/feeds/XXXXXXXX/YYYYYYYY",
]
# Búsquedas en Google Noticias (no requieren configuración):
QUERIES = ["INAMHI", "INAMHI alerta", "INAMHI advertencia meteorológica", "INAMHI pronóstico lluvias"]
DIAS_ATRAS = 2  # cuántos días hacia atrás revisar en cada ejecución
CAPTURAS = False  # guardar una captura de pantalla de cada noticia (requiere Playwright, ver LEEME)
MAX_CAPTURAS = 40  # máximo de capturas por ejecución, para no tardar demasiado
DOCS = BASE / "docs"

TEMAS = [
    ("Tormentas eléctricas", r"tormenta|electric|rayos"),
    ("Radiación UV", r"radiacion|\buv\b|ultravioleta"),
    ("Altas temperaturas", r"ola de calor|altas temperaturas|calor"),
    ("Incendios forestales", r"incendio"),
    ("Inundaciones y crecidas", r"inundaci|crecida|desbord"),
    ("Oleaje", r"oleaje|marejada|mar de fondo"),
    ("Viento", r"viento|rafaga"),
    ("Lluvias", r"lluvia|llovi|lloviz|precipitaci|aguacero|temporal"),
]
LUGARES = [
    "Guayaquil", "Quito", "Cuenca", "Machala", "Manta", "Portoviejo", "Esmeraldas", "Santo Domingo",
    "Ambato", "Riobamba", "Loja", "Ibarra", "Quevedo", "Babahoyo", "Milagro", "Durán", "Samborondón",
    "Daule", "Latacunga", "Tulcán", "Azogues", "Guaranda", "Puyo", "Tena", "Macas", "Zamora",
    "Nueva Loja", "Orellana", "Playas", "Salinas", "Santa Rosa", "Huaquillas", "Galápagos",
    "Guayas", "Pichincha", "Azuay", "Manabí", "El Oro", "Los Ríos", "Santa Elena", "Cotopaxi",
    "Bolívar", "Cañar", "Imbabura", "Carchi", "Chimborazo", "Tungurahua", "Napo", "Pastaza",
    "Morona Santiago", "Zamora Chinchipe", "Sucumbíos", "Costa", "Sierra", "Amazonía", "Litoral",
]


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def limpiar(s):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()


def clasificar_tema(txt):
    t = norm(txt)
    hallados = [n for n, rx in TEMAS if re.search(rx, t)]
    return ", ".join(hallados[:2]) or "Otro"


def clasificar_tipo(txt):
    t = norm(txt)
    if re.search(r"advertencia|advierte", t):
        return "Advertencia"
    if re.search(r"\balerta|\balert", t):
        return "Alerta"
    if re.search(r"madrugada|esta noche|proximas horas|aviso", t):
        return "Aviso corto plazo"
    return "Pronóstico"


def detectar_lugares(txt):
    t = norm(txt)
    out = []
    for l in LUGARES:
        if re.search(r"\b" + re.escape(norm(l)) + r"\b", t) and l not in out:
            out.append(l)
    # evita "Zamora" y "Santo Domingo" duplicados con sus provincias compuestas
    if "Zamora Chinchipe" in out and "Zamora" in out:
        out.remove("Zamora")
    return ", ".join(out[:5]) or "Nacional"


def leer(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) monitor-inamhi"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def descripcion_pagina(url):
    """Mejor esfuerzo: toma la descripción de la nota si el enlace es directo."""
    if "news.google.com" in url:
        return ""
    try:
        h = leer(url, 8).decode("utf-8", "ignore")[:200000]
        m = re.search(r'<meta[^>]+(?:property="og:description"|name="description")[^>]+content="([^"]+)"', h, re.I)
        if not m:
            m = re.search(r'<meta[^>]+content="([^"]+)"[^>]+(?:property="og:description"|name="description")', h, re.I)
        return limpiar(m.group(1)) if m else ""
    except Exception:
        return ""


def fecha_ec(s):
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(EC)


def items_gnews(q):
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(f"{q} when:{DIAS_ATRAS}d")
           + "&hl=es-419&gl=EC&ceid=EC:es-419")
    root = ET.fromstring(leer(url))
    for it in root.iter("item"):
        titulo = limpiar(it.findtext("title"))
        medio = limpiar(it.findtext("source")) or ""
        if medio and titulo.endswith(" - " + medio):
            titulo = titulo[: -len(medio) - 3]
        yield {"m": medio or "Google Noticias", "titulo": titulo, "extra": limpiar(it.findtext("description")),
               "u": it.findtext("link") or "", "f": fecha_ec(it.findtext("pubDate"))}


def items_alert(url):
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(leer(url))
    for e in root.findall("a:entry", ns):
        link = e.find("a:link", ns).get("href", "")
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
        directo = qs.get("url", [link])[0]
        medio = urllib.parse.urlparse(directo).netloc.replace("www.", "")
        f = e.findtext("a:published", namespaces=ns) or e.findtext("a:updated", namespaces=ns)
        yield {"m": medio, "titulo": limpiar(e.findtext("a:title", namespaces=ns)),
               "extra": limpiar(e.findtext("a:content", namespaces=ns)), "u": directo, "f": fecha_ec(f)}


def capturar_lote(pendientes):
    """Abre cada noticia en un Chromium invisible y guarda una captura JPEG."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Capturas desactivadas: instala con  pip3 install playwright  y luego  "
              "python3 -m playwright install chromium", file=sys.stderr)
        return 0
    hechas = 0
    with sync_playwright() as p:
        nav = p.chromium.launch()
        ctx = nav.new_context(viewport={"width": 1280, "height": 900}, locale="es-EC",
                              user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                                         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
        for it, ruta in pendientes:
            pg = ctx.new_page()
            try:
                pg.goto(it["u"], wait_until="domcontentloaded", timeout=30000)
                if "news.google.com" in it["u"]:
                    try:
                        pg.wait_for_url(lambda u: "google.com" not in u, timeout=12000)
                    except Exception:
                        pass
                pg.wait_for_timeout(4000)
                for txt in ("Aceptar todo", "Aceptar", "Acepto", "Entendido", "Accept", "Cerrar"):
                    try:
                        pg.get_by_role("button", name=re.compile(txt, re.I)).first.click(timeout=800)
                        break
                    except Exception:
                        pass
                ruta.parent.mkdir(parents=True, exist_ok=True)
                pg.screenshot(path=str(ruta), type="jpeg", quality=60)
                it["s"] = ruta.relative_to(DOCS).as_posix()
                if "news.google.com" in it["u"] and "google.com" not in pg.url:
                    it["u"] = pg.url  # enlace directo a la nota
                hechas += 1
            except Exception as e:
                print(f"Aviso: sin captura de {it['u'][:70]}... ({e})", file=sys.stderr)
            finally:
                pg.close()
        nav.close()
    return hechas


def main():
    todo = "--todo" in sys.argv  # captura también las noticias antiguas que no tienen captura
    data = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {}
    vistos = {i.get("u") for v in data.values() for i in v} | {(i.get("m"), i.get("d")) for v in data.values() for i in v}
    limite = datetime.now(EC) - timedelta(days=DIAS_ATRAS + 1)
    nuevos = 0
    fuentes = [(items_gnews, q) for q in QUERIES] + [(items_alert, u) for u in ALERT_FEEDS]
    for fn, arg in fuentes:
        try:
            for it in fn(arg):
                texto = it["titulo"] + " " + it["extra"]
                if "inamhi" not in norm(texto) or it["f"] < limite or not it["u"]:
                    continue
                detalle = descripcion_pagina(it["u"]) or it["titulo"]
                clave = (it["m"], detalle)
                if it["u"] in vistos or clave in vistos:
                    continue
                completo = it["titulo"] + " " + detalle
                data.setdefault(it["f"].strftime("%Y-%m-%d"), []).append({
                    "m": it["m"], "c": detectar_lugares(completo), "t": clasificar_tema(completo),
                    "k": clasificar_tipo(completo), "d": detalle, "u": it["u"]})
                vistos.add(it["u"]); vistos.add(clave)
                nuevos += 1
        except Exception as e:
            print(f"Aviso: no se pudo leer {arg[:60]}... ({e})", file=sys.stderr)
    if CAPTURAS:
        desde = "0000-00-00"  # revisa todos los días; completa las capturas pendientes poco a poco
        pend = [(i, DOCS / "capturas" / f / (hashlib.md5(i["u"].encode()).hexdigest()[:10] + ".jpg"))
                for f, lst in sorted(data.items(), reverse=True) if f >= desde
                for i in lst if not i.get("s") and i.get("u")][:MAX_CAPTURAS]
        if pend:
            print(f"Capturas hechas: {capturar_lote(pend)} de {len(pend)}")
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(dict(sorted(data.items())), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{datetime.now(EC):%Y-%m-%d %H:%M} · noticias nuevas: {nuevos}")
    if (BASE / ".git").exists():
        sh = lambda *a: subprocess.run(a, cwd=BASE, capture_output=True, text=True)
        sh("git", "add", "-A")
        if sh("git", "status", "--porcelain").stdout.strip():
            sh("git", "commit", "-m", f"Reporte {datetime.now(EC):%Y-%m-%d %H:%M}")
            r = sh("git", "push")
            print("Publicado en GitHub Pages." if r.returncode == 0 else "Error al publicar: " + r.stderr)
        else:
            print("Sin cambios que publicar.")


if __name__ == "__main__":
    main()
