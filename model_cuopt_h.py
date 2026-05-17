import numpy as np
from typing import List, Tuple, Dict, Any
from config import TIME_LIMIT, MPS_FILE
from model_general import HarvestData
from cuopt_to_mps import save_as_mps

def build_cuopt_problem(data: HarvestData, n: int) -> Tuple[Dict[str, Any], Dict[str, int]]:

    

    field_ids, comb_ids, truck_ids = data.field_ids, data.comb_ids, data.truck_ids
    elev_ids, point_ids, wh_ids = data.elev_ids, data.point_ids, data.wh_ids
    days = data.days
    T_max = len(days)
    T_shift = data.T_shift
    MAX_SHIFT_HOURS = data.T_shift_max
    OVERTIME_HOURS = MAX_SHIFT_HOURS - T_shift
    MIN_HARVEST_TONS = data.min_harvest_tons
    MIN_LOAD_RATIO = data.min_load_ratio
    TERMINAL_DAYS = data.terminal_days
    M_big = data.M_big
    BIG_M = 1e6
    EPS = 0.01
    MAX_IDLE_DAYS = 3
    WINDOW = MAX_IDLE_DAYS + 1


    var_names = np.empty(n, dtype=object)
    var_types = np.empty(n, dtype='U1')
    var_lb = np.zeros(n, dtype=np.float32)
    var_ub = np.full(n, BIG_M, dtype=np.float32)
    obj_coef = np.zeros(n, dtype=np.float32)
    
    var_index: Dict[str, int] = {}
    current_idx = 0

    def idx(name: str) -> int:
        return var_index[name]

    def add_var(name: str, vtype: str = "C", lb: float = 0.0, ub: float = BIG_M):
        nonlocal current_idx
        if name in var_index:
            return
        var_index[name] = current_idx
        var_names[current_idx] = name
        var_types[current_idx] = vtype
        var_lb[current_idx] = lb
        var_ub[current_idx] = ub
        current_idx += 1

    def add_obj(name: str, coef: float):
        if name in var_index:
            obj_coef[idx(name)] += coef

    offsets = [0]
    indices: List[int] = []
    values: List[float] = []
    lower_bounds: List[float] = []
    upper_bounds: List[float] = []

    def add_constraint(coeffs: List[Tuple[int, float]], lb: float, ub: float):
        for i, v in coeffs:
            indices.append(i)
            values.append(v)
        offsets.append(len(indices))
        lower_bounds.append(lb)
        upper_bounds.append(ub)


    for i in field_ids:
        for k in comb_ids:
            for t in days:
                add_var(f"h_{i}_{k}_{t}", "C")
                add_var(f"a_{i}_{k}_{t}", "B")
        for t in days:
            add_var(f"u_{i}_{t}", "B")

    for i in field_ids:
        if data.field_type[i] == 3:
            w = data.field_warehouse[i]
            for t in days: add_var(f"q_{i}_{w}_{t}", "C")
        elif data.field_type[i] in (1, 2):
            for e in elev_ids:
                for t in days: add_var(f"q_fe_{i}_{e}_{t}", "C")
            for p in point_ids:
                for t in days: add_var(f"q_fp_{i}_{p}_{t}", "C")

    for i in field_ids:
        if data.field_type[i] == 3:
            w = data.field_warehouse[i]
            for t in days:
                for m in truck_ids: add_var(f"z_{i}_{w}_{t}_{m}", "I")
        elif data.field_type[i] in (1, 2):
            for e in elev_ids:
                for t in days:
                    for m in truck_ids: add_var(f"z_fe_{i}_{e}_{t}_{m}", "I")
            for p in point_ids:
                for t in days:
                    for m in truck_ids: add_var(f"z_fp_{i}_{p}_{t}_{m}", "I")

    for w in wh_ids:
        for t in days:
            add_var(f"S_w_{w}_{t}", "C")
            add_var(f"overflow_{w}_{t}", "C")
            for e in elev_ids:
                add_var(f"f_{w}_{e}_{t}", "C")
                for m in truck_ids: add_var(f"y_{w}_{e}_{t}_{m}", "I")
            for p in point_ids:
                add_var(f"g_{w}_{p}_{t}", "C")
                for m in truck_ids: add_var(f"yP_{w}_{p}_{t}_{m}", "I")

    for p in point_ids:
        for e in elev_ids:
            for t in days:
                add_var(f"t_pe_{p}_{e}_{t}", "C")
                for m in truck_ids: add_var(f"w_pe_{p}_{e}_{t}_{m}", "I")
        for t in days: add_var(f"S_p_{p}_{t}", "C")

    for e in elev_ids:
        for t in days:
            add_var(f"S_e_{e}_{t}", "C")
            add_var(f"offload_{e}_{t}", "C")
            add_var(f"shortfall_{e}_{t}", "C")

    for i in field_ids:
        add_var(f"unharvested_{i}", "C")
        if data.field_type[i] == 2:
            for t in days:
                add_var(f"S_f_{i}_{t}", "C")
                add_var(f"b_{i}_{t}", "B")

    # Мягкие переменные
    for i in field_ids:
        for k in comb_ids:
            for t in days: add_var(f"h_shortage_{i}_{k}_{t}", "C", ub=1e6)
    for k in comb_ids:
        for t in days: add_var(f"combine_overtime_{k}_{t}", "C", lb=0.0, ub=OVERTIME_HOURS)
    for m in truck_ids:
        for t in days: add_var(f"truck_overtime_{m}_{t}", "C", lb=0.0, ub=OVERTIME_HOURS)
    for i in field_ids:
        for t_start in range(1, T_max - WINDOW + 2):
            add_var(f"idle_penalty_{i}_{t_start}", "C")


    for i in field_ids:
        yield_i = data.field_yield[i]
        for k in comb_ids:
            max_h = min(yield_i, data.comb_productivity[k] * T_shift)
            for t in days:
                var_ub[idx(f"h_{i}_{k}_{t}")] = max_h
                var_ub[idx(f"a_{i}_{k}_{t}")] = 1.0

    for w in wh_ids:
        max_yield = sum(data.field_yield[i] for i in field_ids if data.field_warehouse.get(i) == w)
        for t in days:
            var_ub[idx(f"S_w_{w}_{t}")] = data.wh_capacity[w]
            var_ub[idx(f"overflow_{w}_{t}")] = max_yield

    for e in elev_ids:
        for t in days: var_ub[idx(f"S_e_{e}_{t}")] = data.elev_capacity[e]
    for p in point_ids:
        for t in days: var_ub[idx(f"S_p_{p}_{t}")] = data.point_capacity[p]


    # 1. Комбайны
    for i in field_ids:
        for k in comb_ids:
            for t in days: add_obj(f"h_{i}_{k}_{t}", data.comb_cost[k])

    # 2. Перевозки
    for i in field_ids:
        if data.field_type.get(i) == 3:
            w = data.field_warehouse[i]
            key = ('I', i, 'W', w)
            if key in data.dist:
                d = data.dist[key]
                for t in days:
                    for m in truck_ids: add_obj(f"z_{i}_{w}_{t}_{m}", data.truck_cost_km[m] * 2 * d)

    for w in wh_ids:
        for e in elev_ids:
            key = ('W', w, 'E', e)
            if key in data.dist:
                d = data.dist[key]
                for t in days:
                    for m in truck_ids: add_obj(f"y_{w}_{e}_{t}_{m}", data.truck_cost_km[m] * 2 * d)
        for p in point_ids:
            key = ('W', w, 'P', p)
            if key in data.dist:
                d = data.dist[key]
                for t in days:
                    for m in truck_ids: add_obj(f"yP_{w}_{p}_{t}_{m}", data.truck_cost_km[m] * 2 * d)

    for p in point_ids:
        for e in elev_ids:
            key = ('P', p, 'E', e)
            if key in data.dist:
                d = data.dist[key]
                for t in days:
                    for m in truck_ids: add_obj(f"w_pe_{p}_{e}_{t}_{m}", data.truck_cost_km[m] * 2 * d)

    for i in field_ids:
        if data.field_type[i] in (1, 2):
            for e in elev_ids:
                key = ('I', i, 'E', e)
                if key in data.dist:
                    d = data.dist[key]
                    for t in days:
                        for m in truck_ids: add_obj(f"z_fe_{i}_{e}_{t}_{m}", data.truck_cost_km[m] * 2 * d)
            for p in point_ids:
                key = ('I', i, 'P', p)
                if key in data.dist:
                    d = data.dist[key]
                    for t in days:
                        for m in truck_ids: add_obj(f"z_fp_{i}_{p}_{t}_{m}", data.truck_cost_km[m] * 2 * d)

    # 3. Сушка и хранение
    for e in elev_ids:
        for t in days:
            for p in point_ids: add_obj(f"t_pe_{p}_{e}_{t}", data.elev_drying_cost[e])
            for i in field_ids:
                if data.field_type[i] in (1, 2): add_obj(f"q_fe_{i}_{e}_{t}", data.elev_drying_cost[e])
            add_obj(f"S_e_{e}_{t}", data.elev_storage_cost[e])

    for p in point_ids:
        for t in days: add_obj(f"S_p_{p}_{t}", data.point_storage_cost[p])

    for w in wh_ids:
        for t in days:
            for i in field_ids:
                if data.field_type.get(i) == 3 and data.field_warehouse.get(i) == w:
                    add_obj(f"q_{i}_{w}_{t}", data.wh_drying_cost[w])
            add_obj(f"S_w_{w}_{t}", data.wh_storage_cost[w])

    # 4. Штрафы
    for i in field_ids: add_obj(f"unharvested_{i}", M_big)
    for w in wh_ids:
        for t in days: add_obj(f"overflow_{w}_{t}", M_big)
    for e in elev_ids:
        for t in days: add_obj(f"shortfall_{e}_{t}", M_big)
    for k in comb_ids:
        for t in days: add_obj(f"combine_overtime_{k}_{t}", M_big)
    for m in truck_ids:
        for t in days: add_obj(f"truck_overtime_{m}_{t}", M_big)
    for i in field_ids:
        for k in comb_ids:
            for t in days: add_obj(f"h_shortage_{i}_{k}_{t}", M_big)
    for i in field_ids:
        for t_start in range(1, T_max - WINDOW + 2):
            add_obj(f"idle_penalty_{i}_{t_start}", M_big)          


    for i in field_ids:
        if data.field_type.get(i) == 2:
            loss_rate = data.field_loss_rate.get(i, 0.0)
            if loss_rate > 0:
                daily_penalty = data.M_big * loss_rate
                for t in days:
                    add_obj(f"S_f_{i}_{t}", daily_penalty)


    for p in point_ids:
        loss_rate = data.point_loss.get(p, 0.0)
        if loss_rate > 0:
            daily_penalty = data.M_big * loss_rate
            for t in days:
                add_obj(f"S_p_{p}_{t}", daily_penalty)


    terminal_storage_cost = {
        'warehouse': {w: data.wh_storage_cost[w] * TERMINAL_DAYS for w in data.wh_ids},
        'elevator': {e: data.elev_storage_cost[e] * TERMINAL_DAYS for e in data.elev_ids},
        'point': {p: data.point_storage_cost[p] * TERMINAL_DAYS for p in data.point_ids},
    }
    # Штраф за остатки на складах
    for w in data.wh_ids:
        last_day = data.days[-1]
        var_name = f"S_w_{w}_{last_day}"
        if var_name in var_index:
            penalty = terminal_storage_cost['warehouse'][w]
            add_obj(var_name, penalty)


    # Штраф за остатки на элеваторах
    for e in data.elev_ids:
        last_day = data.days[-1]
        var_name = f"S_e_{e}_{last_day}"
        if var_name in var_index:
            penalty = terminal_storage_cost['elevator'][e]
            add_obj(var_name, penalty)


    # Штраф за остатки на ПП
    for p in data.point_ids:
        last_day = data.days[-1]
        var_name = f"S_p_{p}_{last_day}"
        if var_name in var_index:
            penalty = terminal_storage_cost['point'][p]
            add_obj(var_name, penalty)




    for i in data.field_ids:
        if data.field_type.get(i) == 2:
            loss_rate = data.field_loss_rate.get(i, 0.0)
            if loss_rate > 0: 
                last_day = data.days[-1]
                var_name = f"S_f_{i}_{last_day}"  
                if var_name in var_index:

                    penalty = data.M_big * loss_rate
                    add_obj(var_name, penalty)


    for p in data.point_ids:
        loss_rate = data.point_loss.get(p, 0.0)
        if loss_rate > 0:
            last_day = data.days[-1]
            var_name = f"S_p_{p}_{last_day}"  
            if var_name in var_index:
                penalty = data.M_big * loss_rate
                add_obj(var_name, penalty)
            

    print("3. ФОРМИРОВАНИЕ ОГРАНИЧЕНИЙ В CSR-ФОРМАТЕ")


    for i in field_ids:
        coeffs = [(idx(f"h_{i}_{k}_{t}"), 1.0) for k in comb_ids for t in days]
        coeffs.append((idx(f"unharvested_{i}"), 1.0))
        add_constraint(coeffs, data.field_yield[i], data.field_yield[i])


    for i in field_ids:
        for k in comb_ids:
            prod_k = data.comb_productivity[k]
            for t in days:
                ih, ia = idx(f"h_{i}_{k}_{t}"), idx(f"a_{i}_{k}_{t}")
                iot = idx(f"combine_overtime_{k}_{t}")  

                if t in data.comb_maintenance[k]:
                    var_ub[ih] = 0.0
                    var_ub[ia] = 0.0
                    var_ub[iot] = 0.0  
                else:

                    add_constraint([
                        (ih, 1.0),
                        (ia, -prod_k * T_shift),
                        (iot, -prod_k)
                    ], -BIG_M, 0.0)


                add_constraint([(ih, 1.0), (ia, -MIN_HARVEST_TONS), (idx(f"h_shortage_{i}_{k}_{t}"), 1.0)], 0.0, BIG_M)

    for k in comb_ids:
        for t in days:
            add_constraint([(idx(f"a_{i}_{k}_{t}"), 1.0) for i in field_ids], -BIG_M, 1.0)


    for i in field_ids:
        yi = data.field_yield[i]
        for t in days:
            add_constraint([(idx(f"u_{i}_{t}"), -yi)] + [(idx(f"h_{i}_{k}_{t}"), 1.0) for k in comb_ids], -BIG_M, 0.0)
            add_constraint([(idx(f"u_{i}_{t}"), EPS)] + [(idx(f"h_{i}_{k}_{t}"), -1.0) for k in comb_ids], -BIG_M, 0.0)


    for i in field_ids:
        for t_start in range(1, T_max - WINDOW + 2):
            coeffs = [(idx(f"u_{i}_{t}"), 1.0) for t in range(t_start, t_start + WINDOW)]
            coeffs.append((idx(f"idle_penalty_{i}_{t_start}"), 1.0))
            add_constraint(coeffs, 1.0, BIG_M)


    for i in field_ids:
        ft = data.field_type[i]
        for t_idx, t in enumerate(days):
            h_sum = [(idx(f"h_{i}_{k}_{t}"), 1.0) for k in comb_ids]
            if ft == 3:
                w = data.field_warehouse[i]
                add_constraint(h_sum + [(idx(f"q_{i}_{w}_{t}"), -1.0)], 0.0, 0.0)
            elif ft == 1:
                out = [(idx(f"q_fe_{i}_{e}_{t}"), -1.0) for e in elev_ids] + \
                      [(idx(f"q_fp_{i}_{p}_{t}"), -1.0) for p in point_ids]
                add_constraint(h_sum + out, 0.0, 0.0)
            elif ft == 2:
                loss = data.field_loss_rate.get(i, 0.0)

                out = [(idx(f"q_fe_{i}_{e}_{t}"), -1.0) for e in elev_ids] + \
                      [(idx(f"q_fp_{i}_{p}_{t}"), -1.0) for p in point_ids]


                coeffs = h_sum + out
                coeffs.append((idx(f"S_f_{i}_{t}"), -1.0))  
                
                if t_idx > 0:

                    coeffs.append((idx(f"S_f_{i}_{days[t_idx-1]}"), 1.0 - loss))
                
                add_constraint(coeffs, 0.0, 0.0)


    print("\nНастройка ограничений для полей типа 2...")

    for i in field_ids:
        if data.field_type[i] != 2: 
            continue


        max_days = data.field_max_storage.get(i)
        min_int = data.field_min_interval.get(i)
        
        if max_days is None and min_int is None:
            print(f"Поле {i}: параметры хранения не заданы, пропускаем доп. ограничения")
            continue

        max_trips_per_day = (data.T_shift_max * 60) // 30  
        max_daily_outflow = len(data.truck_ids) * max(data.truck_capacity.values()) * max_trips_per_day
        BigM = max(data.field_yield[i], max_daily_outflow * 1.5) 
        
        print(f"Поле {i}: max_days={max_days}, min_int={min_int}, BigM={BigM:.0f}")


        if max_days and max_days > 0:
            count = 0
            for t_idx, t in enumerate(days):
                start = max(1, t - max_days + 1)
                h_window = [(idx(f"h_{i}_{k}_{s}"), -1.0) 
                            for s in range(start, t+1) for k in comb_ids]
                add_constraint([(idx(f"S_f_{i}_{t}"), 1.0)] + h_window, lb=-BIG_M, ub=0.0)
                count += 1
            print(f"  Добавлено {count} ограничений FIFO (max_storage={max_days})")


        if min_int and min_int > 1:
            print(f"  Активирую min_int={min_int} дня(ей)")
            

            for t in days:

                total_outflow = (
                    [(idx(f"q_fe_{i}_{e}_{t}"), 1.0) for e in elev_ids] +
                    [(idx(f"q_fp_{i}_{p}_{t}"), 1.0) for p in point_ids]
                )
                

                add_constraint(total_outflow + [(idx(f"b_{i}_{t}"), -BigM)], lb=-BigM, ub=0.0)

                add_constraint(total_outflow + [(idx(f"b_{i}_{t}"), -0.1)], lb=0.0, ub=BIG_M)

            violation_count = 0
            for t in days:
                start = max(1, t - min_int + 1)
                window_bs = [(idx(f"b_{i}_{s}"), 1.0) for s in range(start, t+1)]
                add_constraint(window_bs, lb=-BIG_M, ub=1.0)
                violation_count += 1
            
            print(f"         Добавлено {violation_count} ограничений частоты (окно={min_int} дней)")


    for i in field_ids:
        if data.field_type[i] in (1, 2):
            for e in elev_ids:
                for t in days:
                    add_constraint([(idx(f"q_fe_{i}_{e}_{t}"), 1.0)] + 
                                   [(idx(f"z_fe_{i}_{e}_{t}_{m}"), -data.truck_capacity[m]) for m in truck_ids], -BIG_M, 0.0)
            for p in point_ids:
                for t in days:
                    add_constraint([(idx(f"q_fp_{i}_{p}_{t}"), 1.0)] + 
                                   [(idx(f"z_fp_{i}_{p}_{t}_{m}"), -data.truck_capacity[m]) for m in truck_ids], -BIG_M, 0.0)
        elif data.field_type[i] == 3:
            w = data.field_warehouse[i]
            for t in days:
                add_constraint([(idx(f"q_{i}_{w}_{t}"), 1.0)] + 
                               [(idx(f"z_{i}_{w}_{t}_{m}"), -data.truck_capacity[m]) for m in truck_ids], -BIG_M, 0.0)


    for w in wh_ids:
        for t_idx, t in enumerate(days):
            in_q = [(idx(f"q_{i}_{w}_{t}"), -1.0) for i in field_ids if data.field_type.get(i)==3 and data.field_warehouse.get(i)==w]
            out_fg = [(idx(f"f_{w}_{e}_{t}"), 1.0) for e in elev_ids] + [(idx(f"g_{w}_{p}_{t}"), 1.0) for p in point_ids]
            if t_idx == 0:
                add_constraint(in_q + out_fg + [(idx(f"S_w_{w}_{t}"), 1.0)], data.wh_initial[w], data.wh_initial[w])
            else:
                add_constraint(in_q + out_fg + [(idx(f"S_w_{w}_{t}"), 1.0), (idx(f"S_w_{w}_{t-1}"), -1.0)], 0.0, 0.0)
            
            add_constraint([(idx(f"S_w_{w}_{t}"), 1.0), (idx(f"overflow_{w}_{t}"), -1.0)], -BIG_M, data.wh_capacity[w])
            

            q_prev = [(idx(f"q_{i}_{w}_{t-1}"), -1.0) for i in field_ids if data.field_type.get(i)==3 and data.field_warehouse.get(i)==w] if t_idx>0 else []
            add_constraint([(idx(f"S_w_{w}_{t}"), 1.0)] + in_q + q_prev, -BIG_M, 0.0)


    for w in wh_ids:
        for e in elev_ids:
            for t in days:
                add_constraint([(idx(f"f_{w}_{e}_{t}"), 1.0)] + 
                               [(idx(f"y_{w}_{e}_{t}_{m}"), -data.truck_capacity[m]) for m in truck_ids], -BIG_M, 0.0)
        for p in point_ids:
            for t in days:
                add_constraint([(idx(f"g_{w}_{p}_{t}"), 1.0)] + 
                               [(idx(f"yP_{w}_{p}_{t}_{m}"), -data.truck_capacity[m]) for m in truck_ids], -BIG_M, 0.0)


    for e in elev_ids:
        for t_idx, t in enumerate(days):
            in_f = [(idx(f"f_{w}_{e}_{t}"), -1.0) for w in wh_ids]
            in_t = [(idx(f"t_pe_{p}_{e}_{t}"), -1.0) for p in point_ids]
            in_q = [(idx(f"q_fe_{i}_{e}_{t}"), -1.0) for i in field_ids if data.field_type[i] in (1,2)]
            out = [(idx(f"offload_{e}_{t}"), 1.0), (idx(f"S_e_{e}_{t}"), 1.0)]
            if t_idx == 0:
                add_constraint(in_f + in_t + in_q + out, data.elev_initial[e], data.elev_initial[e])
            else:
                add_constraint(in_f + in_t + in_q + out + [(idx(f"S_e_{e}_{t-1}"), -1.0)], 0.0, 0.0)
            add_constraint([(idx(f"S_e_{e}_{t}"), 1.0)], -BIG_M, data.elev_capacity[e])


    for e in elev_ids:
        plan_daily = np.asarray(data.elev_offload.get(e, np.zeros(len(days))), dtype=float).flatten()
        if len(plan_daily) > len(days): plan_daily = plan_daily[:len(days)]
        
        for t_idx, t in enumerate(days):
            plan_val = plan_daily[t_idx]

            if plan_val == 0:
                var_ub[idx(f"offload_{e}_{t}")] = 0.0
            else:

                var_ub[idx(f"offload_{e}_{t}")] = plan_val


    for p in point_ids:
        loss = data.point_loss[p]
        for t_idx, t in enumerate(days):
            in_g = [(idx(f"g_{w}_{p}_{t}"), -1.0) for w in wh_ids]
            in_q = [(idx(f"q_fp_{i}_{p}_{t}"), -1.0) for i in field_ids if data.field_type[i] in (1,2)]
            out = [(idx(f"t_pe_{p}_{e}_{t}"), 1.0) for e in elev_ids] + [(idx(f"S_p_{p}_{t}"), 1.0)]
            if t_idx == 0:
                add_constraint(in_g + in_q + out, data.point_initial[p] * (1 - loss), data.point_initial[p] * (1 - loss))
            else:
                add_constraint(in_g + in_q + out + [(idx(f"S_p_{p}_{t-1}"), -(1 - loss))], 0.0, 0.0)
            add_constraint([(idx(f"S_p_{p}_{t}"), 1.0)], -BIG_M, data.point_capacity[p])

    for p in point_ids:
        for e in elev_ids:
            for t in days:
                add_constraint([(idx(f"t_pe_{p}_{e}_{t}"), 1.0)] + 
                               [(idx(f"w_pe_{p}_{e}_{t}_{m}"), -data.truck_capacity[m]) for m in truck_ids], -BIG_M, 0.0)
        for t_idx, t in enumerate(days):
            if t_idx == 0:
                add_constraint([(idx(f"t_pe_{p}_{e}_{t}"), 1.0) for e in elev_ids], -BIG_M, data.point_initial[p])
            else:
                add_constraint([(idx(f"t_pe_{p}_{e}_{t}"), 1.0) for e in elev_ids] + [(idx(f"S_p_{p}_{t-1}"), -1.0)], -BIG_M, 0.0)


    print("6. Транспортные ресурсы (мягкое ограничение)")
    for t in days:
        for m in truck_ids:
            coeffs = [(idx(f"truck_overtime_{m}_{t}"), -1.0)]
            
            for i in field_ids:
                if data.field_type[i] == 3:
                    w = data.field_warehouse[i]
                    key = ('I', i, 'W', w)
                    if key in data.dist:
                        travel = 2 * data.dist[key] / data.truck_speed[m]
                        coeffs.append((idx(f"z_{i}_{w}_{t}_{m}"), travel))
                        
            for i in field_ids:
                if data.field_type[i] in (1, 2):
                    for e in elev_ids:
                        key = ('I', i, 'E', e)
                        if key in data.dist:
                            travel = 2 * data.dist[key] / data.truck_speed[m]
                            coeffs.append((idx(f"z_fe_{i}_{e}_{t}_{m}"), travel))
                    for p in point_ids:
                        key = ('I', i, 'P', p)
                        if key in data.dist:
                            travel = 2 * data.dist[key] / data.truck_speed[m]
                            coeffs.append((idx(f"z_fp_{i}_{p}_{t}_{m}"), travel))
                            
            for w in wh_ids:
                for e in elev_ids:
                    key = ('W', w, 'E', e)
                    if key in data.dist:
                        travel = 2 * data.dist[key] / data.truck_speed[m]
                        coeffs.append((idx(f"y_{w}_{e}_{t}_{m}"), travel))
                for p in point_ids:
                    key = ('W', w, 'P', p)
                    if key in data.dist:
                        travel = 2 * data.dist[key] / data.truck_speed[m]
                        coeffs.append((idx(f"yP_{w}_{p}_{t}_{m}"), travel))
                        
            for p in point_ids:
                for e in elev_ids:
                    key = ('P', p, 'E', e)
                    if key in data.dist:
                        travel = 2 * data.dist[key] / data.truck_speed[m]
                        coeffs.append((idx(f"w_pe_{p}_{e}_{t}_{m}"), travel))
                        
            add_constraint(coeffs, -BIG_M, T_shift)


    print("7. Мягкие ограничения")
    for e in elev_ids:
        for t_idx, t in enumerate(days):
            add_constraint([(idx(f"offload_{e}_{t}"), 1.0), (idx(f"shortfall_{e}_{t}"), 1.0)], 
                           float(data.elev_offload[e][t_idx]), BIG_M)


    STANDARD_SHIFT = 8.0   
    MAX_OVERTIME = 4.0     

    for k in comb_ids:

        hours_per_ton = 1.0 / data.comb_productivity[k]
        
        for t in days:
            coeffs = [(idx(f"combine_overtime_{k}_{t}"), -1.0)]  
            
            for i in field_ids:

                coeffs.append((idx(f"h_{i}_{k}_{t}"), hours_per_ton))
                

            add_constraint(coeffs, -BIG_M, STANDARD_SHIFT)
            

            var_ub[idx(f"combine_overtime_{k}_{t}")] = MAX_OVERTIME


    print("Добавление нижних границ для связи поток ↔ рейсы...")
    for i in field_ids:
        if data.field_type[i] in (1, 2):
            for p in point_ids:
                for t in days:
                    add_constraint([(idx(f"q_fp_{i}_{p}_{t}"), 1.0)] + 
                                   [(idx(f"z_fp_{i}_{p}_{t}_{m}"), -data.truck_capacity[m]*MIN_LOAD_RATIO) for m in truck_ids], 0.0, BIG_M)
        elif data.field_type[i] == 3:
            w = data.field_warehouse[i]
            for t in days:
                add_constraint([(idx(f"q_{i}_{w}_{t}"), 1.0)] + 
                               [(idx(f"z_{i}_{w}_{t}_{m}"), -data.truck_capacity[m]*MIN_LOAD_RATIO) for m in truck_ids], 0.0, BIG_M)
                
    for w in wh_ids:
        for e in elev_ids:
            for t in days:
                add_constraint([(idx(f"f_{w}_{e}_{t}"), 1.0)] + 
                               [(idx(f"y_{w}_{e}_{t}_{m}"), -data.truck_capacity[m]*MIN_LOAD_RATIO) for m in truck_ids], 0.0, BIG_M)
        for p in point_ids:
            for t in days:
                add_constraint([(idx(f"g_{w}_{p}_{t}"), 1.0)] + 
                               [(idx(f"yP_{w}_{p}_{t}_{m}"), -data.truck_capacity[m]*MIN_LOAD_RATIO) for m in truck_ids], 0.0, BIG_M)
                
    for p in point_ids:
        for e in elev_ids:
            for t in days:
                add_constraint([(idx(f"t_pe_{p}_{e}_{t}"), 1.0)] + 
                               [(idx(f"w_pe_{p}_{e}_{t}_{m}"), -data.truck_capacity[m]*MIN_LOAD_RATIO) for m in truck_ids], 0.0, BIG_M)
                
    for i in field_ids:
        if data.field_type[i] in (1, 2):
            for e in elev_ids:
                for t in days:
                    add_constraint([(idx(f"q_fe_{i}_{e}_{t}"), 1.0)] + 
                                   [(idx(f"z_fe_{i}_{e}_{t}_{m}"), -data.truck_capacity[m]*MIN_LOAD_RATIO) for m in truck_ids], 0.0, BIG_M)
                    
    print(f"Добавлены нижние границы (MIN_LOAD_RATIO={MIN_LOAD_RATIO})")


    print(f"Сохранение модели в MPS: {MPS_FILE}")
    save_as_mps(
        var_names=var_names[:current_idx].tolist(),
        var_types=var_types[:current_idx].tolist(),
        var_lb=var_lb[:current_idx],
        var_ub=var_ub[:current_idx],
        obj_coef=obj_coef[:current_idx],
        offsets=offsets,
        indices=indices,
        values=values,
        con_lb=lower_bounds,
        con_ub=upper_bounds,
        output_path=MPS_FILE
    )
    print(f"MPS готово. {current_idx} переменных, {len(lower_bounds)} ограничений.")


    print(f"Ожидалось: ~{n}, Фактически создано: {current_idx}\n но не страшно, массивы будут сокращены при отправке")
    
    problem = {
        "csr_constraint_matrix": {"offsets": offsets, "indices": indices, "values": values},
        "constraint_bounds": {"lower_bounds": lower_bounds, "upper_bounds": upper_bounds},
        "objective_data": {"coefficients": obj_coef[:current_idx].tolist(), "scalability_factor": 1.0, "offset": 0.0},
        "variable_bounds": {"lower_bounds": var_lb[:current_idx].tolist(), "upper_bounds": var_ub[:current_idx].tolist()},
        "maximize": False,
        "variable_names": var_names[:current_idx].tolist(),
        "variable_types": var_types[:current_idx].tolist(),
        "solver_config": {
            "time_limit": TIME_LIMIT, 
            "log_to_console": True,
        }
    }
    return problem, var_index