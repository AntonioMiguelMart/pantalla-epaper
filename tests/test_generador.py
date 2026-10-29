"""Pruebas sin conexión: simulan las respuestas de las APIs.  Ejecutar:  python -m unittest discover tests"""
import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generador"))
import datos  # noqa: E402
import main  # noqa: E402
from render import H, W  # noqa: E402

TZ = datos.TZ


def redata_respuesta(dia, cada_min=60, base=200.0):
    """Respuesta tipo REData con los instantes reales del día (incluye días de 23 y 25 horas)."""
    inicio = datetime(dia.year, dia.month, dia.day, tzinfo=TZ)
    fin = inicio + timedelta(days=1)
    vals, t = [], inicio.astimezone(datos.ZoneInfo("UTC"))
    while t < fin.astimezone(datos.ZoneInfo("UTC")):
        loc = t.astimezone(TZ)
        vals.append({"value": base + loc.hour, "datetime": loc.isoformat(timespec="milliseconds")})
        t += timedelta(minutes=cada_min)
    return {"included": [
        {"type": "Precio mercado spot (€/MWh)", "attributes": {"title": "Precio mercado spot (€/MWh)", "values": []}},
        {"type": "PVPC (€/MWh)", "attributes": {"title": "PVPC (€/MWh)", "values": vals}},
    ]}


def openmeteo_respuesta(hoy):
    times, temp, ll, code, isday = [], [], [], [], []
    for k in range(7):
        f = hoy + timedelta(days=k)
        for h in range(24):
            times.append(f"{f.isoformat()}T{h:02d}:00")
            temp.append(14 + 10 * max(0, 1 - abs(h - 15) / 9))
            ll.append(10 if h in (15, 16) else 0)
            code.append(3 if h % 2 else 1)
            isday.append(1 if 8 <= h <= 18 else 0)
    days = [(hoy + timedelta(days=k)).isoformat() for k in range(7)]
    return {"hourly": {"time": times, "temperature_2m": temp, "precipitation_probability": ll,
                       "weather_code": code, "is_day": isday},
            "daily": {"time": days, "weather_code": [61, 1, 2, 3, 0, 80, 1],
                      "temperature_2m_max": [22.4] * 7, "temperature_2m_min": [12.6] * 7,
                      "precipitation_probability_max": [60, 5, 10, 30, 0, 80, 5]}}


class TestPrecios(unittest.TestCase):
    def test_dia_normal(self):
        dia = date(2026, 10, 29)
        with mock.patch.object(datos, "_get_json", return_value=redata_respuesta(dia)):
            p, fuente = datos.precios_pvpc(dia)
        self.assertEqual(fuente, "REData")
        self.assertEqual(len(p), 24)
        self.assertAlmostEqual(p[0], 0.200)
        self.assertAlmostEqual(p[23], 0.223)

    def test_cuartos_de_hora(self):
        dia = date(2026, 10, 29)
        with mock.patch.object(datos, "_get_json", return_value=redata_respuesta(dia, cada_min=15)):
            p, _ = datos.precios_pvpc(dia)
        self.assertEqual(len(p), 24)
        self.assertAlmostEqual(p[10], 0.210)

    def test_dia_de_25_horas(self):  # cambio al horario de invierno
        dia = date(2026, 10, 25)
        r = redata_respuesta(dia)
        self.assertEqual(len(r["included"][1]["attributes"]["values"]), 25)
        with mock.patch.object(datos, "_get_json", return_value=r):
            p, _ = datos.precios_pvpc(dia)
        self.assertEqual(len(p), 24)
        self.assertAlmostEqual(p[2], 0.202)

    def test_dia_de_23_horas(self):  # cambio al horario de verano
        dia = date(2027, 3, 28)
        r = redata_respuesta(dia)
        self.assertEqual(len(r["included"][1]["attributes"]["values"]), 23)
        with mock.patch.object(datos, "_get_json", return_value=r):
            p, _ = datos.precios_pvpc(dia)
        self.assertEqual(len(p), 24)
        self.assertAlmostEqual(p[2], p[1])

    def test_sin_publicar_prueba_siguiente_fuente(self):
        dia = date(2026, 10, 30)
        archivo = {"PVPC": [{"Dia": "30/10/2026", "Hora": f"{h:02d}-{h + 1:02d}", "PCB": f"{150 + h},50"}
                            for h in range(24)]}

        def falso(url, headers=None, timeout=30):
            if "apidatos" in url:
                raise OSError("HTTP 404")
            return archivo

        with mock.patch.object(datos, "_get_json", side_effect=falso):
            p, fuente = datos.precios_pvpc(dia)
        self.assertEqual(fuente, "ESIOS archivo")
        self.assertAlmostEqual(p[3], 0.1535)

    def test_nada_disponible(self):
        with mock.patch.object(datos, "_get_json", side_effect=OSError("sin red")):
            p, motivo = datos.precios_pvpc(date(2026, 10, 30))
        self.assertIsNone(p)
        self.assertIn("REData", motivo)


class TestMain(unittest.TestCase):
    def ejecutar(self, momento, manana_publicado):
        hoy = momento.date()

        def falso(url, headers=None, timeout=30):
            if "open-meteo" in url:
                return openmeteo_respuesta(hoy)
            dia = date.fromisoformat(url.split("start_date=")[1][:10])
            if dia > hoy and not manana_publicado:
                raise OSError("HTTP 404")
            return redata_respuesta(dia, base=100.0 + 50 * (dia - hoy).days)

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(datos, "_get_json", side_effect=falso), \
                mock.patch.object(main, "ahora", return_value=momento), \
                mock.patch.object(sys, "argv", ["main.py", "--salida", tmp]):
            self.assertEqual(main.main(), 0)
            with open(os.path.join(tmp, "estado.json"), encoding="utf-8") as fh:
                estado = json.load(fh)
            tam = os.path.getsize(os.path.join(tmp, "pantalla.bin"))
            from PIL import Image
            img = Image.open(os.path.join(tmp, "pantalla.png"))
            grises = sorted(c for _, c in img.getcolors())
            self.assertTrue(os.path.exists(os.path.join(tmp, "index.html")))
        return estado, tam, img.size, grises

    def test_manana_por_la_mañana_modo_hoy(self):
        estado, tam, size, grises = self.ejecutar(datetime(2026, 10, 29, 9, 2, tzinfo=TZ), False)
        self.assertEqual(estado["modo"], "hoy")
        self.assertEqual(tam, W * H // 4)
        self.assertEqual(size, (W, H))
        self.assertTrue(set(grises) <= {0, 85, 170, 255})

    def test_tarde_sin_publicar(self):
        estado, *_ = self.ejecutar(datetime(2026, 10, 29, 20, 2, tzinfo=TZ), False)
        self.assertEqual(estado["modo"], "hoy")

    def test_tarde_publicado(self):
        estado, *_ = self.ejecutar(datetime(2026, 10, 29, 20, 22, tzinfo=TZ), True)
        self.assertEqual(estado["modo"], "manana")
        self.assertEqual(estado["dia"], "2026-10-30")

    def test_ultima_hora(self):
        estado, *_ = self.ejecutar(datetime(2026, 10, 29, 23, 2, tzinfo=TZ), True)
        self.assertEqual(estado["modo"], "manana")


if __name__ == "__main__":
    unittest.main()
