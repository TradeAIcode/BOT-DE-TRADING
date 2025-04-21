# -*- coding: utf-8 -*-
import pandas as pd
import traceback
import time # Añadido para debug
from datetime import datetime  # <--- AÑADE ESTA LÍNEA

def strategy_custom(df, position, config):
    """
    Estrategia personalizada basada en el cruce de EMAs en tiempo real.
    Usa columnas en MINÚSCULAS del DataFrame.
    """
    # --- Añade prints para depuración ---
    print(f"--- DEBUG CUSTOM STRATEGY CALLED ({datetime.now()}) ---")
    if df is None:
        print("--- CUSTOM: DF is None ---")
        return None
    if df.empty:
        print("--- CUSTOM: DF is empty ---")
        return None
    print(f"--- CUSTOM: DF Columns: {df.columns.tolist()} ---")
    print(f"--- CUSTOM: DF Tail:\n{df.tail(3)} ---")
    print(f"--- CUSTOM: Position: {position} ---")
    # ------------------------------------

    try:
        # Leer los periodos de EMA de la configuración (solo para propósitos de log)
        ema_fast_period = int(config.get("ema_fast", 15))
        ema_slow_period = int(config.get("ema_slow", 30))
    except Exception as e:
        print(f"Error en la configuración de periodos EMA: {e}")
        return None

    # --- ¡CORRECCIÓN! Usar nombres de columna en MINÚSCULAS ---
    required_cols = ["open", "high", "low", "close", "ema_fast", "ema_slow"]
    for col in required_cols:
        if col not in df.columns:
            print(f"Error: Falta la columna '{col}' en el DataFrame.")
            return None
    # ---------------------------------------------------------

    if len(df) < 2:
        print("--- CUSTOM: Not enough rows in DF (< 2) ---")
        return None

    # Extraer la vela cerrada (penúltima fila) y la vela en formación (última fila)
    prev_row = df.iloc[-2]
    current_row = df.iloc[-1]

    # --- ¡CORRECIÓN! Usar nombres de columna en MINÚSCULAS ---
    fast_prev = prev_row["ema_fast"]
    slow_prev = prev_row["ema_slow"]
    fast_current = current_row["ema_fast"]
    slow_current = current_row["ema_slow"]
    # ---------------------------------------------------------

    # --- Añade prints para depuración ---
    print(f"--- CUSTOM: EMAs Prev: fast={fast_prev}, slow={slow_prev} ---")
    print(f"--- CUSTOM: EMAs Curr: fast={fast_current}, slow={slow_current} ---")
    # ------------------------------------

    # Comprobar que no existan valores nulos
    if pd.isna(fast_prev) or pd.isna(slow_prev) or pd.isna(fast_current) or pd.isna(slow_current):
        print("--- CUSTOM: NaN found in EMAs ---")
        return None

    # Detectar cruces:
    crossed_up = (fast_prev <= slow_prev) and (fast_current > slow_current)
    crossed_down = (fast_prev >= slow_prev) and (fast_current < slow_current)

    # --- Añade prints para depuración ---
    print(f"--- CUSTOM: Crossed Up: {crossed_up}, Crossed Down: {crossed_down} ---")
    # ------------------------------------

    # --- ¡CORRECIÓN! Usar nombre de columna en MINÚSCULAS ---
    current_price = current_row["close"]
    # -----------------------------------------------------
    if pd.isna(current_price):
        print("--- CUSTOM: NaN found in current price ---")
        return None

    # Si no hay posición activa, se generan las señales de entrada
    if not position:
        print("--- CUSTOM: No active position, checking for entry signals... ---")
        if crossed_up:
            reason = f"Realtime EMA Cross: cruzó ARRIBA (EMA{ema_fast_period} vs EMA{ema_slow_period}) a {current_price:.4f}"
            print(f"--- CUSTOM: SIGNAL LONG DETECTED! Reason: {reason} ---") # <-- DEBUG
            return {
                "action": "long",
                "reason": reason
            }
        elif crossed_down:
            reason = f"Realtime EMA Cross: cruzó ABAJO (EMA{ema_fast_period} vs EMA{ema_slow_period}) a {current_price:.4f}"
            print(f"--- CUSTOM: SIGNAL SHORT DETECTED! Reason: {reason} ---") # <-- DEBUG
            return {
                "action": "short",
                "reason": reason
            }
        else:
             print("--- CUSTOM: No cross detected for entry. ---") # <-- DEBUG
    else:
        print("--- CUSTOM: Active position exists, ignoring entry signals. ---")
        # Si ya hay posición activa, NO se invierte la posición,
        # simplemente se mantiene la posición y se ignoran los cruces contrarios.
        return None

    # Si no se cumplió ninguna condición de entrada (y no había posición)
    print("--- CUSTOM: No signal generated this cycle. ---") # <-- DEBUG
    return None