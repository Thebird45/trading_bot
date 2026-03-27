"""
============================================
TRADING BOT PRO — Fase 2: Obtención de Datos OHLCV
============================================
Descarga datos históricos de Bybit y los guarda
en un archivo CSV listo para analizar.

Uso:
    python fase2_datos.py
"""

import ccxt
import pandas as pd
from datetime import datetime, timezone
import os
import time

# ============================================
# CONFIGURACIÓN
# ============================================
EXCHANGE_ID  = "bybit"
SIMBOLO      = "BTC/USDT"
TIMEFRAME    = "1h"          # 1m, 5m, 15m, 1h, 4h, 1d
DIAS_HISTORIAL = 180         # cuántos días hacia atrás descargar
CARPETA_DATOS  = "datos"     # carpeta donde se guardan los CSV


# ============================================
# FUNCIONES
# ============================================

def crear_exchange():
    """Crea la conexión al exchange (sin API key — solo datos públicos)."""
    exchange = ccxt.bybit({
        "options": {"defaultType": "spot"},
        "enableRateLimit": True,
    })
    return exchange


def descargar_datos(exchange, simbolo, timeframe, dias):
    """
    Descarga datos OHLCV históricos en lotes de 1000 velas.
    Bybit permite máximo 1000 velas por petición.
    """
    print(f"\n📥 Descargando {simbolo} · timeframe {timeframe} · {dias} días...")

    # Calcular timestamp de inicio
    ms_por_dia = 24 * 60 * 60 * 1000
    ahora_ms   = exchange.milliseconds()
    desde_ms   = ahora_ms - (dias * ms_por_dia)

    todas_las_velas = []
    lote            = 1

    while desde_ms < ahora_ms:
        try:
            velas = exchange.fetch_ohlcv(
                simbolo,
                timeframe=timeframe,
                since=desde_ms,
                limit=1000,
            )

            if not velas:
                break

            todas_las_velas.extend(velas)
            desde_ms = velas[-1][0] + 1  # siguiente vela después de la última

            fecha_actual = datetime.fromtimestamp(
                velas[-1][0] / 1000, tz=timezone.utc
            ).strftime("%Y-%m-%d")

            print(f"  Lote {lote:>3} — {len(velas):>4} velas — hasta {fecha_actual}")
            lote += 1

            time.sleep(exchange.rateLimit / 1000)  # respetar límite de la API

        except Exception as e:
            print(f"  ⚠️  Error en lote {lote}: {e}")
            time.sleep(2)
            break

    return todas_las_velas


def velas_a_dataframe(velas):
    """Convierte la lista de velas a un DataFrame de pandas limpio."""
    df = pd.DataFrame(
        velas,
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )

    # Convertir timestamp a fecha legible
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("datetime")
    df = df.drop(columns=["timestamp"])

    # Tipos de datos correctos
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    # Eliminar duplicados y ordenar
    df = df[~df.index.duplicated(keep="last")]
    df = df.sort_index()

    return df


def guardar_csv(df, simbolo, timeframe):
    """Guarda el DataFrame como CSV en la carpeta de datos."""
    os.makedirs(CARPETA_DATOS, exist_ok=True)

    nombre = simbolo.replace("/", "_")
    ruta   = os.path.join(CARPETA_DATOS, f"{nombre}_{timeframe}.csv")

    df.to_csv(ruta)
    return ruta


def mostrar_resumen(df, ruta):
    """Muestra un resumen de los datos descargados."""
    print(f"\n{'='*50}")
    print(f"  ✅ Datos descargados correctamente")
    print(f"{'='*50}")
    print(f"  Archivo   : {ruta}")
    print(f"  Total velas : {len(df):,}")
    print(f"  Desde     : {df.index[0].strftime('%Y-%m-%d %H:%M')}")
    print(f"  Hasta     : {df.index[-1].strftime('%Y-%m-%d %H:%M')}")
    print(f"  Precio mín: ${df['low'].min():,.2f}")
    print(f"  Precio máx: ${df['high'].max():,.2f}")
    print(f"  Precio actual: ${df['close'].iloc[-1]:,.2f}")
    print(f"\n  Primeras 5 filas:")
    print(df.head().to_string())
    print(f"\n{'='*50}")
    print(f"  Listo. Ejecuta la Fase 3: python fase3_estrategia.py")
    print(f"{'='*50}\n")


# ============================================
# EJECUCIÓN PRINCIPAL
# ============================================

if __name__ == "__main__":
    print("\n" + "="*50)
    print("  TRADING BOT PRO — Fase 2: Datos OHLCV")
    print("="*50)

    exchange = crear_exchange()
    velas    = descargar_datos(exchange, SIMBOLO, TIMEFRAME, DIAS_HISTORIAL)

    if not velas:
        print("\n❌ No se pudieron descargar datos. Verifica tu conexión.")
        exit(1)

    df   = velas_a_dataframe(velas)
    ruta = guardar_csv(df, SIMBOLO, TIMEFRAME)
    mostrar_resumen(df, ruta)
