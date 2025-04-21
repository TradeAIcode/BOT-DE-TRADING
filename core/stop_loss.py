# -*- coding: utf-8 -*-
import traceback

def execute_stop_loss(exchange, position_info, current_price, config):
    """
    Verifica si el Stop Loss debe activarse basado en el PNL% o el precio.
    Retorna True si se activó y se debe cerrar, False en caso contrario.
    """
    if not position_info or current_price is None:
        # print("Debug SL: No hay posición o precio actual para evaluar SL.")
        return False # No se puede evaluar sin posición o precio

    # Obtener porcentaje de SL desde la configuración
    sl_pct_config = config.get("stop_loss", 0.0)
    # Asegurarse de que sea un valor numérico y positivo
    try:
        sl_pct = abs(float(sl_pct_config)) # Usar valor absoluto
        if sl_pct <= 0.001: # Considerar un umbral mínimo, si es casi 0, está desactivado
            return False # Stop Loss desactivado o inválido
    except (ValueError, TypeError):
        print(f"Error [Stop Loss]: Valor de stop_loss ('{sl_pct_config}') inválido en config.")
        return False # Error en config, no activar

    side = position_info.get('side')
    entry_price = position_info.get('entry_price')
    pnl_pct = position_info.get('pnl_pct') # PNL% calculado por ccxt (preferido)

    if not side or not entry_price:
         print("Error [Stop Loss]: Información de posición incompleta (side/entry_price).")
         return False

    stop_loss_triggered = False
    trigger_reason = ""

    # --- Método 1: Usar PNL% de CCXT (si está disponible y parece fiable) ---
    # CCXT lo calcula basado en mark_price vs entry_price
    if pnl_pct is not None:
        try:
            current_pnl = float(pnl_pct)
            # Si el PNL actual es peor o igual que el SL configurado (negativo)
            if current_pnl <= -(sl_pct / 100.0):
                trigger_reason = f"PNL% ({current_pnl*100:.2f}% <= -{sl_pct:.1f}%)" # Ajusta el log también si quieres
                stop_loss_triggered = True
            # else: # Log para depuración si se quiere ver por qué NO se activó
            #      print(f"Debug SL (PNL%): {current_pnl:.2f}% > -{sl_pct:.1f}%")

        except (ValueError, TypeError):
            print(f"Advertencia [Stop Loss]: PNL% ('{pnl_pct}') no es numérico. Calculando por precio.")
            pnl_pct = None # Marcar para usar cálculo por precio

    # --- Método 2: Calcular por Precio (si PNL% no estaba disponible o falló) ---
    if not stop_loss_triggered and pnl_pct is None:
        try:
            if side == 'long':
                # Precio al que se activa el SL para LONG
                sl_price = entry_price * (1 - sl_pct / 100.0)
                if current_price <= sl_price:
                    trigger_reason = f"Precio ({current_price:.4f} <= SL Price {sl_price:.4f})"
                    stop_loss_triggered = True
                # else: # Log para depuración
                #      print(f"Debug SL (Price LONG): {current_price:.4f} > {sl_price:.4f}")

            elif side == 'short':
                # Precio al que se activa el SL para SHORT
                sl_price = entry_price * (1 + sl_pct / 100.0)
                if current_price >= sl_price:
                    trigger_reason = f"Precio ({current_price:.4f} >= SL Price {sl_price:.4f})"
                    stop_loss_triggered = True
                # else: # Log para depuración
                #      print(f"Debug SL (Price SHORT): {current_price:.4f} < {sl_price:.4f}")

        except Exception as e:
            print(f"Error [Stop Loss]: Calculando SL por precio: {e}")
            traceback.print_exc()
            return False # No activar si hay error en cálculo

    # Loguear si se activó
    if stop_loss_triggered:
        print(f"⛔ Stop Loss ACTIVADO para {side} @ {entry_price:.4f}. Motivo: {trigger_reason}")

    # Esta función solo decide si se DEBE cerrar.
    # La orden de cierre se ejecuta en el worker.
    return stop_loss_triggered