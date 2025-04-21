# src/utils/db_manager.py
import sqlite3
import os
import traceback
from datetime import datetime, timezone

# Definir la ruta de la base de datos (similar al historial JSON)
DB_DIR = os.path.expanduser("~/Documents/BOT_TRADING/")
DB_NAME = "trading_history.db"
DB_PATH = os.path.join(DB_DIR, DB_NAME)

def get_db_connection():
    """Establece y devuelve una conexión a la base de datos SQLite."""
    try:
        # Asegurar que el directorio exista
        os.makedirs(DB_DIR, exist_ok=True)
        # Conectar a la base de datos (la creará si no existe)
        # isolation_level=None activa autocommit (más simple para inserciones individuales)
        # o usa con context manager para transacciones
        conn = sqlite3.connect(DB_PATH, check_same_thread=False) # Allow access from different threads if needed, use with caution
        conn.row_factory = sqlite3.Row # Devolver filas como diccionarios
        # print(f"Debug DB: Conexión establecida con {DB_PATH}")
        return conn
    except sqlite3.Error as e:
        print(f"Error Crítico [DB]: No se pudo conectar a la base de datos {DB_PATH}: {e}")
        traceback.print_exc()
        return None
    except OSError as e:
         print(f"Error Crítico [DB]: Error de OS al acceder/crear {DB_PATH}: {e}")
         traceback.print_exc()
         return None

def init_db():
    """Inicializa la base de datos creando la tabla 'history' si no existe."""
    conn = get_db_connection()
    if conn is None: return False
    try:
        cursor = conn.cursor()
        # Crear tabla con las 7 columnas + ID + Símbolo
        # Usar tipos SQLite: TEXT, REAL, INTEGER
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT,
                action TEXT NOT NULL,
                entry_price REAL,
                exit_price REAL,
                reason TEXT,
                pnl_percent REAL,
                pnl_usdt REAL
            )
        """)
        # Opcional: Crear índice en timestamp para búsquedas/ordenaciones más rápidas
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history (timestamp)")
        conn.commit()
        print("Debug DB: Tabla 'history' verificada/creada.")
        return True
    except sqlite3.Error as e:
        print(f"Error [DB]: No se pudo crear/verificar la tabla 'history': {e}")
        traceback.print_exc()
        return False
    finally:
        conn.close()

def save_history_entry(entry_dict):
    """Guarda una entrada del historial en la base de datos."""
    # Extraer datos del diccionario con valores por defecto None
    ts = entry_dict.get('timestamp')
    symbol = entry_dict.get('symbol') # Espera que el worker envíe el símbolo
    action = entry_dict.get('accion')
    reason = entry_dict.get('motivo')
    pnl_pct = entry_dict.get('pnl_pct')
    pnl_usdt = entry_dict.get('unrealizedPnl') # Leer la clave correcta
    precio = entry_dict.get('precio')

    if not ts or not action:
        print(f"Error [DB]: Faltan datos esenciales (timestamp o action) para guardar historial: {entry_dict}")
        return False

    entry_price = None
    exit_price = None
    acciones_entrada = ['LONG', 'SHORT', 'MANUAL_LONG', 'MANUAL_SHORT']
    acciones_salida = ['CLOSE', 'SL', 'TP', 'TS', 'LIQUIDATION', 'MANUAL_CLOSE']

    # Asignar precio a columna correcta
    if action.upper() in acciones_entrada: entry_price = precio
    elif action.upper() in acciones_salida: exit_price = precio
    # Si no es ni entrada ni salida, el precio no se asigna a estas columnas

    # Limpiar PNL si no es una acción de salida
    if action.upper() not in acciones_salida:
        pnl_pct = None
        pnl_usdt = None

    conn = get_db_connection()
    if conn is None: return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO history (timestamp, symbol, action, entry_price, exit_price, reason, pnl_percent, pnl_usdt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ts, symbol, action.upper(), entry_price, exit_price, reason, pnl_pct, pnl_usdt))
        conn.commit()
        # print(f"Debug DB: Entrada guardada: {action} @ {ts}") # Log verboso
        return True
    except sqlite3.Error as e:
        print(f"Error [DB]: No se pudo guardar la entrada de historial: {e}")
        print(f"  Datos: {entry_dict}")
        traceback.print_exc()
        return False
    finally:
        conn.close()

def load_history():
    """Carga todo el historial desde la base de datos, ordenado por fecha."""
    history_list = []
    conn = get_db_connection()
    if conn is None: return history_list # Devolver lista vacía si no hay conexión

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM history ORDER BY timestamp ASC")
        rows = cursor.fetchall()
        # Convertir filas (sqlite3.Row) a diccionarios estándar
        for row in rows:
            entry = dict(row)
            # Reconstruir el diccionario 'entry' como lo espera la GUI
            # Necesitamos decidir cómo manejar entry/exit price vs 'precio'
            # Opción 1: Recrear 'precio' basado en acción (como en GUI)
            precio = None
            action_upper = entry.get('action','').upper()
            if action_upper in ['LONG', 'SHORT', 'MANUAL_LONG', 'MANUAL_SHORT']:
                 precio = entry.get('entry_price')
            elif action_upper in ['CLOSE', 'SL', 'TP', 'TS', 'LIQUIDATION', 'MANUAL_CLOSE']:
                 precio = entry.get('exit_price')

            gui_entry = {
                'timestamp': entry.get('timestamp'),
                'accion': entry.get('action'),
                'precio': precio, # Precio del evento
                'motivo': entry.get('reason'),
                'pnl_pct': entry.get('pnl_percent'),
                'unrealizedPnl': entry.get('pnl_usdt'), # Usar la clave que espera la GUI
                'symbol': entry.get('symbol') # Incluir símbolo si se guardó
            }
            history_list.append(gui_entry)

        print(f"Debug DB: {len(history_list)} entradas cargadas desde la base de datos.")
        return history_list
    except sqlite3.Error as e:
        print(f"Error [DB]: No se pudo cargar el historial: {e}")
        traceback.print_exc()
        return [] # Devolver lista vacía en caso de error
    finally:
        conn.close()

# Puedes añadir funciones para borrar historial, filtrar, etc. si es necesario
# def clear_history(): ...
# def get_history_for_symbol(symbol): ...