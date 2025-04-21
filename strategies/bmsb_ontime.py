# src/strategies/bmsb_ontime.py
import pandas as pd

def strategy_bmsb_ontime(df, position, config):
    """Estrategia simple: Entrar Long si la última vela cerró alcista."""
    if df is None or df.empty: return None
    last_candle = df.iloc[-1]
    # Solo entrar si NO hay posición abierta
    if not position and last_candle['close'] > last_candle['open']:
         # return {'action': 'long', 'reason': 'BMSB Ontime: Cierre > Apertura'}
         pass # Desactivado por defecto - Descomentar para activar
    return None