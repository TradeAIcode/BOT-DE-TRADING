# -*- coding: utf-8 -*-
import traceback

def execute_auto_profit(exchange, position_info, current_price, config):
    """
    Verifica si el Auto Profit (Take Profit) debe activarse basado en PNL% o precio.
    Retorna True si se activó y se debe cerrar, False en caso contrario.
    """
    if not position_info or current_price is None:
        # print("Debug AP: No hay posición o precio actual para evaluar AP.")
        return False

    # Obtener porcentaje de AP desde la configuración
    ap_pct_config = config.get("auto_profit", 0.0)
    try:
        ap_pct = abs(float(ap_pct_config)) # Usar valor absoluto
        if ap_pct <= 0.001: # Considerar un umbral mínimo
            return False # Auto Profit desactivado o inválido
    except (ValueError, TypeError):
        print(f"Error [Auto Profit]: Valor de auto_profit ('{ap_pct_config}') inválido en config.")
        return False

    side = position_info.get('side')
    entry_price = position_info.get('entry_price')
    pnl_pct = position_info.get('pnl_pct') # PNL% calculado por ccxt (preferido)

    if not side or not entry_price:
         print("Error [Auto Profit]: Información de posición incompleta (side/entry_price).")
         return False

    take_profit_triggered = False
    trigger_reason = ""

    # --- Método 1: Usar PNL% de CCXT ---
    if pnl_pct is not None:
        try:
            current_pnl = float(pnl_pct)
            # Si el PNL actual es mayor o igual que el AP configurado (positivo)
            if current_pnl >= (ap_pct / 100.0):
                trigger_reason = f"PNL% ({current_pnl*100:.2f}% >= {ap_pct:.1f}%)" # Ajusta el log también si quieres
                take_profit_triggered = True
            # else: # Log para depuración
            #     print(f"Debug AP (PNL%): {current_pnl:.2f}% < {ap_pct:.1f}%")
        except (ValueError, TypeError):
            print(f"Advertencia [Auto Profit]: PNL% ('{pnl_pct}') no es numérico. Calculando por precio.")
            pnl_pct = None # Marcar para usar cálculo por precio

    # --- Método 2: Calcular por Precio (si PNL% no estaba disponible o falló) ---
    if not take_profit_triggered and pnl_pct is None:
        try:
            if side == 'long':
                # Precio al que se activa el AP para LONG
                ap_price = entry_price * (1 + ap_pct / 100.0)
                if current_price >= ap_price:
                    trigger_reason = f"Precio ({current_price:.4f} >= AP Price {ap_price:.4f})"
                    take_profit_triggered = True
                # else: # Log para depuración
                #      print(f"Debug AP (Price LONG): {current_price:.4f} < {ap_price:.4f}")

            elif side == 'short':
                # Precio al que se activa el AP para SHORT
                ap_price = entry_price * (1 - ap_pct / 100.0)
                if current_price <= ap_price:
                    trigger_reason = f"Precio ({current_price:.4f} <= AP Price {ap_price:.4f})"
                    take_profit_triggered = True
                # else: # Log para depuración
                #      print(f"Debug AP (Price SHORT): {current_price:.4f} > {ap_price:.4f}")

        except Exception as e:
            print(f"Error [Auto Profit]: Calculando AP por precio: {e}")
            traceback.print_exc()
            return False

    # Loguear si se activó
    if take_profit_triggered:
        print(f"✅ Auto Profit ACTIVADO para {side} @ {entry_price:.4f}. Motivo: {trigger_reason}")

    # El cierre real se hace en el worker
    return take_profit_triggered