"""Dibuja la pantalla de 800x480 en 4 grises (reTerminal E1001).

    dibujar(datos) -> PIL.Image en modo "L" con solo 4 valores: 0, 85, 170, 255

Ejemplo sin conexión:  python3 generador/render.py --ejemplo salida.png [hoy|manana] [hora]
"""
import math
import os
import sys
from PIL import Image, ImageDraw, ImageFont

W, H = 800, 480
BLACK, DARK, LIGHT, WHITE = 0, 85, 170, 255
GRISES = (BLACK, DARK, LIGHT, WHITE)
FUENTES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fuentes")
# Recuadro inferior derecho que rellena la propia pantalla (cocina, batería y hora de actualización)
PANEL_LOCAL = (568, 396, 776, 476)

_cache = {}


def font(estilo, tam):
    k = (estilo, tam)
    if k not in _cache:
        _cache[k] = ImageFont.truetype(os.path.join(FUENTES, f"Inter-{estilo}.otf"), tam)
    return _cache[k]


def eur(v, n=3):
    return f"{v:.{n}f}".replace(".", ",")


def ventana(precios, desde=0, n=3, peor=False):
    m = [(sum(precios[i:i + n]) / n, i) for i in range(desde, len(precios) - n + 1)]
    return (max if peor else min)(m)


def dibujar(datos):
    modo = datos["modo"]
    hoy = modo == "hoy"
    HORA = datos["hora"]
    P = datos["precios"]
    TEMP, LLUVIA, ICONOS = datos["temp"], datos["lluvia"], datos["iconos"]

    img = Image.new("L", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    media = sum(P) / len(P)
    desde = min(HORA, 21) if hoy else 0
    mejor_v, mejor_i = ventana(P, desde)
    peor_v, peor_i = ventana(P, desde, peor=True)

    # ---------- Cabecera ----------
    d.text((24, 10), "LUZ HOY" if hoy else "LUZ MAÑANA", font=font("SemiBold", 13), fill=DARK)
    d.text((24, 26), datos["titulo_dia"], font=font("Bold", 26), fill=BLACK)
    if datos.get("ahora_precio") is not None:
        lbl = f"AHORA · {HORA}–{HORA + 1} h"
        txt = f"{eur(datos['ahora_precio'])} €/kWh"
    else:
        lbl, txt = "MEDIA DEL DÍA", f"{eur(media)} €/kWh"
    f_lbl, f_big = font("SemiBold", 13), font("Bold", 24)
    d.text((W - 24 - d.textlength(lbl, font=f_lbl), 10), lbl, font=f_lbl, fill=DARK)
    d.text((W - 24 - d.textlength(txt, font=f_big), 28), txt, font=f_big, fill=BLACK)

    # ---------- Eje horario común ----------
    X0, X1 = 58, 776
    SLOT = (X1 - X0) / 24

    def xc(h):
        return X0 + h * SLOT + SLOT / 2

    # ---------- Gráfica de precios ----------
    y0, y1 = 84, 204
    vmax = max(0.45, math.ceil(max(P) * 20) / 20)

    def yp(v):
        return y1 - max(v, 0) / vmax * (y1 - y0)

    f_ax = font("Medium", 11)
    d.text((24, 64), "€/kWh", font=f_ax, fill=DARK)
    if not hoy:
        lab = f"media del día {eur(media)} €/kWh"
        f_m = font("SemiBold", 12)
        d.text((X1 - d.textlength(lab, font=f_m), 64), lab, font=f_m, fill=DARK)
    g = 0.1
    while g < vmax:
        yy = round(yp(g))
        for xx in range(X0, X1, 6):
            d.line([(xx, yy), (xx + 2, yy)], fill=LIGHT)
        lab = eur(g, 1)
        d.text((X0 - 8 - d.textlength(lab, font=f_ax), yy - 7), lab, font=f_ax, fill=DARK)
        g = round(g + 0.1, 2)

    bw = SLOT * 0.68
    i_min = min(range(desde, 24), key=lambda i: P[i])
    i_max = max(range(desde, 24), key=lambda i: P[i])
    f_val = font("Bold", 12)
    for i, p in enumerate(P):
        bx = xc(i) - bw / 2
        if hoy and i < HORA:  # horas ya pasadas: solo contorno
            d.rectangle([bx, yp(p), bx + bw, y1], outline=LIGHT, width=2)
            continue
        col = BLACK if mejor_i <= i < mejor_i + 3 else DARK if peor_i <= i < peor_i + 3 else LIGHT
        d.rectangle([bx, yp(p), bx + bw, y1], fill=col)
        if i in (i_min, i_max) and not (hoy and i == HORA):
            lab = eur(p, 2)
            d.text((xc(i) - d.textlength(lab, font=f_val) / 2, max(yp(p) - 16, 66)), lab, font=f_val, fill=BLACK)
        if hoy and i == HORA:
            d.rectangle([bx - 3, yp(p) - 3, bx + bw + 3, y1], outline=BLACK, width=2)
            ty = max(yp(p) - 18, 82)
            d.polygon([(xc(i) - 6, ty), (xc(i) + 6, ty), (xc(i), ty + 8)], fill=BLACK)
            d.text((xc(i) - d.textlength("ahora", font=f_val) / 2, ty - 16), "ahora", font=f_val, fill=BLACK)
    d.line([(X0, y1), (X1, y1)], fill=BLACK, width=2)
    f_h = font("Medium", 12)
    for h in range(0, 24, 3):
        lab = f"{h}h"
        d.text((xc(h) - d.textlength(lab, font=f_h) / 2, y1 + 4), lab, font=f_h, fill=DARK)

    # ---------- Iconos ----------
    def sol(cx, cy, r):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BLACK)
        for k in range(8):
            a = k * math.pi / 4
            d.line([(cx + math.cos(a) * (r + 2), cy + math.sin(a) * (r + 2)),
                    (cx + math.cos(a) * (r + 5), cy + math.sin(a) * (r + 5))], fill=BLACK, width=2)

    def luna(cx, cy, r):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BLACK)
        d.ellipse([cx - r + r * 0.7, cy - r - r * 0.3, cx + r + r * 0.7, cy + r - r * 0.3], fill=WHITE)

    def nube(cx, cy, s, col=DARK):
        partes = [(cx - s * 0.55, cy - s * 0.05, s * 0.38), (cx - s * 0.1, cy - s * 0.3, s * 0.5),
                  (cx + s * 0.45, cy - s * 0.05, s * 0.38)]
        caja = [cx - s * 0.95, cy - s * 0.1, cx + s * 0.85, cy + s * 0.35]
        for (px, py, r) in partes:
            d.ellipse([px - r - 2, py - r - 2, px + r + 2, py + r + 2], fill=BLACK)
        d.rounded_rectangle([caja[0] - 2, caja[1] - 2, caja[2] + 2, caja[3] + 2], radius=int(s * 0.2), fill=BLACK)
        for (px, py, r) in partes:
            d.ellipse([px - r, py - r, px + r, py + r], fill=col)
        d.rounded_rectangle(caja, radius=int(s * 0.2), fill=col)

    def icono(tipo, cx, cy, k=1.0):
        if tipo == "sol":
            sol(cx, cy, 9 * k)
        elif tipo == "luna":
            luna(cx, cy, 8 * k)
        elif tipo == "luna_nubes":
            luna(cx - 5 * k, cy - 5 * k, 7 * k); nube(cx + 5 * k, cy + 5 * k, 12 * k, col=WHITE)
        elif tipo == "poco_nuboso":
            sol(cx - 5 * k, cy - 6 * k, 8 * k); nube(cx + 6 * k, cy + 6 * k, 13 * k, col=WHITE)
        elif tipo == "nubes":
            nube(cx, cy, 17 * k, col=LIGHT)
        else:  # lluvia
            nube(cx, cy - 5 * k, 16 * k, col=DARK)
            for o in (-8, 0, 8):
                d.line([(cx + o * k, cy + 9 * k), (cx + o * k - 4 * k, cy + 17 * k)], fill=BLACK, width=2)

    def gota(x, yy, col=DARK):
        d.polygon([(x + 4, yy), (x, yy + 7), (x + 8, yy + 7)], fill=col)
        d.ellipse([x, yy + 4, x + 8, yy + 12], fill=col)

    # ---------- Tiempo del día mostrado, por horas ----------
    f_t = font("SemiBold", 13)
    d.text((24, 226), "HOY" if hoy else datos["titulo_dia"][:3].upper(), font=font("SemiBold", 11), fill=DARK)
    for h, tipo in sorted(ICONOS.items()):
        icono(tipo, xc(h), 240, k=0.7)
        lab = f"{round(TEMP[h])}°"
        d.text((xc(h) - d.textlength(lab, font=f_t) / 2, 254), lab, font=f_t,
               fill=LIGHT if hoy and h + 3 <= HORA else BLACK)
    tmin, tmax = min(TEMP), max(TEMP)
    ya, yb = 278, 302

    def yt(t):
        return yb - (t - tmin) / max(tmax - tmin, 1) * (yb - ya)

    pts = [(xc(h), yt(t)) for h, t in enumerate(TEMP)]
    corte = HORA if hoy else 0
    if corte:
        d.line(pts[:corte + 1], fill=LIGHT, width=3)
    d.line(pts[corte:], fill=BLACK, width=3)
    for h in (TEMP.index(tmin), TEMP.index(tmax)):
        x, yy = pts[h]
        d.ellipse([x - 4, yy - 4, x + 4, yy + 4], fill=BLACK)
    d.text((24, 282), "°C", font=f_ax, fill=DARK)
    rb, rh = 330, 22
    d.text((24, 315), "lluvia", font=f_ax, fill=DARK)
    for h, ll in enumerate(LLUVIA):
        if ll:
            d.rectangle([xc(h) - bw / 2, rb - rh * ll / 100, xc(h) + bw / 2, rb], fill=LIGHT)
    if max(LLUVIA) > 0:
        hm = LLUVIA.index(max(LLUVIA))
        lab = f"{round(max(LLUVIA))} %"
        f_ll = font("SemiBold", 11)
        d.text((xc(hm) - d.textlength(lab, font=f_ll) / 2, rb - rh * max(LLUVIA) / 100 - 14), lab, font=f_ll, fill=DARK)
    d.line([(X0, rb), (X1, rb)], fill=LIGHT, width=1)
    if hoy:
        for yy in range(272, rb, 5):
            d.line([(xc(HORA), yy), (xc(HORA), yy + 2)], fill=DARK, width=1)

    # ---------- Mejor / evitar ----------
    yc = 338

    def caja(xa, xb, titulo, horas, precio, relleno):
        if relleno:
            d.rounded_rectangle([xa, yc, xb, yc + 46], radius=8, fill=BLACK)
            c1 = c2 = WHITE
        else:
            d.rounded_rectangle([xa, yc, xb, yc + 46], radius=8, outline=BLACK, width=3)
            c1, c2 = DARK, BLACK
        d.text((xa + 14, yc + 6), titulo, font=font("SemiBold", 12), fill=c1)
        d.text((xa + 14, yc + 19), horas, font=font("Bold", 21), fill=c2)
        t = f"{eur(precio)} €/kWh"
        fp = font("SemiBold", 17)
        d.text((xb - 14 - d.textlength(t, font=fp), yc + 22), t, font=fp, fill=c2)

    caja(24, 392, "PRÓXIMO TRAMO BARATO" if hoy else "MEJOR TRAMO MAÑANA", f"{mejor_i}–{mejor_i + 3} h", mejor_v, True)
    caja(408, 776, "EVITAR" if hoy else "EVITAR MAÑANA", f"{peor_i}–{peor_i + 3} h", peor_v, False)

    # ---------- Próximos días ----------
    d.line([(24, 392), (776, 392)], fill=LIGHT, width=1)
    for k, (dia, tipo, tmx, tmn, ll) in enumerate(datos["semana"][:5]):
        cx = 24 + k * 108
        d.text((cx, 400), dia, font=font("SemiBold", 15), fill=BLACK)
        icono(tipo, cx + 20, 440)
        d.text((cx + 46, 418), f"{tmx}°", font=font("Bold", 21), fill=BLACK)
        d.text((cx + 48, 444), f"{tmn}°", font=font("Medium", 15), fill=DARK)
        gota(cx + 46, 404)
        d.text((cx + 58, 401), f"{round(ll)} %", font=font("Medium", 12), fill=DARK)

    # ---------- Panel local (lo dibuja la pantalla; aquí solo en las vistas previas) ----------
    xr = PANEL_LOCAL[0] + 12
    d.line([(xr - 12, 400), (xr - 12, 468)], fill=LIGHT, width=1)
    pl = datos.get("panel_local")
    if pl:
        d.text((xr, 400), "COCINA", font=font("SemiBold", 13), fill=DARK)
        d.text((xr, 416), f"{eur(pl['temp'], 1)}°", font=font("Bold", 30), fill=BLACK)
        d.text((xr + 92, 426), f"{pl['hum']} %", font=font("Medium", 15), fill=DARK)
        d.text((xr + 92, 444), "humedad", font=font("Medium", 11), fill=DARK)
        bx, by = 690, 403
        d.rectangle([bx, by, bx + 26, by + 12], outline=DARK, width=2)
        d.rectangle([bx + 26, by + 4, bx + 29, by + 8], fill=DARK)
        d.rectangle([bx + 3, by + 3, bx + 3 + int(20 * pl["bat"] / 100), by + 9], fill=DARK)
        d.text((bx + 34, by - 2), f"{pl['bat']} %", font=font("Medium", 12), fill=DARK)
        d.text((xr, 458), f"Actualizado {pl['hora']}", font=font("Medium", 11), fill=DARK)

    return img.point(lambda v: min(GRISES, key=lambda c: abs(c - v)))


def a_bin(img):
    """Empaqueta la imagen en 2 bits por píxel (4 píxeles por byte, el primero en los bits altos).

    Valores: 0 = negro, 1 = gris oscuro, 2 = gris claro, 3 = blanco. Filas de 800 píxeles = 200 bytes.
    """
    nivel = {BLACK: 0, DARK: 1, LIGHT: 2, WHITE: 3}
    px = img.load()
    out = bytearray()
    for y in range(H):
        for x in range(0, W, 4):
            b = 0
            for k in range(4):
                b = (b << 2) | nivel[px[x + k, y]]
            out.append(b)
    return bytes(out)


# ---------------------------------------------------------------------------
# Datos de ejemplo para vistas previas sin conexión
# ---------------------------------------------------------------------------
def ejemplo(modo="hoy", hora=9):
    hoy_p = [0.2126, 0.2130, 0.2130, 0.2130, 0.2138, 0.2203, 0.2410, 0.3002, 0.2667, 0.1711, 0.1612, 0.1246,
             0.1216, 0.1223, 0.0496, 0.0704, 0.1606, 0.2818, 0.3876, 0.4010, 0.4055, 0.3855, 0.2678, 0.2562]
    man_p = [0.190, 0.191, 0.180, 0.174, 0.174, 0.179, 0.205, 0.272, 0.341, 0.252, 0.175, 0.089,
             0.088, 0.088, 0.018, 0.019, 0.019, 0.097, 0.320, 0.393, 0.418, 0.417, 0.323, 0.293]
    t_hoy = [16.0, 15.5, 15.0, 14.6, 14.3, 14.0, 13.9, 14.2, 15.5, 17.5, 19.5, 21.0,
             22.3, 23.2, 23.8, 24.0, 23.5, 22.3, 20.6, 19.2, 18.3, 17.6, 17.0, 16.5]
    t_man = [15.8, 15.2, 14.7, 14.3, 14.0, 13.7, 13.5, 13.8, 15.0, 16.8, 18.6, 20.0,
             21.0, 21.7, 22.0, 22.1, 21.6, 20.5, 19.0, 17.8, 17.0, 16.4, 15.9, 15.5]
    ll_hoy = [5, 5, 5, 5, 0, 0, 0, 0, 0, 5, 5, 10, 10, 15, 25, 35, 40, 30, 20, 10, 5, 5, 5, 5]
    ll_man = [10, 10, 15, 20, 25, 30, 35, 40, 45, 40, 30, 20, 15, 10, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5]
    i_hoy = {0: "luna", 3: "luna", 6: "luna_nubes", 9: "poco_nuboso", 12: "nubes", 15: "nubes", 18: "poco_nuboso", 21: "luna"}
    i_man = {0: "luna_nubes", 3: "nubes", 6: "lluvia", 9: "lluvia", 12: "nubes", 15: "poco_nuboso", 18: "poco_nuboso", 21: "luna"}
    semana = [("Mar", "lluvia", 22, 13, 45), ("Mié", "poco_nuboso", 23, 13, 10), ("Jue", "poco_nuboso", 24, 14, 5),
              ("Vie", "poco_nuboso", 26, 15, 5), ("Sáb", "lluvia", 24, 14, 80), ("Dom", "nubes", 24, 13, 35)]
    base = {"modo": modo, "hora": hora, "ahora_precio": hoy_p[hora],
            "panel_local": {"temp": 21.4, "hum": 58, "bat": 87, "hora": f"{hora:02d}:02"}}
    if modo == "hoy":
        return {**base, "titulo_dia": "Lunes 26 oct", "precios": hoy_p, "temp": t_hoy, "lluvia": ll_hoy,
                "iconos": i_hoy, "semana": semana[:5]}
    return {**base, "titulo_dia": "Martes 27 oct", "precios": man_p, "temp": t_man, "lluvia": ll_man,
            "iconos": i_man, "semana": semana[1:6]}


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--ejemplo":
        modo = sys.argv[3] if len(sys.argv) > 3 else "hoy"
        hora = int(sys.argv[4]) if len(sys.argv) > 4 else (9 if modo == "hoy" else 21)
        dibujar(ejemplo(modo, hora)).save(sys.argv[2])
        print("ok", sys.argv[2])
    else:
        print(__doc__)
