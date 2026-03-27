"""
============================================
TRADING BOT PRO — Fase 5: Optimización
============================================
Grid search sobre parámetros de RSI y SL/TP
para encontrar la configuración más rentable.
Incluye walk-forward validation para evitar
overfitting.

Uso:
    python fase5_optimizacion.py
"""

import pandas as pd
import numpy as np
import ta
import itertools
import matplotlib.pyplot as plt
import os
from datetime import timezone

# ============================================
# CONFIGURACIÓN DEL GRID SEARCH
# ============================================
ARCHIVO_DATOS    = "datos/BTC_USDT_1h_indicadores.csv"
CAPITAL_INICIAL  = 10_000
RIESGO_POR_TRADE = 0.10
COMISION_PCT     = 0.001

# Parámetros a probar
GRID = {
    "rsi_periodo"    : [10, 14, 21],
    "rsi_sobreventa" : [25, 30, 35],
    "rsi_sobrecompra": [65, 70, 75],
    "stop_loss"      : [0.015, 0.02, 0.03],
    "take_profit"    : [0.03, 0.04, 0.06],
}

# Walk-forward: % de datos para entrenamiento
TRAIN_SPLIT = 0.70   # 70% train → 30% test


# ============================================
# MOTOR BACKTEST (compacto para el grid)
# ============================================

def recalcular_senales(df_base, rsi_periodo, rsi_sobreventa, rsi_sobrecompra):
    """Recalcula RSI y señales con nuevos parámetros."""
    df = df_base[["open", "high", "low", "close", "volume"]].copy()

    df["rsi"] = ta.momentum.RSIIndicator(
        close=df["close"], window=rsi_periodo
    ).rsi()
    df = df.dropna()

    df["senal"] = 0
    df.loc[
        (df["rsi"] < rsi_sobreventa) &
        (df["rsi"].shift(1) >= rsi_sobreventa),
        "senal"
    ] = 1
    df.loc[
        (df["rsi"] > rsi_sobrecompra) &
        (df["rsi"].shift(1) <= rsi_sobrecompra),
        "senal"
    ] = -1
    return df


def backtest_rapido(df, stop_loss_pct, take_profit_pct):
    """Backtest simplificado que retorna métricas clave."""
    capital     = CAPITAL_INICIAL
    en_posicion = False
    precio_ent  = 0.0
    sl = tp     = 0.0
    trades      = []
    equity      = []

    for fecha, fila in df.iterrows():
        precio = fila["close"]
        senal  = fila["senal"]

        if en_posicion:
            salida = None
            if precio <= sl:
                salida = sl
            elif precio >= tp:
                salida = tp
            elif senal == -1:
                salida = precio

            if salida is not None:
                tam      = (capital * RIESGO_POR_TRADE) / precio_ent
                com      = tam * salida * COMISION_PCT
                pnl      = tam * (salida - precio_ent) - com
                capital += pnl
                en_posicion = False
                trades.append(pnl)

        if not en_posicion and senal == 1 and capital > 0:
            en_posicion = True
            precio_ent  = precio
            sl          = precio * (1 - stop_loss_pct)
            tp          = precio * (1 + take_profit_pct)

        equity.append(capital)

    if not trades:
        return None

    trades = np.array(trades)
    wins   = trades[trades > 0]
    losses = trades[trades <= 0]

    win_rate      = len(wins) / len(trades) * 100
    gan_bruta     = wins.sum()  if len(wins)   > 0 else 0
    per_bruta     = abs(losses.sum()) if len(losses) > 0 else 1e-9
    profit_factor = gan_bruta / per_bruta

    equity_arr = np.array(equity)
    pico       = np.maximum.accumulate(equity_arr)
    drawdowns  = (equity_arr - pico) / pico * 100
    max_dd     = drawdowns.min()

    retornos = np.diff(equity_arr) / equity_arr[:-1]
    sharpe   = (retornos.mean() / retornos.std() * np.sqrt(8760)
                if retornos.std() > 0 else 0)

    retorno_total = (equity_arr[-1] / CAPITAL_INICIAL - 1) * 100

    return {
        "win_rate"      : win_rate,
        "profit_factor" : profit_factor,
        "max_drawdown"  : max_dd,
        "sharpe_ratio"  : sharpe,
        "retorno_total" : retorno_total,
        "n_trades"      : len(trades),
        "capital_final" : equity_arr[-1],
    }


def score(m):
    """Puntuación combinada para rankear configuraciones."""
    if m is None or m["n_trades"] < 10:
        return -999
    return (
        m["win_rate"]       * 0.30 +
        m["profit_factor"]  * 10   +
        m["sharpe_ratio"]   * 15   +
        m["retorno_total"]  * 0.50 +
        max(0, 15 + m["max_drawdown"]) * 2
    )


# ============================================
# EJECUCIÓN DEL GRID SEARCH
# ============================================

def ejecutar_grid_search(df_train):
    print("\n  Ejecutando Grid Search...")
    print(f"  Probando combinaciones de parámetros...\n")

    claves     = list(GRID.keys())
    valores    = list(GRID.values())
    combos     = list(itertools.product(*valores))
    resultados = []
    total      = len(combos)

    for i, combo in enumerate(combos):
        params = dict(zip(claves, combo))

        # Filtrar combos inválidos
        if params["rsi_sobreventa"] >= params["rsi_sobrecompra"]:
            continue
        if params["stop_loss"] >= params["take_profit"]:
            continue

        df_s = recalcular_senales(
            df_train,
            params["rsi_periodo"],
            params["rsi_sobreventa"],
            params["rsi_sobrecompra"],
        )
        m = backtest_rapido(df_s, params["stop_loss"], params["take_profit"])

        if m:
            resultados.append({**params, **m, "score": score(m)})

        if (i + 1) % 50 == 0 or (i + 1) == total:
            print(f"  [{i+1:>4}/{total}] combinaciones probadas...", end="\r")

    print()
    return pd.DataFrame(resultados).sort_values("score", ascending=False)


# ============================================
# WALK-FORWARD VALIDATION
# ============================================

def walk_forward(df, mejores_params):
    """Valida los mejores parámetros en datos no vistos (out-of-sample)."""
    corte  = int(len(df) * TRAIN_SPLIT)
    df_test = df.iloc[corte:]

    df_s = recalcular_senales(
        df_test,
        mejores_params["rsi_periodo"],
        mejores_params["rsi_sobreventa"],
        mejores_params["rsi_sobrecompra"],
    )
    return backtest_rapido(
        df_s,
        mejores_params["stop_loss"],
        mejores_params["take_profit"],
    )


# ============================================
# REPORTE COMPARATIVO
# ============================================

def imprimir_comparativa(original, optimizado_train, optimizado_test, mejores):
    etiquetas = {
        "win_rate"      : ("Win Rate",      "%",  55,  True),
        "profit_factor" : ("Profit Factor", "",   1.5, True),
        "max_drawdown"  : ("Max Drawdown",  "%",  -15, False),
        "sharpe_ratio"  : ("Sharpe Ratio",  "",   1.0, True),
        "retorno_total" : ("Retorno Total", "%",  0,   True),
    }

    print(f"\n{'='*66}")
    print(f"  COMPARATIVA: Parámetros originales vs Optimizados")
    print(f"{'='*66}")
    print(f"  {'Métrica':<18} {'Original':>12} {'Train':>12} {'Test (OOS)':>12}")
    print(f"{'─'*66}")

    for key, (nombre, unidad, umbral, mayor_es_mejor) in etiquetas.items():
        vo = original.get(key, 0) if original else 0
        vt = optimizado_train.get(key, 0) if optimizado_train else 0
        vx = optimizado_test.get(key, 0) if optimizado_test else 0

        def fmt(v): return f"{v:+.1f}{unidad}" if unidad == "%" else f"{v:.2f}{unidad}"
        ok = "✅" if (vx >= umbral if mayor_es_mejor else vx >= umbral) else "⚠️ "
        print(f"  {ok} {nombre:<16} {fmt(vo):>12} {fmt(vt):>12} {fmt(vx):>12}")

    print(f"{'─'*66}")
    print(f"  {'Trades':<18} {original.get('n_trades',0):>12} "
          f"{optimizado_train.get('n_trades',0):>12} "
          f"{optimizado_test.get('n_trades',0):>12}")
    print(f"{'='*66}")

    print(f"\n  🏆 Mejores parámetros encontrados:")
    print(f"     RSI período    : {mejores['rsi_periodo']}")
    print(f"     RSI sobreventa : {mejores['rsi_sobreventa']}")
    print(f"     RSI sobrecompra: {mejores['rsi_sobrecompra']}")
    print(f"     Stop Loss      : {mejores['stop_loss']*100:.1f}%")
    print(f"     Take Profit    : {mejores['take_profit']*100:.1f}%")
    print(f"{'='*66}")


def graficar_heatmap(df_resultados):
    """Heatmap de Win Rate por combinación SL/TP."""
    pivot = df_resultados.pivot_table(
        values="win_rate",
        index="stop_loss",
        columns="take_profit",
        aggfunc="mean",
    )

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("#0f0f1a")
    ax.set_facecolor("#0f0f1a")

    im = ax.imshow(pivot.values, cmap="RdYlGn", aspect="auto",
                   vmin=20, vmax=60)
    plt.colorbar(im, ax=ax, label="Win Rate %")

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_yticks(range(len(pivot.index)))
    ax.set_xticklabels([f"{v*100:.1f}%" for v in pivot.columns], color="white")
    ax.set_yticklabels([f"{v*100:.1f}%" for v in pivot.index], color="white")
    ax.set_xlabel("Take Profit", color="white")
    ax.set_ylabel("Stop Loss", color="white")
    ax.set_title("Win Rate promedio por SL/TP", color="white", fontsize=12)

    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.0f}%", ha="center", va="center",
                        color="black", fontsize=9, fontweight="bold")

    plt.tight_layout()
    os.makedirs("graficos", exist_ok=True)
    ruta = "graficos/fase5_optimizacion.png"
    plt.savefig(ruta, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"\n  ✅ Heatmap guardado: {ruta}")


# ============================================
# EJECUCIÓN PRINCIPAL
# ============================================

if __name__ == "__main__":
    print("\n" + "="*66)
    print("  TRADING BOT PRO — Fase 5: Optimización de Parámetros")
    print("="*66)

    df = pd.read_csv(ARCHIVO_DATOS, index_col="datetime", parse_dates=True)
    print(f"\n  ✅ Datos cargados: {len(df):,} velas")

    corte    = int(len(df) * TRAIN_SPLIT)
    df_train = df.iloc[:corte]
    print(f"  Train : {len(df_train):,} velas ({TRAIN_SPLIT*100:.0f}%)")
    print(f"  Test  : {len(df) - corte:,} velas ({(1-TRAIN_SPLIT)*100:.0f}%)")

    # Resultado original para comparar
    df_orig = recalcular_senales(df, 14, 30, 70)
    original = backtest_rapido(df_orig, 0.02, 0.04)

    # Grid search en datos de entrenamiento
    df_resultados = ejecutar_grid_search(df_train)

    if df_resultados.empty:
        print("\n  ❌ No se encontraron combinaciones válidas.")
        exit(1)

    # Mejor configuración
    mejores      = df_resultados.iloc[0].to_dict()
    m_train      = {k: mejores[k] for k in ["win_rate","profit_factor",
                    "max_drawdown","sharpe_ratio","retorno_total","n_trades"]}

    # Walk-forward validation
    m_test = walk_forward(df, mejores)

    imprimir_comparativa(original, m_train, m_test, mejores)
    graficar_heatmap(df_resultados)

    # Guardar mejores parámetros
    os.makedirs("datos", exist_ok=True)
    mejores_guardados = {
        "rsi_periodo"    : int(mejores["rsi_periodo"]),
        "rsi_sobreventa" : int(mejores["rsi_sobreventa"]),
        "rsi_sobrecompra": int(mejores["rsi_sobrecompra"]),
        "stop_loss"      : float(mejores["stop_loss"]),
        "take_profit"    : float(mejores["take_profit"]),
    }
    pd.Series(mejores_guardados).to_json("datos/mejores_params.json")
    print(f"  ✅ Parámetros guardados: datos/mejores_params.json")
    print(f"\n  Listo. Ejecuta la Fase 6: python fase6_paper_trading.py\n")
