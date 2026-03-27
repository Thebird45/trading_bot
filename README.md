# 🤖 TRADING BOT PRO — Guía de Inicio

## Fase 1: Preparar el Entorno

---

### Paso 1 — Instalar Python 3.10+

Descarga desde: https://www.python.org/downloads/

> ⚠️ Durante la instalación en Windows, marca la casilla
> **"Add Python to PATH"** antes de hacer clic en Install.

Verifica la instalación abriendo una terminal y escribiendo:
```
python --version
```
Debe mostrar `Python 3.10.x` o superior.

---

### Paso 2 — Descargar los archivos del bot

Crea una carpeta llamada `trading_bot` en tu computador y coloca
dentro todos los archivos del proyecto.

---

### Paso 3 — Crear el entorno virtual

Abre una terminal **dentro de la carpeta** `trading_bot` y ejecuta:

```bash
# Crear entorno virtual
python -m venv venv

# Activarlo (Windows)
venv\Scripts\activate

# Activarlo (Mac / Linux)
source venv/bin/activate
```

Sabrás que está activo porque verás `(venv)` al inicio de tu terminal.

---

### Paso 4 — Instalar las librerías

Con el entorno virtual activo, ejecuta:

```bash
pip install -r requirements.txt
```

Esto instalará automáticamente todas las librerías necesarias
(pandas, ccxt, ta, scikit-learn, etc.). Puede tardar 2–3 minutos.

---

### Paso 5 — Obtener API Keys de Bybit Testnet (GRATIS)

La **testnet** es un entorno de práctica con dinero ficticio.
No arriesgas nada real.

1. Ve a: https://testnet.bybit.com
2. Crea una cuenta gratuita
3. Una vez dentro, ve a tu perfil → **API Management**
4. Haz clic en **"Create New Key"**
5. Marca los permisos: **Read** y **Trade**
6. Copia tu `API Key` y tu `Secret Key`

---

### Paso 6 — Configurar el archivo .env

1. Copia el archivo `.env.example` y renómbralo a `.env`
2. Abre `.env` con cualquier editor de texto
3. Pega tus claves de Bybit Testnet:

```
BYBIT_TESTNET_API_KEY=pega_tu_api_key_aqui
BYBIT_TESTNET_SECRET=pega_tu_secret_aqui
```

> 🔒 El archivo `.env` contiene tus claves privadas.
> Nunca lo compartas ni lo subas a internet.

---

### Paso 7 — Verificar que todo funciona

```bash
python verificar_entorno.py
```

Si ves todos los ✅ verdes, ¡la Fase 1 está completada!

---

## Estructura del Proyecto

```
trading_bot/
│
├── requirements.txt        ← Librerías a instalar
├── .env.example            ← Plantilla de configuración
├── .env                    ← Tus claves reales (no compartir)
├── verificar_entorno.py    ← Script de verificación (Fase 1)
│
├── fase2_datos.py          ← Obtención de datos OHLCV
├── fase3_estrategia.py     ← Estrategia RSI
├── fase4_backtesting.py    ← Backtesting histórico
├── fase5_optimizacion.py   ← Grid search de parámetros
├── fase6_paper_trading.py  ← Paper trading en testnet
├── fase7_automatizacion.py ← Scheduler y alertas
├── fase8_ia.py             ← Modelo XGBoost
└── fase9_dashboard.py      ← Dashboard Streamlit
```

---

## Fases del Proyecto

| # | Fase | Estado |
|---|------|--------|
| 1 | Preparación del entorno | ✅ Esta guía |
| 2 | Obtención de datos OHLCV | 🔜 Siguiente |
| 3 | Estrategia RSI base | 🔜 |
| 4 | Backtesting histórico | 🔜 |
| 5 | Optimización de parámetros | 🔜 |
| 6 | Paper trading en testnet | 🔜 |
| 7 | Automatización y resiliencia | 🔜 |
| 8 | Integración de IA (XGBoost) | 🔜 |
| 9 | Despliegue en producción | 🔜 |

---

*Trading Bot PRO · v1.0 · 2025–2026*
