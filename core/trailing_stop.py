# -*- coding: utf-8 -*-
import traceback
import math # Necesario para -math.inf

# --- CÓDIGO CON LÓGICA BASADA EN PNL% ---
# --- MANTIENE EL NOMBRE execute_trailing_stop ---

# Recordatorio: El estado esperado en trailing_data y DEFAULT_TS_STATE
#               (definido en state_manager.py) debe ser ahora:
# DEFAULT_TS_STATE = {
#    "active": False,
#    "peak_pnl_pct": 0.0,        # PNL% pico (ratio decimal)
#    "target_pnl_pct": -math.inf # PNL% de stop (ratio decimal)
# }

def execute_trailing_stop(exchange, position_info, current_price, trailing_data, config):
    """
    Gestiona la lógica del Trailing Stop BASADO EN PNL%.
    trailing_data esperado: {"active": bool, "peak_pnl_pct": float, "target_pnl_pct": float}
    """
    # --- Validación inicial ---
    if not position_info or current_price is None or current_price <= 0:
        if trailing_data.get("active"):
            print("Debug TS (PNL): Reseteando TS por falta de posición/precio.")
            # Usar el default PNL-based
            trailing_data = {"active": False, "peak_pnl_pct": 0.0, "target_pnl_pct": -math.inf}
        return trailing_data, False, "Sin posición/precio"

    # --- Obtener Parámetros (ts_dist_pct ahora es sobre PNL) ---
    try:
        ts_trigger_pct_cfg = abs(float(config.get("trailing_trigger", 0.0)))
        ts_dist_pct_cfg = abs(float(config.get("trailing_stop", 0.0))) # Ahora es % de caída PNL

        if ts_trigger_pct_cfg <= 0.001 or ts_dist_pct_cfg <= 0.001:
            if trailing_data.get("active"):
                print("Debug TS (PNL): Desactivando TS por config.")
                # Usar el default PNL-based
                trailing_data = {"active": False, "peak_pnl_pct": 0.0, "target_pnl_pct": -math.inf}
            return trailing_data, False, "Trigger/Distancia inválidos"
    except (ValueError, TypeError) as e:
        print(f"Error [Trailing Stop PNL]: Valores de config inválidos: {e}")
        if trailing_data.get("active"):
            # Usar el default PNL-based
            trailing_data = {"active": False, "peak_pnl_pct": 0.0, "target_pnl_pct": -math.inf}
        return trailing_data, False, "Error config TS"

    # --- Extraer PNL% (Asegurar que sea ratio decimal consistente) ---
    pnl_pct = position_info.get('pnl_pct') # Ratio decimal
    if pnl_pct is None:
        print("WARN [Trailing Stop PNL]: pnl_pct no encontrado, calculando manualmente como ratio.")
        side = position_info.get('side')
        entry_price = position_info.get('entry_price')
        if entry_price is not None and entry_price > 0 and current_price is not None and side:
            if side == 'long': pnl_pct = (current_price - entry_price) / entry_price
            elif side == 'short': pnl_pct = (entry_price - current_price) / entry_price
            else: pnl_pct = 0.0
        else: pnl_pct = 0.0
    # Asegurarse de que pnl_pct no sea None
    if pnl_pct is None: pnl_pct = 0.0

    # --- Lógica del Trailing Stop BASADO EN PNL ---
    # Leer estado actual desde trailing_data
    is_active = trailing_data.get("active", False)
    peak_pnl_pct = trailing_data.get("peak_pnl_pct", 0.0)           # PNL pico visto
    target_pnl_pct = trailing_data.get("target_pnl_pct", -math.inf) # PNL que dispara stop
    should_close_now = False
    ts_reason = "Sin cambios"

    # Convertir config a ratio decimal para cálculos
    trigger_ratio = ts_trigger_pct_cfg / 100.0
    # distance_ratio = ts_dist_pct_cfg / 100.0 # <-- Comenta o elimina esta línea
    target_pct_ratio = ts_dist_pct_cfg / 100.0 # <-- AÑADE ESTA LÍNEA (con el nuevo nombre si quieres)

    # 1. Activar si no está activo y PNL alcanza el trigger
    if not is_active:
        if pnl_pct >= trigger_ratio:
            is_active = True
            peak_pnl_pct = pnl_pct # PNL actual es el primer pico
            # target_pnl_pct = peak_pnl_pct - distance_ratio # <-- LÍNEA ORIGINAL COMENTADA
            target_pnl_pct = peak_pnl_pct * target_pct_ratio # <-- NUEVA LÍNEA: Multiplica por el ratio
            ts_reason = f"Activado PNL: {pnl_pct*100:.2f}% >= Trig {ts_trigger_pct_cfg:.1f}%. Stop PNL inicial en {target_pnl_pct*100:.2f}% ({ts_dist_pct_cfg}% del pico)"
            print(f"Debug TS (PNL): {ts_reason}")
        # else: No hacer nada si no se activa

    # 2. Gestionar si ya está activo
    if is_active:
        # a) Comprobar si PNL actual supera el pico guardado
        if pnl_pct > peak_pnl_pct:
            peak_pnl_pct = pnl_pct # Actualizar pico
            # target_pnl_pct = peak_pnl_pct - distance_ratio # <-- LÍNEA ORIGINAL COMENTADA
            target_pnl_pct = peak_pnl_pct * target_pct_ratio # <-- NUEVA LÍNEA: Multiplica por el ratio
            ts_reason = f"Nuevo PNL Pico: {peak_pnl_pct*100:.2f}%. Stop PNL movido a {target_pnl_pct*100:.2f}% ({ts_dist_pct_cfg}% del pico)"
            # print(f"Debug TS (PNL): {ts_reason}") # Log opcional

        # b) Comprobar si PNL actual toca o baja del nivel de stop PNL
        elif pnl_pct <= target_pnl_pct:
             ts_reason = f"Nuevo PNL Pico: {peak_pnl_pct*100:.2f}%. Stop PNL movido a {target_pnl_pct*100:.2f}% ({ts_dist_pct_cfg}% del pico)"
             print(f"⛔ {ts_reason}")
             should_close_now = True
        else:
             # Si no hay nuevo pico ni cierre, indicar estado
             ts_reason = f"Activo, PNL Actual {pnl_pct*100:.2f}%, Stop PNL en {target_pnl_pct*100:.2f}% ({ts_dist_pct_cfg}% del pico)"

    # --- Actualizar y devolver estado ---
    # Crear copia para devolver con los campos correctos
    new_trailing_data = {} # Empezar diccionario vacío
    new_trailing_data["active"] = is_active
    new_trailing_data["peak_pnl_pct"] = peak_pnl_pct
    new_trailing_data["target_pnl_pct"] = target_pnl_pct

    if should_close_now:
        # Resetear estado PNL-based para la próxima vez
        new_trailing_data["active"] = False
        new_trailing_data["peak_pnl_pct"] = 0.0
        new_trailing_data["target_pnl_pct"] = -math.inf
        # ts_reason ya se estableció

    # Devolver el estado actualizado, si se debe cerrar, y la razón
    return new_trailing_data, should_close_now, ts_reason

# --- FIN CÓDIGO MODIFICADO ---