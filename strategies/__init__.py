# BOT_V7/strategies/__init__.py
# -*- coding: utf-8 -*-

import traceback
# Importar la función para cargar el código personalizado
# Asegúrate que la ruta a config_manager es correcta desde aquí
# Si utils está al mismo nivel que strategies, esto debería funcionar:
try:
    from utils.config_manager import load_custom_strategy
except ImportError:
    print("ERROR CRÍTICO [Strategies]: No se pudo importar 'load_custom_strategy' desde utils.config_manager.")
    # Puedes decidir si lanzar una excepción aquí para detener el bot si es esencial
    # raise

# --- Importar las funciones de estrategia ESTÁTICAS desde sus archivos ---
from .bmsb_ontime import strategy_bmsb_ontime
from .bmsb_close import strategy_bmsb_close
from .bmsb_invert import strategy_bmsb_close_inverted
from .rsi_improved import strategy_rsi_contrarian_improved
from .ema_pullback import strategy_ema_pullback_entry
from .rsi_contrarian_original import strategy_rsi_contrarian_original
from .ema_cross_original import strategy_ema_cross_original
# ---------------------------------------------------------------------

# --- Definir el Mapa de Estrategias INICIAL (sin 'custom' todavía) ---
STRATEGY_MAP = {
    # Estrategias Mejoradas/Nuevas
    "rsi": strategy_rsi_contrarian_improved,
    "ema": strategy_ema_pullback_entry,
    # Estrategias BMSB
    "bmsb_ontime": strategy_bmsb_ontime,
    "bmsb_close": strategy_bmsb_close,
    "bmsb_invert": strategy_bmsb_close_inverted,
    # Estrategias Originales
    "rsi_original": strategy_rsi_contrarian_original,
    "ema_cross": strategy_ema_cross_original,
    # La estrategia 'custom' se añadirá dinámicamente si existe
}
# -------------------------------------------------------------------

# --- NUEVA FUNCIÓN PARA CARGAR Y AÑADIR LA ESTRATEGIA CUSTOM ---
def load_dynamic_custom_strategy():
    """
    Carga el código desde custom_strategy.py, lo ejecuta para obtener
    la función strategy_custom y la añade a STRATEGY_MAP si es válida.
    """
    print("Debug [Strategies]: Intentando cargar estrategia personalizada...")
    # Usamos partial para pasar el logger (print en este caso)
    # from functools import partial
    # load_callback_with_log = partial(load_custom_strategy, log_callback=print)
    # code_str = load_callback_with_log()
    # O simplemente:
    code_str = load_custom_strategy(log_callback=print) # load_custom_strategy ya loguea

    if code_str:
        namespace = {}
        try:
            # ¡Punto crítico! Ejecuta el código cargado desde el archivo.
            # Aceptamos el riesgo para uso individual como comentamos.
            exec(code_str, namespace)

            custom_fn = namespace.get('strategy_custom') # Busca la función definida

            if custom_fn and callable(custom_fn):
                # Añadir la función encontrada al mapa global
                STRATEGY_MAP["custom"] = custom_fn
                print("✅ Estrategia personalizada 'custom' cargada y añadida a STRATEGY_MAP.")
            else:
                # Si el archivo existe pero no define la función correctamente
                print("❌ Error: Archivo custom_strategy.py no define la función `strategy_custom(df, position, config)` correctamente.")
                # Eliminar 'custom' del mapa si existía de una carga anterior fallida
                if "custom" in STRATEGY_MAP:
                    del STRATEGY_MAP["custom"]

        except SyntaxError as se:
            print(f"❌ Error de Sintaxis en custom_strategy.py: {se}")
            traceback.print_exc()
            if "custom" in STRATEGY_MAP: del STRATEGY_MAP["custom"]
        except Exception as e:
            # Otros errores durante la ejecución del código cargado (NameError, etc.)
            print(f"❌ Error ejecutando el código de custom_strategy.py: {e}")
            traceback.print_exc()
            if "custom" in STRATEGY_MAP: del STRATEGY_MAP["custom"]
    else:
        # Si no se encontró el archivo custom_strategy.py
        print("ℹ️ No se encontró archivo custom_strategy.py o estaba vacío.")
        # Asegurarse de que 'custom' no esté en el mapa si el archivo no existe
        if "custom" in STRATEGY_MAP:
            del STRATEGY_MAP["custom"]
# --- FIN NUEVA FUNCIÓN ---

def get_available_strategies():
    """Retorna una lista de los nombres de las estrategias disponibles (incluye 'custom' si se cargó)."""
    # Asegurarse de intentar cargarla antes de devolver las disponibles? Opcional.
    # load_dynamic_custom_strategy() # Podría llamarse aquí, pero mejor al inicio del worker
    return list(STRATEGY_MAP.keys())

# Código de diagnóstico inicial (sin cambios)
print(f"Debug Strategies: STRATEGY_MAP inicializado con claves: {get_available_strategies()}")
# Nota: 'custom' no aparecerá aquí al inicio, solo después de llamar a load_dynamic_custom_strategy()