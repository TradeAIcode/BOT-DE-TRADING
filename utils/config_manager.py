# -*- coding: utf-8 -*-
import os
import json
import traceback

DEFAULT_CONFIG_PATH = os.path.expanduser("~/Documents/BOT_TRADING/config_bot.json")

# --- Valores por defecto para la configuración ---
# Añadir aquí cualquier nuevo parámetro con su valor default
DEFAULT_CONFIG = {
    "symbol": "ID/USDT:USDT",
    "leverage": 50,
    "timeframe": "15m",
    "inversion": 100,
    "trade_pct": 50,
    "stop_loss": 50,
    "auto_profit": 200,
    "trailing_stop": 30,
    "trailing_offset": 50, # % obsoleto si se usa trigger, pero mantener por si acaso
    "trailing_trigger": 25,
    "rsi_threshold": "85 / 25",
    "loop_interval": 2, # Intervalo del bucle del worker en segundos

    # --- NUEVAS VARIABLES PARA EMA PULLBACK ---
    "ema_fast": 5,            # Periodo EMA Rápida (Usado por la estrategia)
    "ema_slow": 15,            # Periodo EMA Lenta (Usado por la estrategia)
    "ema_filter_period": 100,  # Periodo EMA Filtro (Usado por Worker y Estrategia si activa)
    "ema_use_trend_filter": False # Activar/Desactivar filtro para EMA Pullback y RSI Mejorado
    # ------------------------------------------
    # Añadir aquí también los periodos que use la estrategia EMA Cross simple si es distinta
    # "ema_cross_fast": 9, # Ejemplo
    # "ema_cross_slow": 21, # Ejemplo
}

# ... (resto del código de load_config y save_config SIN CAMBIOS) ...

def log_error(log_callback, message):
    """Función auxiliar para loguear errores o mensajes importantes."""
    prefix = "[Config Manager]"
    full_message = f"{prefix} {message}"
    if callable(log_callback):
        # Asume que log_callback es seguro para hilos si es necesario
        # (TradingBotGUI.append_log usa QTimer)
        log_callback(full_message)
    else:
        # Fallback a consola si no hay callback
        print(full_message)

def load_config(log_callback=print, config_path=DEFAULT_CONFIG_PATH):
    """
    Carga la configuración desde un archivo JSON.
    Valida las claves y tipos contra DEFAULT_CONFIG.
    Si el archivo no existe o hay errores, usa/guarda los valores por defecto.
    """
    log_error(log_callback, f"Cargando config desde {config_path}...")
    config_to_use = DEFAULT_CONFIG.copy() # Empezar con defaults
    log_msg = f"ℹ️ Usando configuración por defecto. Creando/Usando {config_path}"

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f: # Especificar encoding
                loaded_config = json.load(f)

            # Validar y fusionar con defaults
            valid_loaded = {}
            found_keys = set()
            for key, default_value in DEFAULT_CONFIG.items():
                found_keys.add(key)
                if key in loaded_config:
                    loaded_value = loaded_config[key]
                    # Validar tipo (permitir string si el default es string, o número si default es número, o bool si default es bool)
                    is_type_ok = False
                    if isinstance(default_value, str) and isinstance(loaded_value, str):
                        is_type_ok = True
                    elif isinstance(default_value, (int, float)) and isinstance(loaded_value, (int, float)):
                        is_type_ok = True
                    elif isinstance(default_value, bool) and isinstance(loaded_value, bool): # <-- Añadida validación bool
                        is_type_ok = True
                    # Añadir más tipos si es necesario

                    if is_type_ok:
                        valid_loaded[key] = loaded_value
                    else:
                        log_error(log_callback, f"⚠️ Tipo incorrecto para '{key}' en JSON ({type(loaded_value).__name__}), se esperaba {type(default_value).__name__}. Usando default: {default_value}")
                        valid_loaded[key] = default_value
                else: # Clave no encontrada en JSON, usar default
                    valid_loaded[key] = default_value
                    log_error(log_callback, f"ℹ️ Clave '{key}' no encontrada en JSON. Usando default: {default_value}") # Log opcional

            # Comprobar si hay claves extras en el archivo JSON
            extra_keys = set(loaded_config.keys()) - found_keys
            if extra_keys:
                log_error(log_callback, f"ℹ️ Claves extra ignoradas en JSON: {', '.join(extra_keys)}")

            config_to_use = valid_loaded
            log_msg = f"✅ Configuración cargada y validada desde {config_path}"

        except json.JSONDecodeError as e:
            log_msg = f"❌ Error decodificando JSON en {config_path}: {e}. Usando/Guardando defaults."
            config_to_use = DEFAULT_CONFIG.copy() # Asegurarse de usar defaults en error de carga
        except Exception as e:
            log_msg = f"⚠️ Error inesperado cargando {config_path}: {e}. Usando/Guardando defaults."
            log_error(log_callback, traceback.format_exc()) # Loguear stack trace completo
            config_to_use = DEFAULT_CONFIG.copy() # Asegurarse de usar defaults en error de carga


    log_error(log_callback, log_msg)
    # print(f"Debug [Config Manager]: Config a usar: {config_to_use}") # Debug detallado

    # Guardar la configuración (default o cargada/validada) para asegurar consistencia
    # Solo guardar si hubo cambios o el archivo no existía
    if log_msg.startswith("ℹ️") or log_msg.startswith("❌") or log_msg.startswith("⚠️") or not os.path.exists(config_path):
         save_config(config_to_use, log_callback, config_path)

    return config_to_use

def save_config(config_data, log_callback=print, config_path=DEFAULT_CONFIG_PATH):
    """Guarda el diccionario de configuración proporcionado en un archivo JSON."""
    if config_data is None:
        log_error(log_callback, "❌ Intento de guardar configuración nula. Cancelado.")
        return

    # Asegurarse que se guardan todas las claves default, incluso si no estaban en un archivo viejo
    config_to_save = DEFAULT_CONFIG.copy()
    config_to_save.update(config_data) # Sobrescribir defaults con los valores actuales

    folder = os.path.dirname(config_path)
    try:
        os.makedirs(folder, exist_ok=True)
        with open(config_path, "w", encoding='utf-8') as f: # Especificar encoding
            json.dump(config_to_save, f, indent=4, ensure_ascii=False) # ensure_ascii=False para caracteres especiales
        # print(f"Debug [Config Manager]: Config guardada en {config_path}") # Evitar log en cada guardado normal
    except Exception as e:
        log_msg = f"❌ Error guardando config en {config_path}: {e}"
        log_error(log_callback, log_msg)
        log_error(log_callback, traceback.format_exc())
        
        

CUSTOM_STRATEGY_PATH = os.path.expanduser("~/Documents/BOT_TRADING/custom_strategy.py")

def save_custom_strategy(code_str, log_callback=print):
    """Guarda el string del código de la estrategia personalizada en un archivo .py."""
    folder = os.path.dirname(CUSTOM_STRATEGY_PATH)
    try:
        os.makedirs(folder, exist_ok=True)
        with open(CUSTOM_STRATEGY_PATH, 'w', encoding='utf-8') as file:
            file.write(code_str)
        log_error(log_callback, f"✅ Estrategia personalizada guardada en {CUSTOM_STRATEGY_PATH}")
        return True # Indicar éxito
    except Exception as e:
        log_msg = f"❌ Error guardando estrategia personalizada en {CUSTOM_STRATEGY_PATH}: {e}"
        log_error(log_callback, log_msg)
        log_error(log_callback, traceback.format_exc())
        return False # Indicar fallo

def load_custom_strategy(log_callback=print):
    """Carga el código de la estrategia personalizada desde el archivo .py."""
    if os.path.exists(CUSTOM_STRATEGY_PATH):
        try:
            with open(CUSTOM_STRATEGY_PATH, 'r', encoding='utf-8') as file:
                code = file.read()
            log_error(log_callback, f"ℹ️ Estrategia personalizada cargada desde {CUSTOM_STRATEGY_PATH}")
            return code
        except Exception as e:
            log_msg = f"❌ Error cargando estrategia personalizada desde {CUSTOM_STRATEGY_PATH}: {e}"
            log_error(log_callback, log_msg)
            log_error(log_callback, traceback.format_exc())
            return None # Indicar fallo
    else:
        # log_error(log_callback, f"ℹ️ Archivo de estrategia personalizada no encontrado en {CUSTOM_STRATEGY_PATH}")
        return None # No existe el archivo

# --- Fin Gestión Estrategia Personalizada ---
        