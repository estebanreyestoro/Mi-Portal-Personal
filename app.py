from flask import Flask, render_template, jsonify
import requests
from bs4 import BeautifulSoup
import re
import email.utils
from datetime import datetime, timezone, timedelta
from config import config

app = Flask(__name__)
app.config.from_object(config['production'])

# --- UTILIDADES ---
def obtener_hora_y_fecha(fecha_str):
    if not fecha_str: return None
    try:
        tupla = email.utils.parsedate_tz(fecha_str)
        if tupla:
            timestamp = email.utils.mktime_tz(tupla)
            return datetime.fromtimestamp(timestamp, tz=timezone(timedelta(hours=-3)))
    except: return None
    return None

def procesar_google_news(url):
    noticias = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        res = requests.get(url, headers=headers)
        print(f"DEBUG: Status Code de noticias: {res.status_code}")
        
        if res.status_code != 200:
            print(f"DEBUG: Error en la respuesta: {res.text[:100]}") # Solo los primeros 100 caracteres
            return []

        sopa = BeautifulSoup(res.text, "xml")
        items = sopa.find_all('item')
        print(f"DEBUG: Cantidad de noticias encontradas: {len(items)}")
        sopa = BeautifulSoup(res.text, "xml")
        for item in sopa.find_all('item', limit=8):
            fecha_dt = obtener_hora_y_fecha(item.pubDate.text if item.find('pubDate') else "")
            titulo_full = item.title.text
            partes = titulo_full.split(" - ")
            fuente = partes[-1] if len(partes) > 1 else "Info"
            titulo = " - ".join(partes[:-1]) if len(partes) > 1 else titulo_full
            noticias.append({
                "titulo": titulo,
                "link": item.link.text,
                "fecha": fecha_dt.strftime("%d/%m") if fecha_dt else "2026",
                "hora": fecha_dt.strftime("%H:%M") if fecha_dt else "00:00",
                "timestamp": fecha_dt.timestamp() if fecha_dt else 0,
                "fuente": fuente
            })
    except: pass
    # Ordenar por timestamp descendente (más recientes primero)
    noticias_ordenadas = sorted(noticias, key=lambda x: x['timestamp'], reverse=True)
    return jsonify(noticias_ordenadas)

# --- FUNCIONES PARA SCRAPING DE CINE REX VIEDMA ---
def obtener_cartelera_cine():
    """Obtiene la cartelera actual del Cine Rex Viedma por día de la semana.

    Usa el endpoint oficial que entrega funciones (horarios) por fecha.
    Retorna un dict con claves: "Lunes".."Domingo" y listas de películas.

    Cada película incluye:
    - titulo, clasificacion, duracion, genero
    - horarios: lista de strings (12:00)
    - disponible: bool (true si tiene al menos una función ese día)
    """
    cartelera_por_dia = {}
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    try:
        # Construir fechas de la semana actual (lunes a domingo) en zona horaria -3
        hoy = datetime.now(tz=timezone(timedelta(hours=-3)))
        dias_desde_lunes = hoy.weekday()  # 0=lunes, 6=domingo
        fecha_lunes = hoy - timedelta(days=dias_desde_lunes)

        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "http://www.cinerexviedma.com.ar/programacion.php",
            "X-Requested-With": "XMLHttpRequest",
        }

        for indice, dia_nombre in enumerate(dias_semana):
            fecha = fecha_lunes + timedelta(days=indice)
            fecha_str = fecha.strftime("%d/%m/%Y")
            cartelera_por_dia[dia_nombre] = []

            try:
                res = session.post(
                    "http://www.cinerexviedma.com.ar/mobile/consultas/peliculas/PeliculasConFuncionesYHorarios.php",
                    data={"fecha": fecha_str},
                    headers=headers,
                    timeout=15,
                )

                # Si la API no responde correctamente, continuar al siguiente día
                if res.status_code != 200:
                    continue

                json_data = res.json()
                datos = json_data.get("datos") or []
                funciones = json_data.get("funciones") or []

                # Agrupar funciones por película para crear horarios
                funciones_por_pelicula = {}
                for func in funciones:
                    codigo = func.get("codPelicula")
                    if not codigo:
                        continue
                    funciones_por_pelicula.setdefault(codigo, []).append(func)

                for pelicula in datos:
                    titulo = pelicula.get("peliculas_nombre", "").strip()
                    codigo = pelicula.get("peliculas_codigo")

                    func_list = funciones_por_pelicula.get(codigo, [])
                    horarios = [f.get("hora") for f in func_list if f.get("hora")]

                    pelicula_info = {
                        "titulo": titulo or "(Sin título)",
                        "clasificacion": pelicula.get("peliculas_clasificacion", "ATP"),
                        "duracion": pelicula.get("peliculas_duracion", "--"),
                        "genero": pelicula.get("peliculas_genero", "General"),
                        "horarios": horarios,
                        "disponible": len(horarios) > 0,
                    }
                    cartelera_por_dia[dia_nombre].append(pelicula_info)

            except Exception:
                # Ignorar errores individuales de fecha para no romper la semana completa
                continue

        # Si por alguna razón no conseguimos datos para la semana, usamos cuotas "estáticas" de respaldo
        if not any(cartelera_por_dia.get(dia) for dia in dias_semana):
            raise ValueError("No se obtuvieron datos válidos de la API de Cine Rex")

    except Exception as e:
        print(f"Error obteniendo cartelera del cine: {e}")
        # Retornar estructura básica con valores de respaldo
        peliculas_default = [
            {
                "titulo": "Hoppers - Operación Castor",
                "clasificacion": "ATP",
                "duracion": "105",
                "genero": "Animación",
                "horarios": ["18:00"],
                "disponible": True,
            }
        ]
        for dia in dias_semana:
            cartelera_por_dia[dia] = peliculas_default

    return cartelera_por_dia

# --- RUTAS ---

@app.route('/')
def inicio():
    # Este será tu menú limpio con los botones
    return render_template('index.html')

@app.route('/tv')
def vista_tv():
    # Sub-página exclusiva para YouTube/Spotify
    return render_template('tv.html')

@app.route('/motor')
def vista_motor():
    # Sub-página exclusiva para F1, WEC, IMSA
    return render_template('motor.html')

@app.route('/utilidades')
def vista_utilidades():
    return render_template('utilidades.html')

@app.route('/cine')
def vista_cine():
    return render_template('cine.html')

@app.route('/futbol')
def vista_futbol():
    return render_template('futbol.html')

@app.route('/noticias')
def vista_noticias():
    return render_template('noticias.html')

@app.route('/api/noticias')
def obtener_noticias():
    # Definir fuentes RSS de geopolítica
    fuentes_rss = [
        {"name": "BBC Mundo", "url": "https://feeds.bbci.co.uk/mundo/rss.xml"},
        {"name": "DW Español", "url": "https://rss.dw.com/rdf/rss-es-all"},
        {"name": "RT en Español", "url": "https://actualidad.rt.com/rss"},
        {"name": "France 24 Español", "url": "https://www.france24.com/es/rss"},
        {"name": "El País Internacional", "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada"}
    ]
    
    todas_noticias = []
    
    # Procesar cada fuente por separado
    for fuente in fuentes_rss:
        try:
            res = requests.get(fuente["url"], timeout=10)
            sopa = BeautifulSoup(res.text, "xml")
            
            # Obtener hasta 4 items por fuente
            for item in sopa.find_all('item', limit=4):
                fecha_dt = obtener_hora_y_fecha(item.pubDate.text if item.find('pubDate') else "")
                todas_noticias.append({
                    "titulo": item.title.text,
                    "link": item.link.text,
                    "fuente": fuente["name"],
                    "fecha": fecha_dt.strftime("%d/%m") if fecha_dt else "2026",
                    "hora": fecha_dt.strftime("%H:%M") if fecha_dt else "00:00",
                    "timestamp": fecha_dt.timestamp() if fecha_dt else 0
                })
        except Exception as e:
            # Si una fuente falla, continuar con las demás
            print(f"Error obteniendo noticias de {fuente['name']}: {e}")
            continue
    
    # Ordenar todas las noticias por timestamp descendente (más recientes primero)
    noticias_ordenadas = sorted(todas_noticias, key=lambda x: x['timestamp'], reverse=True)
    return jsonify(noticias_ordenadas)

@app.route('/api/futbol/<equipo>/<categoria>')
def obtener_futbol(equipo, categoria):
    queries = {
        "noticias": f"{equipo} noticias futbol",
        "partidos": f"{equipo} partidos resultados",
        "jugadores": f"{equipo} plantel transfermarkt"
    }
    query = queries.get(categoria, equipo)
    url = f"https://news.google.com/rss/search?q={query}&hl=es-419&gl=AR&ceid=AR:es-419&tbs=qdr:w"
    return procesar_google_news(url)

@app.route('/api/f1/<categoria>')
def obtener_f1(categoria):
    # Primero verificar si es calendario
    if categoria == "calendario":
        # Retornar calendario de F1
        if "f1" in CALENDARIOS_MOTORSPORT:
            return jsonify(CALENDARIOS_MOTORSPORT["f1"])
        return jsonify([])
    
    # CARRIL EXCLUSIVO: POSICIONES (SCRAPING MOTORSPORT.COM)
    if categoria == "posiciones":
        url = "https://lat.motorsport.com/f1/standings/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        posiciones = []
        try:
            res = requests.get(url, headers=headers, timeout=10)
            sopa = BeautifulSoup(res.text, "html.parser")
            tabla = sopa.find('table')
            
            if tabla:
                filas = tabla.find_all('tr')[1:]  # Saltar encabezado
                
                for fila in filas[:25]:  # Limit to top 25
                    cols = fila.find_all('td')
                    
                    if len(cols) >= 3:
                        pos = cols[0].get_text(strip=True)
                        puntos = cols[2].get_text(strip=True)
                        
                        # Extraer piloto y equipo usando selectores específicos
                        nombre_span = cols[1].find('span', class_='name-short')
                        equipo_span = cols[1].find('span', class_='team')
                        
                        piloto = nombre_span.get_text(strip=True) if nombre_span else ""
                        equipo = equipo_span.get_text(strip=True) if equipo_span else ""
                        
                        # Validar que posición sea un número
                        if pos.isdigit() and piloto:
                            posiciones.append({
                                "pos": pos,
                                "piloto": piloto,
                                "equipo": equipo,
                                "puntos": puntos
                            })
            
            if not posiciones:
                # Si no encuentra la tabla, retornar mensaje de error
                return jsonify([{"pos": "ERR", "piloto": "No se pudo cargar desde Motorsport.com", "equipo": "", "puntos": "-"}])
            
            return jsonify(posiciones)
        except Exception as e:
            print(f"Error F1 Scraping: {e}")
            return jsonify([])

    # CARRIL NORMAL: NOTICIAS Y CALENDARIO (GOOGLE NEWS)
    queries = {
        "noticias": "F1 McLaren Lando Norris Oscar Piastri",
        "calendario": "F1 2026 proxima carrera horarios argentina"
    }
    query = queries.get(categoria, "F1")
    url = f"https://news.google.com/rss/search?q={query}&hl=es-419&gl=AR&ceid=AR:es-419"
    return procesar_google_news(url)

# --- RUTAS MOTORSPORT (WEC, IndyCar, IMSA) - CALENDARIOS Y NOTICIAS ---

# Calendarios de carreras 2026 para cada categoría (datos verificados de Wikipedia y fuentes oficiales)
CALENDARIOS_MOTORSPORT = {
    "wec": [
        {"id": 1, "nombre": "6 Horas de Imola", "fecha": "2026-04-19", "ubicacion": "Imola, Italia"},
        {"id": 2, "nombre": "6 Horas de Spa-Francorchamps", "fecha": "2026-05-09", "ubicacion": "Spa, Bélgica"},
        {"id": 3, "nombre": "24 Horas de Le Mans", "fecha": "2026-06-13", "ubicacion": "Le Mans, Francia"},
        {"id": 4, "nombre": "6 Horas de São Paulo", "fecha": "2026-07-12", "ubicacion": "São Paulo, Brasil"},
        {"id": 5, "nombre": "Lone Star Le Mans (Austin)", "fecha": "2026-09-06", "ubicacion": "Austin, USA"},
        {"id": 6, "nombre": "6 Horas de Fuji", "fecha": "2026-09-27", "ubicacion": "Fuji, Japón"},
        {"id": 7, "nombre": "Qatar 1812 km", "fecha": "2026-10-24", "ubicacion": "Lusail, Qatar"},
        {"id": 8, "nombre": "8 Horas de Bahréin", "fecha": "2026-11-07", "ubicacion": "Sakhir, Bahréin"},
    ],
    "indycar": [
        {"id": 1, "nombre": "Grand Prix de St. Petersburg", "fecha": "2026-03-01", "ubicacion": "St. Petersburg, USA"},
        {"id": 2, "nombre": "Good Ranchers 250", "fecha": "2026-03-07", "ubicacion": "Phoenix, USA"},
        {"id": 3, "nombre": "Grand Prix de Arlington", "fecha": "2026-03-15", "ubicacion": "Arlington, USA"},
        {"id": 4, "nombre": "Grand Prix de Barber", "fecha": "2026-03-29", "ubicacion": "Birmingham, USA"},
        {"id": 5, "nombre": "Acura Grand Prix de Long Beach", "fecha": "2026-04-19", "ubicacion": "Long Beach, USA"},
        {"id": 6, "nombre": "Sonsio Grand Prix", "fecha": "2026-05-09", "ubicacion": "Indianapolis Road Course, USA"},
        {"id": 7, "nombre": "Indianapolis 500", "fecha": "2026-05-24", "ubicacion": "Indianapolis, USA"},
        {"id": 8, "nombre": "Detroit Grand Prix", "fecha": "2026-05-31", "ubicacion": "Detroit, USA"},
        {"id": 9, "nombre": "Gateway 500", "fecha": "2026-06-07", "ubicacion": "Madison, USA"},
        {"id": 10, "nombre": "Road America Grand Prix", "fecha": "2026-06-21", "ubicacion": "Elkhart Lake, USA"},
        {"id": 11, "nombre": "Honda Indy 200", "fecha": "2026-07-05", "ubicacion": "Mid-Ohio, USA"},
        {"id": 12, "nombre": "Music City Grand Prix", "fecha": "2026-07-19", "ubicacion": "Nashville, USA"},
        {"id": 13, "nombre": "Portland Grand Prix", "fecha": "2026-08-09", "ubicacion": "Portland, USA"},
        {"id": 14, "nombre": "Markham Indy", "fecha": "2026-08-16", "ubicacion": "Markham, Canadá"},
        {"id": 15, "nombre": "Washington D.C. Grand Prix", "fecha": "2026-08-23", "ubicacion": "Washington D.C., USA"},
        {"id": 16, "nombre": "Milwaukee Mile Race 1", "fecha": "2026-08-29", "ubicacion": "Milwaukee, USA"},
        {"id": 17, "nombre": "Milwaukee Mile Race 2", "fecha": "2026-08-30", "ubicacion": "Milwaukee, USA"},
        {"id": 18, "nombre": "Monterey Grand Prix", "fecha": "2026-09-06", "ubicacion": "Monterey, USA"},
    ],
    "imsa": [
        {"id": 1, "nombre": "Rolex 24 en Daytona", "fecha": "2026-01-25", "ubicacion": "Daytona, USA"},
        {"id": 2, "nombre": "12 Horas de Sebring", "fecha": "2026-03-21", "ubicacion": "Sebring, USA"},
        {"id": 3, "nombre": "Acura Grand Prix de Long Beach", "fecha": "2026-04-18", "ubicacion": "Long Beach, USA"},
        {"id": 4, "nombre": "Motul Course de Monterey", "fecha": "2026-05-03", "ubicacion": "Monterey, USA"},
        {"id": 5, "nombre": "Detroit Sports Car Classic", "fecha": "2026-05-30", "ubicacion": "Detroit, USA"},
        {"id": 6, "nombre": "6 Horas de The Glen", "fecha": "2026-06-28", "ubicacion": "Watkins Glen, USA"},
        {"id": 7, "nombre": "Grand Prix de Mosport", "fecha": "2026-07-12", "ubicacion": "Toronto, Canadá"},
        {"id": 8, "nombre": "Road America Endurance", "fecha": "2026-08-02", "ubicacion": "Elkhart Lake, USA"},
        {"id": 9, "nombre": "Virginia Sports Car Challenge", "fecha": "2026-08-23", "ubicacion": "Alton, USA"},
        {"id": 10, "nombre": "Battle on the Bricks", "fecha": "2026-09-20", "ubicacion": "Indianapolis, USA"},
        {"id": 11, "nombre": "Petit Le Mans", "fecha": "2026-10-03", "ubicacion": "Road Atlanta, USA"},
    ],
    "f1": [
        {"id": 1, "nombre": "Gran Premio de Australia", "fecha": "2026-03-08", "ubicacion": "Albert Park, Australia"},
        {"id": 2, "nombre": "Gran Premio de China", "fecha": "2026-03-15", "ubicacion": "Shanghai, China"},
        {"id": 3, "nombre": "Gran Premio de Japón", "fecha": "2026-03-29", "ubicacion": "Suzuka, Japón"},
        {"id": 4, "nombre": "Gran Premio de Miami", "fecha": "2026-05-03", "ubicacion": "Miami, USA"},
        {"id": 5, "nombre": "Gran Premio de Canadá", "fecha": "2026-05-24", "ubicacion": "Montreal, Canadá"},
        {"id": 6, "nombre": "Gran Premio de Mónaco", "fecha": "2026-06-07", "ubicacion": "Mónaco"},
        {"id": 7, "nombre": "Gran Premio de Barcelona-Catalunya", "fecha": "2026-06-14", "ubicacion": "Barcelona, España"},
        {"id": 8, "nombre": "Gran Premio de Austria", "fecha": "2026-06-28", "ubicacion": "Spielberg, Austria"},
        {"id": 9, "nombre": "Gran Premio de Gran Bretaña", "fecha": "2026-07-05", "ubicacion": "Silverstone, Inglaterra"},
        {"id": 10, "nombre": "Gran Premio de Bélgica", "fecha": "2026-07-19", "ubicacion": "Spa-Francorchamps, Bélgica"},
        {"id": 11, "nombre": "Gran Premio de Hungría", "fecha": "2026-07-26", "ubicacion": "Hungaroring, Hungría"},
        {"id": 12, "nombre": "Gran Premio de Países Bajos", "fecha": "2026-08-23", "ubicacion": "Zandvoort, Países Bajos"},
        {"id": 13, "nombre": "Gran Premio de Italia", "fecha": "2026-09-06", "ubicacion": "Monza, Italia"},
        {"id": 14, "nombre": "Gran Premio de España (Madrid)", "fecha": "2026-09-13", "ubicacion": "Madring, Madrid, España"},
        {"id": 15, "nombre": "Gran Premio de Azerbaiyán", "fecha": "2026-09-26", "ubicacion": "Baku, Azerbaiyán"},
        {"id": 16, "nombre": "Gran Premio de Singapur", "fecha": "2026-10-11", "ubicacion": "Marina Bay, Singapur"},
        {"id": 17, "nombre": "Gran Premio de Estados Unidos", "fecha": "2026-10-25", "ubicacion": "Austin, USA"},
        {"id": 18, "nombre": "Gran Premio de México", "fecha": "2026-11-01", "ubicacion": "Ciudad de México, México"},
        {"id": 19, "nombre": "Gran Premio de Brasil", "fecha": "2026-11-08", "ubicacion": "São Paulo, Brasil"},
        {"id": 20, "nombre": "Gran Premio de Las Vegas", "fecha": "2026-11-21", "ubicacion": "Las Vegas, USA"},
        {"id": 21, "nombre": "Gran Premio de Qatar", "fecha": "2026-11-29", "ubicacion": "Lusail, Qatar"},
        {"id": 22, "nombre": "Gran Premio de Abu Dhabi", "fecha": "2026-12-06", "ubicacion": "Yas Marina, UAE"},
    ]
}

# Links oficiales de standings
LINKS_STANDINGS = {
    "wec": "https://lat.motorsport.com/wec/standings/",
    "indycar": "https://www.indycar.com/standings",
    "imsa": "https://www.imsa.com/"
}

# --- FUNCIONES PARA SCRAPING DE ERREPAR ---

def _search_errepar_products():
    base_search_url = "https://tiendaonline.errepar.com/busqueda?controller=search&search_query=Separata"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    }
    all_products = []
    
    for page_num in range(1, 5): # Busca en las primeras 4 páginas
        search_url = f"{base_search_url}&page={page_num}" if page_num > 1 else base_search_url
        try:
            res = requests.get(search_url, headers=headers, timeout=15)
            if res.status_code == 200:
                sopa = BeautifulSoup(res.text, "html.parser")
                
                # MÉTODO ROBUSTO: Buscar por todos los enlaces (<a>) en lugar de clases CSS que cambian
                enlaces = sopa.find_all("a")
                
                for a in enlaces:
                    title = a.get_text(strip=True)
                    link = a.get("href", "")
                    
                    # Filtramos: Si tiene texto, dice "separata" y es un link real
                    if title and "separata" in title.lower() and link.startswith("http"):
                        # Evitar agregar el mismo producto duplicado
                        if not any(p["link"] == link for p in all_products):
                            all_products.append({"title": title, "link": link})
        except Exception as e:
            print(f"Error searching Errepar products on page {page_num}: {e}")
            
    return all_products

def _scrape_errepar_product_page(product_url, product_title):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    product_info = {
        "version_actual": None,
        "fecha_version": datetime.now().strftime("%Y-%m"), # Fallback visual
        "disponible": False
    }
    
    # 1. Intentar sacar la versión directamente del título primero (Ej: "Separata IVA 4.1")
    version_match = re.search(r"(\d+\.\d+)", product_title)
    if version_match:
        product_info["version_actual"] = version_match.group(1)

    try:
        res = requests.get(product_url, headers=headers, timeout=15)
        if res.status_code == 200:
            sopa = BeautifulSoup(res.text, "html.parser")
            
            # 2. Si no tenía números en el título, buscar la palabra "Versión X.X" adentro de la página
            if not product_info["version_actual"]:
                v_match = re.search(r"versión\s*([\d]+\.[\d]+)", res.text, re.IGNORECASE)
                if v_match:
                    product_info["version_actual"] = v_match.group(1)
                else:
                    product_info["version_actual"] = "Última" # Valor de rescate para que no falle el HTML

            # Verificar disponibilidad
            html_text = res.text.lower()
            if sopa.find("button", class_="add-to-cart") or "comprar" in html_text or "añadir al carrito" in html_text or "stock" in html_text:
                product_info["disponible"] = True
                
    except Exception as e:
        print(f"Error scraping product page {product_url}: {e}")
        
    # Seguro antierrores: Si encontramos la versión pero falló el check de botón, la marcamos disponible igual
    if product_info["version_actual"] and not product_info["disponible"]:
         product_info["disponible"] = True
         
    return product_info

def obtener_separatas_errepar():
    """Obtiene información en tiempo real de las separatas disponibles en Errepar"""
    separatas = {
        "iva": {
            "nombre": "Separata de IVA",
            "version_actual": None,
            "fecha_version": None,
            "proxima_version": None,
            "estimacion_proxima": None,
            "disponible": False,
            "link_compra": None
        },
        "ganancias": {
            "nombre": "Separata de Ganancias",
            "version_actual": None,
            "fecha_version": None,
            "proxima_version": None,
            "estimacion_proxima": None,
            "disponible": False,
            "link_compra": None
        }
    }
    
    try:
        all_products = _search_errepar_products()
        
        for product in all_products:
            title = product["title"].lower()
            link_lower = product["link"].lower() # Extraemos la URL en minúscula
            link_original = product["link"]
            
            # FIX PARA IVA: Buscamos también en la URL por si el título visual está cortado (ej: "Valor...")
            if ("valor agregado" in title or "iva" in title or "valor-agregado" in link_lower or "impuesto-al-valor" in link_lower) and not separatas["iva"]["version_actual"]:
                info = _scrape_errepar_product_page(link_original, product["title"])
                if info["version_actual"]:
                    separatas["iva"].update(info)
                    separatas["iva"]["link_compra"] = link_original
            
            # FIX PARA GANANCIAS: Le sumamos la lectura de URL por las dudas para que sea igual de robusto
            if ("ganancias" in title or "ganancias" in link_lower) and not separatas["ganancias"]["version_actual"]:
                info = _scrape_errepar_product_page(link_original, product["title"])
                if info["version_actual"]:
                    separatas["ganancias"].update(info)
                    separatas["ganancias"]["link_compra"] = link_original
                    
            # Detener si ya encontramos ambas
            if separatas["iva"]["version_actual"] and separatas["ganancias"]["version_actual"]:
                break
                
    except Exception as e:
        print(f"Error general en scraping Errepar: {e}")
    
    return separatas

@app.route('/api/motor/<categoria>/noticias')
def obtener_motor_noticias(categoria):
    """Obtiene noticias de motorsport por categoría"""
    queries = {
        "wec": "WEC FIA World Endurance Championship 2026",
        "indycar": "IndyCar NTT INDYCAR SERIES 2026",
        "imsa": "IMSA SportsCar Championship 2026"
    }
    query = queries.get(categoria.lower(), categoria)
    url = f"https://news.google.com/rss/search?q={query}&hl=es-419&gl=AR&ceid=AR:es-419&tbs=qdr:w"
    return procesar_google_news(url)

@app.route('/api/motor/<categoria>/calendario')
def obtener_motor_calendario(categoria):
    """Obtiene calendario de carreras 2026 para categoria motorsport"""
    categoria = categoria.lower()
    if categoria in CALENDARIOS_MOTORSPORT:
        return jsonify(CALENDARIOS_MOTORSPORT[categoria])
    return jsonify([])

@app.route('/api/motor/<categoria>/standings-link')
def obtener_motor_standings_link(categoria):
    """Obtiene link oficial a standings"""
    categoria = categoria.lower()
    if categoria in LINKS_STANDINGS:
        return jsonify({"link": LINKS_STANDINGS[categoria]})
    return jsonify({"link": ""})

@app.route('/api/errepar/separatas')
def obtener_errepar_separatas():
    """Obtiene información en tiempo real de las últimas versiones de separatas Errepar"""
    separatas = obtener_separatas_errepar()
    return jsonify(separatas)

@app.route('/api/cine/cartelera')
def obtener_cartelera():
    """Obtiene la cartelera de la semana del Cine Rex Viedma"""
    cartelera = obtener_cartelera_cine()
    return jsonify(cartelera)

if __name__ == '__main__':
    app.run(debug=True)
