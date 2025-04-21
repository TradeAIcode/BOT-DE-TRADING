# -*- coding: utf-8 -*-
import os
import json
import traceback

# Usar un nombre de archivo diferente al de los parámetros del bot
API_CONFIG_FILENAME = "api_credentials.json"
# Guardar en el mismo directorio que config_bot.json por simplicidad
API_CONFIG_PATH = os.path.join(os.path.dirname(os.path.expanduser("~/Documents/BOT_TRADING/config_bot.json")), API_CONFIG_FILENAME)

# --- Valores por defecto para la configuración API ---
DEFAULT_API_CONFIG = {
    "api_key": "",
    "secret_key": "",
    "password": "", # Contraseña API (opcional)
    "exchange_name": "Gate.io",
    "default_type": "swap",
    "is_sandbox": False
}

def log_api_error(message):
    """Log simple para errores de este manager."""
    print(f"[API Config Manager] {message}")

def load_api_config(config_path=API_CONFIG_PATH):
    """Carga la configuración API desde un archivo JSON."""
    log_api_error(f"Cargando config API desde {config_path}...")
    config_to_use = DEFAULT_API_CONFIG.copy()
    log_msg = f"ℹ️ Usando config API por defecto (archivo no encontrado o vacío)."

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)

            if not loaded_config: # Si el archivo está vacío
                 log_api_error("Advertencia: El archivo de config API está vacío.")
            else:
                # Sobrescribir defaults con valores cargados si existen y son del tipo correcto (simple)
                for key, default_value in DEFAULT_API_CONFIG.items():
                    if key in loaded_config and isinstance(loaded_config[key], type(default_value)):
                        config_to_use[key] = loaded_config[key]
                    elif key in loaded_config:
                         log_api_error(f"Advertencia: Tipo incorrecto para '{key}' en JSON API. Usando default.")
                         # Mantiene el valor default si el tipo es incorrecto

                log_msg = f"✅ Config API cargada desde {config_path}"

        except json.JSONDecodeError as e:
            log_msg = f"❌ Error decodificando JSON API en {config_path}: {e}. Usando defaults."
        except Exception as e:
            log_msg = f"⚠️ Error inesperado cargando {config_path}: {e}. Usando defaults."
            log_api_error(traceback.format_exc())

    log_api_error(log_msg)
    # NO guardar automáticamente al cargar, solo cargar lo que haya
    return config_to_use

def save_api_config(api_config_data, config_path=API_CONFIG_PATH):
    """Guarda la configuración API en un archivo JSON."""
    if api_config_data is None:
        log_api_error("❌ Intento de guardar config API nula. Cancelado.")
        return

    # Asegurarse de que solo se guardan las claves esperadas
    config_to_save = {}
    for key in DEFAULT_API_CONFIG.keys():
        config_to_save[key] = api_config_data.get(key, DEFAULT_API_CONFIG[key]) # Usar valor o default

    folder = os.path.dirname(config_path)
    try:
        os.makedirs(folder, exist_ok=True)
        # --- ¡ADVERTENCIA! Guardando claves en texto plano ---
        with open(config_path, "w", encoding='utf-8') as f:
            json.dump(config_to_save, f, indent=4, ensure_ascii=False)
        log_api_error(f"✅ Config API guardada en {config_path} (¡Claves en texto plano!).")
        # --- FIN ADVERTENCIA ---
    except Exception as e:
        log_msg = f"❌ Error guardando config API en {config_path}: {e}"
        log_api_error(log_msg)
        log_api_error(traceback.format_exc())