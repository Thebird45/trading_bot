"""
============================================
TRADING BOT PRO — Fase 1: Verificación del Entorno
============================================
Ejecuta este script para confirmar que todo
está correctamente instalado y configurado.

Uso:
    python verificar_entorno.py
"""

import sys
import os

def check(nombre, fn):
    try:
        fn()
        print(f"  ✅ {nombre}")
        return True
    except Exception as e:
        print(f"  ❌ {nombre} → {e}")
        return False

def main():
    print("\n" + "="*50)
    print("  TRADING BOT PRO — Verificación del Entorno")
    print("="*50)

    # 1. Versión de Python
    print("\n📌 Python:")
    version = sys.version_info
    if version.major == 3 and version.minor >= 10:
        print(f"  ✅ Python {version.major}.{version.minor}.{version.micro} (compatible)")
    else:
        print(f"  ❌ Python {version.major}.{version.minor} — Se requiere 3.10 o superior")

    # 2. Librerías
    print("\n📦 Librerías:")
    check("pandas",       lambda: __import__("pandas"))
    check("numpy",        lambda: __import__("numpy"))
    check("ta",           lambda: __import__("ta"))
    check("ccxt",         lambda: __import__("ccxt"))
    check("scikit-learn", lambda: __import__("sklearn"))
    check("xgboost",      lambda: __import__("xgboost"))
    check("matplotlib",   lambda: __import__("matplotlib"))
    check("plotly",       lambda: __import__("plotly"))
    check("streamlit",    lambda: __import__("streamlit"))
    check("python-dotenv",lambda: __import__("dotenv"))
    check("loguru",       lambda: __import__("loguru"))
    check("schedule",     lambda: __import__("schedule"))

    # 3. Archivo .env
    print("\n🔑 Configuración:")
    if os.path.exists(".env"):
        print("  ✅ Archivo .env encontrado")
        from dotenv import load_dotenv
        load_dotenv()
        key = os.getenv("BYBIT_TESTNET_API_KEY", "")
        if key and key != "tu_api_key_aqui":
            print("  ✅ API Key de Bybit Testnet configurada")
        else:
            print("  ⚠️  API Key vacía — completa tu .env con tus claves de Bybit")
    else:
        print("  ⚠️  No existe .env — copia .env.example y renómbralo a .env")

    # 4. Prueba de conexión a Bybit (datos públicos, sin API key)
    print("\n🌐 Conexión al exchange (Bybit — datos públicos):")
    try:
        import ccxt
        exchange = ccxt.bybit({'options': {'defaultType': 'spot'}})
        ticker = exchange.fetch_ticker("BTC/USDT")
        precio = ticker['last']
        print(f"  ✅ Conexión exitosa — BTC/USDT: ${precio:,.2f}")
    except Exception as e:
        print(f"  ❌ Error de conexión: {e}")

    print("\n" + "="*50)
    print("  Listo. Ahora ejecuta la Fase 2: obtener_datos.py")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
