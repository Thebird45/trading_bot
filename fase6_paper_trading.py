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
import sys
import time
from datetime import datetime, timezone
from loguru import logger


# ============================================
# CONFIGURACIÓN
# ============================================
SIMBOLO          = "BTC/USDT"
TIMEFRAME        = "1h"
CAPITAL_INICIAL  = 10_000.0     # USD simulados
RIESGO_POR_TRADE = 0.10
COMISION_PCT     = 0.001

# Cargar parámetros optimizados
PARAMS_FILE = "datos/mejores_params.json"
ESTADO_FILE = "datos/estado_bot.json"


def configurar_logger():
    os.makedirs("logs", exist_ok=True)
    logger.remove()
    logger.add(sys.stdout, level="INFO", enqueue=True)
    logger.add("logs/paper_trading.log", rotation="1 day", level="INFO", enqueue=True)

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

    def to_dict(self):
        return {
            "capital": self.capital,
            "en_posicion": self.en_posicion,
            "precio_entrada": self.precio_entrada,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "fecha_entrada": self.fecha_entrada.isoformat() if self.fecha_entrada else None,
            "trades": self.trades,
            "velas_vistas": self.velas_vistas,
        }

    @classmethod
    def from_dict(cls, data):
        estado = cls(data.get("capital", CAPITAL_INICIAL))
        estado.en_posicion = data.get("en_posicion", False)
        estado.precio_entrada = data.get("precio_entrada", 0.0)
        estado.stop_loss = data.get("stop_loss", 0.0)
        estado.take_profit = data.get("take_profit", 0.0)
        fecha_entrada = data.get("fecha_entrada")
        estado.fecha_entrada = datetime.fromisoformat(fecha_entrada) if fecha_entrada else None
        estado.trades = data.get("trades", [])
        estado.velas_vistas = data.get("velas_vistas", 0)
        return estado


def cargar_estado():
    os.makedirs("datos", exist_ok=True)
    if not os.path.exists(ESTADO_FILE):
        logger.info("No se encontró estado previo; iniciando bot desde cero")
        return EstadoBot(CAPITAL_INICIAL)

    with open(ESTADO_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info(f"Estado cargado desde {ESTADO_FILE}")
    return EstadoBot.from_dict(data)


def guardar_estado(estado):
    os.makedirs("datos", exist_ok=True)
    with open(ESTADO_FILE, "w", encoding="utf-8") as f:
        json.dump(estado.to_dict(), f, indent=2)
    logger.info(f"Estado guardado en {ESTADO_FILE}")


# ============================================
# FUNCIONES DE MERCADO
# ============================================

# ============================================
# FUNCIONES DE MERCADO
# ============================================
def crear_exchange(max_retries=3):
    """Crea el exchange con reconexión automática"""
    for intento in range(max_retries):
        try:
            exchange = ccxt.binance({
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',
                },
                'timeout': 30000,        # 30 segundos
            })
            # Prueba ligera de conexión
            markets = exchange.load_markets()
            logger.info(f"✅ Conexión exitosa con Binance (intento {intento+1})")
            return exchange
        except Exception as e:
            logger.warning(f"⚠️ Intento de conexión {intento+1}/{max_retries} fallido: {e}")
            if intento < max_retries - 1:
                time.sleep(5)
    logger.error("❌ No se pudo conectar con Binance después de varios intentos")
    raise Exception("Fallo crítico de conexión con Binance")


def obtener_velas(exchange, simbolo, timeframe, limite=150):
    """Obtiene velas con reconexión y backoff"""
    max_intentos = 3
    for intento in range(max_intentos):
        try:
            velas = exchange.fetch_ohlcv(simbolo, timeframe=timeframe, limit=limite)
            df = pd.DataFrame(velas, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df = df.set_index("datetime").drop(columns=["timestamp"])
            return df
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            logger.warning(f"Error de red/API obteniendo velas (intento {intento+1}/{max_intentos}): {e}")
            
            if intento < max_intentos - 1:
                espera = 8 * (2 ** intento)   # backoff simple
                time.sleep(espera)
                # Intentar reconectar
                try:
                    exchange = crear_exchange()
                except Exception as recon_error:
                    logger.warning(f"Reconexión fallida tras error de red: {recon_error}")
            else:
                logger.error("No se pudieron obtener velas tras varios intentos; se reintentará en el siguiente ciclo")
                return None
        except Exception as e:
            logger.exception(f"Error inesperado obteniendo velas: {e}")
            raise


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


def mostrar_estado(estado, precio_actual, rsi, senal, params, ciclo):
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    retorno = (estado.capital / CAPITAL_INICIAL - 1) * 100
    signo   = "+" if retorno >= 0 else ""

    if rsi < params["rsi_sobreventa"]:
        zona_rsi = "SOBREVENTA"
    elif rsi > params["rsi_sobrecompra"]:
        zona_rsi = "SOBRECOMPRA"
    else:
        zona_rsi = "NEUTRAL"

    lineas = [
        "=" * 54,
        f"TRADING BOT PRO | PAPER TRADING | {ahora} | Ciclo #{ciclo}",
        f"Mercado: {SIMBOLO} | Timeframe: {TIMEFRAME}",
        f"Capital: ${estado.capital:>10,.2f} ({signo}{retorno:.2f}%)",
        f"Precio actual: ${precio_actual:>12,.2f}",
        f"RSI({params['rsi_periodo']}): {rsi:>6.1f} | Zona: {zona_rsi}",
    ]

    if estado.en_posicion:
        pnl_actual = (precio_actual / estado.precio_entrada - 1) * 100
        signo_pnl  = "+" if pnl_actual >= 0 else ""
        lineas.extend([
            "Posición: ABIERTA",
            f"Entrada: ${estado.precio_entrada:>10,.2f}",
            f"Stop Loss: ${estado.stop_loss:>10,.2f} ({params['stop_loss']*100:.1f}%)",
            f"Take Profit: ${estado.take_profit:>10,.2f} ({params['take_profit']*100:.1f}%)",
            f"P&L actual: {signo_pnl}{pnl_actual:.2f}%",
        ])
    else:
        lineas.append("Posición: SIN POSICIÓN ABIERTA")

    if senal == 1:
        lineas.append("Señal: COMPRA detectada")
    elif senal == -1:
        lineas.append("Señal: VENTA detectada")
    else:
        lineas.append("Señal: sin novedad")

    if estado.trades:
        lineas.append("Últimos trades:")
        for t in estado.trades[-5:]:
            resultado = "WIN" if t["pnl"] > 0 else "LOSS"
            lineas.append(f"{resultado} | {t['entrada']} | ${t['pnl']:+.2f} | {t['razon']}")

        r = estado.resumen()
        lineas.append(
            f"Operaciones: {r['total']} | Win Rate: {r['win_rate']:.0f}% | P&L total: ${r['pnl_total']:+.2f}"
        )
    else:
        lineas.append("Sin trades aún; esperando primera señal")

    lineas.append("Ctrl+C para detener y guardar reporte")
    lineas.append("=" * 54)

    logger.info("\n" + "\n".join(lineas))


# ============================================
# EJECUCIÓN ÚNICA
# ============================================
def main():
    configurar_logger()
    logger.info("Script iniciado - modo una ejecución para GitHub Actions")
    
    try:
        params = cargar_params()
        estado = cargar_estado()
        exchange = crear_exchange()
        logger.info("Exchange creado correctamente (Binance)")

    except Exception as e:
        logger.error(f"Error crítico al iniciar: {e}")
        logger.exception("Error fatal al iniciar el bot")
        raise

    logger.info("=" * 75)
    logger.info("TRADING BOT PRO — PAPER TRADING | EJECUCIÓN ÚNICA")
    logger.info(f"Symbol: {SIMBOLO} | Timeframe: {TIMEFRAME} | Capital: ${CAPITAL_INICIAL:,.2f}")
    logger.info(
        f"RSI Period: {params['rsi_periodo']} | SV: {params['rsi_sobreventa']} | SC: {params['rsi_sobrecompra']}"
    )

    try:
        df = obtener_velas(exchange, SIMBOLO, TIMEFRAME, limite=150)
        if df is None:
            logger.warning("No se recibieron velas en esta ejecución; se conserva el estado actual")
            guardar_estado(estado)
            return

        precio = df["close"].iloc[-1]
        senal, rsi = detectar_senal(df, params)

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
                logger.info(f"CIERRE [{razon}] | P&L: ${pnl:+.2f} | Capital: ${estado.capital:,.2f}")

        if not estado.en_posicion and senal == 1:
            estado.abrir_posicion(
                precio,
                datetime.now(timezone.utc),
                params["stop_loss"],
                params["take_profit"],
            )
            logger.info(f"APERTURA @ ${precio:,.2f} | SL: ${estado.stop_loss:,.2f} | TP: ${estado.take_profit:,.2f}")

        mostrar_estado(estado, precio, rsi, senal, params, ciclo=1)
        estado.guardar_log()
        guardar_estado(estado)

        r = estado.resumen()
        if r:
            logger.info("RESUMEN ACTUAL")
            logger.info(f"Operaciones: {r['total']}")
            logger.info(f"Win Rate: {r['win_rate']:.1f}%")
            logger.info(f"P&L Total: ${r['pnl_total']:+,.2f}")
            logger.info(f"Capital final: ${r['capital']:,.2f}")

    except KeyboardInterrupt:
        logger.info("Ejecución interrumpida manualmente")
        estado.guardar_log()
        guardar_estado(estado)

    except Exception as e:
        logger.error(f"Error en la ejecución del ciclo: {e}")
        logger.exception("Fallo durante la ejecución única")
        estado.guardar_log()
        guardar_estado(estado)
        raise


if __name__ == "__main__":
    main()