# Firmware de la pantalla (pendiente)

Se escribirá cuando llegue la reTerminal E1001. Comportamiento previsto:

1. **Despertar** (deep sleep del ESP32-S3):
   - de 7:00 a 20:00, cada hora en el minuto 4;
   - de 20:00 a 21:30, cada 5 minutos (para mostrar los precios de mañana en cuanto se publiquen);
   - de 0:00 a 7:00, nada;
   - el botón de actualizar fuerza un despertar.
2. **Conectar al WiFi** (solo 2,4 GHz) y sincronizar la hora por NTP.
3. **Descargar `estado.json`** y comparar `version` con la guardada en memoria RTC.
   - Si no ha cambiado: dormir sin redibujar.
   - Si ha cambiado: descargar `pantalla.bin` (96.000 bytes) a la PSRAM.
4. **Leer el sensor** de temperatura y humedad y la tensión de la batería, y **dibujar** la imagen en 4 grises más el recuadro local (`panel_local` en `estado.json`): cocina, batería y hora de actualización.
5. **Dormir** hasta el siguiente despertar.

Para programarla: Arduino IDE con el paquete de placas ESP32 de Espressif, placa `XIAO_ESP32S3`, PSRAM `OPI PSRAM`. Librería `Seeed_GxEPD2` (ejemplo `GxEPD2_reTerminal_E1001`) o `Seeed_GFX`. Configuración en un `secrets.h` (WiFi y URL), que no se sube al repositorio.
