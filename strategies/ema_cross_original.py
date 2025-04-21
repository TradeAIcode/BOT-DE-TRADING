# ema_cross_original.py
import pandas as pd
import traceback

def strategy_ema_cross_original(df, position, config):
    """
    Versión original de EMA Cross,
    pero usando las columnas 'ema_fast' y 'ema_slow' precalculadas 
    (en lugar de calcular internamente).
    """
    if df is None or df.empty:
        return None

    try:
        # Lee los periodos de la config (solo para logs o validaciones)
        ema_fast_period = int(config.get("ema_fast", 15))
        ema_slow_period = int(config.get("ema_slow", 30))

        # Asegúrate de que las columnas existan
        if 'ema_fast' not in df.columns or 'ema_slow' not in df.columns:
            print("Debug: No se encontraron columnas 'ema_fast' o 'ema_slow' en df")
            return None

        # Chequea que haya suficientes filas
        # (realmente ya no es tan estricto porque el worker se encargó
        #  de pedir las velas necesarias y calular la EMA)
        if len(df) < 2:
            return None

        # Extraer las últimas dos filas
        fast_prev = df['ema_fast'].iloc[-2]
        slow_prev = df['ema_slow'].iloc[-2]
        fast_last = df['ema_fast'].iloc[-1]
        slow_last = df['ema_slow'].iloc[-1]

        # Verificar que no haya NaN
        if pd.isna(fast_prev) or pd.isna(slow_prev) or pd.isna(fast_last) or pd.isna(slow_last):
            return None

        # Detectar cruce
        crossed_up = (fast_prev <= slow_prev) and (fast_last > slow_last)
        crossed_down = (fast_prev >= slow_prev) and (fast_last < slow_last)

        # Lógica de Entrada
        if not position:
            if crossed_up:
                return {
                    'action': 'long',
                    'reason': f'EMA Cross Orig: cruza ARRIBA ({ema_fast_period} vs {ema_slow_period})'
                }
            elif crossed_down:
                return {
                    'action': 'short',
                    'reason': f'EMA Cross Orig: cruza ABAJO ({ema_fast_period} vs {ema_slow_period})'
                }

        # Lógica de Salida / Inversión (Opcional)
        if position:
            current_side = position.get('side', '').lower()
            if current_side == 'long' and crossed_down:
                return {
                    'action': 'invertir_posicion',
                    'reason': f'Invertir LONG->SHORT (cruce bajista EMA{ema_fast_period} vs {ema_slow_period})'
                }
            elif current_side == 'short' and crossed_up:
                return {
                    'action': 'invertir_posicion',
                    'reason': f'Invertir SHORT->LONG (cruce alcista EMA{ema_fast_period} vs {ema_slow_period})'
                }

    except Exception as e:
        print(f"Error [EMA Cross Original Strategy]: {e}")
        traceback.print_exc()
        return None

    return None
