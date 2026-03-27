"""
============================================
TRADING BOT PRO — Fase 4: Backtesting
============================================
Simula operaciones históricas con la estrategia
RSI y calcula métricas de rendimiento reales.

Uso:
    python fase4_backtesting.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

# ============================================
# CONFIGURACIÓN
# ============================================
ARCHIVO_DATOS    = "datos/BTC_USDT_1h_indicadores.csv"
CAPITAL_INICIAL  = 10_000    # USD simulados
RIESGO_POR_TRADE = 0.10      # 10% del capital por operación
STOP_LOSS_PCT    = 0.02      # 2%
TAKE_PROFIT_PCT  = 0.04      # 4%
COMISION_PCT     = 0.001     # 0.1% por operación (típico en Bybit)


# ============================================
# MOTOR DE BACKTESTING
# ============================================

def cargar_datos(ruta):
    df = pd.read_csv(ruta, index_col="datetime", parse_dates=True)
    print(f"  ✅ Datos cargados: {len(df):,} velas")
    return df


def ejecutar_backtest(df):
    """
    Simula cada operación vela por vela.
    - Entra en COMPRA cuando senal == 1
    - Sale por Take Profit, Stop Loss o señal de VENTA
    - Solo una operación abierta a la vez
    """
    capital      = CAPITAL_INICIAL
    en_posicion  = False
    precio_entrada = 0.0
    stop_loss    = 0.0
    take_profit  = 0.0
    trades       = []
    curva_equity = []

    for i, (fecha, fila) in enumerate(df.iterrows()):
        precio = fila["close"]
        senal  = fila["senal"]

        # --- Gestión de posición abierta ---
        if en_posicion:
            salida = None
            razon  = ""

            if precio <= stop_loss:
                salida = stop_loss
                razon  = "Stop Loss"
            elif precio >= take_profit:
                salida = take_profit
                razon  = "Take Profit"
            elif senal == -1:
                salida = precio
                razon  = "Señal RSI"

            if salida is not None:
                # Calcular resultado de la operación
                tamano    = (capital * RIESGO_POR_TRADE) / precio_entrada
                comision  = tamano * salida * COMISION_PCT
                pnl       = tamano * (salida - precio_entrada) - comision
                capital  += pnl
                en_posicion = False

                trades.append({
                    "entrada_fecha" : fecha_entrada,
                    "salida_fecha"  : fecha,
                    "precio_entrada": precio_entrada,
                    "precio_salida" : salida,
                    "razon_salida"  : razon,
                    "pnl"           : pnl,
                    "pnl_pct"       : (salida / precio_entrada - 1) * 100,
                    "capital"       : capital,
                })

        # --- Nueva entrada ---
        if not en_posicion and senal == 1 and capital > 0:
            en_posicion    = True
            precio_entrada = precio
            fecha_entrada  = fecha
            stop_loss      = precio * (1 - STOP_LOSS_PCT)
            take_profit    = precio * (1 + TAKE_PROFIT_PCT)

        curva_equity.append({"datetime": fecha, "capital": capital})

    return pd.DataFrame(trades), pd.DataFrame(curva_equity).set_index("datetime")


def calcular_metricas(trades, equity):
    """Calcula todas las métricas del proyecto."""
    if trades.empty:
        print("  ⚠️  Sin operaciones para analizar.")
        return {}

    ganadores  = trades[trades["pnl"] > 0]
    perdedores = trades[trades["pnl"] <= 0]

    win_rate       = len(ganadores) / len(trades) * 100
    ganancia_bruta = ganadores["pnl"].sum() if not ganadores.empty else 0
    perdida_bruta  = abs(perdedores["pnl"].sum()) if not perdedores.empty else 1
    profit_factor  = ganancia_bruta / perdida_bruta if perdida_bruta > 0 else float("inf")

    capital_final  = equity["capital"].iloc[-1]
    retorno_total  = (capital_final / CAPITAL_INICIAL - 1) * 100

    # Max Drawdown
    pico = equity["capital"].cummax()
    dd   = (equity["capital"] - pico) / pico * 100
    max_drawdown = dd.min()

    # Sharpe Ratio (anualizado, asumiendo velas 1h)
    retornos_horarios = equity["capital"].pct_change().dropna()
    if retornos_horarios.std() > 0:
        sharpe = (retornos_horarios.mean() / retornos_horarios.std()) * np.sqrt(8760)
    else:
        sharpe = 0.0

    pnl_medio_ganador  = ganadores["pnl"].mean() if not ganadores.empty else 0
    pnl_medio_perdedor = perdedores["pnl"].mean() if not perdedores.empty else 0

    return {
        "total_trades"    : len(trades),
        "ganadores"       : len(ganadores),
        "perdedores"      : len(perdedores),
        "win_rate"        : win_rate,
        "profit_factor"   : profit_factor,
        "retorno_total"   : retorno_total,
        "capital_final"   : capital_final,
        "max_drawdown"    : max_drawdown,
        "sharpe_ratio"    : sharpe,
        "pnl_medio_win"   : pnl_medio_ganador,
        "pnl_medio_loss"  : pnl_medio_perdedor,
        "mejor_trade"     : trades["pnl"].max(),
        "peor_trade"      : trades["pnl"].min(),
    }


def imprimir_reporte(m):
    objetivos = {
        "win_rate"     : (55,  "% (objetivo > 55%)"),
        "max_drawdown" : (-15, "% (objetivo > -15%)"),
        "profit_factor": (1.5, " (objetivo > 1.5)"),
        "sharpe_ratio" : (1.0, " (objetivo > 1.0)"),
    }

    def estado(key, valor):
        if key == "win_rate"      : return "✅" if valor >= 55   else "⚠️ "
        if key == "max_drawdown"  : return "✅" if valor >= -15  else "⚠️ "
        if key == "profit_factor" : return "✅" if valor >= 1.5  else "⚠️ "
        if key == "sharpe_ratio"  : return "✅" if valor >= 1.0  else "⚠️ "
        return ""

    print(f"\n{'='*54}")
    print(f"  REPORTE DE BACKTESTING")
    print(f"{'='*54}")
    print(f"  Capital inicial : ${CAPITAL_INICIAL:>10,.2f}")
    print(f"  Capital final   : ${m['capital_final']:>10,.2f}")
    retorno_color = "+" if m['retorno_total'] >= 0 else ""
    print(f"  Retorno total   : {retorno_color}{m['retorno_total']:>9.2f}%")
    print(f"{'─'*54}")
    print(f"  Total operaciones : {m['total_trades']:>6}")
    print(f"  Ganadoras         : {m['ganadores']:>6}  (${m['pnl_medio_win']:,.2f} promedio)")
    print(f"  Perdedoras        : {m['perdedores']:>6}  (${m['pnl_medio_loss']:,.2f} promedio)")
    print(f"  Mejor trade       : ${m['mejor_trade']:>9,.2f}")
    print(f"  Peor trade        : ${m['peor_trade']:>9,.2f}")
    print(f"{'─'*54}")
    print(f"  {estado('win_rate', m['win_rate'])} Win Rate      : {m['win_rate']:>7.1f}{objetivos['win_rate'][1]}")
    print(f"  {estado('max_drawdown', m['max_drawdown'])} Max Drawdown  : {m['max_drawdown']:>7.1f}{objetivos['max_drawdown'][1]}")
    print(f"  {estado('profit_factor', m['profit_factor'])} Profit Factor : {m['profit_factor']:>7.2f}{objetivos['profit_factor'][1]}")
    print(f"  {estado('sharpe_ratio', m['sharpe_ratio'])} Sharpe Ratio  : {m['sharpe_ratio']:>7.2f}{objetivos['sharpe_ratio'][1]}")
    print(f"{'='*54}")


def graficar(trades, equity):
    """Gráfico de curva de equity + distribución de P&L."""
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(14, 5),
        gridspec_kw={"width_ratios": [3, 1]}
    )
    fig.patch.set_facecolor("#0f0f1a")
    for ax in [ax1, ax2]:
        ax.set_facecolor("#0f0f1a")
        ax.tick_params(colors="white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#333355")

    # Curva de equity
    color_linea = "#00e676" if equity["capital"].iloc[-1] >= CAPITAL_INICIAL else "#ff5252"
    ax1.plot(equity.index, equity["capital"], color=color_linea, linewidth=1.5)
    ax1.axhline(CAPITAL_INICIAL, color="#ffffff", linewidth=0.7,
                linestyle="--", alpha=0.4, label=f"Capital inicial ${CAPITAL_INICIAL:,}")
    ax1.fill_between(equity.index, CAPITAL_INICIAL, equity["capital"],
                     where=(equity["capital"] >= CAPITAL_INICIAL),
                     alpha=0.15, color="#00e676")
    ax1.fill_between(equity.index, CAPITAL_INICIAL, equity["capital"],
                     where=(equity["capital"] < CAPITAL_INICIAL),
                     alpha=0.15, color="#ff5252")

    # Marcar operaciones en la curva
    if not trades.empty:
        for _, t in trades.iterrows():
            c = "#00e676" if t["pnl"] > 0 else "#ff5252"
            ax1.axvline(t["salida_fecha"], color=c, alpha=0.25, linewidth=0.5)

    ax1.set_title("Curva de Equity — BTC/USDT RSI Strategy", color="white", fontsize=12)
    ax1.set_ylabel("Capital (USD)", color="white")
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator())
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=30, ha="right", color="white")
    ax1.legend(facecolor="#1a1a2e", labelcolor="white", fontsize=8)

    # Distribución de P&L
    if not trades.empty:
        colores = ["#00e676" if p > 0 else "#ff5252" for p in trades["pnl"]]
        ax2.bar(range(len(trades)), trades["pnl"].values, color=colores, width=0.8)
        ax2.axhline(0, color="white", linewidth=0.7, alpha=0.5)
        ax2.set_title("P&L por operación", color="white", fontsize=12)
        ax2.set_ylabel("USD", color="white")
        ax2.set_xlabel("# Operación", color="white")
        ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))

    plt.tight_layout()
    os.makedirs("graficos", exist_ok=True)
    ruta = "graficos/fase4_backtesting.png"
    plt.savefig(ruta, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  ✅ Gráfico guardado: {ruta}")


# ============================================
# EJECUCIÓN PRINCIPAL
# ============================================

if __name__ == "__main__":
    print("\n" + "="*54)
    print("  TRADING BOT PRO — Fase 4: Backtesting")
    print("="*54 + "\n")

    df              = cargar_datos(ARCHIVO_DATOS)
    trades, equity  = ejecutar_backtest(df)
    metricas        = calcular_metricas(trades, equity)

    imprimir_reporte(metricas)
    graficar(trades, equity)

    # Guardar historial de trades
    os.makedirs("datos", exist_ok=True)
    trades.to_csv("datos/trades_historico.csv")
    print(f"  ✅ Trades guardados: datos/trades_historico.csv")
    print(f"\n  Listo. Ejecuta la Fase 5: python fase5_optimizacion.py\n")
