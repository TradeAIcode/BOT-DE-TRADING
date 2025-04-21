# src/strategies/bmsb_close.py
import pandas as pd

def strategy_bmsb_close(df, position, config):
    """Estrategia simple: Cerrar Long si la última vela cerró bajista."""
    if df is None or df.empty: return None
    last_candle = df.iloc[-1]
    # Solo cerrar si hay posición LONG abierta
    if position and position.get('side') == 'long' and last_candle['close'] < last_candle['open']:
         # return {'action': 'close', 'reason': 'BMSB Close: Cierre < Apertura'}
         pass # Desactivado por defecto
    return None