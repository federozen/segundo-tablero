"""
Monitor Deportivo Pro — Streamlit Edition v1.0
Adaptación del UserScript para correr como app web local con Streamlit.

Instalar dependencias:
    pip install streamlit anthropic requests beautifulsoup4 lxml

Correr:
    streamlit run app.py
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import unicodedata
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from datetime import datetime
import anthropic
import random
import math

# ─── CONFIG ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Monitor Deportivo Pro",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS GLOBAL ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Fuente base más grande ── */
html, body, [class*="css"] {
    font-size: 16px !important;
}

/* ── Tabs principales: envolver en lugar de scrollear ── */
.stTabs [data-baseweb="tab-list"] {
    flex-wrap: wrap !important;
    gap: 4px !important;
    overflow-x: visible !important;
    white-space: normal !important;
}
.stTabs [data-baseweb="tab"] {
    font-size: 15px !important;
    font-weight: 600 !important;
    padding: 8px 16px !important;
    white-space: nowrap !important;
    border-radius: 6px 6px 0 0 !important;
}

/* ── Títulos de noticias en cards ── */
.stMarkdown a, .stMarkdown p, .stMarkdown span {
    font-size: 15px;
    line-height: 1.55;
}

/* ── Sidebar más legible ── */
[data-testid="stSidebar"] {
    font-size: 15px !important;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stSelectbox,
[data-testid="stSidebar"] .stButton button {
    font-size: 15px !important;
}

/* ── Selectbox y radios más grandes ── */
.stSelectbox > div, .stRadio label {
    font-size: 15px !important;
}

/* ── Expanders ── */
.streamlit-expanderHeader {
    font-size: 14px !important;
}
</style>
""", unsafe_allow_html=True)

MAX_ITEMS = 50
SIMILITUD_UMBRAL = 0.22

# ─── FUENTES ──────────────────────────────────────────────────────────────────
FUENTES_NAC = [
    {"id": "ole",           "nombre": "Olé",           "url": "https://www.ole.com.ar/",                             "color": "#00a846", "es_ole": True},
    {"id": "espn",          "nombre": "ESPN AR",        "url": "https://www.espn.com.ar/",                            "color": "#cc0000", "es_espn": True},
    {"id": "tyc",           "nombre": "TyC Sports",     "url": "https://www.tycsports.com/",                          "color": "#1565c0"},
    {"id": "infobae",       "nombre": "Infobae",        "url": "https://www.infobae.com/deportes/",                   "color": "#b00020"},
    {"id": "lanacion",      "nombre": "La Nación",      "url": "https://www.lanacion.com.ar/deportes/",               "color": "#1565c0"},
    {"id": "tn",            "nombre": "TN Deportes",    "url": "https://tn.com.ar/deportes/",                         "color": "#cc2200"},
    {"id": "clarin",        "nombre": "Clarín Dep.",    "url": "https://www.clarin.com/deportes/",                    "color": "#c00000"},
    {"id": "elgrafico",     "nombre": "El Gráfico",     "url": "https://www.elgrafico.com.ar/",                       "color": "#b07800"},
    {"id": "dobleamarilla", "nombre": "Doble Amarilla", "url": "https://www.dobleamarilla.com.ar/",                   "color": "#a07800", "es_wp": True},
    {"id": "bolavip",       "nombre": "Bolavip",        "url": "https://bolavip.com/ar",                              "color": "#c04a00"},
    {"id": "lavoz",         "nombre": "La Voz",         "url": "https://www.lavoz.com.ar/deportes/",                  "color": "#8b0000"},
    {"id": "capital",       "nombre": "La Capital",     "url": "https://www.lacapital.com.ar/secciones/ovacion.html", "color": "#6a0d8a"},
    {"id": "na",            "nombre": "Noticias Arg.",  "url": "https://noticiasargentinas.com/search?category=65552a2ae38b1d41233b1aac", "color": "#c00060"},
]

FUENTES_INT = [
    {"id": "as",        "nombre": "AS",              "url": "https://as.com/futbol/",                          "color": "#b00020", "es_as": True},
    {"id": "marca",     "nombre": "Marca",            "url": "https://www.marca.com/",                          "color": "#267326"},
    {"id": "mundodep",  "nombre": "Mundo Deportivo",  "url": "https://www.mundodeportivo.com/",                 "color": "#1565c0"},
    {"id": "sport",     "nombre": "Sport",            "url": "https://www.sport.es/es/",                        "color": "#cc0020"},
    {"id": "globo",     "nombre": "Globoesporte",     "url": "https://ge.globo.com/",                           "color": "#007a2f"},
    {"id": "placar",    "nombre": "Placar",           "url": "https://placar.com.br/feed/",                     "color": "#c00040", "es_rss": True},
    {"id": "gazzetta",  "nombre": "Gazzetta Sport",   "url": "https://www.gazzetta.it/Calcio/",                 "color": "#e8000a"},
    {"id": "corriere",  "nombre": "Corriere Sport",   "url": "https://www.corrieredellosport.it/calcio",        "color": "#e06000"},
    {"id": "record",    "nombre": "Record PT",        "url": "https://www.record.pt/futebol/",                  "color": "#c8000a"},

    {"id": "bbc",       "nombre": "BBC Sport",        "url": "https://feeds.bbci.co.uk/sport/football/rss.xml",      "color": "#bb1919", "es_rss": True},
    {"id": "goal",      "nombre": "Goal",             "url": "https://www.goal.com/es",                         "color": "#00a878"},
    {"id": "espnint",   "nombre": "ESPN INT",         "url": "https://www.espn.com/soccer/",                    "color": "#d00000"},
    {"id": "cbssport",  "nombre": "CBS Sports",       "url": "https://www.cbssports.com/rss/headlines/soccer/", "color": "#004b87", "es_rss": True},
    {"id": "sportnews", "nombre": "Sporting News",    "url": "https://www.sportingnews.com/us/soccer",          "color": "#cc3300"},
    {"id": "lequipe",   "nombre": "L'Equipe",         "url": "https://www.lequipe.fr/Football/",                "color": "#f5c400"},
    {"id": "fifa",      "nombre": "FIFA (RSS)",       "url": "https://www.fifa.com/rss-feeds/index.html",       "color": "#326295"},

    # ── Nuevos: inglés + especialistas de mercado (todos por RSS) ──
    {"id": "guardian",   "nombre": "Guardian Fútbol",  "url": "https://www.theguardian.com/football/rss",        "color": "#052962", "es_rss": True},
    {"id": "skysports",  "nombre": "Sky Sports",       "url": "https://www.skysports.com/rss/12040",             "color": "#0072c9", "es_rss": True},
    {"id": "dimarzio",   "nombre": "Di Marzio",        "url": "https://www.gianlucadimarzio.com/it/rss",         "color": "#0a3d62", "es_rss": True},
    {"id": "calciomer",  "nombre": "Calciomercato",    "url": "https://www.calciomercato.com/rss",               "color": "#c8102e", "es_rss": True},
]

TODAS_FUENTES = FUENTES_NAC + FUENTES_INT
FUENTES_NAC_IDS = {f["id"] for f in FUENTES_NAC}

# ─── STOPWORDS ────────────────────────────────────────────────────────────────
STOPWORDS = set([
    "de","la","el","en","y","a","los","del","se","las","por","un","para","con","una","su","al","lo",
    "como","más","pero","sus","le","ya","o","fue","este","ha","si","porque","esta","son","entre",
    "cuando","muy","sin","sobre","también","me","hasta","hay","donde","quien","desde","todo","nos",
    "durante","e","esto","mi","antes","yo","otro","otras","otra","él","bien","así","cada","ser",
    "tiene","había","era","no","es","que","the","a","an","and","or","but","in","on","at","to","for",
    "of","with","by","from","is","was","are","were","be","been","have","has","had","will","would",
    "could","should","may","might","can","da","do","em","para","com","por","que","um","uma",
    "os","as","ao","na","no","nas","nos","se","seu","sua","seus","suas","não","após","tras",
    "vs","vs.","after","over","into","than","then","their","they","this","that",
])

# ─── SIMILITUD SEMÁNTICA ──────────────────────────────────────────────────────
@lru_cache(maxsize=8192)
def normalizar_titulo(titulo: str) -> set:
    t = titulo.lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return {w for w in t.split() if len(w) >= 3 and w not in STOPWORDS}

def similitud_jaccard(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    interseccion = len(set_a & set_b)
    union = len(set_a | set_b)
    return interseccion / union if union > 0 else 0.0

def es_exclusivo(titulo: str, propio_id: str, resultados: dict) -> bool:
    keys = normalizar_titulo(titulo)
    if len(keys) < 2:
        return False
    for f in TODAS_FUENTES:
        if f["id"] == propio_id:
            continue
        for n in resultados.get(f["id"], []):
            if similitud_jaccard(keys, normalizar_titulo(n["titulo"])) >= SIMILITUD_UMBRAL:
                return False
    return True

def analizar_ole_vs_competencia(resultados: dict) -> dict:
    # Pre-calcular keysets
    keysets = {}
    for f in TODAS_FUENTES:
        keysets[f["id"]] = [
            {"noticia": n, "keys": normalizar_titulo(n["titulo"])}
            for n in resultados.get(f["id"], [])
        ]

    ole_items = keysets.get("ole", [])
    competencia = [f for f in TODAS_FUENTES if not f.get("es_ole")]

    # 1. Exclusivos Olé
    exclusivos_ole = []
    for item in ole_items:
        encontrado = any(
            similitud_jaccard(item["keys"], ci["keys"]) >= SIMILITUD_UMBRAL
            for fid, citems in keysets.items()
            if fid != "ole"
            for ci in citems
        )
        if not encontrado:
            exclusivos_ole.append(item["noticia"])

    # 2. Faltantes en Olé
    faltantes_en_ole = []
    ya_agregados_keys = []
    for fuente in competencia:
        for item in keysets.get(fuente["id"], []):
            # ¿Lo tiene Olé?
            tiene_ole = any(
                similitud_jaccard(item["keys"], oi["keys"]) >= SIMILITUD_UMBRAL
                for oi in ole_items
            )
            if not tiene_ole:
                # Deduplicar entre faltantes
                es_dup = any(
                    similitud_jaccard(item["keys"], k) >= SIMILITUD_UMBRAL
                    for k in ya_agregados_keys
                )
                if not es_dup:
                    ya_agregados_keys.append(item["keys"])
                    faltantes_en_ole.append({
                        "titulo": item["noticia"]["titulo"],
                        "url": item["noticia"].get("url"),
                        "fuente_id": fuente["id"],
                        "fuente_nombre": fuente["nombre"],
                        "fuente_color": fuente["color"],
                    })

    # 3. Cubiertos por ambos
    cubiertos_por_ambos = []
    for item in ole_items:
        competidores = []
        for fid, citems in keysets.items():
            if fid == "ole":
                continue
            for ci in citems:
                sim = similitud_jaccard(item["keys"], ci["keys"])
                if sim >= SIMILITUD_UMBRAL:
                    competidores.append({"fuente_id": fid, "noticia": ci["noticia"], "sim": sim})
                    break
        if competidores:
            cubiertos_por_ambos.append({
                "noticia_ole": item["noticia"],
                "competencia": competidores[:4],
            })

    return {
        "exclusivos_ole": exclusivos_ole,
        "faltantes_en_ole": faltantes_en_ole,
        "cubiertos_por_ambos": cubiertos_por_ambos,
    }

def calcular_tendencias(resultados: dict) -> list:
    todas = []
    for f in TODAS_FUENTES:
        for n in resultados.get(f["id"], []):
            todas.append({"noticia": n, "fuente": f, "keys": normalizar_titulo(n["titulo"])})

    UMBRAL_CLUSTER = 0.20
    clusters = []
    asignado = [False] * len(todas)

    for i in range(len(todas)):
        if asignado[i]:
            continue
        cluster = {
            "titulo": todas[i]["noticia"]["titulo"],
            "url": todas[i]["noticia"].get("url"),
            "fuente_ids": {todas[i]["fuente"]["id"]},
            "noticias": [{"noticia": todas[i]["noticia"], "fuente": todas[i]["fuente"]}],
            "keys": todas[i]["keys"],
        }
        asignado[i] = True
        for j in range(i + 1, len(todas)):
            if asignado[j]:
                continue
            if similitud_jaccard(cluster["keys"], todas[j]["keys"]) >= UMBRAL_CLUSTER:
                cluster["fuente_ids"].add(todas[j]["fuente"]["id"])
                cluster["noticias"].append({"noticia": todas[j]["noticia"], "fuente": todas[j]["fuente"]})
                asignado[j] = True
        if len(cluster["fuente_ids"]) >= 2:
            clusters.append(cluster)

    clusters.sort(key=lambda c: (-len(c["fuente_ids"]), -len(c["noticias"])))
    return [
        {
            "titulo": c["titulo"],
            "url": c["url"],
            "cant_medios": len(c["fuente_ids"]),
            "fuente_ids": list(c["fuente_ids"]),
            "noticias": c["noticias"],
            "tiene_ole": "ole" in c["fuente_ids"],
            "nac": sum(1 for n in c["noticias"] if n["fuente"]["id"] in FUENTES_NAC_IDS),
            "intl": sum(1 for n in c["noticias"] if n["fuente"]["id"] not in FUENTES_NAC_IDS),
        }
        for c in clusters
    ]

# ─── AGENDA ACCIONABLE + MOMENTUM ─────────────────────────────────────────────
def calcular_momentum(tendencias: list, prev_tendencias: list) -> dict:
    """Compara cada cluster actual con el más parecido del snapshot anterior.
    Devuelve {indice_actual: {'delta': int, 'nuevo': bool}}.
    'delta' = variación en cantidad de medios; 'nuevo' si no matchea ninguno previo."""
    prev = prev_tendencias or []
    prev_keys = [normalizar_titulo(c["titulo"]) for c in prev]
    out = {}
    for i, c in enumerate(tendencias):
        k = normalizar_titulo(c["titulo"])
        best_j, best_sim = -1, 0.0
        for j, pk in enumerate(prev_keys):
            s = similitud_jaccard(k, pk)
            if s > best_sim:
                best_sim, best_j = s, j
        if best_j >= 0 and best_sim >= 0.30:
            out[i] = {"delta": c["cant_medios"] - prev[best_j]["cant_medios"], "nuevo": False}
        else:
            out[i] = {"delta": c["cant_medios"], "nuevo": True}
    return out

def construir_agenda(tendencias: list, ole_analisis: dict, prev_tendencias: list,
                     max_items: int = 14) -> list:
    """Convierte tendencias + análisis Olé en una lista priorizada de ACCIONES.
    Cada ítem trae un verbo (SUBIR YA / REDACTAR / SEGUIR / EMPUJAR), el motivo,
    el momentum y las noticias del cluster."""
    momentum = calcular_momentum(tendencias, prev_tendencias)
    items = []
    for i, c in enumerate(tendencias):
        mom = momentum.get(i, {"delta": 0, "nuevo": False})
        delta, nuevo = mom["delta"], mom["nuevo"]
        base = c["cant_medios"]
        tiene_ole = c.get("tiene_ole")
        score = base + max(delta, 0) * 2.5 + (3 if nuevo else 0) + (4 if not tiene_ole else 0)

        if not tiene_ole and base >= 3:
            accion, motivo = "SUBIR YA", f"{base} medios lo tienen y Olé no"
        elif not tiene_ole:
            accion, motivo = "REDACTAR", f"{base} medio(s) lo cubren y Olé no"
        elif nuevo or delta >= 2:
            accion = "SEGUIR"
            motivo = ("tema nuevo creciendo" if nuevo else f"creciendo (+{delta} medios)") + " — reforzá tu ángulo"
            score += 1
        else:
            continue  # ya cubierto por Olé y estable: no es una acción

        items.append({
            "accion": accion, "motivo": motivo, "titulo": c["titulo"], "url": c.get("url"),
            "cant_medios": base, "delta": delta, "nuevo": nuevo,
            "nac": c.get("nac", 0), "intl": c.get("intl", 0),
            "noticias": c.get("noticias", []), "score": score,
        })

    for n in (ole_analisis or {}).get("exclusivos_ole", [])[:5]:
        items.append({
            "accion": "EMPUJAR", "motivo": "exclusivo de Olé — promocionalo o hacé segunda vuelta",
            "titulo": n["titulo"], "url": n.get("url"),
            "cant_medios": 1, "delta": 0, "nuevo": False, "nac": 1, "intl": 0,
            "noticias": [], "score": 2.0,
        })

    items.sort(key=lambda x: -x["score"])
    return items[:max_items]

def prompt_parte_editorial(agenda: list) -> str:
    lineas = "\n".join(
        f"  {i+1}. [{it['accion']}] {it['titulo']} ({it['cant_medios']} medios; {it['motivo']})"
        for i, it in enumerate(agenda[:10])
    )
    return f"""Sos editor jefe de Olé. Esta es la agenda priorizada de forma automática.
Por cada ítem, en UNA sola línea, decime por qué le importa a un lector argentino y un ángulo concreto para la nota. Telegráfico, español rioplatense, sin relleno.

{lineas}"""

def prompt_brief_item(item: dict) -> str:
    fuentes_ctx = ""
    if item.get("noticias"):
        fuentes_ctx = "\nCómo lo titularon otros medios:\n" + "\n".join(
            f'  • [{n["fuente"]["nombre"]}] {n["noticia"]["titulo"]}'
            for n in item["noticias"][:6]
        )
    return f"""Sos editor jefe de Olé. Para este tema, dame un mini-brief en 3 líneas, español rioplatense, telegráfico y sin relleno:
VALOR: por qué es noticia de verdad (no cuántos medios lo tienen, sino qué está en juego).
ÁNGULO: el enfoque puntual para el lector de Olé (hincha argentino).
TÍTULO: un título sugerido, filoso, de una línea.

TEMA: {item["titulo"]}{fuentes_ctx}"""

AGENDA_COLORES = {
    "SUBIR YA": "#c0392b", "REDACTAR": "#d68910",
    "SEGUIR": "#2471a3", "EMPUJAR": "#1e8449",
}

def analizar_ole_vs_compecencia_safe(resultados: dict) -> dict:
    """Wrapper seguro para el análisis semántico."""
    try:
        return analizar_ole_vs_competencia(resultados)
    except Exception as e:
        return {"exclusivos_ole": [], "faltantes_en_ole": [], "cubiertos_por_ambos": []}

# ─── EXTRACCIÓN HTML ──────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Referer": "https://www.google.com/",
}

# Patrones para detectar imágenes genéricas/logos (definidos aquí para uso en extraer_generico)
_GENERIC_IMAGE_PATTERNS_EARLY = [
    "logo", "brand", "favicon", "default", "placeholder",
    "og-default", "og_default", "share-default",
    "ole-logo", "ole_logo", "icon",
]

def _es_imagen_generica(img_url: str) -> bool:
    """Retorna True si la URL parece ser un logo o imagen genérica del sitio."""
    if not img_url:
        return True
    lower = img_url.lower()
    return any(pat in lower for pat in _GENERIC_IMAGE_PATTERNS_EARLY)

def _extraer_imagen_rss_item(item_raw: str) -> str:
    """Extrae la imagen de un item RSS crudo (string XML). Más robusto que BS4 con namespaces."""
    # 1. media:content url="..."
    m = re.search(r'<media:content[^>]+url=["\']([^"\']+)["\']', item_raw)
    if m:
        src = m.group(1)
        if src.startswith("http") and not src.endswith(".gif") and not _es_imagen_generica(src):
            return src

    # 2. media:thumbnail url="..."
    m = re.search(r'<media:thumbnail[^>]+url=["\']([^"\']+)["\']', item_raw)
    if m:
        src = m.group(1)
        if src.startswith("http") and not src.endswith(".gif") and not _es_imagen_generica(src):
            return src

    # 3. enclosure type="image/..." url="..."
    m = re.search(r'<enclosure[^>]+type=["\']image/[^"\']*["\'][^>]+url=["\']([^"\']+)["\']', item_raw)
    if not m:
        m = re.search(r'<enclosure[^>]+url=["\']([^"\']+)["\'][^>]+type=["\']image/[^"\']*["\']', item_raw)
    if m:
        src = m.group(1)
        if src.startswith("http") and not _es_imagen_generica(src):
            return src

    # 4. content:encoded o description — buscar primer <img src="...">
    for tag in ["content:encoded", "description"]:
        m = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', item_raw, re.DOTALL)
        if m:
            content = m.group(1)
            # Decodificar CDATA si aplica
            cdata = re.search(r'<!\[CDATA\[(.*?)\]\]>', content, re.DOTALL)
            if cdata:
                content = cdata.group(1)
            # Buscar src= en img tags
            img_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
            if img_m:
                src = img_m.group(1)
                if src.startswith("http") and not src.endswith(".gif") and not _es_imagen_generica(src):
                    return src
            # También wp:featuredmedia o similares con URL
            wp_m = re.search(r'https?://[^\s"\'<>]+(?:jpg|jpeg|png|webp)', content, re.IGNORECASE)
            if wp_m:
                src = wp_m.group(0)
                if not _es_imagen_generica(src):
                    return src

    return ""

def extraer_rss(xml_text: str) -> list:
    noticias, vistos = [], set()
    try:
        soup = BeautifulSoup(xml_text, "xml")
        # Dividir el XML en items crudos para extraer imágenes con regex
        items_raw = re.findall(r'<item[^>]*>(.*?)</item>', xml_text, re.DOTALL | re.IGNORECASE)
        if not items_raw:
            items_raw = re.findall(r'<entry[^>]*>(.*?)</entry>', xml_text, re.DOTALL | re.IGNORECASE)

        for i, item in enumerate(soup.find_all(["item", "entry"])[:MAX_ITEMS]):
            titulo_tag = item.find("title")
            if not titulo_tag:
                continue
            titulo = titulo_tag.get_text(strip=True)
            titulo = re.sub(r"<[^>]+>", "", titulo)
            titulo = titulo.replace("&amp;","&").replace("&lt;","<").replace("&gt;",">").replace("&quot;",'"').replace("&#39;","'")
            if not titulo or len(titulo) < 15 or len(titulo) > 300 or titulo in vistos:
                continue
            vistos.add(titulo)
            url = None
            link_tag = item.find("link")
            if link_tag:
                url = link_tag.get_text(strip=True) or link_tag.get("href")
            if not url or not url.startswith("http"):
                guid = item.find("guid", isPermaLink="true")
                url = guid.get_text(strip=True) if guid else None
            # Extraer imagen del item crudo correspondiente
            imagen = ""
            if i < len(items_raw):
                imagen = _extraer_imagen_rss_item(items_raw[i])
            noticias.append({"titulo": titulo, "url": url, "imagen": imagen})
    except Exception:
        pass
    return noticias[:MAX_ITEMS]

def _extraer_ole(html: str, fuente: dict) -> list:
    """
    Scraper específico para Olé.
    - Prioriza links que terminan en .html (formato estándar de notas de Olé)
    - Escala el DOM hacia los padres para encontrar el link envolvente
    - Filtra autores/tags tanto en URLs como en imágenes (evita fotos de firma)
    """
    soup = BeautifulSoup(html, "html.parser")
    BASE = "https://www.ole.com.ar"
    noticias, vistos = [], set()

    _OLE_URL_SKIP = [
        "/autor/", "/autores/", "/firma/", "/columnistas/", "/tag/", "/tags/",
        "/categoria/", "/seccion/", "/author/", "tag=", "/tema/",
        "mailto:", "javascript:", "#",
    ]
    _FIRMA_CLASES = [
        "author", "autor", "firma", "byline", "avatar", "perfil", "profile",
        "journalist", "periodista", "columnist", "writer", "reporter",
        "signature", "bio", "headshot",
    ]

    def resolve_ole(href):
        if not href:
            return None
        if any(s in href for s in _OLE_URL_SKIP):
            return None
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/"):
            return BASE + href
        if href.startswith("http"):
            return href
        return None

    def _es_img_firma(tag):
        for parent in tag.parents:
            cls = " ".join(parent.get("class", [])).lower()
            pid = (parent.get("id") or "").lower()
            if any(p in cls or p in pid for p in _FIRMA_CLASES):
                return True
            if parent.name in ("article", "section", "main"):
                break
        return False

    def get_best_link(titulo_el, card):
        """Prioriza .html, escala DOM hasta 4 niveles hacia arriba."""
        candidatos = []

        # 1. Padre directo <a>
        p = titulo_el.find_parent("a")
        if p:
            u = resolve_ole(p.get("href", ""))
            if u:
                candidatos.append(u)

        # 2. <a> hijo del título
        ic = titulo_el.find("a")
        if ic:
            u = resolve_ole(ic.get("href", ""))
            if u and u not in candidatos:
                candidatos.append(u)

        # 3. Todos los <a> del card
        for a in card.find_all("a", href=True):
            u = resolve_ole(a.get("href", ""))
            if u and u not in candidatos:
                candidatos.append(u)

        # 4. Escalar DOM del card hacia arriba (4 niveles)
        parent = card.parent
        for _ in range(4):
            if not parent or parent.name in ("body", "html", "[document]"):
                break
            if parent.name == "a":
                u = resolve_ole(parent.get("href", ""))
                if u and u not in candidatos:
                    candidatos.append(u)
            for a in (parent.find_all("a", href=True, recursive=False) or []):
                u = resolve_ole(a.get("href", ""))
                if u and u not in candidatos:
                    candidatos.append(u)
            parent = parent.parent

        if not candidatos:
            return None
        # Priorizar .html
        html_links = [u for u in candidatos if u.endswith(".html")]
        return html_links[0] if html_links else candidatos[0]

    def get_mejor_imagen(card):
        """Imagen principal del card, ignorando fotos de firma/autor."""
        IMG_ATTRS = ["src", "data-src", "data-lazy-src", "data-original", "data-url"]
        candidatos = []

        for tag in card.find_all("img"):
            if _es_img_firma(tag):
                continue
            best_src = ""
            srcset = tag.get("srcset", "") or tag.get("data-srcset", "")
            if srcset:
                parts = [s.strip().split(" ") for s in srcset.split(",") if s.strip()]
                sized = []
                for p in parts:
                    url_s = p[0]
                    try:
                        w = int(p[1].rstrip("w")) if len(p) > 1 and p[1].endswith("w") else 0
                    except ValueError:
                        w = 0
                    sized.append((w, url_s))
                sized.sort(key=lambda x: x[0], reverse=True)
                for _, url_s in sized:
                    if url_s.startswith("http") and not _es_imagen_generica(url_s) and "1x1" not in url_s:
                        best_src = url_s
                        break
            if not best_src:
                for attr in IMG_ATTRS:
                    src = tag.get(attr, "")
                    if (src and src.startswith("http")
                            and not src.endswith(".gif")
                            and not _es_imagen_generica(src)
                            and "1x1" not in src
                            and "pixel" not in src.lower()):
                        best_src = src
                        break
            if best_src:
                score = 0
                cls = " ".join(tag.get("class", [])).lower()
                for good in ["featured", "hero", "portada", "principal", "cover",
                             "thumb", "thumbnail", "wp-post-image", "article-image"]:
                    if good in cls:
                        score += 300
                m = re.search(r'[-/](\d{3,4})x(\d{3,4})[-/.]', best_src)
                if m:
                    score += int(m.group(1)) + int(m.group(2))
                if tag.get("srcset") or tag.get("data-srcset"):
                    score += 100
                candidatos.append((score, best_src))

        if not candidatos:
            return ""
        candidatos.sort(key=lambda x: x[0], reverse=True)
        return candidatos[0][1]

    CARD_SELS_OLE = [
        "article", "[class*=card]", "[class*=nota]", "[class*=story]",
        "[class*=article]", "[class*=item]",
    ]
    TITLE_SELS_OLE = ["h1", "h2", "h3", "h4", "[class*=title]", "[class*=titular]", "[class*=headline]"]

    for sel in CARD_SELS_OLE:
        for card in soup.select(sel)[:MAX_ITEMS * 2]:
            if len(noticias) >= MAX_ITEMS:
                break
            titulo_el = None
            for tsel in TITLE_SELS_OLE:
                titulo_el = card.select_one(tsel)
                if titulo_el:
                    break
            if not titulo_el:
                continue
            titulo = titulo_el.get_text(strip=True)
            if len(titulo) < 20 or len(titulo) > 300 or titulo in vistos:
                continue
            vistos.add(titulo)
            url = get_best_link(titulo_el, card)
            img = get_mejor_imagen(card)
            noticias.append({"titulo": titulo, "url": url, "imagen": img})

    # Fallback: h2/h3 con links directos
    if len(noticias) < 8:
        for el in soup.select("h2 a[href], h3 a[href]"):
            if len(noticias) >= MAX_ITEMS:
                break
            titulo = el.get_text(strip=True)
            if len(titulo) < 20 or len(titulo) > 300 or titulo in vistos:
                continue
            url = resolve_ole(el.get("href", ""))
            if url:
                vistos.add(titulo)
                noticias.append({"titulo": titulo, "url": url, "imagen": ""})

    return noticias[:MAX_ITEMS]

def _extraer_as(html: str, fuente: dict) -> list:
    """Scraper específico para AS (as.com/futbol/). Filtra links de autores/tags."""
    soup = BeautifulSoup(html, "html.parser")
    BASE = "https://as.com"
    noticias, vistos = [], set()

    _AS_URL_SKIP = ["/autor/", "/autores/", "/tag/", "/tags/", "/tema/",
                    "/categoria/", "mailto:", "javascript", "/redaccion/"]

    def resolve_as(href):
        if not href:
            return None
        if any(s in href for s in _AS_URL_SKIP):
            return None
        if href.startswith("javascript") or href == "#":
            return None
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/"):
            return BASE + href
        if href.startswith("http"):
            return href
        return None

    def get_nota_url_as(titulo_el, card):
        parent_a = titulo_el.find_parent("a")
        if parent_a:
            u = resolve_as(parent_a.get("href", ""))
            if u:
                return u
        inner_a = titulo_el.find("a")
        if inner_a:
            u = resolve_as(inner_a.get("href", ""))
            if u:
                return u
        for a in card.find_all("a", href=True):
            u = resolve_as(a.get("href", ""))
            if u:
                return u
        return None

    CARD_SELS_AS = [
        "article", "[class*=card]", "[class*=article]",
        "[class*=noticia]", "[class*=story]", "[class*=item]",
        "li[class*=list]",
    ]
    TITLE_SELS_AS = ["h1", "h2", "h3", "[class*=title]", "[class*=headline]", "[class*=titular]"]

    for sel in CARD_SELS_AS:
        for card in soup.select(sel)[:MAX_ITEMS * 2]:
            if len(noticias) >= MAX_ITEMS:
                break
            titulo_el = None
            for tsel in TITLE_SELS_AS:
                titulo_el = card.select_one(tsel)
                if titulo_el:
                    break
            if not titulo_el:
                continue
            titulo = titulo_el.get_text(strip=True)
            if len(titulo) < 20 or len(titulo) > 300 or titulo in vistos:
                continue
            vistos.add(titulo)
            url = get_nota_url_as(titulo_el, card)
            img = ""
            for tag in card.find_all("img"):
                src = (tag.get("src") or tag.get("data-src") or
                       tag.get("data-lazy-src") or tag.get("data-original") or "")
                if src and src.startswith("http") and not _es_imagen_generica(src):
                    img = src
                    break
            noticias.append({"titulo": titulo, "url": url, "imagen": img})

    if len(noticias) < 8:
        for el in soup.select("h2 a[href], h3 a[href]"):
            if len(noticias) >= MAX_ITEMS:
                break
            titulo = el.get_text(strip=True)
            if len(titulo) < 20 or len(titulo) > 300 or titulo in vistos:
                continue
            vistos.add(titulo)
            url = resolve_as(el.get("href", ""))
            if url:
                noticias.append({"titulo": titulo, "url": url, "imagen": ""})

    return noticias[:MAX_ITEMS]


def _extraer_espn(html: str, fuente: dict) -> list:
    """Scraper dedicado para ESPN AR (SPA React). El HTML estático trae JSON-LD
    con las URLs reales; las notas siguen el patrón /_/id/NNNNNN/."""
    noticias, seen = [], set()
    soup = BeautifulSoup(html, "html.parser")
    BASE = "https://www.espn.com.ar"
    ESPN_SKIP = ["/autor/", "/author/", "/tag/", "/tags/", "/equipo/", "/liga/",
                 "/atletismo/", "javascript:", "mailto:", "#", "/video/"]

    def resolve_espn(href):
        if not href:
            return None
        if any(s in href for s in ESPN_SKIP):
            return None
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/"):
            return BASE + href
        if href.startswith("http"):
            return href
        return None

    def es_url_nota(url):
        if not url:
            return False
        return "/_/id/" in url or "/nota/" in url or "/historia/" in url or "/story/" in url

    urls_json = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")

            def _walk(obj):
                if isinstance(obj, dict):
                    if obj.get("@type") in ("NewsArticle", "Article", "WebPage"):
                        u = obj.get("url") or obj.get("mainEntityOfPage", {}).get("@id", "")
                        if u and es_url_nota(u) and u not in urls_json:
                            urls_json.append(u)
                    if obj.get("@type") == "ItemList":
                        for item in obj.get("itemListElement", []):
                            u = item.get("url") or item.get("item", {}).get("url", "")
                            if u and es_url_nota(u) and u not in urls_json:
                                urls_json.append(u)
                    for v in obj.values():
                        _walk(v)
                elif isinstance(obj, list):
                    for v in obj:
                        _walk(v)
            _walk(data)
        except Exception:
            pass

    urls_html = []
    for a in soup.find_all("a", href=True):
        url = resolve_espn(a.get("href", ""))
        if url and es_url_nota(url) and url not in urls_html:
            urls_html.append(url)

    todas_urls = list(dict.fromkeys(urls_json + urls_html))

    url_to_titulo = {}
    TITLE_SELS_ESPN = ["h1", "h2", "h3", "h4",
                       "[class*=title]", "[class*=Title]",
                       "[class*=headline]", "[class*=Headline]",
                       "[class*=contentItem__title]"]
    for a in soup.find_all("a", href=True):
        url = resolve_espn(a.get("href", ""))
        if not url or not es_url_nota(url):
            continue
        titulo = None
        for sel in TITLE_SELS_ESPN:
            t_el = a.select_one(sel)
            if t_el:
                titulo = t_el.get_text(strip=True)
                break
        if not titulo:
            titulo = a.get_text(strip=True)
        titulo = " ".join(titulo.split())
        if 20 <= len(titulo) <= 300 and url not in url_to_titulo:
            url_to_titulo[url] = titulo

    for url in todas_urls:
        if len(noticias) >= MAX_ITEMS:
            break
        titulo = url_to_titulo.get(url)
        if not titulo:
            slug = url.rstrip("/").split("/")[-1]
            slug = re.sub(r"^\d+-", "", slug)
            titulo = slug.replace("-", " ").title()
            if len(titulo) < 15:
                continue
        if titulo in seen:
            continue
        seen.add(titulo)
        noticias.append({"titulo": titulo, "url": url, "imagen": ""})

    return noticias[:MAX_ITEMS]


def extraer_generico(html: str, fuente: dict) -> list:
    # Scrapers específicos
    if fuente.get("es_ole"):
        return _extraer_ole(html, fuente)
    if fuente.get("es_as"):
        return _extraer_as(html, fuente)
    if fuente.get("es_espn"):
        return _extraer_espn(html, fuente)

    if fuente.get("es_rss"):
        return extraer_rss(html)

    # Doble Amarilla es WordPress — usar su feed RSS que incluye imágenes
    if fuente.get("es_wp"):
        feed_url = fuente["url"].rstrip("/") + "/feed/"
        try:
            resp = requests.get(feed_url, headers=_FETCH_HEADERS, timeout=15)
            if resp.status_code == 200 and "<rss" in resp.text[:500]:
                return extraer_rss(resp.text)
        except Exception:
            pass  # Fallback al scraping normal si el feed falla

    soup = BeautifulSoup(html, "html.parser")
    base_url = re.match(r"https?://[^/]+", fuente["url"])
    base = base_url.group(0) if base_url else ""
    noticias, vistos = [], set()

    CARD_SELS = ["article", "[class*=card]", "[class*=story]", "[class*=nota]", "[class*=item]", "[class*=news]"]
    TITLE_SELS = ["h1","h2","h3","h4","[class*=title]","[class*=headline]","[class*=titular]"]

    def resolve_url(href):
        if not href or href.startswith("javascript") or href == "#":
            return None
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/"):
            return base + href
        if href.startswith("http"):
            return href
        return None

    def get_titulo(el):
        for sel in TITLE_SELS:
            t = el.select_one(sel)
            if t:
                return t.get_text(strip=True)
        return None

    def get_url(el, titulo_el):
        link = titulo_el.find_parent("a") or titulo_el.find("a") or el.find("a")
        if link:
            return resolve_url(link.get("href", ""))
        return None

    # Patrones de clases/padres que indican imagen de firma/autor (NO foto de nota)
    AUTOR_PATTERNS = [
        "author", "autor", "firma", "byline", "avatar", "perfil", "profile",
        "journalist", "periodista", "columnist", "writer", "reporter",
        "signature", "bio", "headshot",
    ]

    def _es_img_autor(tag):
        """Retorna True si la imagen está dentro de un contenedor de firma/autor."""
        for parent in tag.parents:
            cls = " ".join(parent.get("class", [])).lower()
            pid = (parent.get("id") or "").lower()
            combined = cls + " " + pid
            if any(p in combined for p in AUTOR_PATTERNS):
                return True
            # No escalar más allá del card
            if parent == tag.parent.parent.parent:
                break
        return False

    def _img_score(tag, src):
        """Puntúa una imagen: más grande y más prominente = mayor score."""
        score = 0
        # Dimensiones explícitas
        try:
            w = int(tag.get("width") or tag.get("data-width") or 0)
            h = int(tag.get("height") or tag.get("data-height") or 0)
            score += w + h
        except (ValueError, TypeError):
            pass
        # Clases que sugieren imagen principal (incluyendo WordPress)
        cls = " ".join(tag.get("class", [])).lower()
        for good in [
            "featured", "hero", "portada", "principal", "cover",
            "thumb", "thumbnail", "featured-image", "post-image",
            "article-image", "nota-img", "card-img",
            # WordPress específico
            "wp-post-image", "attachment-", "size-large", "size-full",
            "size-medium_large", "wp-block-image", "entry-thumb",
        ]:
            if good in cls:
                score += 500
        # Clases de autor = penalizar mucho
        for bad in AUTOR_PATTERNS:
            if bad in cls:
                score -= 9999
        # Si es autor por contexto = penalizar
        if _es_img_autor(tag):
            score -= 9999
        # srcset presente = suele ser imagen de contenido
        if tag.get("srcset") or tag.get("data-srcset"):
            score += 200
        # Dimensiones implícitas de URL (Olé usa /fit-in/NxN/, WP usa -NNNxNNN.)
        m = re.search(r'[-/](\d{3,4})x(\d{3,4})[-/.]', src)
        if m:
            score += int(m.group(1)) + int(m.group(2))
        # alt descriptivo (no vacío, no "logo") también suma
        alt = (tag.get("alt") or "").lower()
        if alt and len(alt) > 5 and "logo" not in alt:
            score += 50
        return score

    def get_imagen(el):
        """Extrae la imagen principal de una card, ignorando fotos de autores."""
        IMG_ATTRS = ["src", "data-src", "data-lazy-src", "data-original", "data-url", "data-image"]
        candidatos = []  # (score, src)

        for tag in el.find_all("img"):
            best_src = ""
            # srcset primero — generalmente tiene la versión más grande
            srcset = tag.get("srcset", "") or tag.get("data-srcset", "")
            if srcset:
                parts = [s.strip().split(" ") for s in srcset.split(",") if s.strip()]
                # Ordenar por ancho declarado (ej "800w") descendente
                sized = []
                for p in parts:
                    url = p[0]
                    try:
                        w = int(p[1].rstrip("w")) if len(p) > 1 and p[1].endswith("w") else 0
                    except ValueError:
                        w = 0
                    sized.append((w, url))
                sized.sort(key=lambda x: x[0], reverse=True)
                for _, url in sized:
                    if url.startswith("http") and not _es_imagen_generica(url) and "1x1" not in url:
                        best_src = url
                        break

            if not best_src:
                for attr in IMG_ATTRS:
                    src = tag.get(attr, "")
                    if (src and src.startswith("http")
                            and not src.endswith(".gif")
                            and not _es_imagen_generica(src)
                            and "1x1" not in src
                            and "pixel" not in src.lower()):
                        best_src = src
                        break

            if best_src:
                score = _img_score(tag, best_src)
                candidatos.append((score, best_src))

        # background-image en estilos
        for tag in el.find_all(style=True):
            m = re.search(r'background(?:-image)?:\s*url\(["\']?(https?://[^"\')\s]+)["\']?\)', tag["style"])
            if m:
                src = m.group(1)
                if not _es_imagen_generica(src) and "1x1" not in src:
                    cls = " ".join(tag.get("class", [])).lower()
                    score = 100
                    for bad in AUTOR_PATTERNS:
                        if bad in cls:
                            score = -9999
                    candidatos.append((score, src))

        if not candidatos:
            return ""
        # Tomar la de mayor score, descartar si score muy negativo (= autor)
        candidatos.sort(key=lambda x: x[0], reverse=True)
        best_score, best_src = candidatos[0]
        return best_src if best_score > -100 else ""

    # Intentar cards
    for sel in CARD_SELS:
        for card in soup.select(sel)[:MAX_ITEMS * 2]:
            if len(noticias) >= MAX_ITEMS:
                break
            titulo_el = None
            for tsel in TITLE_SELS:
                titulo_el = card.select_one(tsel)
                if titulo_el:
                    break
            if not titulo_el:
                continue
            titulo = titulo_el.get_text(strip=True)
            if len(titulo) < 20 or len(titulo) > 300 or titulo in vistos:
                continue
            vistos.add(titulo)
            url = get_url(card, titulo_el)
            imagen = get_imagen(card)
            noticias.append({"titulo": titulo, "url": url, "imagen": imagen})

    # Fallback: sólo headings
    if len(noticias) < 8:
        for sel in ["h2","h3"]:
            for el in soup.select(sel)[:MAX_ITEMS * 2]:
                if len(noticias) >= MAX_ITEMS:
                    break
                titulo = el.get_text(strip=True)
                if len(titulo) < 20 or len(titulo) > 300 or titulo in vistos:
                    continue
                vistos.add(titulo)
                link = el.find_parent("a") or el.find("a")
                url = resolve_url(link.get("href", "")) if link else None
                noticias.append({"titulo": titulo, "url": url})

    return noticias[:MAX_ITEMS]

def fetch_fuente(fuente: dict) -> dict:
    try:
        resp = requests.get(fuente["url"], headers=HEADERS, timeout=15)
        resp.raise_for_status()
        # Detectar encoding real desde el header o el HTML antes de usar resp.text
        # requests a veces asume ISO-8859-1 para text/html sin charset declarado
        content_type = resp.headers.get("content-type", "").lower()
        if "charset=" in content_type:
            # Respetar el charset del servidor
            encoding = content_type.split("charset=")[-1].split(";")[0].strip()
        else:
            # Intentar detectar desde el meta charset del HTML
            raw = resp.content
            sniff = raw[:4096].decode("ascii", errors="ignore").lower()
            if 'charset="utf-8"' in sniff or "charset=utf-8" in sniff:
                encoding = "utf-8"
            elif 'charset="iso-8859-1"' in sniff or 'charset=iso-8859-1' in sniff:
                encoding = "iso-8859-1"
            elif 'charset="windows-1252"' in sniff or 'charset=windows-1252' in sniff:
                encoding = "windows-1252"
            else:
                # Si apparent_encoding detecta latin, usarlo; si no, utf-8
                detected = (resp.apparent_encoding or "utf-8").lower()
                # Confiar en la detección (incluye windows-1252/latin para páginas
                # ES/PT/IT/FR sin charset declarado); sólo caer a utf-8 si es ascii/vacío.
                encoding = "utf-8" if detected in ("ascii", "") else detected
        resp.encoding = encoding
        noticias = extraer_generico(resp.text, fuente)
        return {"id": fuente["id"], "noticias": noticias, "error": None}
    except Exception as e:
        return {"id": fuente["id"], "noticias": [], "error": str(e)}

# ─── IA — CLAUDE ──────────────────────────────────────────────────────────────
def call_claude(prompt: str, api_key: str, max_tokens: int = 2000) -> str:
    if not api_key:
        raise RuntimeError("Falta la API key de Anthropic.")
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        raise RuntimeError(f"Error al llamar a Claude: {e}") from e
    # Concatenar todos los bloques de texto (no asumir que content[0] es texto)
    partes = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
    return "\n".join(partes).strip()

def prompt_analisis_general(resultados: dict) -> str:
    bloque = "\n\n".join(
        f"### {f['nombre']}\n" + "\n".join(
            f"  • {n['titulo']}"
            for n in resultados.get(f["id"], [])[:25]
        ) or "  (sin datos)"
        for f in TODAS_FUENTES
    )
    return f"""Sos editor jefe de un portal deportivo argentino. Analizá estos titulares de {len(TODAS_FUENTES)} medios deportivos y respondé en español rioplatense:

1. AGENDA DEL MOMENTO — 4 oraciones sobre qué temas dominan ahora.
2. TEMAS CON MAYOR VOLUMEN — Los 5 temas que más medios cubren simultáneamente.
3. OPORTUNIDADES EDITORIALES — 3 ideas de notas que nadie cubre bien pero tienen potencial.
4. DIFERENCIAS NACIONALES vs INTERNACIONALES — Qué cubren los medios españoles/brasileños/ingleses que los argentinos ignoran, y viceversa.

Separar secciones con ───────. Sé directo y accionable.

{bloque}"""

def prompt_informe_ole(resultados: dict, analisis: dict) -> str:
    exclusivos = analisis["exclusivos_ole"]
    faltantes = analisis["faltantes_en_ole"]
    compartidos = analisis["cubiertos_por_ambos"]

    bloque_excl = "\n".join(f"  • {n['titulo']}" for n in exclusivos[:30]) or "  (ninguno)"
    bloque_falt = "\n".join(f"  • [{f['fuente_nombre']}] {f['titulo']}" for f in faltantes[:40]) or "  (ninguno)"
    bloque_comp = "\n\n".join(
        f"  • OLÉ: \"{c['noticia_ole']['titulo']}\"\n" +
        "\n".join(
            f"    → [{TODAS_FUENTES[[x['id'] for x in TODAS_FUENTES].index(comp['fuente_id'])]['nombre'] if comp['fuente_id'] in [x['id'] for x in TODAS_FUENTES] else comp['fuente_id']}] {comp['noticia']['titulo']}"
            for comp in c["competencia"]
        )
        for c in compartidos[:20]
    ) or "  (ninguno)"

    return f"""Sos editor jefe de Olé. Tenés un análisis semántico automático que agrupó noticias por TEMA (no por título exacto).

⚠️ Si un tema figura en "FALTANTES", es porque verdaderamente no está en Olé.

─────────────────────────────────────────────────────
## EXCLUSIVOS DE OLÉ ({len(exclusivos)} temas):
{bloque_excl}

─────────────────────────────────────────────────────
## FALTANTES EN OLÉ ({len(faltantes)} temas):
{bloque_falt}

─────────────────────────────────────────────────────
## TEMAS COMPARTIDOS CON ÁNGULO DIFERENTE:
{bloque_comp}
─────────────────────────────────────────────────────

Generá un informe editorial en español rioplatense:

1. 🟢 DONDE OLÉ ESTÁ ADELANTE — 5 exclusivos más valiosos.
2. 🔴 LO QUE OLÉ NO DIO — TOP 5 urgentes con título sugerido y ángulo para Argentina.
3. 🔵 MISMO TEMA, MEJOR ÁNGULO — 3 casos donde la competencia lo enfocó mejor.
4. ⚡ ALERTAS INTERNACIONALES — Top 3 noticias europeas/brasileñas con potencial para Olé.
5. 📋 PLAN EDITORIAL — 4 acciones prioritarias para las próximas 3 horas.

Separar secciones con ───────. Sé muy específico y accionable."""

# ─── SCRAPING DE CUERPO DE NOTA ──────────────────────────────────────────────
def _extraer_cuerpo_nota(url: str, max_chars: int = 900) -> str:
    """Intenta extraer los primeros párrafos del cuerpo de una nota. Retorna '' si falla.
    Limitado a 900 chars por nota para controlar el gasto de tokens de entrada."""
    if not url or not url.startswith("http"):
        return ""
    try:
        resp = requests.get(url, headers=_FETCH_HEADERS, timeout=12, allow_redirects=True)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        # Eliminar scripts, estilos, menús, publicidades
        for tag in soup(["script", "style", "nav", "header", "footer",
                          "aside", "form", "figure", "noscript", "iframe"]):
            tag.decompose()
        # Selectores de cuerpo de nota, del más específico al más genérico
        BODY_SELS = [
            "article .article-body", "article .nota-cuerpo", "article .entry-content",
            "article .article-content", "article .post-content", "article .content-body",
            ".article__body", ".nota__cuerpo", ".article-text", ".news-body",
            "[class*=article-body]", "[class*=nota-cuerpo]", "[class*=entry-content]",
            "[class*=article-content]", "[class*=post-body]",
            "article", "[role=main]",
        ]
        texto = ""
        for sel in BODY_SELS:
            el = soup.select_one(sel)
            if el:
                parrafos = [p.get_text(" ", strip=True) for p in el.find_all("p") if len(p.get_text(strip=True)) > 40]
                texto = "\n".join(parrafos[:5])  # máx 5 párrafos por nota
                if len(texto) > 200:
                    break
        if not texto:
            # Último recurso: todos los <p> largos de la página
            parrafos = [p.get_text(" ", strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 60]
            texto = "\n".join(parrafos[:4])
        return texto[:max_chars].strip()
    except Exception:
        return ""

def scrape_cuerpos_notas(titulares: list, max_notas: int = 6) -> list:
    """
    Enriquece los titulares con el cuerpo scrapeado de cada URL.
    Retorna lista de dicts con keys: fuente, noticia, cuerpo, ok.
    Solo scrappea las primeras max_notas con URL válida.
    """
    enriquecidos = []
    con_url = [item for item in titulares if item["noticia"].get("url")][:max_notas]
    sin_url  = [item for item in titulares if not item["noticia"].get("url")]

    if con_url:
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = {ex.submit(_extraer_cuerpo_nota, item["noticia"]["url"]): item for item in con_url}
            for future in as_completed(futures):
                item = futures[future]
                try:
                    cuerpo = future.result()
                except Exception:
                    cuerpo = ""
                enriquecidos.append({**item, "cuerpo": cuerpo, "ok": bool(cuerpo)})

    for item in sin_url:
        enriquecidos.append({**item, "cuerpo": "", "ok": False})

    # Agregar el resto de titulares (más allá de max_notas) sin cuerpo
    ids_procesados = {id(item) for item in con_url + sin_url}
    for item in titulares:
        if id(item) not in ids_procesados:
            enriquecidos.append({**item, "cuerpo": "", "ok": False})

    return enriquecidos

def prompt_nota_rapida(tema: str, titulares_enriquecidos: list, estilo: str, tipo_nota: str, contexto_extra: str = "") -> str:
    con_cuerpo  = [t for t in titulares_enriquecidos if t.get("ok")]
    solo_titulo = [t for t in titulares_enriquecidos if not t.get("ok")]
    tiene_info_real = len(con_cuerpo) > 0

    # Bloque de fuentes con cuerpo completo
    bloque_completo = ""
    if con_cuerpo:
        partes = []
        for t in con_cuerpo:
            f, n = t["fuente"], t["noticia"]
            partes.append(
                f"── [{f['nombre']}] {n['titulo']}\n"
                f"URL: {n.get('url','')}\n"
                f"TEXTO:\n{t['cuerpo']}"
            )
        bloque_completo = "\n\n".join(partes)

    # Bloque de fuentes solo con titular
    bloque_titulares = ""
    if solo_titulo:
        bloque_titulares = "\n".join(
            f"  • [{t['fuente']['nombre']}] {t['noticia']['titulo']}"
            for t in solo_titulo
        )

    estilos = {
        "Informativa": (
            "Estilo agencia de noticias argentina (Télam/NA). "
            "Tono directo, neutro, sin opinión ni adjetivos innecesarios. "
            "Verbos en pasado o presente simple. Oraciones cortas. "
            "Los datos concretos van primero, el contexto después."
        ),
        "Analítica": (
            "Estilo agencia argentina con profundidad. "
            "Tono directo y neutro pero con contexto, antecedentes y proyección. "
            "Cada afirmación tiene respaldo en las fuentes. "
            "Párrafos más largos, estructura de causa-efecto."
        ),
        "Urgente/Flash": (
            "Estilo despacho urgente de agencia argentina. "
            "Máximo 3 párrafos muy cortos. Verbo en presente. "
            "Solo el dato central, sin contexto. "
            "Primera oración = toda la noticia en una línea."
        ),
    }
    tipos = {
        "Nota completa": (
            "Nota con subtítulos (SIN lead/cierre clásico de manual). Estructura:\n"
            "- Primer párrafo suelto: el hecho central en 2-3 oraciones directas, sin subtítulo.\n"
            "- Luego 3 o 4 secciones, cada una con subtítulo informativo en negrita (## Subtítulo), "
            "seguido de 2-3 párrafos de 60-80 palabras.\n"
            "- La nota entera: entre 400 y 550 palabras.\n"
            "- Los subtítulos deben ser concretos y periodísticos, no genéricos "
            "(ej: '## La lesión y los plazos de recuperación' en vez de '## Contexto')."
        ),
        "Solo titulares alternativos": (
            "Generá 8 titulares alternativos: 2 impactantes, 2 SEO, "
            "2 para redes sociales (con gancho), 2 estilo agencia neutro. "
            "Para cada uno agregá una línea corta explicando el enfoque."
        ),
        "Esqueleto + ángulos": (
            "Esqueleto con subtítulos numerados (## 1. ..., ## 2. ...) "
            "y una línea describiendo qué información va en cada sección. "
            "Al final, 3 ángulos posibles con título sugerido para cada uno."
        ),
    }

    if tiene_info_real:
        instruccion_alucinacion = """⚠️ REGLAS ANTI-ALUCINACIÓN (CRÍTICAS — leelas antes de escribir una sola palabra):
- Usá ÚNICAMENTE datos, cifras, citas y hechos que aparezcan textualmente en las FUENTES de abajo.
- Prohibido agregar contexto histórico, estadísticas o antecedentes que no estén en los textos.
- Las citas entre comillas SOLO pueden ser frases que aparezcan literalmente en los textos fuente.
- Si un dato no está en los textos, escribí [DATO A CONFIRMAR] en su lugar. Sin excepciones.
- Si dos fuentes se contradicen, mencioná la contradicción explícitamente."""

        instruccion_formato = """
FORMATO DE RESPUESTA OBLIGATORIO — respetá este orden exacto:

════════════════════════════════════
NOTA
════════════════════════════════════
[Aquí va la nota redactada según el estilo y entregable solicitado]


════════════════════════════════════
TABLA DE VERIFICACIÓN
════════════════════════════════════
Lista TODOS los datos concretos que usaste en la nota (cifras, nombres, citas, hechos).
Para cada uno indicá:
• DATO: el dato exacto como aparece en la nota
• FUENTE: nombre del medio de donde lo tomaste
• VERIFICADO: ✅ si está textualmente en el cuerpo scrapeado | ⚠️ si solo aparece en el titular | ❌ si no encontrás respaldo

Ejemplo de fila:
• DATO: "sufrió un desgarro en el isquiotibial derecho" | FUENTE: TyC Sports | VERIFICADO: ✅

════════════════════════════════════
ÁNGULOS ALTERNATIVOS
════════════════════════════════════
2 enfoques distintos para trabajar la nota, con título sugerido para cada uno.
"""

        bloque_fuentes = f"""=== FUENTES CON TEXTO COMPLETO ({len(con_cuerpo)}) — de estas podés extraer datos ===
{bloque_completo}"""
        if bloque_titulares:
            bloque_fuentes += f"""

=== FUENTES SOLO CON TITULAR ({len(solo_titulo)}) — NO inferir datos, solo confirmar que el tema existe ===
{bloque_titulares}"""
    else:
        instruccion_alucinacion = """⚠️ MODO ESQUELETO SEGURO — no se pudo leer el cuerpo de ninguna nota.
No redactes la nota. En cambio, seguí el formato de respuesta obligatorio de abajo."""

        instruccion_formato = """
FORMATO DE RESPUESTA OBLIGATORIO:

════════════════════════════════════
ESQUELETO DE NOTA
════════════════════════════════════
Estructura con secciones numeradas y vacías, listas para que el redactor complete.
Indicá qué tipo de información va en cada sección.

════════════════════════════════════
DATOS CONFIRMADOS (solo desde titulares)
════════════════════════════════════
Lista con bullet points. Solo lo que los titulares permiten afirmar con certeza.
Formato: • [dato] — confirmado por: [medio]

════════════════════════════════════
DATOS A CONFIRMAR ANTES DE PUBLICAR
════════════════════════════════════
Lista de preguntas concretas que el redactor debe responder antes de publicar.

════════════════════════════════════
ÁNGULOS ALTERNATIVOS
════════════════════════════════════
3 enfoques distintos según qué datos aparezcan, con título sugerido para cada uno.
"""
        bloque_fuentes = f"""=== SOLO TITULARES DISPONIBLES ({len(solo_titulo)}) ===
{bloque_titulares}"""

    return f"""Sos un redactor deportivo de un portal argentino. Tu tarea es trabajar sobre este tema:

TEMA: {tema}
ESTILO: {estilos.get(estilo, estilos["Informativa"])}
ENTREGABLE: {tipos.get(tipo_nota, tipos["Nota completa"])}

{instruccion_alucinacion}
{instruccion_formato}

{bloque_fuentes}

Escribí en español rioplatense con voseo. Tono de agencia de noticias argentina (estilo Télam, NA, DyN).
Reglas de estilo periodístico argentino:
- Los clubes se nombran como los nombra la prensa argentina: "River" (no "River Plate"), "Boca" (no "Boca Juniors"), "Racing" (no "Racing Club"), "San Lorenzo" (no "San Lorenzo de Almagro"), "Independiente", "Huracán", "Vélez", "Lanús", "Defensa", etc.
- Los seleccionados: "la Selección" o "el equipo nacional" (no "la Albiceleste" salvo que sea en un contexto festivo), "la Sub-20", "la Sub-23".
- Los jugadores se mencionan por apellido a partir de la segunda referencia: "Messi" (no "La Pulga"), "Di María" (no "el Fideo"). Sin apodos en texto de agencia.
- Cargos y funciones en minúscula: "el entrenador Scaloni", "el presidente Laporta", "el director técnico".
- Evitá frases como "en este contexto", "cabe destacar", "vale la pena mencionar", "a su vez", "en tanto".
- No uses adjetivos valorativos ("increíble", "impresionante", "histórico", "brillante") salvo que estén textualmente en la fuente.
- Nunca uses "lead", "bajada" ni ningún término de manual de redacción en el cuerpo de la nota.
{("\n=== CONTEXTO ADICIONAL DEL REDACTOR ===\n" + contexto_extra + "\n(Podés usar este contexto libremente en la nota — es información aportada por el redactor, no requiere verificación de fuente.)") if contexto_extra else ""}
"""


def prompt_tono_editorial(query: str, titulares_filtrados: list) -> str:
    bloque = "\n".join(
        f'[{item["fuente"]["nombre"]}] {item["noticia"]["titulo"]}'
        for item in titulares_filtrados
    )
    return f"""Analizá el tono editorial de estos titulares sobre "{query}".

TITULARES ({len(titulares_filtrados)} en total):
{bloque}

Respondé ÚNICAMENTE con un objeto JSON válido, sin texto antes ni después, sin backticks.
El JSON debe tener exactamente esta estructura:

{{
  "resumen": "una oración que describe el tono general de la cobertura",
  "distribucion": {{
    "positivo": 0,
    "negativo": 0,
    "neutro": 0,
    "alarmista": 0,
    "expectante": 0
  }},
  "por_medio": [
    {{
      "medio": "nombre del medio",
      "tono": "positivo|negativo|neutro|alarmista|expectante",
      "titular": "el titular analizado",
      "razon": "una línea explicando por qué ese tono"
    }}
  ],
  "patrones": [
    "patrón editorial detectado 1",
    "patrón editorial detectado 2"
  ]
}}

Tonos posibles:
- positivo: elogio, logro, buena noticia
- negativo: crítica, fracaso, escándalo, mala noticia
- neutro: informativo puro, sin carga valorativa
- alarmista: urgencia, crisis, peligro, dramatismo
- expectante: incertidumbre, espera, "podría", "se espera"
"""

if "resultados" not in st.session_state:
    st.session_state.resultados = {}
if "ultima_act" not in st.session_state:
    st.session_state.ultima_act = None
if "analisis_general" not in st.session_state:
    st.session_state.analisis_general = ""
if "informe_ole" not in st.session_state:
    st.session_state.informe_ole = ""
if "ole_analisis" not in st.session_state:
    st.session_state.ole_analisis = None
if "tendencias" not in st.session_state:
    st.session_state.tendencias = []
if "prev_tendencias" not in st.session_state:
    st.session_state.prev_tendencias = []
if "agenda_parte" not in st.session_state:
    st.session_state.agenda_parte = ""
if "agenda_briefs" not in st.session_state:
    st.session_state.agenda_briefs = {}
if "nota_rapida" not in st.session_state:
    st.session_state.nota_rapida = ""
if "nota_rapida_titulares" not in st.session_state:
    st.session_state.nota_rapida_titulares = []
if "nota_rapida_modo" not in st.session_state:
    st.session_state.nota_rapida_modo = ""
if "sentimiento_resultado" not in st.session_state:
    st.session_state.sentimiento_resultado = None
if "sentimiento_query" not in st.session_state:
    st.session_state.sentimiento_query = ""
if "canasta" not in st.session_state:
    st.session_state.canasta = []  # lista de dicts {fuente, noticia}
if "canasta_borrador" not in st.session_state:
    st.session_state.canasta_borrador = ""

# Cache de imágenes a nivel de módulo (accesible desde threads)
# Se mantiene mientras el proceso de Streamlit esté vivo
_IMAGE_CACHE: dict = {}

# ─── IMÁGENES OG ─────────────────────────────────────────────────────────────
_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Referer": "https://www.google.com/",
}

def fetch_og_image(url: str) -> str:
    """Busca la imagen principal de una nota. Retorna la URL de la imagen o ''."""
    if not url or not url.startswith("http") or "google.com/search" in url:
        return ""
    if url in _IMAGE_CACHE:
        return _IMAGE_CACHE[url]
    try:
        resp = requests.get(url, headers=_FETCH_HEADERS, timeout=10, allow_redirects=True)
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1. Intentar og:image / twitter:image
        for meta in [
            soup.find("meta", property="og:image"),
            soup.find("meta", property="og:image:url"),
            soup.find("meta", attrs={"name": "twitter:image"}),
            soup.find("meta", attrs={"name": "twitter:image:src"}),
        ]:
            if not meta:
                continue
            candidate = meta.get("content", "") or meta.get("value", "") or ""
            if candidate and not _es_imagen_generica(candidate):
                _IMAGE_CACHE[url] = candidate
                return candidate

        # 2. Fallback: primera imagen grande dentro del artículo
        #    Selectores ordenados de más específico a más genérico
        img_selectors = [
            "article figure img",
            "article .image img",
            "article img[src]",
            ".nota-cuerpo img",
            ".article-body img",
            ".entry-content img",
            "figure img",
            "[class*=hero] img",
            "[class*=featured] img",
            "[class*=portada] img",
            "[class*=cover] img",
        ]
        for sel in img_selectors:
            for tag in soup.select(sel):
                src = (
                    tag.get("src") or tag.get("data-src") or
                    tag.get("data-lazy-src") or tag.get("data-original") or ""
                )
                if (src and src.startswith("http")
                        and not src.endswith(".gif")
                        and not _es_imagen_generica(src)
                        and "1x1" not in src and "pixel" not in src.lower()):
                    _IMAGE_CACHE[url] = src
                    return src

        _IMAGE_CACHE[url] = ""
        return ""
    except Exception:
        _IMAGE_CACHE[url] = ""
        return ""

def fetch_og_images_batch(noticias: list) -> None:
    """Fetch og:images en paralelo para una lista de noticias. Guarda en _IMAGE_CACHE."""
    urls_sin_cache = [
        n["url"] for n in noticias
        if n.get("url") and n["url"] not in _IMAGE_CACHE
    ]
    if not urls_sin_cache:
        return
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(fetch_og_image, u) for u in urls_sin_cache]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception:
                pass

def _canasta_agregar(titulo: str, url: str, fuente: dict, scrape_cuerpo: bool = True):
    """
    Agrega una noticia a la canasta si no está ya.
    Si scrape_cuerpo=True y hay URL, intenta leer el cuerpo de la nota en el momento.
    """
    ya = any(item["noticia"]["titulo"] == titulo for item in st.session_state.canasta)
    if ya:
        return
    cuerpo = ""
    if scrape_cuerpo and url:
        try:
            cuerpo = _extraer_cuerpo_nota(url, max_chars=1800)
        except Exception:
            cuerpo = ""
    st.session_state.canasta.append({
        "fuente": fuente,
        "noticia": {"titulo": titulo, "url": url},
        "cuerpo": cuerpo,
    })

def render_news_cards(noticias: list, fuente: dict, resultados: dict, cols_per_row: int = 3):
    """
    Renderiza noticias como cards con imagen grande arriba del título.
    Descarga og:images en paralelo antes de renderizar.
    """
    if not noticias:
        st.warning("Sin datos para esta fuente.")
        return

    # Separar noticias sin imagen del scraping — esas necesitan fetch de og:image
    sin_imagen = [n for n in noticias if not n.get("imagen") and n.get("url")]
    if sin_imagen:
        with st.spinner("Cargando imágenes..."):
            fetch_og_images_batch(sin_imagen)

    # Render en grilla
    rows = [noticias[i:i+cols_per_row] for i in range(0, len(noticias), cols_per_row)]
    color = fuente["color"]

    for row in rows:
        cols = st.columns(cols_per_row)
        for col, n in zip(cols, row):
            with col:
                # Prioridad: imagen extraída del card > og:image cacheado
                img_url = n.get("imagen") or _IMAGE_CACHE.get(n.get("url", ""), "")
                excl = es_exclusivo(n["titulo"], fuente["id"], resultados)

                # Card HTML completa
                excl_badge = (
                    f'<div style="position:absolute;top:8px;left:8px;'
                    f'background:rgba(212,160,23,.92);color:#fff;'
                    f'font-size:10px;font-weight:700;padding:2px 8px;'
                    f'border-radius:3px;letter-spacing:.6px">★ EXCLUSIVO</div>'
                ) if excl else ""

                img_html = (
                    f'<div style="position:relative;width:100%;padding-bottom:52%;'
                    f'overflow:hidden;background:#eef0f5;border-radius:8px 8px 0 0">'
                    f'<img src="{img_url}" style="position:absolute;inset:0;width:100%;'
                    f'height:100%;object-fit:cover" onerror="this.style.display=\'none\'">'
                    f'{excl_badge}</div>'
                ) if img_url else (
                    f'<div style="width:100%;padding:28px 0;background:#eef0f5;'
                    f'border-radius:8px 8px 0 0;text-align:center;font-size:28px">⚽</div>'
                )

                border_color = "#d4a017" if excl else color
                bg_excl = "background:#fffdf4;" if excl else ""

                titulo_link = (
                    f'<a href="{n["url"]}" target="_blank" rel="noopener" '
                    f'style="color:#14171a;text-decoration:none;font-size:15px;'
                    f'font-weight:600;line-height:1.5;display:block">'
                    f'{n["titulo"]}</a>'
                ) if n.get("url") else (
                    f'<span style="color:#14171a;font-size:15px;font-weight:600;'
                    f'line-height:1.5">{n["titulo"]}</span>'
                )

                fuente_tag = (
                    f'<span style="font-size:10px;font-weight:700;color:{color};'
                    f'font-family:sans-serif;letter-spacing:.6px;text-transform:uppercase">'
                    f'{fuente["nombre"]}</span>'
                )

                card_html = f"""
                <div style="border:1px solid #dde1ea;border-left:3px solid {border_color};
                     border-radius:8px;overflow:hidden;margin-bottom:4px;{bg_excl}
                     box-shadow:0 1px 4px rgba(0,0,0,.07)">
                  {img_html}
                  <div style="padding:10px 12px 12px">
                    {fuente_tag}
                    <div style="margin-top:5px">{titulo_link}</div>
                  </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
                # Botón agregar a canasta (debajo de cada card)
                en_canasta = any(
                    item["noticia"]["titulo"] == n["titulo"]
                    for item in st.session_state.canasta
                )
                btn_label = "✅ En canasta" if en_canasta else "🧺 Agregar a canasta"
                if st.button(
                    btn_label,
                    key=f"canasta_{fuente['id']}_{hash(n['titulo'])}",
                    use_container_width=True,
                    disabled=en_canasta,
                ):
                    _canasta_agregar(n["titulo"], n.get("url"), fuente)
                    st.rerun()

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📡 Monitor Deportivo Pro")
    st.markdown(f"**{len(TODAS_FUENTES)} medios** · {len(FUENTES_NAC)} nac + {len(FUENTES_INT)} int")
    st.divider()

    try:
        _default_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        _default_key = ""
    api_key = st.text_input(
        "🔑 Anthropic API Key",
        type="password",
        value=_default_key,
        placeholder="sk-ant-api03-...",
        help="Se puede dejar en Secrets de Streamlit (ANTHROPIC_API_KEY). Los feeds cargan sin key.",
    )

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        solo_nac = st.checkbox("Solo nacionales", value=False)
    with col_b:
        solo_int = st.checkbox("Solo int.", value=False)

    if st.button("↺ Actualizar fuentes", type="primary", use_container_width=True):
        fuentes_a_cargar = TODAS_FUENTES
        if solo_nac:
            fuentes_a_cargar = FUENTES_NAC
        elif solo_int:
            fuentes_a_cargar = FUENTES_INT

        progress = st.progress(0, text="Cargando medios...")
        resultados_nuevos = {}
        errores = []
        total = len(fuentes_a_cargar)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_fuente, f): f for f in fuentes_a_cargar}
            done = 0
            for future in as_completed(futures):
                res = future.result()
                resultados_nuevos[res["id"]] = res["noticias"]
                if res["error"]:
                    errores.append(f"{res['id']}: {res['error']}")
                done += 1
                progress.progress(done / total, text=f"Cargando... {done}/{total}")

        st.session_state.resultados = resultados_nuevos
        st.session_state.ultima_act = datetime.now()
        st.session_state.ole_analisis = analizar_ole_vs_compecencia_safe(resultados_nuevos)
        st.session_state.prev_tendencias = st.session_state.get("tendencias", []) or []
        st.session_state.tendencias = calcular_tendencias(resultados_nuevos)
        progress.empty()

        total_noticias = sum(len(v) for v in resultados_nuevos.values())
        st.success(f"✔ {total_noticias} noticias de {total} medios")
        if errores:
            with st.expander(f"⚠ {len(errores)} errores"):
                st.text("\n".join(errores))
        st.rerun()

    if st.session_state.ultima_act:
        st.caption(f"Última actualización: {st.session_state.ultima_act.strftime('%H:%M:%S')}")
        total_noticias = sum(len(v) for v in st.session_state.resultados.values())
        st.metric("Total de noticias", total_noticias)

    st.divider()
    # ── CANASTA ──────────────────────────────────────────────────────────────
    cant_canasta = len(st.session_state.canasta)
    st.markdown(f"**🧺 Canasta** — {cant_canasta} nota(s)")
    if cant_canasta > 0:
        col_ca, col_cb = st.columns(2)
        with col_ca:
            if st.button("🗑 Vaciar", use_container_width=True, key="sidebar_vaciar_canasta"):
                st.session_state.canasta = []
                st.rerun()
        with col_cb:
            texto_canasta = "\n\n".join(
                f"[{item['fuente']['nombre']}] {item['noticia']['titulo']}\n{item['noticia'].get('url','')}"
                for item in st.session_state.canasta
            )
            st.download_button(
                "📥 Exportar",
                texto_canasta,
                file_name=f"canasta_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain",
                use_container_width=True,
                key="sidebar_exportar_canasta",
            )

    st.divider()
    st.markdown("**IA con Claude**")

    if st.button("✦ Análisis General", use_container_width=True):
        if not api_key:
            st.error("Ingresá tu API key")
        elif not st.session_state.resultados:
            st.error("Actualizá las fuentes primero")
        else:
            with st.spinner("Analizando con Claude..."):
                try:
                    prompt = prompt_analisis_general(st.session_state.resultados)
                    st.session_state.analisis_general = call_claude(prompt, api_key, 1800)
                    st.success("✔ Análisis generado")
                except Exception as e:
                    st.error(f"Error: {e}")

    if st.button("🟢 Informe Olé IA", use_container_width=True):
        if not api_key:
            st.error("Ingresá tu API key")
        elif not st.session_state.resultados:
            st.error("Actualizá las fuentes primero")
        else:
            analisis = st.session_state.ole_analisis or analizar_ole_vs_compecencia_safe(st.session_state.resultados)
            with st.spinner("Generando informe Olé..."):
                try:
                    prompt = prompt_informe_ole(st.session_state.resultados, analisis)
                    st.session_state.informe_ole = call_claude(prompt, api_key, 2400)
                    st.success("✔ Informe generado")
                except Exception as e:
                    st.error(f"Error: {e}")





# ─── MAIN ─────────────────────────────────────────────────────────────────────
st.title("📡 Monitor Deportivo Pro")

if not st.session_state.resultados:
    st.info("👈 Hacé clic en **↺ Actualizar fuentes** en el panel izquierdo para comenzar.")
    st.stop()

resultados = st.session_state.resultados
ole_analisis = st.session_state.ole_analisis
tendencias = st.session_state.tendencias

# ─── TABS PRINCIPALES ────────────────────────────────────────────────────────
tab_agenda, tab_nac, tab_int, tab_ole, tab_tend, tab_ia, tab_nota, tab_sent, tab_canasta = st.tabs([
    "🎯 Agenda",
    f"🇦🇷 Nacionales ({sum(len(resultados.get(f['id'],[])) for f in FUENTES_NAC)})",
    f"🌍 Internacionales ({sum(len(resultados.get(f['id'],[])) for f in FUENTES_INT)})",
    "⭐ Olé vs Todos",
    f"📊 Tendencias ({len(tendencias)})",
    "🤖 Análisis IA",
    "✍️ Nota Rápida",
    "🌡️ Tono Editorial",
    f"🧺 Canasta ({len(st.session_state.canasta)})",
])

# ─── TAB AGENDA ──────────────────────────────────────────────────────────────
with tab_agenda:
    st.subheader("🎯 Qué se puede hacer ahora")
    agenda = construir_agenda(tendencias, ole_analisis, st.session_state.get("prev_tendencias"))

    hay_prev = bool(st.session_state.get("prev_tendencias"))
    if not hay_prev:
        st.caption("Momentum disponible desde el segundo refresco (compara contra el anterior).")

    if not agenda:
        st.info("No hay acciones destacadas todavía. Actualizá las fuentes un par de veces.")
    else:
        col_h1, col_h2 = st.columns([3, 1])
        with col_h1:
            st.caption(f"{len(agenda)} acciones priorizadas · rojo = urgente · verde = tu ventaja")
        with col_h2:
            if st.button("✦ Parte editorial (IA)", use_container_width=True):
                if not api_key:
                    st.error("Ingresá tu API key en el panel izquierdo")
                else:
                    with st.spinner("Redactando el parte con Claude..."):
                        try:
                            st.session_state.agenda_parte = call_claude(
                                prompt_parte_editorial(agenda), api_key, 1200
                            )
                        except Exception as e:
                            st.error(f"Error: {e}")

        if st.session_state.get("agenda_parte"):
            with st.expander("📝 Parte editorial (IA)", expanded=True):
                st.markdown(st.session_state.agenda_parte)

        for it in agenda:
            color = AGENDA_COLORES.get(it["accion"], "#555")
            if it["nuevo"]:
                mom = "🆕 nuevo"
            elif it["delta"] > 0:
                mom = f"▲ +{it['delta']} medios"
            elif it["delta"] < 0:
                mom = f"▼ {it['delta']} medios"
            else:
                mom = "= estable"
            titulo_html = (
                f'<a href="{it["url"]}" target="_blank" rel="noopener" '
                f'style="color:#14171a;text-decoration:none;font-weight:600">{it["titulo"]}</a>'
                if it.get("url") else
                f'<span style="color:#14171a;font-weight:600">{it["titulo"]}</span>'
            )
            st.markdown(f"""
            <div style="border:1px solid #dde1ea;border-left:5px solid {color};
                 border-radius:8px;padding:10px 14px;margin-bottom:6px;
                 box-shadow:0 1px 4px rgba(0,0,0,.06)">
              <span style="background:{color};color:#fff;font-size:11px;font-weight:800;
                    padding:2px 8px;border-radius:4px;letter-spacing:.5px">{it["accion"]}</span>
              <span style="font-size:12px;color:#657786;margin-left:8px">{it["motivo"]}</span>
              <div style="margin-top:6px;font-size:15px">{titulo_html}</div>
              <div style="margin-top:4px;font-size:12px;color:#657786">
                {it["cant_medios"]} medios · {it["nac"]} nac / {it["intl"]} int · {mom}
              </div>
            </div>
            """, unsafe_allow_html=True)

            brief_key = str(hash(it["titulo"]))
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("✦ Brief IA", key=f"agenda_brief_{it['accion']}_{brief_key}",
                             use_container_width=True):
                    if not api_key:
                        st.error("Ingresá tu API key")
                    else:
                        with st.spinner("Pensando el ángulo..."):
                            try:
                                st.session_state.agenda_briefs[brief_key] = call_claude(
                                    prompt_brief_item(it), api_key, 400
                                )
                            except Exception as e:
                                st.error(f"Error: {e}")
            with col_b2:
                en_canasta = any(
                    item["noticia"]["titulo"] == it["titulo"] for item in st.session_state.canasta
                )
                if st.button(
                    "✅ En canasta" if en_canasta else "🧺 A canasta",
                    key=f"agenda_canasta_{it['accion']}_{brief_key}",
                    use_container_width=True, disabled=en_canasta,
                ):
                    fuente_rep = (it["noticias"][0]["fuente"]
                                  if it.get("noticias") else
                                  {"id": "agenda", "nombre": "Agenda", "color": color})
                    _canasta_agregar(it["titulo"], it.get("url"), fuente_rep)
                    st.rerun()

            if st.session_state.agenda_briefs.get(brief_key):
                st.info(st.session_state.agenda_briefs[brief_key])

# ─── TAB NACIONALES ──────────────────────────────────────────────────────────
with tab_nac:
    fuente_sel = st.selectbox(
        "Medio",
        [f["nombre"] for f in FUENTES_NAC],
        key="sel_nac",
    )
    fuente_obj = next(f for f in FUENTES_NAC if f["nombre"] == fuente_sel)
    noticias = resultados.get(fuente_obj["id"], [])

    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown(
            f'<span style="color:{fuente_obj["color"]};font-weight:700;font-size:18px">'
            f'{fuente_obj["nombre"]}</span> — {len(noticias)} noticias',
            unsafe_allow_html=True,
        )
    with col_h2:
        cols_per_row = st.selectbox("Columnas", [2, 3, 4], index=1, key="cols_nac")

    filtro = st.text_input("🔍 Filtrar por palabra", key="filtro_nac")
    lista = [n for n in noticias if filtro.lower() in n["titulo"].lower()] if filtro else noticias

    render_news_cards(lista, fuente_obj, resultados, cols_per_row=cols_per_row)

# ─── TAB INTERNACIONALES ─────────────────────────────────────────────────────
with tab_int:
    fuente_sel_i = st.selectbox(
        "Medio",
        [f["nombre"] for f in FUENTES_INT],
        key="sel_int",
    )
    fuente_obj_i = next(f for f in FUENTES_INT if f["nombre"] == fuente_sel_i)
    noticias_i = resultados.get(fuente_obj_i["id"], [])

    col_h1i, col_h2i = st.columns([3, 1])
    with col_h1i:
        st.markdown(
            f'<span style="color:{fuente_obj_i["color"]};font-weight:700;font-size:18px">'
            f'{fuente_obj_i["nombre"]}</span> — {len(noticias_i)} noticias',
            unsafe_allow_html=True,
        )
    with col_h2i:
        cols_per_row_i = st.selectbox("Columnas", [2, 3, 4], index=1, key="cols_int")

    filtro_i = st.text_input("🔍 Filtrar por palabra", key="filtro_int")
    lista_i = [n for n in noticias_i if filtro_i.lower() in n["titulo"].lower()] if filtro_i else noticias_i

    render_news_cards(lista_i, fuente_obj_i, resultados, cols_per_row=cols_per_row_i)

# ─── TAB OLÉ VS TODOS ────────────────────────────────────────────────────────
with tab_ole:
    if not ole_analisis:
        st.info("Actualizá las fuentes para ver el análisis semántico.")
    else:
        excl = ole_analisis["exclusivos_ole"]
        falt = ole_analisis["faltantes_en_ole"]
        comp = ole_analisis["cubiertos_por_ambos"]

        c1, c2, c3 = st.columns(3)
        c1.metric("⭐ Exclusivos Olé", len(excl), help="Temas que solo cubre Olé")
        c2.metric("❌ Ausentes en Olé", len(falt), help="Temas que tiene la competencia y Olé NO cubre")
        c3.metric("🔄 Temas compartidos", len(comp), help="Cubiertos por ambos, posible ángulo diferente")

        st.divider()

        sub1, sub2, sub3 = st.tabs([
            f"⭐ Exclusivos Olé ({len(excl)})",
            f"❌ Faltantes ({len(falt)})",
            f"🔄 Compartidos ({len(comp)})",
        ])

        with sub1:
            if not excl:
                st.info("No se detectaron exclusivos.")
            for n in excl:
                if n.get("url"):
                    st.markdown(f"⭐ [{n['titulo']}]({n['url']})")
                else:
                    st.markdown(f"⭐ {n['titulo']}")

        with sub2:
            if not falt:
                st.success("✔ Olé cubre todos los temas detectados.")
            else:
                for f_item in falt:
                    col_hex = f_item["fuente_color"]
                    badge_html = (
                        f'<span style="background:{col_hex}22;color:{col_hex};border:1px solid {col_hex}55;'
                        f'padding:1px 8px;border-radius:4px;font-size:11px;font-weight:700">'
                        f'{f_item["fuente_nombre"]}</span>'
                    )
                    if f_item.get("url"):
                        st.markdown(
                            f'{badge_html} [{f_item["titulo"]}]({f_item["url"]})',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f'{badge_html} {f_item["titulo"]}',
                            unsafe_allow_html=True,
                        )

        with sub3:
            if not comp:
                st.info("Sin temas compartidos detectados.")
            for item in comp[:30]:
                nol = item["noticia_ole"]
                with st.expander(f"🔄 {nol['titulo'][:90]}..."):
                    if nol.get("url"):
                        st.markdown(f"**Olé:** [{nol['titulo']}]({nol['url']})")
                    else:
                        st.markdown(f"**Olé:** {nol['titulo']}")
                    for ci in item["competencia"]:
                        fobj = next((f for f in TODAS_FUENTES if f["id"] == ci["fuente_id"]), None)
                        nombre = fobj["nombre"] if fobj else ci["fuente_id"]
                        color = fobj["color"] if fobj else "#666"
                        badge = (
                            f'<span style="color:{color};font-weight:700;font-size:11px">{nombre}</span>'
                        )
                        if ci["noticia"].get("url"):
                            st.markdown(
                                f'{badge} [{ci["noticia"]["titulo"]}]({ci["noticia"]["url"]})',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(f'{badge} {ci["noticia"]["titulo"]}', unsafe_allow_html=True)

# ─── TAB TENDENCIAS ──────────────────────────────────────────────────────────
with tab_tend:
    if not tendencias:
        st.info("Actualizá las fuentes para ver las tendencias.")
    else:
        total_fuentes = len(TODAS_FUENTES)
        sin_ole = [t for t in tendencias if not t["tiene_ole"]]
        con_ole = [t for t in tendencias if t["tiene_ole"]]
        hot     = [t for t in tendencias if t["cant_medios"] / total_fuentes >= 0.20]

        # ── Métricas ─────────────────────────────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Temas detectados", len(tendencias))
        m2.metric("❌ Sin Olé", len(sin_ole))
        m3.metric("✅ Con Olé", len(con_ole))
        m4.metric("🔥 Trending", len(hot))

        st.divider()

        # ── Helpers de frecuencia de palabras ────────────────────────────────
        EXTRA_STOP = {
            "partido","partidos","juego","juegos","dice","dijo","señalo",
            "aseguro","confirmo","revelo","anuncio","hablo","tiene","hoy",
            "ayer","manana","semana","anno","mes","vez","nuevo","nueva",
            "gran","primer","primera","sera","puede","equipo","sobre",
            "habla","luego","hace","dado","segun","after","over","into",
            "than","their","they","this","that","with","will","from",
        }

        def build_word_freq(fuente_ids: list) -> list:
            freq = {}
            for fid in fuente_ids:
                for n in (st.session_state.resultados or {}).get(fid, []):
                    for w in normalizar_titulo(n["titulo"]) - EXTRA_STOP:
                        if len(w) > 3:
                            freq[w] = freq.get(w, 0) + 1
            return sorted(freq.items(), key=lambda x: -x[1])

        def html_word_cloud(freq_list: list, color_hex: str) -> str:
            """Genera una nube de palabras como HTML puro con posicionamiento en espiral."""
            if not freq_list:
                return "<p style='color:#aaa;text-align:center;padding:40px'>Sin datos</p>"

            words = freq_list[:60]
            max_c = words[0][1]
            min_c = words[-1][1]
            rng   = max_c - min_c or 1

            # Parsear color hex → rgb
            h = color_hex.lstrip("#")
            cr, cg, cb = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)

            # Posicionamiento en espiral (coordenadas % dentro del contenedor)
            placed = []  # (cx, cy, half_w, half_h)
            items_html = []
            random.seed(42)

            for word, count in words:
                t = (count - min_c) / rng          # 0..1
                fsize = 11 + t * 26                # 11px..37px
                # Color: interpolar entre color_hex (t=1) y gris claro (t=0)
                r = int(cr + (220 - cr) * (1 - t))
                g = int(cg + (225 - cg) * (1 - t))
                b = int(cb + (230 - cb) * (1 - t))
                weight = "700" if t > 0.45 else "400"
                opacity = 0.5 + t * 0.5

                # Estimar tamaño en % (contenedor 480×260px)
                hw = len(word) * fsize * 0.30 / 4.8   # half-width %
                hh = fsize * 0.65 / 2.6               # half-height %

                ok = False
                for step in range(400):
                    angle  = step * 0.28
                    radius = step * 0.15
                    cx = 50 + radius * math.cos(angle)
                    cy = 50 + radius * math.sin(angle) * 0.55
                    if cx - hw < 1 or cx + hw > 99 or cy - hh < 2 or cy + hh > 98:
                        continue
                    pad = 1.2
                    if not any(
                        abs(cx - px) < hw + phw + pad and abs(cy - py) < hh + phh + pad
                        for px, py, phw, phh in placed
                    ):
                        placed.append((cx, cy, hw, hh))
                        items_html.append(
                            f'<span style="position:absolute;left:{cx:.1f}%;top:{cy:.1f}%;'
                            f'transform:translate(-50%,-50%);font-size:{fsize:.1f}px;'
                            f'font-weight:{weight};color:rgb({r},{g},{b});'
                            f'opacity:{opacity:.2f};white-space:nowrap;'
                            f'font-family:Barlow,sans-serif;line-height:1;'
                            f'cursor:default" title="{count} menciones">{word}</span>'
                        )
                        ok = True
                        break

            return (
                '<div style="position:relative;width:100%;height:260px;'
                'background:#f8fafc;border-radius:10px;overflow:hidden;'
                'border:1px solid #e2e8f0">'
                + "".join(items_html)
                + "</div>"
            )

        # ── Layout: ranking | nubes ───────────────────────────────────────────
        # ── NUBE DE PALABRAS (ancho completo, arriba) ─────────────────────────
        st.markdown("#### 🔤 Nube de palabras")
        nac_ids  = [f["id"] for f in FUENTES_NAC]
        intl_ids = [f["id"] for f in FUENTES_INT]
        ct1, ct2 = st.tabs(["🇦🇷 Nacionales", "🌍 Internacionales"])

        def _cloud_section(fuente_ids, color_hex):
            freq = build_word_freq(fuente_ids)
            cloud_html = html_word_cloud(freq, color_hex).replace("height:260px", "height:320px")
            st.markdown(cloud_html, unsafe_allow_html=True)
            if freq:
                top = " &nbsp;·&nbsp; ".join(
                    f'<b>{w}</b> <span style="color:#94a3b8;font-size:11px">×{c}</span>'
                    for w, c in freq[:14]
                )
                st.markdown(
                    f'<div style="margin-top:8px;font-size:12px;line-height:2;color:#374151">{top}</div>',
                    unsafe_allow_html=True,
                )

        with ct1:
            _cloud_section(nac_ids, "#00a846")
        with ct2:
            _cloud_section(intl_ids, "#1a7fc1")

        st.divider()

        # ── RANKING DE TEMAS (ancho completo, abajo) ─────────────────────────
        st.markdown("#### 📊 Ranking de temas")
        filtro = st.radio(
            "Filtrar por",
            ["Sin Olé ❌", "Con Olé ✅", "🔥 Hot", "Todos"],
            horizontal=True, key="filtro_tend",
        )
        lista = tendencias[:80]
        if filtro == "Sin Olé ❌":   lista = [t for t in lista if not t["tiene_ole"]]
        elif filtro == "Con Olé ✅": lista = [t for t in lista if t["tiene_ole"]]
        elif filtro == "🔥 Hot":     lista = [t for t in lista if t["cant_medios"] / total_fuentes >= 0.20]

        st.caption(f"{len(lista)} temas · similitud Jaccard ≥ {SIMILITUD_UMBRAL}")

        for t in lista[:50]:
            pct = t["cant_medios"] / total_fuentes
            bar_pct = int(pct * 100)
            if pct >= 0.5:    accent, emoji = "#dc2626", "🔥🔥"
            elif pct >= 0.30: accent, emoji = "#ea580c", "🔥"
            elif pct >= 0.15: accent, emoji = "#ca8a04", "▲"
            else:             accent, emoji = "#3b82f6", "·"

            ole_dot = "🟢" if t["tiene_ole"] else "🔴"

            chips = "".join(
                f'<span style="font-size:9px;font-weight:700;padding:1px 5px;'
                f'border-radius:3px;background:{item["fuente"]["color"]}18;'
                f'color:{item["fuente"]["color"]};border:1px solid {item["fuente"]["color"]}30">'
                f'{item["fuente"]["nombre"]}</span> '
                for item in t["noticias"]
            )

            st.markdown(
                f"""<div style="margin-bottom:7px;padding:9px 12px;border-radius:8px;
                    border-left:4px solid {accent};background:#fafafa;
                    border:1px solid #eee;border-left:4px solid {accent}">
                  <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                    <span style="font-size:11px;font-weight:700;color:{accent}">{emoji} {t['cant_medios']} medios</span>
                    <span>{ole_dot}</span>
                    <span style="font-size:10px;color:#94a3b8">{t['nac']}🇦🇷 {t['intl']}🌍</span>
                    <div style="flex:1;height:5px;background:#e2e8f0;border-radius:3px;overflow:hidden">
                      <div style="width:{bar_pct}%;height:100%;background:{accent}"></div>
                    </div>
                    <span style="font-size:10px;color:#94a3b8">{bar_pct}%</span>
                  </div>
                  <div style="font-size:15px;font-weight:600;color:#0f172a;
                      line-height:1.4;margin-bottom:5px">{t['titulo'][:130]}</div>
                  <div style="display:flex;flex-wrap:wrap;gap:2px">{chips}</div>
                </div>""",
                unsafe_allow_html=True,
            )

            # ── Botones de acción por card ────────────────────────────────────
            t_idx = lista.index(t)
            btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 4])
            with btn_col1:
                ver_notas = st.button("▸ Ver notas", key=f"vernotas_{t_idx}", use_container_width=True)
            with btn_col2:
                analizar_tono = st.button("🌡️ Tono", key=f"tono_{t_idx}", use_container_width=True)

            if ver_notas:
                st.session_state[f"open_notas_{t_idx}"] = not st.session_state.get(f"open_notas_{t_idx}", False)
            if analizar_tono:
                st.session_state[f"open_tono_{t_idx}"] = not st.session_state.get(f"open_tono_{t_idx}", False)
                if st.session_state[f"open_tono_{t_idx}"]:
                    st.session_state[f"tono_resultado_{t_idx}"] = None  # reset para nueva búsqueda

            if st.session_state.get(f"open_notas_{t_idx}", False):
                with st.container():
                    for item in t["noticias"]:
                        n, f = item["noticia"], item["fuente"]
                        badge = (f'<span style="color:{f["color"]};font-size:10px;font-weight:700;'
                                 f'background:{f["color"]}18;padding:1px 6px;border-radius:3px">'
                                 f'{f["nombre"]}</span>')
                        if n.get("url"):
                            st.markdown(f'{badge} [{n["titulo"]}]({n["url"]})', unsafe_allow_html=True)
                        else:
                            st.markdown(f'{badge} {n["titulo"]}', unsafe_allow_html=True)

            if st.session_state.get(f"open_tono_{t_idx}", False):
                tono_key = f"tono_resultado_{t_idx}"
                if st.session_state.get(tono_key) is None:
                    if not api_key:
                        st.warning("Ingresá tu API key en el panel izquierdo para analizar el tono.")
                    else:
                        with st.spinner("Analizando tono editorial..."):
                            try:
                                prompt = prompt_tono_editorial(t["titulo"], t["noticias"][:40])
                                raw_json = call_claude(prompt, api_key, 1200)
                                clean = raw_json.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                                st.session_state[tono_key] = json.loads(clean)
                            except Exception as e:
                                st.session_state[tono_key] = {"error": str(e)}

                res = st.session_state.get(tono_key)
                if res and "error" not in res:
                    TONO_CFG = {
                        "positivo":  ("🟢", "#16a34a", "#f0fdf4"),
                        "negativo":  ("🔴", "#dc2626", "#fef2f2"),
                        "neutro":    ("⚪", "#6b7280", "#f9fafb"),
                        "alarmista": ("🟡", "#d97706", "#fffbeb"),
                        "expectante":("🔵", "#2563eb", "#eff6ff"),
                    }
                    with st.container():
                        st.markdown(
                            f'<div style="padding:10px 14px;border-radius:8px;background:#f0f9ff;'
                            f'border-left:4px solid #0ea5e9;font-size:14px;margin:6px 0">'
                            f'📝 {res.get("resumen","")}</div>',
                            unsafe_allow_html=True,
                        )
                        dist = res.get("distribucion", {})
                        total_cl = sum(dist.values()) or 1
                        dcols = st.columns(5)
                        for i, (tono, count) in enumerate(dist.items()):
                            em, col, bg = TONO_CFG.get(tono, ("⚫","#374151","#f9fafb"))
                            pct = int(count / total_cl * 100)
                            with dcols[i]:
                                st.markdown(
                                    f'<div style="text-align:center;padding:8px 4px;border-radius:7px;'
                                    f'background:{bg};border:1px solid {col}30">'
                                    f'<div style="font-size:18px">{em}</div>'
                                    f'<div style="font-size:17px;font-weight:700;color:{col}">{count}</div>'
                                    f'<div style="font-size:10px;color:#6b7280;text-transform:capitalize">{tono}</div>'
                                    f'<div style="font-size:9px;color:#9ca3af">{pct}%</div>'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )
                        for item in res.get("por_medio", []):
                            tono = item.get("tono", "neutro")
                            em, col, bg = TONO_CFG.get(tono, ("⚫","#374151","#f9fafb"))
                            st.markdown(
                                f'<div style="display:flex;gap:8px;align-items:flex-start;'
                                f'padding:7px 10px;margin-top:4px;border-radius:6px;'
                                f'background:{bg};border:1px solid {col}20">'
                                f'<span style="font-size:16px;flex-shrink:0">{em}</span>'
                                f'<div><span style="font-size:10px;font-weight:700;color:{col};text-transform:uppercase">'
                                f'{item.get("medio","")} · {tono}</span><br>'
                                f'<span style="font-size:12px;color:#1e293b">{item.get("titular","")}</span><br>'
                                f'<span style="font-size:11px;color:#64748b;font-style:italic">{item.get("razon","")}</span>'
                                f'</div></div>',
                                unsafe_allow_html=True,
                            )
                elif res and "error" in res:
                    st.error(f"Error al analizar: {res['error']}")

# ─── TAB IA ──────────────────────────────────────────────────────────────────
with tab_ia:
    ia1, ia2, ia3 = st.tabs(["✦ Análisis General", "🟢 Informe Olé", "📋 Exclusivos (todos)"])

    with ia1:
        if st.session_state.analisis_general:
            st.text_area(
                "Análisis General",
                st.session_state.analisis_general,
                height=500,
                label_visibility="collapsed",
            )
            st.download_button(
                "📥 Descargar análisis",
                st.session_state.analisis_general,
                file_name="analisis_general.txt",
                mime="text/plain",
            )
        else:
            st.info("Hacé clic en **✦ Análisis General** en el panel izquierdo (requiere API key).")

    with ia2:
        if st.session_state.informe_ole:
            st.text_area(
                "Informe Olé",
                st.session_state.informe_ole,
                height=500,
                label_visibility="collapsed",
            )
            st.download_button(
                "📥 Descargar informe",
                st.session_state.informe_ole,
                file_name="informe_ole.txt",
                mime="text/plain",
            )
        else:
            st.info("Hacé clic en **🟢 Informe Olé IA** en el panel izquierdo (requiere API key).")

    with ia3:
        st.markdown(f"**Titulares únicos por tema** — similitud Jaccard < {SIMILITUD_UMBRAL}")
        exclusivos_todos = []
        for f in TODAS_FUENTES:
            for n in resultados.get(f["id"], []):
                if es_exclusivo(n["titulo"], f["id"], resultados):
                    exclusivos_todos.append({"fuente": f, "noticia": n})

        if not exclusivos_todos:
            st.info("No se detectaron exclusivos.")
        else:
            st.caption(f"{len(exclusivos_todos)} exclusivos detectados")
            for item in exclusivos_todos[:100]:
                f = item["fuente"]
                n = item["noticia"]
                badge = (
                    f'<span style="color:{f["color"]};font-weight:700;font-size:11px;'
                    f'background:{f["color"]}15;padding:1px 8px;border-radius:4px">'
                    f'{f["nombre"]}</span>'
                )
                if n.get("url"):
                    st.markdown(f'{badge} [{n["titulo"]}]({n["url"]})', unsafe_allow_html=True)
                else:
                    st.markdown(f'{badge} {n["titulo"]}', unsafe_allow_html=True)

# ─── TAB NOTA RÁPIDA ─────────────────────────────────────────────────────────
with tab_nota:
    st.markdown("### ✍️ Asistente de Nota Rápida")
    st.caption("Buscá un tema, elegí las notas que querés usar y generá el borrador con IA.")

    # ── PASO 1: Fuente del tema ───────────────────────────────────────────────
    st.markdown("#### 1️⃣ ¿De dónde tomamos las notas?")
    modo_tema = st.radio(
        "",
        ["📊 Desde el ranking de tendencias", "🔍 Buscar en los medios cargados", "✏️ Escribir tema libre"],
        horizontal=True,
        key="nota_modo_tema",
        label_visibility="collapsed",
    )

    titulares_seleccionados = []
    tema_elegido = ""

    # ── Modo 1: Desde el ranking de tendencias ──────────────────────────────
    if modo_tema == "📊 Desde el ranking de tendencias":
        if not tendencias:
            st.warning("Primero actualizá las fuentes para cargar tendencias.")
        else:
            opciones_temas = [
                f"[{t['cant_medios']} medios] {t['titulo'][:90]}"
                for t in tendencias[:40]
            ]
            tema_idx = st.selectbox(
                "Tema del ranking",
                range(len(opciones_temas)),
                format_func=lambda i: opciones_temas[i],
                key="nota_tema_idx",
            )
            tema_elegido = tendencias[tema_idx]["titulo"]
            titulares_pool = tendencias[tema_idx]["noticias"]

            st.caption(f"**{len(titulares_pool)}** notas en este tema — marcá las que querés usar:")
            sel_key_t = f"nota_sel_tend_{tema_idx}"
            if sel_key_t not in st.session_state:
                st.session_state[sel_key_t] = set(range(len(titulares_pool)))  # todas por defecto

            col_ta, col_tb = st.columns([1, 5])
            with col_ta:
                if st.button("☑ Todas", key="nota_tend_all", use_container_width=True):
                    st.session_state[sel_key_t] = set(range(len(titulares_pool)))
                    st.rerun()
            with col_tb:
                if st.button("☐ Ninguna", key="nota_tend_none", use_container_width=True):
                    st.session_state[sel_key_t] = set()
                    st.rerun()

            for idx, item in enumerate(titulares_pool):
                f = item["fuente"]
                n = item["noticia"]
                checked = idx in st.session_state[sel_key_t]
                badge_html = (
                    f'<span style="font-size:10px;font-weight:700;padding:1px 6px;'
                    f'border-radius:3px;background:{f["color"]}18;color:{f["color"]};'
                    f'border:1px solid {f["color"]}30">{f["nombre"]}</span>'
                )
                col_ck, col_txt = st.columns([1, 11])
                with col_ck:
                    nuevo = st.checkbox("", value=checked, key=f"nota_tend_ck_{tema_idx}_{idx}")
                    if nuevo and idx not in st.session_state[sel_key_t]:
                        st.session_state[sel_key_t].add(idx)
                    elif not nuevo and idx in st.session_state[sel_key_t]:
                        st.session_state[sel_key_t].discard(idx)
                with col_txt:
                    titulo_display = f"[{n['titulo']}]({n['url']})" if n.get("url") else n["titulo"]
                    st.markdown(f'{badge_html} {titulo_display}', unsafe_allow_html=True)

            titulares_seleccionados = [titulares_pool[i] for i in sorted(st.session_state.get(sel_key_t, set())) if i < len(titulares_pool)]
            if titulares_seleccionados:
                col_ok, col_basket = st.columns([3, 2])
                with col_ok:
                    st.success(f"✔ {len(titulares_seleccionados)} nota(s) seleccionada(s)")
                with col_basket:
                    if st.button("🧺 Agregar seleccionadas a canasta", key="nota_tend_a_canasta", use_container_width=True):
                        for item in titulares_seleccionados:
                            _canasta_agregar(item["noticia"]["titulo"], item["noticia"].get("url"), item["fuente"])
                        st.success(f"✔ {len(titulares_seleccionados)} nota(s) enviadas a la canasta")
                        st.rerun()

    # ── Modo 2: Búsqueda por palabra clave ───────────────────────────────────
    elif modo_tema == "🔍 Buscar en los medios cargados":
        col_bq1, col_bq2 = st.columns([3, 1])
        with col_bq1:
            busqueda = st.text_input(
                "Palabra o nombre a buscar",
                placeholder="Ej: Messi, Boca, lesión, Scaloni...",
                key="nota_busqueda",
            )
        with col_bq2:
            fuente_busq = st.selectbox(
                "Fuentes",
                ["Todas", "Solo nacionales", "Solo internacionales"],
                key="nota_busq_fuentes",
            )

        resultados_busq = []
        if busqueda.strip():
            q = busqueda.strip().lower()
            pool = TODAS_FUENTES
            if fuente_busq == "Solo nacionales":   pool = FUENTES_NAC
            elif fuente_busq == "Solo internacionales": pool = FUENTES_INT
            for f in pool:
                for n in resultados.get(f["id"], []):
                    if q in n["titulo"].lower():
                        resultados_busq.append({"fuente": f, "noticia": n})

        if resultados_busq:
            tema_elegido = busqueda.strip()
            st.caption(f"**{len(resultados_busq)}** notas encontradas — marcá las que querés usar:")

            # Inicializar selección en session state
            sel_key = f"nota_sel_{busqueda}"
            if sel_key not in st.session_state:
                st.session_state[sel_key] = set()

            col_sa, col_sb = st.columns([1, 5])
            with col_sa:
                if st.button("☑ Todas", key="nota_sel_all", use_container_width=True):
                    st.session_state[sel_key] = set(range(len(resultados_busq)))
                    st.rerun()
            with col_sb:
                if st.button("☐ Ninguna", key="nota_sel_none", use_container_width=True):
                    st.session_state[sel_key] = set()
                    st.rerun()

            for idx, item in enumerate(resultados_busq[:50]):
                f = item["fuente"]
                n = item["noticia"]
                checked = idx in st.session_state[sel_key]
                badge_html = (
                    f'<span style="font-size:10px;font-weight:700;padding:1px 6px;'
                    f'border-radius:3px;background:{f["color"]}18;color:{f["color"]};'
                    f'border:1px solid {f["color"]}30">{f["nombre"]}</span>'
                )
                col_ck, col_txt = st.columns([1, 11])
                with col_ck:
                    nuevo = st.checkbox("", value=checked, key=f"nota_ck_{busqueda}_{idx}")
                    if nuevo and idx not in st.session_state[sel_key]:
                        st.session_state[sel_key].add(idx)
                    elif not nuevo and idx in st.session_state[sel_key]:
                        st.session_state[sel_key].discard(idx)
                with col_txt:
                    titulo_display = f"[{n['titulo']}]({n['url']})" if n.get("url") else n["titulo"]
                    st.markdown(f'{badge_html} {titulo_display}', unsafe_allow_html=True)

            seleccionados_idx = st.session_state.get(sel_key, set())
            titulares_seleccionados = [resultados_busq[i] for i in sorted(seleccionados_idx) if i < len(resultados_busq)]
            if titulares_seleccionados:
                col_ok2, col_basket2 = st.columns([3, 2])
                with col_ok2:
                    st.success(f"✔ {len(titulares_seleccionados)} nota(s) seleccionada(s) para generar")
                with col_basket2:
                    if st.button("🧺 Agregar seleccionadas a canasta", key="nota_busq_a_canasta", use_container_width=True):
                        for item in titulares_seleccionados:
                            _canasta_agregar(item["noticia"]["titulo"], item["noticia"].get("url"), item["fuente"])
                        st.success(f"✔ {len(titulares_seleccionados)} nota(s) enviadas a la canasta")
                        st.rerun()
            else:
                st.info("Marcá al menos una nota para continuar.")

        elif busqueda.strip():
            st.warning(f'No se encontraron notas que mencionen "{busqueda}". Probá con otro término.')

    # ── Modo 3: Tema libre ────────────────────────────────────────────────────
    else:
        tema_elegido = st.text_input(
            "Escribí el tema de la nota",
            placeholder="Ej: Lesión de Lautaro Martínez antes de la Copa América",
            key="nota_tema_libre",
        )
        titulares_libres = st.text_area(
            "Pegá titulares de referencia (uno por línea, opcional)",
            placeholder="Lautaro Martínez se lesionó en el entrenamiento\nEl Toro en duda para el próximo partido...",
            height=100,
            key="nota_titulares_libres",
        )
        if titulares_libres.strip():
            fuente_generica = {"nombre": "Referencia", "color": "#666666", "id": "manual"}
            titulares_seleccionados = [
                {"fuente": fuente_generica, "noticia": {"titulo": t.strip(), "url": None}}
                for t in titulares_libres.strip().split("\n") if t.strip()
            ]

    st.divider()

    # ── PASO 2: Opciones + Contexto ───────────────────────────────────────────
    st.markdown("#### 2️⃣ Opciones de redacción")
    col_nota2a, col_nota2b = st.columns([1, 1])
    with col_nota2a:
        estilo_nota = st.selectbox(
            "Estilo",
            ["Informativa", "Analítica", "Urgente/Flash"],
            key="nota_estilo",
        )
        tipo_nota = st.selectbox(
            "Entregable",
            ["Nota completa", "Solo titulares alternativos", "Esqueleto + ángulos"],
            key="nota_tipo",
        )
    with col_nota2b:
        contexto_extra = st.text_area(
            "Contexto adicional (opcional)",
            placeholder=(
                "Agregá datos propios, información de fondo, declaraciones que tengas, "
                "el ángulo que querés tomar, o cualquier detalle extra que el redactor manejó y no está en las notas..."
            ),
            height=120,
            key="nota_contexto",
        )

    st.divider()

    # ── PASO 3: Generar ───────────────────────────────────────────────────────
    api_key_nota = api_key
    puede_generar = bool(titulares_seleccionados or (modo_tema == "✏️ Escribir tema libre" and tema_elegido.strip()))

    col_btn1, col_btn2, _ = st.columns([1, 1, 2])
    with col_btn1:
        generar = st.button(
            "✦ Generar con IA",
            type="primary",
            use_container_width=True,
            disabled=not puede_generar,
            key="btn_generar_nota",
        )
    with col_btn2:
        if st.button("🗑 Limpiar", use_container_width=True, key="btn_limpiar_nota"):
            st.session_state.nota_rapida = ""
            st.rerun()

    if generar:
        if not api_key_nota:
            st.error("Ingresá tu API key en el panel izquierdo para usar la IA.")
        elif not tema_elegido and not titulares_seleccionados:
            st.error("Seleccioná al menos una nota o escribí un tema.")
        else:
            if not tema_elegido and titulares_seleccionados:
                tema_elegido = titulares_seleccionados[0]["noticia"]["titulo"]

            urls_disponibles = [t for t in titulares_seleccionados if t["noticia"].get("url")]
            max_scrape = min(6, len(urls_disponibles))

            titulares_enriquecidos = titulares_seleccionados
            if urls_disponibles:
                with st.spinner(f"🔍 Leyendo el cuerpo de {max_scrape} nota(s) seleccionada(s)..."):
                    titulares_enriquecidos = scrape_cuerpos_notas(titulares_seleccionados, max_notas=max_scrape)
                ok_count = sum(1 for t in titulares_enriquecidos if t.get("ok"))
                if ok_count > 0:
                    st.success(f"✔ Cuerpo leído en {ok_count}/{max_scrape} notas")
                else:
                    st.warning("⚠️ No se pudo leer el cuerpo — modo esqueleto seguro")
            else:
                st.warning("⚠️ Las notas seleccionadas no tienen URL — modo esqueleto seguro")
                titulares_enriquecidos = [{**t, "cuerpo": "", "ok": False} for t in titulares_seleccionados]

            with st.spinner("✦ Redactando con Claude..."):
                try:
                    prompt = prompt_nota_rapida(tema_elegido, titulares_enriquecidos, estilo_nota, tipo_nota, contexto_extra.strip())
                    st.session_state.nota_rapida = call_claude(prompt, api_key_nota, 3500)
                    st.session_state.nota_rapida_titulares = titulares_enriquecidos
                    ok_final = sum(1 for t in titulares_enriquecidos if t.get("ok"))
                    st.session_state.nota_rapida_modo = "con cuerpo completo" if ok_final > 0 else "esqueleto seguro (sin cuerpo)"
                except Exception as e:
                    st.error(f"Error al llamar a Claude: {e}")

    # ── PASO 4: Resultado ─────────────────────────────────────────────────────
    if st.session_state.nota_rapida:
        modo_badge = st.session_state.get("nota_rapida_modo", "")
        raw = st.session_state.nota_rapida

        def _split_seccion(texto, encabezado):
            pattern = rf"════+\s*{re.escape(encabezado)}\s*════+\s*(.*?)(?=════|$)"
            m = re.search(pattern, texto, re.DOTALL | re.IGNORECASE)
            return m.group(1).strip() if m else ""

        seccion_nota        = _split_seccion(raw, "NOTA") or _split_seccion(raw, "ESQUELETO DE NOTA")
        seccion_verificacion = _split_seccion(raw, "TABLA DE VERIFICACIÓN") or _split_seccion(raw, "DATOS CONFIRMADOS.*")
        seccion_angulos     = _split_seccion(raw, "ÁNGULOS ALTERNATIVOS")
        sin_secciones = not (seccion_nota or seccion_verificacion)

        if "esqueleto" in modo_badge:
            st.warning("🦴 **Modo esqueleto seguro** — completá los espacios antes de publicar.")
        elif modo_badge:
            ok_n = sum(1 for t in st.session_state.nota_rapida_titulares if t.get("ok"))
            st.info(f"📰 Generado con el cuerpo real de **{ok_n}** nota(s). Revisá la Tabla de Verificación antes de publicar.")

        if sin_secciones:
            st.markdown("#### 📄 Resultado")
            nota_editada = st.text_area("", value=raw, height=560, label_visibility="collapsed", key="nota_textarea")
        else:
            tab_r1, tab_r2, tab_r3 = st.tabs(["📄 Nota / Esqueleto", "🔍 Tabla de Verificación", "💡 Ángulos Alternativos"])

            with tab_r1:
                st.caption("Editá el texto antes de copiar o descargar.")
                nota_editada = st.text_area("", value=seccion_nota, height=480, label_visibility="collapsed", key="nota_textarea")
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    st.download_button("📥 .txt", nota_editada,
                        file_name=f"nota_{datetime.now().strftime('%Y%m%d_%H%M')}.txt", mime="text/plain", use_container_width=True)
                with col_dl2:
                    st.download_button("📥 .md", nota_editada,
                        file_name=f"nota_{datetime.now().strftime('%Y%m%d_%H%M')}.md", mime="text/markdown", use_container_width=True)

            with tab_r2:
                if seccion_verificacion:
                    for linea in seccion_verificacion.split("\n"):
                        linea = linea.strip()
                        if not linea: continue
                        if "✅" in linea:   color, bg, borde = "#166534", "#f0fdf4", "#86efac"
                        elif "⚠️" in linea: color, bg, borde = "#92400e", "#fffbeb", "#fcd34d"
                        elif "❌" in linea:  color, bg, borde = "#991b1b", "#fef2f2", "#fca5a5"
                        else:               color, bg, borde = "#374151", "#f9fafb", "#e5e7eb"
                        st.markdown(
                            f'<div style="padding:7px 12px;margin-bottom:5px;border-radius:6px;'
                            f'background:{bg};border-left:3px solid {borde};color:{color};font-size:14px">{linea}</div>',
                            unsafe_allow_html=True)
                    st.download_button("📥 Tabla .txt", seccion_verificacion,
                        file_name=f"verificacion_{datetime.now().strftime('%Y%m%d_%H%M')}.txt", mime="text/plain")
                else:
                    st.info("No se generó tabla de verificación.")

            with tab_r3:
                if seccion_angulos:
                    st.markdown(seccion_angulos)
                else:
                    st.info("No se detectaron ángulos alternativos.")

        st.divider()
        st.download_button("📥 Descargar respuesta completa", raw,
            file_name=f"nota_completa_{datetime.now().strftime('%Y%m%d_%H%M')}.txt", mime="text/plain")
    else:
        st.info("El borrador aparecerá acá una vez que lo generes.")


# ─── TAB TONO EDITORIAL ─────────────────────────────────────────────────────
with tab_sent:
    st.markdown("### 🌡️ Tono Editorial")
    st.caption("Analizá cómo distintos medios cubren un tema, jugador o club con IA.")

    col_s1, col_s2 = st.columns([3, 1])
    with col_s1:
        query_sent = st.text_input(
            "Buscá un tema, jugador, club o DT",
            placeholder='Ej: Messi, Boca, River, Milito, Selección...',
            key="sent_query_input",
        )
    with col_s2:
        fuente_sent = st.selectbox(
            "Fuentes",
            ["Todas", "Solo nacionales", "Solo internacionales"],
            key="sent_fuentes",
        )

    # Filtrar titulares que mencionan la query
    titulares_sent = []
    if query_sent.strip():
        q = query_sent.strip().lower()
        fuentes_pool = TODAS_FUENTES
        if fuente_sent == "Solo nacionales":
            fuentes_pool = FUENTES_NAC
        elif fuente_sent == "Solo internacionales":
            fuentes_pool = FUENTES_INT

        for f in fuentes_pool:
            for n in resultados.get(f["id"], []):
                if q in n["titulo"].lower():
                    titulares_sent.append({"fuente": f, "noticia": n})

        if titulares_sent:
            st.caption(f"Se encontraron **{len(titulares_sent)}** titulares que mencionan *{query_sent}*")
            with st.expander(f"Ver los {len(titulares_sent)} titulares encontrados", expanded=False):
                for item in titulares_sent:
                    f = item["fuente"]
                    n = item["noticia"]
                    badge = (f'<span style="font-size:10px;font-weight:700;padding:1px 6px;'
                             f'border-radius:3px;background:{f["color"]}18;color:{f["color"]};'
                             f'border:1px solid {f["color"]}30">{f["nombre"]}</span>')
                    st.markdown(f'{badge} {n["titulo"]}', unsafe_allow_html=True)
        elif query_sent.strip():
            st.warning(f'No se encontraron titulares que mencionen "{query_sent}". Probá con otro término.')

    st.divider()

    col_sb1, col_sb2 = st.columns([1, 3])
    with col_sb1:
        analizar_sent = st.button(
            "🌡️ Analizar tono",
            type="primary",
            use_container_width=True,
            disabled=not titulares_sent,
            key="btn_analizar_sent",
        )
    if analizar_sent:
        if not api_key:
            st.error("Ingresá tu API key en el panel izquierdo.")
        elif not titulares_sent:
            st.error("No hay titulares para analizar.")
        else:
            with st.spinner(f"Analizando tono de {len(titulares_sent)} titulares..."):
                try:
                    prompt = prompt_tono_editorial(query_sent, titulares_sent[:40])
                    raw_json = call_claude(prompt, api_key, 1200)
                    # Limpiar posibles backticks
                    clean = raw_json.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    resultado = json.loads(clean)
                    st.session_state.sentimiento_resultado = resultado
                    st.session_state.sentimiento_query = query_sent
                except json.JSONDecodeError:
                    st.error("Error al parsear la respuesta. Intentá de nuevo.")
                except Exception as e:
                    st.error(f"Error: {e}")

    # ── Mostrar resultado ────────────────────────────────────────────────────
    if st.session_state.sentimiento_resultado:
        res = st.session_state.sentimiento_resultado
        q_display = st.session_state.sentimiento_query

        st.markdown(f"#### Resultado para: *{q_display}*")

        # Resumen
        st.markdown(
            f'<div style="padding:12px 16px;border-radius:8px;background:#f0f9ff;'
            f'border-left:4px solid #0ea5e9;font-size:15px;margin-bottom:16px">'
            f'📝 {res.get("resumen","")}</div>',
            unsafe_allow_html=True,
        )

        # Distribución
        dist = res.get("distribucion", {})
        total_cl = sum(dist.values()) or 1
        TONO_CFG = {
            "positivo":  ("🟢", "#16a34a", "#f0fdf4"),
            "negativo":  ("🔴", "#dc2626", "#fef2f2"),
            "neutro":    ("⚪", "#6b7280", "#f9fafb"),
            "alarmista": ("🟡", "#d97706", "#fffbeb"),
            "expectante":("🔵", "#2563eb", "#eff6ff"),
        }
        st.markdown("##### Distribución de tono")
        cols_dist = st.columns(5)
        for i, (tono, count) in enumerate(dist.items()):
            emoji, color, bg = TONO_CFG.get(tono, ("⚫", "#374151", "#f9fafb"))
            pct = int(count / total_cl * 100)
            with cols_dist[i]:
                st.markdown(
                    f'<div style="text-align:center;padding:10px 6px;border-radius:8px;'
                    f'background:{bg};border:1px solid {color}30">'
                    f'<div style="font-size:22px">{emoji}</div>'
                    f'<div style="font-size:20px;font-weight:700;color:{color}">{count}</div>'
                    f'<div style="font-size:11px;color:#6b7280;text-transform:capitalize">{tono}</div>'
                    f'<div style="font-size:10px;color:#9ca3af">{pct}%</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("##### Tono por medio")
        por_medio = res.get("por_medio", [])
        for item in por_medio:
            tono = item.get("tono", "neutro")
            emoji, color, bg = TONO_CFG.get(tono, ("⚫", "#374151", "#f9fafb"))
            medio = item.get("medio", "")
            titular = item.get("titular", "")
            razon = item.get("razon", "")
            st.markdown(
                f'<div style="display:flex;gap:10px;align-items:flex-start;'
                f'padding:9px 12px;margin-bottom:5px;border-radius:7px;'
                f'background:{bg};border:1px solid {color}20">'
                f'<span style="font-size:18px;flex-shrink:0">{emoji}</span>'
                f'<div style="flex:1">'
                f'<span style="font-size:11px;font-weight:700;color:{color};text-transform:uppercase">'
                f'{medio} · {tono}</span><br>'
                f'<span style="font-size:13px;color:#1e293b">{titular}</span><br>'
                f'<span style="font-size:11px;color:#64748b;font-style:italic">{razon}</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        if res.get("patrones"):
            st.markdown("##### Patrones detectados")
            for p in res["patrones"]:
                st.markdown(f"- {p}")

        # Descarga
        st.divider()
        export = json.dumps(res, ensure_ascii=False, indent=2)
        st.download_button(
            "📥 Descargar análisis JSON",
            export,
            file_name=f"tono_{q_display}_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
        )

# ─── TAB CANASTA ─────────────────────────────────────────────────────────────
with tab_canasta:
    st.markdown("### 🧺 Canasta de notas")
    st.caption(
        "Agregá notas desde cualquier tab usando el botón **🧺 Agregar a canasta** de cada card. "
        "Luego podés copiar todo el texto o enviarlo a la IA para generar una nota."
    )

    canasta = st.session_state.canasta

    if not canasta:
        st.info("La canasta está vacía. Navegá por las tabs y agregá notas con el botón 🧺.")
    else:
        st.success(f"**{len(canasta)} nota(s)** en la canasta")

        # ── Controles superiores ──────────────────────────────────────────────
        col_c1, col_c2, col_c3 = st.columns([1, 1, 2])
        with col_c1:
            if st.button("🗑 Vaciar canasta", use_container_width=True, key="canasta_vaciar"):
                st.session_state.canasta = []
                st.rerun()
        with col_c2:
            # Texto completo: título + URL + cuerpo scrapeado
            def _texto_item_canasta(item):
                fuente_n = item["fuente"]["nombre"]
                titulo_n = item["noticia"]["titulo"]
                url_n = item["noticia"].get("url") or "(sin URL)"
                cuerpo_n = item.get("cuerpo", "").strip()
                partes = [f"[{fuente_n}] {titulo_n}", f"URL: {url_n}"]
                if cuerpo_n:
                    partes.append(f"TEXTO:\n{cuerpo_n}")
                return "\n".join(partes)

            texto_export = "\n\n──────────────────────\n\n".join(
                _texto_item_canasta(item) for item in canasta
            )
            st.download_button(
                "📥 Exportar .txt",
                texto_export,
                file_name=f"canasta_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain",
                use_container_width=True,
                key="canasta_exportar",
            )

        st.divider()

        # ── Lista de notas en canasta ─────────────────────────────────────────
        st.markdown("#### Notas acumuladas")
        for idx, item in enumerate(canasta):
            f = item["fuente"]
            n = item["noticia"]
            cuerpo_item = item.get("cuerpo", "").strip()
            badge_html = (
                f'<span style="font-size:10px;font-weight:700;padding:2px 8px;'
                f'border-radius:3px;background:{f["color"]}18;color:{f["color"]};'
                f'border:1px solid {f["color"]}30">{f["nombre"]}</span>'
            )
            col_rem, col_exp = st.columns([1, 11])
            with col_rem:
                if st.button("✕", key=f"canasta_rm_{idx}", help="Quitar de la canasta"):
                    st.session_state.canasta.pop(idx)
                    st.rerun()
            with col_exp:
                titulo_display = f"[{n['titulo']}]({n['url']})" if n.get("url") else n["titulo"]
                # Si hay cuerpo: mostrar en expander; si no, mostrar plano
                if cuerpo_item:
                    with st.expander(f"{badge_html} {titulo_display}", expanded=False):
                        st.markdown(
                            f'<div style="font-size:13px;color:#374151;line-height:1.6;'
                            f'padding:6px 0">{cuerpo_item[:600]}{"..." if len(cuerpo_item) > 600 else ""}</div>',
                            unsafe_allow_html=True,
                        )
                        if n.get("url"):
                            st.caption(f"🔗 [Ver nota completa]({n['url']})")
                        col_re_scr, _ = st.columns([2, 4])
                        with col_re_scr:
                            if st.button("🔄 Re-scrapear", key=f"canasta_rescrap_{idx}"):
                                nuevo_cuerpo = _extraer_cuerpo_nota(n["url"], max_chars=1800)
                                st.session_state.canasta[idx]["cuerpo"] = nuevo_cuerpo
                                st.rerun()
                else:
                    st.markdown(f'{badge_html} {titulo_display}', unsafe_allow_html=True)
                    if n.get("url"):
                        col_scr, _ = st.columns([2, 6])
                        with col_scr:
                            if st.button("📄 Leer cuerpo", key=f"canasta_leer_{idx}"):
                                with st.spinner("Leyendo nota..."):
                                    cuerpo_nuevo = _extraer_cuerpo_nota(n["url"], max_chars=1800)
                                st.session_state.canasta[idx]["cuerpo"] = cuerpo_nuevo
                                st.rerun()

        st.divider()

        # ── Texto acumulado para copiar ───────────────────────────────────────
        st.markdown("#### 📋 Texto acumulado (para copiar)")
        cant_con_cuerpo = sum(1 for item in canasta if item.get("cuerpo"))
        st.caption(f"{cant_con_cuerpo}/{len(canasta)} notas con cuerpo scrapeado")
        st.text_area(
            "Copiá este bloque",
            texto_export,
            height=300,
            key="canasta_textarea",
            label_visibility="collapsed",
        )

        st.divider()

        # ── Enviar canasta a la IA ─────────────────────────────────────────────
        st.markdown("#### ✦ Procesar con IA")
        st.caption("Usá las notas de la canasta como fuente para generar una nota con Claude.")

        col_ai1, col_ai2 = st.columns([3, 1])
        with col_ai1:
            tema_canasta = st.text_input(
                "Tema de la nota (podés dejarlo vacío para que lo infiera de las notas)",
                placeholder="Ej: Mercado de pases de Boca, lesión de Messi...",
                key="canasta_tema_ia",
            )
        with col_ai2:
            estilo_canasta = st.selectbox(
                "Estilo",
                ["Informativa", "Analítica", "Urgente/Flash"],
                key="canasta_estilo_ia",
            )

        tipo_canasta = st.selectbox(
            "Entregable",
            ["Nota completa", "Solo titulares alternativos", "Esqueleto + ángulos"],
            key="canasta_tipo_ia",
        )

        contexto_canasta = st.text_area(
            "Contexto adicional (opcional)",
            placeholder="Agregá datos propios, declaraciones o el ángulo que querés tomar...",
            height=80,
            key="canasta_contexto_ia",
        )

        col_gen_c1, col_gen_c2, _ = st.columns([1, 1, 2])
        with col_gen_c1:
            generar_canasta = st.button(
                "✦ Generar con IA",
                type="primary",
                use_container_width=True,
                key="canasta_btn_generar",
                disabled=not bool(canasta),
            )
        with col_gen_c2:
            if st.button("🗑 Limpiar borrador", use_container_width=True, key="canasta_btn_limpiar"):
                st.session_state["canasta_borrador"] = ""
                st.rerun()

        if generar_canasta:
            if not api_key:
                st.error("Ingresá tu API key en el panel izquierdo.")
            else:
                tema_final = tema_canasta.strip() or canasta[0]["noticia"]["titulo"]

                # Usar cuerpo ya scrapeado en la canasta; re-scrapear solo los que no tienen
                titulares_enr = []
                sin_cuerpo = []
                for item in canasta:
                    if item.get("cuerpo"):
                        # Ya tiene cuerpo scrapeado → formato compatible con prompt_nota_rapida
                        titulares_enr.append({
                            "fuente": item["fuente"],
                            "noticia": item["noticia"],
                            "cuerpo": item["cuerpo"],
                            "ok": True,
                        })
                    elif item["noticia"].get("url"):
                        sin_cuerpo.append(item)
                    else:
                        titulares_enr.append({
                            "fuente": item["fuente"],
                            "noticia": item["noticia"],
                            "cuerpo": "",
                            "ok": False,
                        })

                if sin_cuerpo:
                    max_extra = min(6, len(sin_cuerpo))
                    with st.spinner(f"🔍 Leyendo {max_extra} nota(s) sin cuerpo..."):
                        enriquecidos_extra = scrape_cuerpos_notas(sin_cuerpo, max_notas=max_extra)
                    # Actualizar canasta con los cuerpos recién scrapeados
                    for enr in enriquecidos_extra:
                        titulo_enr = enr["noticia"]["titulo"]
                        for i, ci in enumerate(st.session_state.canasta):
                            if ci["noticia"]["titulo"] == titulo_enr and enr.get("cuerpo"):
                                st.session_state.canasta[i]["cuerpo"] = enr["cuerpo"]
                                break
                        titulares_enr.append(enr)

                ok_cnt = sum(1 for t in titulares_enr if t.get("ok"))
                if ok_cnt > 0:
                    st.success(f"✔ {ok_cnt}/{len(titulares_enr)} notas con cuerpo para la IA")
                else:
                    st.warning("⚠️ No se pudo leer el cuerpo — modo esqueleto seguro")

                with st.spinner("✦ Generando nota con Claude..."):
                    try:
                        prompt = prompt_nota_rapida(
                            tema_final, titulares_enr,
                            estilo_canasta, tipo_canasta, contexto_canasta
                        )
                        raw = call_claude(prompt, api_key, 3000)
                        st.session_state["canasta_borrador"] = raw
                    except Exception as e:
                        st.error(f"Error: {e}")

        # ── Mostrar borrador de canasta ───────────────────────────────────────
        if st.session_state.get("canasta_borrador"):
            st.divider()
            st.markdown("#### Borrador generado")
            raw = st.session_state["canasta_borrador"]
            secciones = re.split(r"[═=]{10,}", raw)
            if len(secciones) > 1:
                for sec in secciones:
                    sec = sec.strip()
                    if not sec:
                        continue
                    if "\n" in sec and len(sec.split("\n")[0]) < 50:
                        titulo_sec = sec.split("\n")[0].strip()
                        cuerpo_sec = "\n".join(sec.split("\n")[1:]).strip()
                        st.markdown(f"##### {titulo_sec}")
                        if cuerpo_sec:
                            st.markdown(cuerpo_sec)
                    else:
                        st.markdown(sec)
            else:
                st.markdown(raw)

            st.divider()
            st.download_button(
                "📥 Descargar nota",
                raw,
                file_name=f"nota_canasta_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain",
                key="canasta_download_nota",
            )



st.divider()
st.caption(
    f"Monitor Deportivo Pro v1.0 (Streamlit) · "
    f"Similitud semántica Jaccard (umbral: {SIMILITUD_UMBRAL}) · "
    f"{len(TODAS_FUENTES)} medios"
)
