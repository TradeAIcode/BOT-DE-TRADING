# src/strategies/ema_pullback.py
import pandas as pd

def strategy_ema_pullback_entry(df, position, config):
    """
    Estrategia EMA Cross con Entrada en Pullback + posibilidad de inversión.
    """
    use_trend_filter = config.get("ema_use_trend_filter", False)
    ema_fast_period_for_reason = int(config.get("ema_fast", 15))

    required_cols = ['ema_fast', 'ema_slow', 'close', 'low', 'high', 'open']
    if use_trend_filter:
        required_cols.append('ema_filter')

    if df is None or df.empty or len(df) < 1:
        return None
    if any(col not in df.columns for col in required_cols):
        print(f"Debug EMA PB: Faltan cols: {[c for c in required_cols if c not in df.columns]}")
        return None

    last_row = df.iloc[-1]
    if pd.isna(last_row[required_cols]).any():
        return None

    ema_fast_last = last_row['ema_fast']
    ema_slow_last = last_row['ema_slow']
    last_candle = last_row

    # ================================
    # 1. LÓGICA DE ENTRADA (si NO hay posición)
    # ================================
    if not position:
        trend_ok_long = True
        trend_ok_short = True
        if use_trend_filter:
            ema_filter_last = last_row['ema_filter']
            trend_ok_long = (last_candle['close'] > ema_filter_last)
            trend_ok_short = (last_candle['close'] < ema_filter_last)

        # Condiciones de LONG
        is_uptrending = (ema_fast_last > ema_slow_last)
        touched_fast_long = (last_candle['low'] <= ema_fast_last)
        closed_bullish = (last_candle['close'] > last_candle['open'])
        if is_uptrending and touched_fast_long and closed_bullish and trend_ok_long:
            reason = f'Pullback EMA{ema_fast_period_for_reason} ({ema_fast_last:.4f}) rebote'
            if use_trend_filter:
                reason += ' (Filtro OK)'
            return {'action': 'long', 'reason': reason}

        # Condiciones de SHORT
        is_downtrending = (ema_fast_last < ema_slow_last)
        touched_fast_short = (last_candle['high'] >= ema_fast_last)
        closed_bearish = (last_candle['close'] < last_candle['open'])
        if is_downtrending and touched_fast_short and closed_bearish and trend_ok_short:
            reason = f'Pullback EMA{ema_fast_period_for_reason} ({ema_fast_last:.4f}) rechazo'
            if use_trend_filter:
                reason += ' (Filtro OK)'
            return {'action': 'short', 'reason': reason}

    # ================================
    # 2. LÓGICA DE INVERSIÓN (si SÍ hay posición)
    # ================================
    else:
        current_side = position['side'].lower()

        # Supongamos que interpretas “señal contraria” más o menos igual que “entrada” al lado opuesto
        # Por ejemplo, si estamos en LONG y se detecta un escenario de SHORT:
        # (is_downtrending, touched_fast_short, closed_bearish, etc.)

        is_uptrending = (ema_fast_last > ema_slow_last)
        is_downtrending = (ema_fast_last < ema_slow_last)
        touched_fast_long = (last_candle['low'] <= ema_fast_last)
        touched_fast_short = (last_candle['high'] >= ema_fast_last)
        closed_bullish = (last_candle['close'] > last_candle['open'])
        closed_bearish = (last_candle['close'] < last_candle['open'])

        # Filtro de tendencia si lo usas también para invertir
        trend_ok_long = True
        trend_ok_short = True
        if use_trend_filter:
            ema_filter_last = last_row['ema_filter']
            trend_ok_long = (last_candle['close'] > ema_filter_last)
            trend_ok_short = (last_candle['close'] < ema_filter_last)

        if current_side == 'long':
            # Revisar si hay condiciones para “SHORT de Pullback”
            if is_downtrending and touched_fast_short and closed_bearish and trend_ok_short:
                reason = f'Invertir LONG->SHORT por Pullback EMA{ema_fast_period_for_reason} ({ema_fast_last:.4f})'
                if use_trend_filter:
                    reason += ' (Filtro OK)'
                return {'action': 'invertir_posicion', 'reason': reason}

        elif current_side == 'short':
            # Revisar si hay condiciones para “LONG de Pullback”
            if is_uptrending and touched_fast_long and closed_bullish and trend_ok_long:
                reason = f'Invertir SHORT->LONG por Pullback EMA{ema_fast_period_for_reason} ({ema_fast_last:.4f})'
                if use_trend_filter:
                    reason += ' (Filtro OK)'
                return {'action': 'invertir_posicion', 'reason': reason}

    # Si nada coincide
    return None
