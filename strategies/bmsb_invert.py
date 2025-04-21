# src/strategies/bmsb_invert.py
import pandas as pd

def strategy_bmsb_close_inverted(df, position, config):
    """Estrategia: Si hay señal opuesta a la posición actual, cerrar e invertir."""
    if df is None or df.empty: return None
    last_candle = df.iloc[-1]
    signal = None
    reason = ""

    # Determinar señal básica (alcista/bajista) de la última vela
    if last_candle['close'] > last_candle['open']:
        signal = 'long'; reason = "BMSB Invert: Vela Alcista"
    elif last_candle['close'] < last_candle['open']:
        signal = 'short'; reason = "BMSB Invert: Vela Bajista"

    if position: # Si hay posición, buscar inversión
        current_side = position.get('side')
        if current_side == 'long' and signal == 'short':
            return {'action': 'short', 'reason': reason + " (Invierte LONG a SHORT)"}
        elif current_side == 'short' and signal == 'long':
            return {'action': 'long', 'reason': reason + " (Invierte SHORT a LONG)"}
    elif signal: # Si no hay posición, entrar (pero está desactivado)
        # return {'action': signal, 'reason': reason + " (Entrada)"}
        pass # Desactivado por defecto para no interferir con otras estrategias de entrada

    return None