# src/utils/state_manager.py
import json
import os
import traceback
import math # Necesario para -math.inf

# --- CÓDIGO MODIFICADO PARA TS BASADO EN PNL ---

# Definir ruta (sin cambios)
STATE_DIR = os.path.expanduser("~/Documents/BOT_TRADING/")
# Podrías usar un nombre de archivo diferente si quieres mantener ambos estados
# TS_STATE_FILE = "trailing_stop_state_pnl.json"
TS_STATE_FILE = "trailing_stop_state.json" # O mantener el mismo y sobrescribir
TS_STATE_FILE_PATH = os.path.join(STATE_DIR, TS_STATE_FILE)

# --- NUEVA ESTRUCTURA DEL ESTADO POR DEFECTO ---
# active: El TS está buscando activarse o ya está activo.
# peak_pnl_pct: El PNL% más alto (ratio decimal) alcanzado desde la activación.
# target_pnl_pct: El PNL% (ratio decimal) que, si se alcanza o se baja de él, dispara el stop.
DEFAULT_TS_STATE = {
    "active": False,
    "peak_pnl_pct": 0.0,
    "target_pnl_pct": -math.inf # Usar infinito negativo como valor inicial seguro
    }
# ---------------------------------------------

def _load_all_ts_states():
    """Carga todos los estados TS desde el archivo JSON (sin cambios lógicos)."""
    if os.path.exists(TS_STATE_FILE_PATH):
        try:
            with open(TS_STATE_FILE_PATH, 'r', encoding='utf-8') as f:
                states = json.load(f)
            if isinstance(states, dict):
                # VALIDACIÓN BÁSICA: Asegurarse de que los estados cargados tengan las claves esperadas
                # Si un estado antiguo (con ts_price) se carga, se reemplazará con default al usarse.
                # Podrías añadir una migración aquí si fuera necesario.
                return states
            else:
                print(f"Advertencia [TS State]: Archivo {TS_STATE_FILE} no contiene un diccionario. Ignorando.")
                return {} # Devolver dict vacío si el formato es incorrecto
        except json.JSONDecodeError:
            print(f"Error [TS State]: Archivo {TS_STATE_FILE} corrupto. Ignorando.")
            return {}
        except Exception as e:
            print(f"Error [TS State]: Error inesperado cargando estados TS: {e}")
            traceback.print_exc()
            return {}
    else:
        # print(f"Debug [TS State]: Archivo {TS_STATE_FILE} no encontrado. Iniciando estados vacíos.")
        return {} # Devolver dict vacío si el archivo no existe

def load_ts_state(symbol):
    """Carga el estado del Trailing Stop para un símbolo específico."""
    if not symbol:
        print("Error [TS State]: Se requiere un símbolo para cargar el estado TS.")
        return DEFAULT_TS_STATE.copy() # Devuelve la NUEVA estructura default

    all_states = _load_all_ts_states()
    # Obtener estado guardado o devolver el NUEVO default si no existe o no tiene las claves correctas
    loaded_state = all_states.get(symbol)
    if isinstance(loaded_state, dict) and all(k in loaded_state for k in DEFAULT_TS_STATE.keys()):
         return loaded_state # Devuelve estado cargado si tiene las claves correctas
    else:
         if loaded_state: # Si existía pero no tenía las claves correctas
              print(f"Advertencia [TS State]: Estado cargado para {symbol} no coincide con la estructura esperada. Usando default.")
         return DEFAULT_TS_STATE.copy() # Devuelve la NUEVA estructura default


def save_ts_state(symbol, ts_data):
    """Guarda el estado del Trailing Stop para un símbolo específico."""
    if not symbol:
        print("Error [TS State]: Se requiere un símbolo para guardar el estado TS.")
        return

    # --- VALIDAR LA NUEVA ESTRUCTURA ---
    if not isinstance(ts_data, dict) or not all(k in ts_data for k in DEFAULT_TS_STATE.keys()):
         print(f"Error [TS State]: Datos de estado TS (PNL based) inválidos para guardar: {ts_data}")
         return
    # ----------------------------------

    all_states = _load_all_ts_states()
    # Actualizar el estado para el símbolo dado
    all_states[symbol] = ts_data

    try:
        # Asegurar que el directorio exista (sin cambios)
        os.makedirs(STATE_DIR, exist_ok=True)
        # Guardar todos los estados de vuelta en el archivo (sin cambios)
        # Nota: json no puede serializar -math.inf directamente, lo convertirá a "-Infinity" string.
        # json.load lo leerá como float('-inf') al cargar, lo cual está bien.
        with open(TS_STATE_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(all_states, f, indent=2)
        # print(f"Debug [TS State]: Estado TS (PNL based) guardado para {symbol}: {ts_data}") # Log verboso
    except PermissionError as pe:
         print(f"Error Permiso [TS State]: No se pudo guardar {TS_STATE_FILE_PATH}: {pe}")
         traceback.print_exc()
    except OSError as oe:
          print(f"Error OS [TS State]: No se pudo guardar {TS_STATE_FILE_PATH}: {oe}")
          traceback.print_exc()
    except Exception as e:
        print(f"Error inesperado [TS State]: No se pudo guardar estado TS: {e}")
        traceback.print_exc()

# --- FIN CÓDIGO MODIFICADO ---