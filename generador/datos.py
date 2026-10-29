"""Descarga de datos: precios PVPC (Red Eléctrica) y previsión del tiempo (Open-Meteo)."""
import json
import os
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")
LAT, LON = 37.99, -1.03  # Alquerías (Murcia)
UA = {"User-Agent": "pantalla-epaper/1.0 (+https://github.com)", "Accept": "application/json"}


def _get_json(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Precios PVPC 2.0TD (Península), en €/kWh, 24 valores por día (hora local 0..23)
# ---------------------------------------------------------------------------
def _a_24_horas(pares):
    """pares: lista de (datetime con zona, valor €/MWh). Devuelve 24 valores €/kWh por hora local.

    Agrupa los cuartos de hora en horas y resuelve los días de cambio de hora:
    con 25 h se promedia la hora repetida; con 23 h se rellena la que falta con la anterior.
    """
    por_hora = defaultdict(list)
    for dt, v in pares:
        if v is None:
            continue
        por_hora[dt.astimezone(TZ).hour].append(float(v) / 1000.0)
    if len(por_hora) < 23:
        return None
    precios = []
    for h in range(24):
        if por_hora.get(h):
            precios.append(sum(por_hora[h]) / len(por_hora[h]))
        elif precios:
            precios.append(precios[-1])
        else:
            return None
    if not all(-0.5 < p < 3.0 for p in precios):
        return None
    return precios


def _redata(dia: date):
    """API pública REData de Red Eléctrica (sin token)."""
    q = urllib.parse.urlencode({
        "start_date": f"{dia.isoformat()}T00:00",
        "end_date": f"{dia.isoformat()}T23:59",
        "time_trunc": "hour",
        "geo_trunc": "electric_system",
        "geo_limit": "peninsular",
        "geo_ids": "8741",
    })
    j = _get_json(f"https://apidatos.ree.es/es/datos/mercados/precios-mercados-tiempo-real?{q}")
    for item in j.get("included", []):
        titulo = (item.get("attributes", {}).get("title") or item.get("type") or "").upper()
        if "PVPC" in titulo:
            vals = item["attributes"].get("values", [])
            pares = [(datetime.fromisoformat(v["datetime"]), v.get("value")) for v in vals]
            pares = [(dt, v) for dt, v in pares if dt.astimezone(TZ).date() == dia]
            return _a_24_horas(pares)
    return None


def _esios_archivo(dia: date):
    """Fichero diario público del PVPC en ESIOS (formato histórico, sin token)."""
    j = _get_json(f"https://api.esios.ree.es/archives/70/download_json?locale=es&date={dia.isoformat()}")
    filas = j.get("PVPC") or []
    pares = []
    for f in filas:
        if f.get("Dia") and f["Dia"] != dia.strftime("%d/%m/%Y"):
            continue
        h = int(f["Hora"][:2])
        v = f.get("PCB") or f.get("GEN")
        if v is None:
            continue
        v = float(str(v).replace(".", "").replace(",", "."))
        pares.append((datetime(dia.year, dia.month, dia.day, h, tzinfo=TZ), v))
    return _a_24_horas(pares)


def _esios_token(dia: date):
    """API ESIOS con token personal (solo si existe la variable ESIOS_TOKEN)."""
    token = os.environ.get("ESIOS_TOKEN")
    if not token:
        return None
    q = urllib.parse.urlencode({"start_date": f"{dia.isoformat()}T00:00", "end_date": f"{dia.isoformat()}T23:59"})
    j = _get_json(f"https://api.esios.ree.es/indicators/1001?{q}",
                  headers={"x-api-key": token, "Accept": "application/json; application/vnd.esios-api-v1+json"})
    vals = [v for v in j["indicator"]["values"] if v.get("geo_id") in (8741, None)]
    pares = [(datetime.fromisoformat(v["datetime"]), v.get("value")) for v in vals]
    pares = [(dt, v) for dt, v in pares if dt.astimezone(TZ).date() == dia]
    return _a_24_horas(pares)


def precios_pvpc(dia: date):
    """Devuelve (precios[24], fuente) o (None, motivo) si aún no están publicados o fallan las fuentes."""
    errores = []
    for nombre, fn in (("REData", _redata), ("ESIOS archivo", _esios_archivo), ("ESIOS token", _esios_token)):
        try:
            p = fn(dia)
            if p:
                return p, nombre
            errores.append(f"{nombre}: sin datos")
        except Exception as e:  # noqa: BLE001 — se prueba la siguiente fuente
            errores.append(f"{nombre}: {type(e).__name__}: {e}")
    return None, "; ".join(errores)


# ---------------------------------------------------------------------------
# Tiempo (Open-Meteo, gratis y sin registro)
# ---------------------------------------------------------------------------
def icono_wmo(code, es_dia=True):
    code = int(code or 0)
    if code == 0:
        return "sol" if es_dia else "luna"
    if code in (1, 2):
        return "poco_nuboso" if es_dia else "luna_nubes"
    if code in (3, 45, 48):
        return "nubes"
    return "lluvia"  # llovizna, lluvia, chubascos, nieve y tormenta


def tiempo():
    q = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON, "timezone": "Europe/Madrid", "forecast_days": 7,
        "hourly": "temperature_2m,precipitation_probability,weather_code,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
    })
    j = _get_json(f"https://api.open-meteo.com/v1/forecast?{q}")
    hh = j["hourly"]
    horas = defaultdict(dict)
    for i, t in enumerate(hh["time"]):
        dt = datetime.fromisoformat(t)
        horas[dt.date()][dt.hour] = {
            "temp": hh["temperature_2m"][i],
            "lluvia": hh["precipitation_probability"][i] or 0,
            "icono": icono_wmo(hh["weather_code"][i], bool(hh["is_day"][i])),
        }
    dd = j["daily"]
    dias = []
    for i, t in enumerate(dd["time"]):
        dias.append({
            "fecha": date.fromisoformat(t),
            "icono": icono_wmo(dd["weather_code"][i]),
            "max": round(dd["temperature_2m_max"][i]),
            "min": round(dd["temperature_2m_min"][i]),
            "lluvia": dd["precipitation_probability_max"][i] or 0,
        })
    return horas, dias


def por_horas(horas_dia):
    """Convierte {hora: {...}} en listas de 24 valores (rellenando huecos con el vecino)."""
    temp, lluvia, iconos = [], [], {}
    ultimo = None
    for h in range(24):
        x = horas_dia.get(h) or ultimo
        if x is None:
            x = next(iter(horas_dia.values()))
        temp.append(x["temp"]); lluvia.append(x["lluvia"]); ultimo = x
        if h % 3 == 0:
            iconos[h] = x["icono"]
    return temp, lluvia, iconos


def ahora():
    return datetime.now(TZ)


def manana(d: date):
    return d + timedelta(days=1)
