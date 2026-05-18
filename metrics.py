from collections import defaultdict
from types import NoneType
from typing import Any, Dict, List, Tuple

import numpy as np
from model_general import HarvestData, NormalizedSolution


class MetricsCalculator:
    
    def __init__(self, data: HarvestData, solution: NormalizedSolution):
        self.data = data
        self.sol = solution
        self.T = len(data.days)
        
    def compute_all(self) -> Dict:
        return {
            'costs': self._compute_costs(),
            'harvest': self._compute_harvest(),
            'final_stocks': self._compute_final_stocks(),
            'field_harvest_table': self._compute_field_harvest_table(),
            'field_type_summary': self._compute_field_type_summary(),
            'routes_by_volume': self._compute_routes(),
            'elev_inflow_by_source': self._compute_elev_inflow(),
            'daily_field_harvest': self._compute_daily_harvest(),
            'storage_daily': self._compute_storage_daily(),
            'truck_daily': self._compute_truck_daily(),
            'comb_daily': self._compute_comb_daily(),
            'harvest_by_day': self._compute_harvest_by_day(),
            'storage_chart_data': self._compute_storage_charts(),
            'input_summary': self._compute_input_summary(),  
            'type2_field_dynamics': self._compute_type2_field_dynamics(),  
            'elev_balance': self._compute_elevator_balance(),  
            'point_daily': self._compute_point_daily(),
            'warehouse_daily': self._compute_warehouse_daily()
        }
    
    def _compute_costs(self) -> Dict[str, float]:

        costs = defaultdict(float)
        data, sol = self.data, self.sol
        
        # 1. Уборка
        for i in data.field_ids:
            for k in data.comb_ids:
                for t in data.days:
                    h = sol.get(f"h_{i}_{k}_{t}", 0.0)
                    if h > 1e-4:
                        costs['harvesting'] += h * data.comb_cost[k]
        
        # 2. Транспорт
        def add_transport(prefix: str, src_ids: List, dst_ids: List, 
                         src_type: str, dst_type: str, cost_key: str):
            for s in src_ids:
                for d in dst_ids:
                    key = (src_type, s, dst_type, d)
                    dist = data.dist.get(key, 0)
                    if dist == 0: continue
                    for t in data.days:
                        for m in data.truck_ids:
                            trips = sol.get(f"{prefix}_{s}_{d}_{t}_{m}", 0.0)
                            if trips > 0.1:
                                costs[cost_key.replace('_km', '')] += trips * getattr(data, cost_key)[m] * 2 * dist
        
        for i in data.field_ids:
            if data.field_type[i] == 3:
                w = data.field_warehouse[i]
                add_transport("z", [i], [w], 'I', 'W', 'truck_cost_km')
            elif data.field_type[i] in (1, 2):
                add_transport("z_fe", [i], data.elev_ids, 'I', 'E', 'truck_cost_km')
                add_transport("z_fp", [i], data.point_ids, 'I', 'P', 'truck_cost_km')
        
        add_transport("y", data.wh_ids, data.elev_ids, 'W', 'E', 'truck_cost_km')
        add_transport("yP", data.wh_ids, data.point_ids, 'W', 'P', 'truck_cost_km')
        add_transport("w_pe", data.point_ids, data.elev_ids, 'P', 'E', 'truck_cost_km')
        
        # 3. Сушка
        for e in data.elev_ids:
            for t in data.days:
                for p in data.point_ids:
                    costs['drying_elev'] += sol.get(f"t_pe_{p}_{e}_{t}", 0.0) * data.elev_drying_cost[e]
                for i in data.field_ids:
                    if data.field_type[i] in (1, 2):
                        costs['drying_elev'] += sol.get(f"q_fe_{i}_{e}_{t}", 0.0) * data.elev_drying_cost[e]
        
        for w in data.wh_ids:
            for t in data.days:
                for i in data.field_ids:
                    if data.field_type.get(i) == 3 and data.field_warehouse.get(i) == w:
                        costs['drying_wh'] += sol.get(f"q_{i}_{w}_{t}", 0.0) * data.wh_drying_cost[w]
        
        # 4. Хранение
        for t in data.days:
            for w in data.wh_ids: costs['storage_wh'] += sol.get(f"S_w_{w}_{t}", 0.0) * data.wh_storage_cost[w]
            for e in data.elev_ids: costs['storage_elev'] += sol.get(f"S_e_{e}_{t}", 0.0) * data.elev_storage_cost[e]
            for p in data.point_ids: costs['storage_point'] += sol.get(f"S_p_{p}_{t}", 0.0) * data.point_storage_cost[p]
        

        penalties = defaultdict(float)
        
        for i in data.field_ids: penalties['penalty_unharvested'] += sol.get(f"unharvested_{i}", 0.0) * data.M_big
        

        max_idle_penalty_t = len(data.days) - (getattr(data, 'MAX_IDLE_DAYS', 3) + 1) + 2
        for i in data.field_ids:
            for t in range(1, max(2, max_idle_penalty_t)):
                penalties['penalty_idle'] += sol.get(f"idle_penalty_{i}_{t}", 0.0) * data.M_big
                
            for k in data.comb_ids:
                for t in data.days:
                    penalties['penalty_h_shortage'] += sol.get(f"h_shortage_{i}_{k}_{t}", 0.0) * data.M_big

        for w in data.wh_ids:
            for t in data.days: penalties['penalty_overflow'] += sol.get(f"overflow_{w}_{t}", 0.0) * data.M_big

        for e in data.elev_ids:
            for t in data.days: penalties['penalty_shortfall'] += sol.get(f"shortfall_{e}_{t}", 0.0) * data.M_big 

        for k in data.comb_ids:
            for t in data.days: penalties['penalty_combine_overtime'] += sol.get(f"combine_overtime_{k}_{t}", 0.0) * data.M_big

        for m in data.truck_ids:
            for t in data.days: penalties['penalty_truck_overtime'] += sol.get(f"truck_overtime_{m}_{t}", 0.0) * data.M_big


        for i in data.field_ids:
            if data.field_type.get(i) == 2:
                loss_rate = data.field_loss_rate.get(i, 0.0)
                if loss_rate > 0:
                    coef = data.M_big * loss_rate
                    for t in data.days:
                        penalties['penalty_field_loss_type2'] += sol.get(f"S_f_{i}_{t}", 0.0) * coef

        for p in data.point_ids:
            loss_rate = data.point_loss.get(p, 0.0)
            if loss_rate > 0:
                coef = data.M_big * loss_rate
                for t in data.days:
                    penalties['penalty_point_loss'] += sol.get(f"S_p_{p}_{t}", 0.0) * coef


        last_day = data.days[-1]
        term_days = data.terminal_days
        
        penalties['penalty_terminal_wh'] = sum(
            sol.get(f"S_w_{w}_{last_day}", 0.0) * data.wh_storage_cost[w] * term_days for w in data.wh_ids
        )
        penalties['penalty_terminal_elev'] = sum(
            sol.get(f"S_e_{e}_{last_day}", 0.0) * data.elev_storage_cost[e] * term_days for e in data.elev_ids
        )
        penalties['penalty_terminal_point'] = sum(
            sol.get(f"S_p_{p}_{last_day}", 0.0) * data.point_storage_cost[p] * term_days for p in data.point_ids
        )


        for i in data.field_ids:
            if data.field_type.get(i) == 2:
                loss_rate = data.field_loss_rate.get(i, 0.0)
                if loss_rate > 0:
                    penalties['penalty_terminal_field_loss'] += (
                        sol.get(f"S_f_{i}_{last_day}", 0.0) * loss_rate * data.M_big
                    )

        for p in data.point_ids:
            loss_rate = data.point_loss.get(p, 0.0)
            if loss_rate > 0:
                penalties['penalty_terminal_point_loss'] += (
                    sol.get(f"S_p_{p}_{last_day}", 0.0) * loss_rate * data.M_big
                )

        costs.update(penalties)
        return dict(costs)

    
    def _compute_harvest(self) -> Dict:

        data, sol = self.data, self.sol
        
        harvested_by_field = {}
        for i in data.field_ids:
            total = sum(sol.get(f"h_{i}_{k}_{t}") for k in data.comb_ids for t in data.days)
            harvested_by_field[i] = total
        
        planned = sum(data.field_yield[i] for i in data.field_ids)
        harvested = sum(harvested_by_field.values())
        
        return {
            'planned_total': planned,
            'harvested_total': harvested,
            'completion_pct': (harvested / planned * 100) if planned > 0 else 0,
            'by_field': harvested_by_field
        }
    
    def _compute_final_stocks(self) -> Dict:

        data, sol = self.data, self.sol
        last_day = data.days[-1]
        
        return {
            'warehouses': {w: sol.get(f"S_w_{w}_{last_day}") for w in data.wh_ids},
            'elevators': {e: sol.get(f"S_e_{e}_{last_day}") for e in data.elev_ids},
            'points': {p: sol.get(f"S_p_{p}_{last_day}") for p in data.point_ids}
        }
    
    def _compute_field_harvest_table(self) -> List[Dict]:

        data, sol = self.data, self.sol
        rows = []
        
        for i in data.field_ids:
            planned = data.field_yield[i]
            harvested = sum(sol.get(f"h_{i}_{k}_{t}") for k in data.comb_ids for t in data.days)
            rows.append({
                'field_id': i,
                'type': data.field_type[i],
                'warehouse': data.field_warehouse.get(i, '-') if data.field_type[i] == 3 else '-',
                'planned': planned,
                'harvested': harvested,
                'completion_pct': (harvested / planned * 100) if planned > 0 else 100,
                'remaining': max(0, planned - harvested)
            })
        
        return sorted(rows, key=lambda x: x['harvested'], reverse=True)
    
    def _compute_field_type_summary(self) -> Dict:

        summary = {t: {'planned': 0.0, 'harvested': 0.0, 'count': 0, 'completion_pct': 0.0} for t in [1, 2, 3]}
        
        for i in self.data.field_ids:
            f_type = self.data.field_type[i]  
            summary[f_type]['planned'] += self.data.field_yield[i]
            summary[f_type]['count'] += 1
            
            summary[f_type]['harvested'] += sum(
                self.sol.get(f"h_{i}_{k}_{day}") 
                for k in self.data.comb_ids 
                for day in self.data.days
            )
        
        # Расчёт выполнения по типам
        for f_type in summary:
            planned = summary[f_type]['planned']
            if planned > 0:
                summary[f_type]['completion_pct'] = (summary[f_type]['harvested'] / planned) * 100
            else:
                summary[f_type]['completion_pct'] = 100.0
                
        return summary
    
    def _compute_elev_inflow(self) -> Dict:
        data, sol = self.data, self.sol
        inflow = {e: {1: 0.0, 2: 0.0, 3: 0.0, 'total': 0.0} for e in data.elev_ids}
        
        for e in data.elev_ids:
            for t in data.days:
                # Со складов (тип 3)
                for w in data.wh_ids:
                    val = sol.get(f"f_{w}_{e}_{t}")
                    inflow[e][3] += val
                    inflow[e]['total'] += val
                # С ПП
                for p in data.point_ids:
                    val = sol.get(f"t_pe_{p}_{e}_{t}")
                    inflow[e][1] += val * 0.5
                    inflow[e][2] += val * 0.5
                    inflow[e]['total'] += val
                # Прямые с полей
                for i in data.field_ids:
                    if data.field_type[i] in (1, 2):
                        val = sol.get(f"q_fe_{i}_{e}_{t}")
                        inflow[e][data.field_type[i]] += val
                        inflow[e]['total'] += val
        
        # Проценты
        for e in data.elev_ids:
            total = inflow[e]['total']
            if total > 0:
                for t in [1, 2, 3]:
                    inflow[e][f'{t}_pct'] = inflow[e][t] / total * 100
        
        return inflow
    
    def _compute_daily_harvest(self) -> Dict:
        data, sol = self.data, self.sol
        daily = defaultdict(lambda: defaultdict(lambda: {'tons': 0.0, 'combiners': []}))
        
        for i in data.field_ids:
            for t in data.days:
                day_harvest = 0.0
                combs = []
                for k in data.comb_ids:
                    h = sol.get(f"h_{i}_{k}_{t}")
                    if h > 1e-4:
                        day_harvest += h
                        combs.append(k)
                daily[i][t] = {'tons': day_harvest, 'combiners': combs}
        
        return {i: dict(days) for i, days in daily.items()}
    
    def _compute_storage_daily(self) -> Dict:
        """Ежедневный баланс хранилищ"""
        data, sol = self.data, self.sol
        
        def compute(storage_type: str, ids: List, prefix: str, initial_attr: str):
            result = {}
            for eid in ids:
                init = getattr(data, initial_attr).get(eid, 0)
                days_data = []
                for t in data.days:
                    days_data.append({
                        'day': int(t),
                        'stock_end': sol.get(f"{prefix}_{eid}_{t}"),
                    })
                result[eid] = {'initial': init, 'daily': days_data}
            return result
        
        return {
            'warehouses': compute('warehouse', data.wh_ids, 'S_w', 'wh_initial'),
            'elevators': compute('elevator', data.elev_ids, 'S_e', 'elev_initial'),
            'points': compute('point', data.point_ids, 'S_p', 'point_initial'),
        }
    

    def _compute_truck_daily(self) -> Dict:
        data, sol = self.data, self.sol
        daily = {}
        
        for m in data.truck_ids:
            days_data = []
            for t in data.days:
                trips = 0
                
                # 1. Поле → Склад (тип 3)
                for i in data.field_ids:
                    if data.field_type[i] == 3:
                        w = data.field_warehouse[i]
                        trips += int(round(sol.get(f"z_{i}_{w}_{t}_{m}")))
                
                # 2. Поле → Элеватор (тип 1,2)
                for i in data.field_ids:
                    if data.field_type[i] in (1, 2):
                        for e in data.elev_ids:
                            trips += int(round(sol.get(f"z_fe_{i}_{e}_{t}_{m}")))
                
                # 3. Поле → ПП (тип 1,2)
                for i in data.field_ids:
                    if data.field_type[i] in (1, 2):
                        for p in data.point_ids:
                            trips += int(round(sol.get(f"z_fp_{i}_{p}_{t}_{m}")))
                
                # 4. Склад → Элеватор
                for w in data.wh_ids:
                    for e in data.elev_ids:
                        trips += int(round(sol.get(f"y_{w}_{e}_{t}_{m}")))
                
                # 5. Склад → ПП
                for w in data.wh_ids:
                    for p in data.point_ids:
                        trips += int(round(sol.get(f"yP_{w}_{p}_{t}_{m}")))
                
                # 6. ПП → Элеватор
                for p in data.point_ids:
                    for e in data.elev_ids:
                        trips += int(round(sol.get(f"w_pe_{p}_{e}_{t}_{m}")))
                
                overtime = sol.get(f"truck_overtime_{m}_{t}", 0.0)
                
                days_data.append({
                    'day': int(t),
                    'trips': trips,
                    'overtime_hours': overtime,
                    'shift_violated': overtime > 0.01
                })
            daily[m] = days_data
        
        total_trips = sum(d['trips'] for days in daily.values() for d in days)
        if total_trips == 0 and daily:
            print(f"ВНИМАНИЕ: Все рейсы грузовиков = 0. Проверь переменные z_*, y_*, w_pe в решении.")
        
        return daily

    def _compute_comb_daily(self) -> Dict:

        data, sol = self.data, self.sol
        daily = {}
        
        for k in data.comb_ids:
            days_data = []
            for t in data.days:
                harvest = 0.0
                for i in data.field_ids:
                    harvest += sol.get(f"h_{i}_{k}_{t}", 0.0)
                
                overtime_hours = sol.get(f"combine_overtime_{k}_{t}", 0.0)
                
                days_data.append({
                    'day': int(t),
                    'harvest_tons': harvest,
                    'overtime_hours': overtime_hours,
                    'shift_violated': overtime_hours > 0.01
                })
            daily[k] = days_data
        

        total_harvest = sum(d['harvest_tons'] for days in daily.values() for d in days)
        total_overtime = sum(d['overtime_hours'] for days in daily.values() for d in days)
        if total_harvest < 1.0 and daily:
            print(f"ВНИМАНИЕ: Выработка комбайнов ~0. Проверь переменные h_* в решении.")
        if total_overtime > 0:
            print(f"Найдена переработка комбайнов: {total_overtime:.2f} часов суммарно")
        else:
            print(f"Переработка комбайнов = 0 (модель уложилась в 8-часовую смену)")    
        
        return daily

    def _compute_routes(self) -> List[Tuple[str, Dict]]:
        data, sol = self.data, self.sol
        routes = defaultdict(lambda: {'trips': 0, 'tons': 0.0, 'km': 0.0})
        

        def add_tons(name: str, flow_var: str):
            tons = sol.get(flow_var, 0.0)
            routes[name]['tons'] += tons  

        def add_route(name: str, trip_var_prefix: str, 
                     src_id: int, dst_id: int, src_type: str, dst_type: str, t: int, m: int):

            trips = sol.get(f"{trip_var_prefix}_{src_id}_{dst_id}_{t}_{m}", 0.0)
            
            key = (src_type, src_id, dst_type, dst_id)
            dist = data.dist.get(key, 0.0)
            
            routes[name]['trips'] += trips
            routes[name]['km'] += dist * trips

        
        # 1. Поле → Склад (тип 3)
        for i in data.field_ids:
            if data.field_type[i] == 3:
                w = data.field_warehouse[i]
                for t in data.days:
                    name = f"F{i}→W{w}"
                    add_tons(name, f"q_{i}_{w}_{t}")
                    for m in data.truck_ids:
                        add_route(name, "z", i, w, 'I', 'W', t, m)
        
        # 2. Поле → Элеватор (тип 1,2)
        for i in data.field_ids:
            if data.field_type[i] in (1, 2):
                for e in data.elev_ids:
                    for t in data.days:
                        name = f"F{i}→E{e}"
                        add_tons(name, f"q_fe_{i}_{e}_{t}")
                        for m in data.truck_ids:
                            add_route(name, "z_fe", i, e, 'I', 'E', t, m)
        
        # 3. Поле → ПП (тип 1,2)
        for i in data.field_ids:
            if data.field_type[i] in (1, 2):
                for p in data.point_ids:
                    for t in data.days:
                        name = f"F{i}→P{p}"
                        add_tons(name, f"q_fp_{i}_{p}_{t}")
                        for m in data.truck_ids:
                            add_route(name, "z_fp", i, p, 'I', 'P', t, m)

        # 4. Склад → Элеватор
        for w in data.wh_ids:
            for e in data.elev_ids:
                for t in data.days:
                    name = f"W{w}→E{e}"
                    add_tons(name, f"f_{w}_{e}_{t}")
                    for m in data.truck_ids:
                        add_route(name, "y", w, e, 'W', 'E', t, m)
        
        # 5. Склад → ПП
        for w in data.wh_ids:
            for p in data.point_ids:
                for t in data.days:
                    name = f"W{w}→P{p}"
                    add_tons(name, f"g_{w}_{p}_{t}")
                    for m in data.truck_ids:
                        add_route(name, "yP", w, p, 'W', 'P', t, m)
        
        # 6. ПП → Элеватор
        for p in data.point_ids:
            for e in data.elev_ids:
                for t in data.days:
                    name = f"P{p}→E{e}"
                    add_tons(name,  f"t_pe_{p}_{e}_{t}")
                    for m in data.truck_ids:
                        add_route(name, "w_pe", p, e, 'P', 'E', t, m)
        
        # Сортировка и возврат
        result = sorted(
            [(name, dict(data)) for name, data in routes.items()],
            key=lambda x: x[1]['tons'],
            reverse=True
        )
        
        if not result:
            print("ВНИМАНИЕ: Список маршрутов пуст. Проверь переменные потоков (q_*, f, g, t_pe) в решении.")
        
        return result
    
    def _compute_harvest_by_day(self) -> Dict[int, float]:

        data, sol = self.data, self.sol
        return {
            int(t): sum(sol.get(f"h_{i}_{k}_{t}") for i in data.field_ids for k in data.comb_ids)
            for t in data.days
        }
    
    def _compute_storage_charts(self) -> Dict:

        data, sol = self.data, self.sol
        charts = {}

        for stype, ids, prefix in [
            ('warehouse', data.wh_ids, 'S_w'),
            ('elevator', data.elev_ids, 'S_e'),
            ('point', data.point_ids, 'S_p')
        ]:
            for eid in ids:
                inflows, outflows, stocks, days_list = [], [], [], []

                for t in data.days:
                    days_list.append(int(t))
                    inflow, outflow = 0.0, 0.0


                    if stype == 'warehouse':
                        # Поступление с полей типа 3
                        for i in data.field_ids:
                            if data.field_type.get(i) == 3 and data.field_warehouse.get(i) == eid:
                                inflow += sol.get(f"q_{i}_{eid}_{t}")

                    elif stype == 'elevator':
                        # Со складов
                        for w in data.wh_ids:
                            inflow += sol.get(f"f_{w}_{eid}_{t}")
                        # С ПП
                        for p in data.point_ids:
                            inflow += sol.get(f"t_pe_{p}_{eid}_{t}")
                        # Прямые с полей
                        for i in data.field_ids:
                            if data.field_type[i] in (1, 2):
                                inflow += sol.get(f"q_fe_{i}_{eid}_{t}")

                    elif stype == 'point':
                        # Со складов
                        for w in data.wh_ids:
                            inflow += sol.get(f"g_{w}_{eid}_{t}")
                        # Прямые с полей
                        for i in data.field_ids:
                            if data.field_type[i] in (1, 2):
                                inflow += sol.get(f"q_fp_{i}_{eid}_{t}")

                    # === РАСЧЁТ OUTFLOW ===
                    if stype == 'warehouse':
                        # Отгрузка на элеваторы
                        for e in data.elev_ids:
                            outflow += sol.get(f"f_{eid}_{e}_{t}")
                        # Отгрузка на ПП
                        for p in data.point_ids:
                            outflow += sol.get(f"g_{eid}_{p}_{t}")

                    elif stype == 'elevator':
                        # Отгрузка (offload)
                        outflow = sol.get(f"offload_{eid}_{t}")

                    elif stype == 'point':
                        # Отгрузка на элеваторы
                        for e in data.elev_ids:
                            outflow += sol.get(f"t_pe_{eid}_{e}_{t}")

                    # === ЗАПАС ===
                    stock = sol.get(f"{prefix}_{eid}_{t}")

                    inflows.append(inflow)
                    outflows.append(outflow)
                    stocks.append(stock)

                charts[f"{stype}_{eid}"] = {
                    'days': days_list,
                    'inflow': inflows,
                    'outflow': outflows,
                    'stock': stocks 
                }

        return charts
    
    def _compute_input_summary(self) -> Dict[str, Any]:
            data = self.data
            summary = {}


            summary['Масштаб'] = {
                'Всего полей': len(data.field_ids),
                'По типам': {
                    1: sum(1 for i in data.field_ids if data.field_type[i] == 1),
                    2: sum(1 for i in data.field_ids if data.field_type[i] == 2),
                    3: sum(1 for i in data.field_ids if data.field_type[i] == 3)
                },
                'Комбайнов': len(data.comb_ids),
                'Грузовиков': len(data.truck_ids),
                'Складов': len(data.wh_ids),
                'Элеваторов': len(data.elev_ids),
                'ПП': len(data.point_ids),
                'Дней планирования': len(data.days),
                'Период': f"{min(data.days)}–{max(data.days)}" if len(data.days) > 0 else "-"
            }

            print(data.field_loss_rate)

            summary['Поля (поштучно)'] = {}
            for i in data.field_ids:
                a=data.field_loss_rate.get(i, 0.0)
                if type(a) == NoneType or type(a)==int: 
                    a=0.0
                summary['Поля (поштучно)'][f"Поле {i}"] = {
                    'Тип': data.field_type[i],
                    'Урожайность (т)': data.field_yield[i],
                    'Привязанный склад': data.field_warehouse.get(i, '-') if data.field_type[i] == 3 else '-',
                    'Потери (%)': round(a * 100.0, 2),
                    'Макс. хранение (дн)': data.field_max_storage.get(i, '∞'),
                    'Мин. интервал вывоза': data.field_min_interval.get(i, '-')
                }


            summary['Комбайны (поштучно)'] = {}
            for k in data.comb_ids:
                summary['Комбайны (поштучно)'][f"Комбайн {k}"] = {
                    'Производительность (т/ч)': data.comb_productivity[k],
                    'Стоимость уборки (руб/т)': data.comb_cost[k],
                    'Дней ТО': len(data.comb_maintenance.get(k, []))
                }


            summary['Грузовики (поштучно)'] = {}
            for m in data.truck_ids:
                summary['Грузовики (поштучно)'][f"Грузовик {m}"] = {
                    'Вместимость (т)': data.truck_capacity[m],
                    'Стоимость (руб/км)': data.truck_cost_km[m],
                    'Скорость (км/ч)': data.truck_speed[m]
                }

            summary['Параметры и штрафы'] = {
                'Смена (ч)': data.T_shift,
                'Макс. смена (ч)': getattr(data, 'T_shift_max', data.T_shift + 4),
                'Лимит переработки (ч)': getattr(data, 'T_shift_max', data.T_shift + 4) - data.T_shift,
                'Штраф: неубранный урожай (руб/т)': data.M_big,
                'Штраф: переработка комбайна (руб/ч)': data.M_big,
                'Штраф: переработка грузовика (руб/ч)': data.M_big,
                'Штраф: недоотгрузка элеватора (руб/т)': data.M_big,
                'Штраф: переполнение склада (руб/т)': data.M_big,
                'Штраф: простой/неравномерность (руб/окно)': data.M_big,
                'Штраф: недовыработка комбайна (руб/т)': data.M_big,
                'Терминальный остаток (дн)': getattr(data, 'terminal_days', 0),
                'Мин. загрузка грузовика (%)': round(getattr(data, 'min_load_ratio', 0) * 100, 1)
            }

            return summary
    
    def _compute_type2_field_dynamics(self) -> Dict:

        data, sol = self.data, self.sol
        result = {}
        
        # Фильтруем только поля типа 2
        type2_fields = [i for i in data.field_ids if data.field_type.get(i) == 2]
        if not type2_fields:
            return {}
        
        for i in type2_fields:
            loss_rate = data.field_loss_rate.get(i, 0.0)
            days_list, stock_start, stock_end = [], [], []
            harvest_list, outflow_list, losses_list = [], [], []
            
            for t_idx, t in enumerate(data.days):
                days_list.append(int(t))
                
                # 1. Убрано за день
                day_harvest = sum(sol.get(f"h_{i}_{k}_{t}", 0.0) for k in data.comb_ids)
                
                # 2. Вывоз: на элеваторы + на ПП
                out_elev = sum(sol.get(f"q_fe_{i}_{e}_{t}", 0.0) for e in data.elev_ids)
                out_point = sum(sol.get(f"q_fp_{i}_{p}_{t}", 0.0) for p in data.point_ids)
                day_outflow = out_elev + out_point
                
                # 3. Остатки: конец текущего дня
                s_end = sol.get(f"S_f_{i}_{t}", 0.0)
                s_start = sol.get(f"S_f_{i}_{data.days[t_idx-1]}", 0.0) if t_idx > 0 else 0.0
                
                # 4. Потери: применяются к остатку на начало дня
                daily_loss = s_start * loss_rate
                
                # 5. Фильтрация численного шума (< 0.05 т → 0)
                def clean(v): return round(v, 2)
                
                stock_start.append(clean(s_start))
                stock_end.append(clean(s_end))
                harvest_list.append(clean(day_harvest))
                outflow_list.append(clean(day_outflow))
                losses_list.append(clean(daily_loss))
            
            result[i] = {
                'field_id': i,
                'loss_rate_pct': round(loss_rate * 100, 2),
                'days': days_list,
                'stock_start': stock_start,      # Запас на начало дня
                'stock_end': stock_end,          # Запас на конец дня
                'harvest': harvest_list,         # Убрано за день
                'outflow': outflow_list,         # Вывезено за день
                'losses': losses_list,           # Потери за день
                'balance_check': [
                    round(stock_start[j]*(1-loss_rate) + harvest_list[j] - outflow_list[j] - stock_end[j], 3)
                    for j in range(len(days_list))
                ]
            }
        
        return result
        
    def _compute_elevator_balance(self) -> Dict:

        data, sol = self.data, self.sol
        result = {}
        
        for e in data.elev_ids:
            n_days = len(data.days)
            in_wh, in_point, in_field, offload, stock_end, stock_start = [], [], [], [], [], []
            
            

            plan_raw = data.elev_offload.get(e) or data.elev_offload.get(str(e))
            print(plan_raw)
            if plan_raw is None or (isinstance(plan_raw, (list, np.ndarray)) and len(plan_raw) == 0):
                print(f"План отгрузки для элеватора {e} отсутствует. Используется нулевой вектор.")
                plan_daily = np.zeros(n_days)
            else:
                plan_daily = np.asarray(plan_raw, dtype=np.float64).flatten()

                if len(plan_daily) != n_days:
                    plan_daily = plan_daily[:n_days] if len(plan_daily) > n_days else np.pad(plan_daily, (0, n_days - len(plan_daily)), mode='constant')
            
            initial_stock = data.elev_initial.get(e, 0.0)
            print(f"Elev {e} | Keys: {list(data.elev_offload.keys())[:3]} | Plan len: {len(plan_daily)} | Plan[:3]: {plan_daily[:3]}")
            

            for t_idx, t in enumerate(data.days):
                in_wh.append(sum(sol.get(f"f_{w}_{e}_{t}", 0.0) for w in data.wh_ids))
                in_point.append(sum(sol.get(f"t_pe_{p}_{e}_{t}", 0.0) for p in data.point_ids))
                in_field.append(sum(sol.get(f"q_fe_{i}_{e}_{t}", 0.0) for i in data.field_ids if data.field_type.get(i) in (1, 2)))
                
                offload.append(sol.get(f"offload_{e}_{t}", 0.0))
                s_end = sol.get(f"S_e_{e}_{t}", 0.0)
                s_start = initial_stock if t_idx == 0 else sol.get(f"S_e_{e}_{data.days[t_idx-1]}", 0.0)
                stock_end.append(s_end)
                stock_start.append(s_start)
                

            in_wh, in_point, in_field = np.array(in_wh), np.array(in_point), np.array(in_field)
            offload, stock_start, stock_end = np.array(offload), np.array(stock_start), np.array(stock_end)
            total_in = in_wh + in_point + in_field
            

            shortfall = np.maximum(0.0, plan_daily - offload)
            

            balance_check = stock_start + total_in - offload - stock_end
            
            result[e] = {
                'elev_id': e,
                'capacity': data.elev_capacity.get(e, 0.0),
                'initial_stock': initial_stock,
                'days': data.days.tolist(),
                'in_wh': in_wh.tolist(),
                'in_point': in_point.tolist(),
                'in_field': in_field.tolist(),
                'total_in': total_in.tolist(),
                'offload': offload.tolist(),
                'plan_offload': plan_daily.tolist(),    
                'shortfall': shortfall.tolist(),           
                'stock_start': stock_start.tolist(),
                'stock_end': stock_end.tolist(),
                'balance_check': balance_check.tolist()
            }
            
        return result
    
    def _compute_point_daily(self) -> Dict:
        data, sol = self.data, self.sol
        res = {}
        for p in data.point_ids:
            loss_rate = data.point_loss.get(p, 0.0)
            days, s_start, in_f, in_w, out, s_end, losses = [], [], [], [], [], [], []
            for t_idx, t in enumerate(data.days):
                days.append(int(t))
                in_f.append(sum(sol.get(f"q_fp_{i}_{p}_{t}", 0) for i in data.field_ids if data.field_type.get(i) in (1,2)))
                in_w.append(sum(sol.get(f"g_{w}_{p}_{t}", 0) for w in data.wh_ids))
                out.append(sum(sol.get(f"t_pe_{p}_{e}_{t}", 0) for e in data.elev_ids))
                s_end.append(sol.get(f"S_p_{p}_{t}", 0))
                s_start.append(sol.get(f"S_p_{p}_{data.days[t_idx-1]}", 0) if t_idx > 0 else 0)
                losses.append(s_start[-1] * loss_rate)
            res[p] = {'days': days, 'stock_start': s_start, 'in_field': in_f, 'in_wh': in_w, 
                    'total_in': [x+y for x,y in zip(in_f, in_w)], 'outflow': out, 
                    'stock_end': s_end, 'losses': losses}
        return res

    def _compute_warehouse_daily(self) -> Dict:
        data, sol = self.data, self.sol
        res = {}
        for w in data.wh_ids:
            days, s_start, total_in, total_out, s_end = [], [], [], [], []
            for t_idx, t in enumerate(data.days):
                days.append(int(t))
                total_in.append(sum(sol.get(f"q_{i}_{w}_{t}", 0) for i in data.field_ids if data.field_type.get(i)==3 and data.field_warehouse.get(i)==w))
                total_out.append(sum(sol.get(f"f_{w}_{e}_{t}", 0) for e in data.elev_ids) + sum(sol.get(f"g_{w}_{p}_{t}", 0) for p in data.point_ids))
                s_end.append(sol.get(f"S_w_{w}_{t}", 0))
                s_start.append(sol.get(f"S_w_{w}_{data.days[t_idx-1]}", 0) if t_idx > 0 else 0)
            res[w] = {'days': days, 'stock_start': s_start, 'total_in': total_in, 
                    'total_out': total_out, 'stock_end': s_end}
        return res
    
def print_input_summary(summary: Dict, indent: int = 0):
    prefix = "  " * indent
    for section, content in summary.items():
        print(f"\n{prefix} {section.upper()}")
        print(f"{prefix}{'='*60}")

        if not isinstance(content, dict):
            print(f"{prefix}  {content}")
            continue

        is_entities = len(content) > 0 and all(isinstance(v, dict) for v in content.values())

        if is_entities:

            headers = ["Единица"] + list(next(iter(content.values())).keys())

            col_widths = [len(h) for h in headers]
            for vals in content.values():
                for idx, v in enumerate(vals.values()):
                    formatted = f"{v:.2f}" if isinstance(v, float) else str(v)
                    if len(formatted) > col_widths[idx]:
                        col_widths[idx] = len(formatted)
            col_widths = [max(w, 14) for w in col_widths]  


            header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
            print(f"{prefix}{header_line}")
            print(f"{prefix}{'-' * len(header_line)}")


            for entity, attrs in content.items():
                row_vals = [entity] + [f"{v:.2f}" if isinstance(v, float) else str(v) for v in attrs.values()]
                row_line = " | ".join(row_vals[i].ljust(col_widths[i]) for i in range(len(row_vals)))
                print(f"{prefix}{row_line}")
        else:

            for key, val in content.items():
                if isinstance(val, dict):
                    print(f"{prefix}  {key}:")
                    for k2, v2 in val.items():
                        formatted = f"{v2:.2f}" if isinstance(v2, float) else str(v2)
                        print(f"{prefix}    • {k2}: {formatted}")
                else:
                    formatted = f"{val:.2f}" if isinstance(val, float) else str(val)
                    print(f"{prefix}  • {key}: {formatted}")    

