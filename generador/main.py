"""Genera la pantalla con datos reales y la deja en la carpeta de salida.

Salida:
  pantalla.png   imagen de 800x480 en 4 grises (para verla)
  pantalla.bin   la misma imagen en 2 bits por píxel (para la pantalla)
  estado.json    versión, modo, hora de generación... (la pantalla lo consulta para saber si hay imagen nueva)
  index.html     visor para el móvil o el PC

Uso:
  python generador/main.py --salida salida
  python generador/main.py --salida salida --esperar-manana   # por la tarde: espera a los precios de mañana
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datos import TZ, ahora, por_horas, precios_pvpc, tiempo  # noqa: E402
from render import PANEL_LOCAL, a_bin, dibujar  # noqa: E402

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
ABR = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def titulo(f):
    return f"{DIAS[f.weekday()]} {f.day} {MESES[f.month - 1]}"


def esperar_precios_manana(hasta):
    """Consulta cada 2 minutos hasta que estén los precios de mañana o hasta la hora límite."""
    lim_h, lim_m = map(int, hasta.split(":"))
    while True:
        now = ahora()
        p, info = precios_pvpc(now.date() + timedelta(days=1))
        if p:
            print(f"{now:%H:%M} precios de mañana disponibles ({info})")
            return True
        if (now.hour, now.minute) >= (lim_h, lim_m):
            print(f"{now:%H:%M} sin precios de mañana a la hora límite: {info}")
            return False
        print(f"{now:%H:%M} aún no están los precios de mañana; reintento en 2 min")
        time.sleep(120)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default="salida")
    ap.add_argument("--esperar-manana", action="store_true")
    ap.add_argument("--desde", default="19:30", help="hora local a partir de la cual tiene sentido esperar")
    ap.add_argument("--hasta", default="21:45", help="hora local límite de la espera")
    args = ap.parse_args()

    if args.esperar_manana:
        now = ahora()
        dh, dm = map(int, args.desde.split(":"))
        hh, hm = map(int, args.hasta.split(":"))
        if not ((dh, dm) <= (now.hour, now.minute) <= (hh, hm)):
            print(f"{now:%H:%M} fuera de la ventana {args.desde}–{args.hasta}; no hago nada")
            return 0
        p, _ = precios_pvpc(now.date() + timedelta(days=1))
        if p:
            print("Los precios de mañana ya estaban publicados; lo cubre la actualización de cada hora")
            return 0
        if not esperar_precios_manana(args.hasta):
            return 0

    now = ahora()
    hoy_f = now.date()
    man_f = hoy_f + timedelta(days=1)

    p_hoy, f_hoy = precios_pvpc(hoy_f)
    if not p_hoy:
        print(f"ERROR: no hay precios de hoy: {f_hoy}")
        return 1
    p_man, f_man = precios_pvpc(man_f) if now.hour >= 19 else (None, "no toca")
    modo = "manana" if p_man else "hoy"
    dia = man_f if p_man else hoy_f
    precios = p_man if p_man else p_hoy

    horas, dias = tiempo()
    temp, lluvia, iconos = por_horas(horas[dia])
    semana = [(ABR[x["fecha"].weekday()], x["icono"], x["max"], x["min"], x["lluvia"])
              for x in dias if x["fecha"] > dia][:5]

    datos = {
        "modo": modo, "hora": now.hour, "titulo_dia": titulo(dia), "precios": precios,
        "ahora_precio": p_hoy[now.hour], "temp": temp, "lluvia": lluvia, "iconos": iconos,
        "semana": semana, "panel_local": None,
    }
    img = dibujar(datos)
    binario = a_bin(img)

    os.makedirs(args.salida, exist_ok=True)
    img.save(os.path.join(args.salida, "pantalla.png"), optimize=True)
    with open(os.path.join(args.salida, "pantalla.bin"), "wb") as fh:
        fh.write(binario)
    estado = {
        "version": hashlib.sha1(binario).hexdigest()[:12],
        "generado": now.isoformat(timespec="minutes"),
        "modo": modo,
        "dia": dia.isoformat(),
        "hay_precios_manana": bool(p_man),
        "fuente_precios": f_man if p_man else f_hoy,
        "panel_local": dict(zip(("x0", "y0", "x1", "y1"), PANEL_LOCAL)),
        "formato_bin": "800x480, 2 bits por píxel, 4 píxeles por byte (bits altos primero), "
                       "0=negro 1=gris oscuro 2=gris claro 3=blanco, 96000 bytes",
    }
    with open(os.path.join(args.salida, "estado.json"), "w", encoding="utf-8") as fh:
        json.dump(estado, fh, ensure_ascii=False, indent=2)
    shutil.copy(os.path.join(RAIZ, "web", "index.html"), os.path.join(args.salida, "index.html"))
    print(json.dumps(estado, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
