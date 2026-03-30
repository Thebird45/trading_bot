"""
============================================
TRADING BOT PRO — Fase 6: Paper Trading
============================================
Simula operaciones en tiempo real usando datos
del mercado en vivo, sin arriesgar dinero real.
Usa los parámetros optimizados de la Fase 5.

Uso:
    python fase6_paper_trading.py

Presiona Ctrl+C para detener.
"""

import ccxt
import pandas as pd
import ta
import json
import os
import time
import threading
from datetime import datetime, timezone
from loguru import logger
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============================================
# MINI SERVIDOR WEB (para que Render no duerma)
# ============================================

class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Trading Bot PRO - Fase 6 corriendo!")

    def log_message(self, format, *args):
        pass  # silenciar logs del servidor


def iniciar_servidor_web():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    server.serve_forever()


# ============================================
# CONFIGURACIÓN
# ============================================
SIMBOLO          = "BTC/USDT"
TIMEFRAME        = "1h"
CAPITAL_INICIAL  = 10_000.0     # USD simulados
RIESGO_POR_TRADE = 0.10
COMISION_PCT     = 0.001
INTERVALO_SEG    = 60           # revisar cada 60 segundos

# Cargar parámetros optimizados
PARAMS_FILE = "datos/mejores_params.json"

def cargar_params():
    if os.path.exists(PARAMS_FILE):
        with open(PARAMS_FILE) as f:
            p = json.load(f)
        logger.info(f"Parámetros cargados desde {PARAMS_FILE}")
        return p
    else:
        logger.warning("No se encontró mejores_params.json — usando parámetros por defecto")
        return {
            "rsi_periodo"    : 21,
            "rsi_sobreventa" : 30,
            "rsi_sobrecompra": 70,
            "stop_loss"      : 0.03,
            "take_profit"    : 0.06,
        }

# ============================================
# ESTADO DEL BOT
# ============================================
class EstadoBot:
    def __init__(self, capital):
        self.capital       = capital
        self.en_posicion   = False
        self.precio_entrada= 0.0
        self.stop_loss     = 0.0
        self.take_profit   = 0.0
        self.fecha_entrada = None
        self.trades        = []
        self.velas_vistas  = 0

    def abrir_posicion(self, precio, fecha, sl_pct, tp_pct):
        self.en_posicion    = True
        self.precio_entrada = precio
        self.fecha_entrada  = fecha
        self.stop_loss      = precio * (1 - sl_pct)
        self.take_profit    = precio * (1 + tp_pct)

    def cerrar_posicion(self, precio_salida, razon):
        tam     = (self.capital * RIESGO_POR_TRADE) / self.precio_entrada
        comision= tam * precio_salida * COMISION_PCT
        pnl     = tam * (precio_salida - self.precio_entrada) - comision
        self.capital += pnl
        self.en_posicion = False

        trade = {
            "entrada"       : self.fecha_entrada.strftime("%Y-%m-%d %H:%M"),
            "salida"        : datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "precio_entrada": self.precio_entrada,
            "precio_salida" : precio_salida,
            "razon"         : razon,
            "pnl"           : round(pnl, 2),
            "capital"       : round(self.capital, 2),
        }
        self.trades.append(trade)
        return pnl

    def resumen(self):
        if not self.trades:
            return
        df = pd.DataFrame(self.trades)
        wins = df[df["pnl"] > 0]
        return {
            "total"      : len(df),
            "ganadores"  : len(wins),
            "win_rate"   : len(wins)/len(df)*100,
            "pnl_total"  : df["pnl"].sum(),
            "capital"    : self.capital,
        }

    def guardar_log(self):
        os.makedirs("datos", exist_ok=True)
        if self.trades:
            pd.DataFrame(self.trades).to_csv(
                "datos/paper_trading_log.csv", index=False
            )


# ============================================
# FUNCIONES DE MERCADO
# ============================================

# ============================================
# FUNCIONES DE MERCADO
# ============================================
def crear_exchange():
    return ccxt.binance({
        'enableRateLimit': True,          # ← Esto evita que te baneen por rate limit
        'options': {
            'defaultType': 'spot',
        }
    })


def obtener_velas(exchange, simbolo, timeframe, limite=150):
    """Descarga las últimas N velas del exchange."""
    try:
        velas = exchange.fetch_ohlcv(simbolo, timeframe=timeframe, limit=limite)
        df = pd.DataFrame(velas, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("datetime").drop(columns=["timestamp"])
        return df
    except Exception as e:
        logger.error(f"Error al obtener velas: {e}")
        time.sleep(10)   # espera antes de reintentar
        raise  # para que el bucle principal lo maneje
    return df


def calcular_rsi(df, periodo):
    return ta.momentum.RSIIndicator(close=df["close"], window=periodo).rsi()


def detectar_senal(df, params):
    """Detecta señal en la vela más reciente."""
    rsi = calcular_rsi(df, params["rsi_periodo"])
    rsi_actual   = rsi.iloc[-1]
    rsi_anterior = rsi.iloc[-2]

    senal = 0
    if rsi_actual < params["rsi_sobreventa"] and rsi_anterior >= params["rsi_sobreventa"]:
        senal = 1   # COMPRA
    elif rsi_actual > params["rsi_sobrecompra"] and rsi_anterior <= params["rsi_sobrecompra"]:
        senal = -1  # VENTA

    return senal, rsi_actual


# ============================================
# DISPLAY EN CONSOLA
# ============================================

def limpiar():
    os.system("cls" if os.name == "nt" else "clear")


def mostrar_estado(estado, precio_actual, rsi, senal, params, ciclo):
    limpiar()
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    print("╔══════════════════════════════════════════════╗")
    print("║      TRADING BOT PRO — Paper Trading         ║")
    print("╚══════════════════════════════════════════════╝")
    print(f"  🕐 {ahora}   Ciclo #{ciclo}")
    print(f"  📊 {SIMBOLO} · {TIMEFRAME}")
    print()

    retorno = (estado.capital / CAPITAL_INICIAL - 1) * 100
    signo   = "+" if retorno >= 0 else ""
    print(f"  💰 Capital : ${estado.capital:>10,.2f}  ({signo}{retorno:.2f}%)")
    print()

    # RSI
    if rsi < params["rsi_sobreventa"]:
        zona_rsi = "🟢 SOBREVENTA"
    elif rsi > params["rsi_sobrecompra"]:
        zona_rsi = "🔴 SOBRECOMPRA"
    else:
        zona_rsi = "🟡 NEUTRAL"

    print(f"  📈 BTC/USDT : ${precio_actual:>12,.2f}")
    print(f"  📉 RSI({params['rsi_periodo']})  :  {rsi:>6.1f}  {zona_rsi}")
    print()

    # Posición actual
    if estado.en_posicion:
        pnl_actual = (precio_actual / estado.precio_entrada - 1) * 100
        signo_pnl  = "+" if pnl_actual >= 0 else ""
        print(f"  🔵 POSICIÓN ABIERTA")
        print(f"     Entrada    : ${estado.precio_entrada:>10,.2f}")
        print(f"     Stop Loss  : ${estado.stop_loss:>10,.2f}  ({params['stop_loss']*100:.1f}%)")
        print(f"     Take Profit: ${estado.take_profit:>10,.2f}  ({params['take_profit']*100:.1f}%)")
        print(f"     P&L actual : {signo_pnl}{pnl_actual:.2f}%")
    else:
        print(f"  ⚪ Sin posición abierta — esperando señal")

    # Señal actual
    print()
    if senal == 1:
        print(f"  🚀 SEÑAL: COMPRA detectada")
    elif senal == -1:
        print(f"  🛑 SEÑAL: VENTA detectada")
    else:
        print(f"  ⏳ Sin señal nueva")

    # Historial de trades
    print()
    print(f"  ─────────────────────────────────────────")
    if estado.trades:
        print(f"  Últimos trades:")
        for t in estado.trades[-5:]:
            emoji = "✅" if t["pnl"] > 0 else "❌"
            print(f"  {emoji} {t['entrada']} → ${t['pnl']:+.2f}  [{t['razon']}]")

        r = estado.resumen()
        print(f"\n  Operaciones: {r['total']}  |  Win Rate: {r['win_rate']:.0f}%  |  P&L total: ${r['pnl_total']:+.2f}")
    else:
        print(f"  Sin trades aún — esperando primera señal")

    print(f"  ─────────────────────────────────────────")
    print(f"\n  [Ctrl+C para detener y guardar reporte]")


# ============================================
# BUCLE PRINCIPAL
# ============================================

def main():
    # Iniciar servidor web en hilo separado (necesario para Render)
    threading.Thread(target=iniciar_servidor_web, daemon=True).start()
    logger.info("Servidor web iniciado para mantener el servicio activo")

    params  = cargar_params()
    estado  = EstadoBot(CAPITAL_INICIAL)
    exchange= crear_exchange()
    ciclo   = 0

    logger.remove()  # silenciar loguru en consola durante el display
    os.makedirs("logs", exist_ok=True)
    logger.add("logs/paper_trading.log", rotation="1 day", level="INFO")

    logger.info("="*50)
    logger.info("Paper Trading iniciado")
    logger.info(f"Parámetros: {params}")
    logger.info(f"Capital inicial: ${CAPITAL_INICIAL:,.2f}")

    print(f"\n  Iniciando Paper Trading en {SIMBOLO}...")
    print(f"  Parámetros: RSI({params['rsi_periodo']}) | "
          f"SV:{params['rsi_sobreventa']} | SC:{params['rsi_sobrecompra']} | "
          f"SL:{params['stop_loss']*100:.1f}% | TP:{params['take_profit']*100:.1f}%")
    print(f"\n  Descargando datos iniciales...")
    time.sleep(2)

    try:
        while True:
            ciclo += 1

            # Obtener datos frescos
            df     = obtener_velas(exchange, SIMBOLO, TIMEFRAME, limite=150)
            precio = df["close"].iloc[-1]

            # Detectar señal
            senal, rsi = detectar_senal(df, params)

            # Lógica de posición
            if estado.en_posicion:
                razon = None
                salida = None

                if precio <= estado.stop_loss:
                    salida, razon = estado.stop_loss, "Stop Loss"
                elif precio >= estado.take_profit:
                    salida, razon = estado.take_profit, "Take Profit"
                elif senal == -1:
                    salida, razon = precio, "Señal RSI"

                if razon:
                    pnl = estado.cerrar_posicion(salida, razon)
                    logger.info(f"CIERRE [{razon}] P&L: ${pnl:+.2f} | Capital: ${estado.capital:,.2f}")

            if not estado.en_posicion and senal == 1:
                estado.abrir_posicion(
                    precio,
                    datetime.now(timezone.utc),
                    params["stop_loss"],
                    params["take_profit"],
                )
                logger.info(f"APERTURA @ ${precio:,.2f} | SL:${estado.stop_loss:,.2f} | TP:${estado.take_profit:,.2f}")

            # Mostrar estado en consola
            mostrar_estado(estado, precio, rsi, senal, params, ciclo)
            estado.guardar_log()

            time.sleep(INTERVALO_SEG)

    except KeyboardInterrupt:
        print("\n\n  🛑 Paper Trading detenido por el usuario.")
        estado.guardar_log()

        r = estado.resumen()
        if r:
            print(f"\n  ══ RESUMEN FINAL ══")
            print(f"  Operaciones : {r['total']}")
            print(f"  Win Rate    : {r['win_rate']:.1f}%")
            print(f"  P&L Total   : ${r['pnl_total']:+,.2f}")
            print(f"  Capital     : ${r['capital']:,.2f}")
        else:
            print(f"\n  Sin operaciones registradas.")

        print(f"\n  Log guardado en: datos/paper_trading_log.csv")
        print(f"  Log detallado : logs/paper_trading.log\n")


if __name__ == "__main__":
    main()