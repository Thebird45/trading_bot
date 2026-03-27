"""
============================================
TRADING BOT PRO — Fase 3: Estrategia RSI
============================================
Carga los datos OHLCV, calcula indicadores
técnicos (RSI, MACD, Bollinger Bands) y
genera señales de compra/venta.

Uso:
    python fase3_estrategia.py
"""

import pandas as pd
import ta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

# ============================================
# CONFIGURACIÓN DE LA ESTRATEGIA
# ============================================
ARCHIVO_DATOS   = "datos/BTC_USDT_1h.csv"

# RSI
RSI_PERIODO     = 14
RSI_SOBRECOMPRA = 70      # señal de VENTA
RSI_SOBREVENTA  = 30      # señal de COMPRA

# Gestión de riesgo
STOP_LOSS_PCT   = 0.02    # 2% de pérdida máxima
TAKE_PROFIT_PCT = 0.04    # 4% de ganancia objetivo

# ============================================
# FUNCIONES
# ============================================

def cargar_datos(ruta):
    """Carga el CSV generado en la Fase 2."""
    df = pd.read_csv(ruta, index_col="datetime", parse_dates=True)
    print(f"  ✅ Datos cargados: {len(df):,} velas")
    return df


def calcular_indicadores(df):
    """
    Agrega columnas de indicadores técnicos al DataFrame.
    - RSI: momentum (sobrecompra / sobreventa)
    - MACD: tendencia
    - Bollinger Bands: volatilidad
    """
    # RSI
    df["rsi"] = ta.momentum.RSIIndicator(
        close=df["close"], window=RSI_PERIODO
    ).rsi()

    # MACD
    macd = ta.trend.MACD(close=df["close"])
    df["macd"]        = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_diff"]   = macd.macd_diff()

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(close=df["close"], window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_mid"]   = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_width"] = bb.bollinger_wband()

    # Eliminar filas sin indicadores (período de calentamiento)
    df = df.dropna()
    print(f"  ✅ Indicadores calculados: {len(df):,} velas válidas")
    return df


def generar_senales(df):
    """
    Genera señales de compra (1) y venta (-1) basadas en RSI.

    Regla:
      COMPRA  → RSI cruza por debajo de 30 (sobreventa: precio muy bajo)
      VENTA   → RSI cruza por encima de 70 (sobrecompra: precio muy alto)
    """
    df["senal"] = 0

    # Cruce hacia abajo (entrada en sobreventa)
    df.loc[
        (df["rsi"] < RSI_SOBREVENTA) &
        (df["rsi"].shift(1) >= RSI_SOBREVENTA),
        "senal"
    ] = 1   # COMPRA

    # Cruce hacia arriba (salida en sobrecompra)
    df.loc[
        (df["rsi"] > RSI_SOBRECOMPRA) &
        (df["rsi"].shift(1) <= RSI_SOBRECOMPRA),
        "senal"
    ] = -1  # VENTA

    n_compras = (df["senal"] == 1).sum()
    n_ventas  = (df["senal"] == -1).sum()
    print(f"  ✅ Señales generadas → Compras: {n_compras} | Ventas: {n_ventas}")
    return df


def guardar_datos_con_indicadores(df):
    """Guarda el DataFrame con indicadores para usar en Fase 4."""
    os.makedirs("datos", exist_ok=True)
    ruta = "datos/BTC_USDT_1h_indicadores.csv"
    df.to_csv(ruta)
    print(f"  ✅ Guardado: {ruta}")
    return ruta


def mostrar_resumen_rsi(df):
    """Muestra estadísticas del RSI actual."""
    rsi_actual = df["rsi"].iloc[-1]
    rsi_medio  = df["rsi"].mean()
    rsi_min    = df["rsi"].min()
    rsi_max    = df["rsi"].max()

    if rsi_actual < 30:
        estado = "🟢 SOBREVENTA — posible zona de compra"
    elif rsi_actual > 70:
        estado = "🔴 SOBRECOMPRA — posible zona de venta"
    else:
        estado = "🟡 NEUTRAL"

    print(f"\n  RSI actual : {rsi_actual:.1f}  →  {estado}")
    print(f"  RSI medio  : {rsi_medio:.1f}")
    print(f"  RSI rango  : {rsi_min:.1f} – {rsi_max:.1f}")


def graficar(df):
    """Genera un gráfico con precio, señales y RSI."""
    # Tomar últimas 500 velas para visualización clara
    df_plot = df.tail(500).copy()

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 8),
        gridspec_kw={"height_ratios": [3, 1]},
        sharex=True
    )
    fig.patch.set_facecolor("#0f0f1a")
    for ax in [ax1, ax2]:
        ax.set_facecolor("#0f0f1a")
        ax.tick_params(colors="white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#333355")

    # --- Panel superior: precio + Bollinger Bands + señales ---
    ax1.plot(df_plot.index, df_plot["close"],
             color="#4fc3f7", linewidth=1.2, label="BTC/USDT", zorder=3)
    ax1.fill_between(df_plot.index, df_plot["bb_lower"], df_plot["bb_upper"],
                     alpha=0.15, color="#7986cb", label="Bollinger Bands")
    ax1.plot(df_plot.index, df_plot["bb_mid"],
             color="#7986cb", linewidth=0.7, linestyle="--")

    # Señales de compra
    compras = df_plot[df_plot["senal"] == 1]
    ax1.scatter(compras.index, compras["close"],
                marker="^", color="#00e676", s=80, zorder=5, label="Compra")

    # Señales de venta
    ventas = df_plot[df_plot["senal"] == -1]
    ax1.scatter(ventas.index, ventas["close"],
                marker="v", color="#ff5252", s=80, zorder=5, label="Venta")

    ax1.set_ylabel("Precio (USDT)", color="white", fontsize=10)
    ax1.set_title("BTC/USDT — Estrategia RSI", color="white", fontsize=13, pad=12)
    ax1.legend(facecolor="#1a1a2e", labelcolor="white", fontsize=8)
    ax1.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"${x:,.0f}")
    )

    # --- Panel inferior: RSI ---
    ax2.plot(df_plot.index, df_plot["rsi"],
             color="#ffb74d", linewidth=1.2, label="RSI(14)")
    ax2.axhline(70, color="#ff5252", linewidth=0.8, linestyle="--", alpha=0.8)
    ax2.axhline(30, color="#00e676", linewidth=0.8, linestyle="--", alpha=0.8)
    ax2.fill_between(df_plot.index, 30, df_plot["rsi"],
                     where=(df_plot["rsi"] < 30),
                     alpha=0.3, color="#00e676")
    ax2.fill_between(df_plot.index, 70, df_plot["rsi"],
                     where=(df_plot["rsi"] > 70),
                     alpha=0.3, color="#ff5252")
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("RSI", color="white", fontsize=10)
    ax2.text(df_plot.index[-1], 72, " Sobrecompra", color="#ff5252", fontsize=7, va="bottom")
    ax2.text(df_plot.index[-1], 28, " Sobreventa",  color="#00e676", fontsize=7, va="top")
    ax2.legend(facecolor="#1a1a2e", labelcolor="white", fontsize=8)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator())
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right", color="white")

    plt.tight_layout(rect=[0, 0, 1, 1])

    os.makedirs("graficos", exist_ok=True)
    ruta = "graficos/fase3_rsi.png"
    plt.savefig(ruta, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  ✅ Gráfico guardado: {ruta}")


# ============================================
# EJECUCIÓN PRINCIPAL
# ============================================

if __name__ == "__main__":
    print("\n" + "="*50)
    print("  TRADING BOT PRO — Fase 3: Estrategia RSI")
    print("="*50 + "\n")

    df = cargar_datos(ARCHIVO_DATOS)
    df = calcular_indicadores(df)
    df = generar_senales(df)
    mostrar_resumen_rsi(df)
    guardar_datos_con_indicadores(df)
    graficar(df)

    print(f"\n{'='*50}")
    print(f"  Parámetros de la estrategia:")
    print(f"  RSI período  : {RSI_PERIODO}")
    print(f"  Señal COMPRA : RSI < {RSI_SOBREVENTA}")
    print(f"  Señal VENTA  : RSI > {RSI_SOBRECOMPRA}")
    print(f"  Stop Loss    : {STOP_LOSS_PCT*100:.0f}%")
    print(f"  Take Profit  : {TAKE_PROFIT_PCT*100:.0f}%")
    print(f"  R/R Ratio    : 1 : {int(TAKE_PROFIT_PCT/STOP_LOSS_PCT)}")
    print(f"{'='*50}")
    print(f"  Listo. Ejecuta la Fase 4: python fase4_backtesting.py")
    print(f"{'='*50}\n")
