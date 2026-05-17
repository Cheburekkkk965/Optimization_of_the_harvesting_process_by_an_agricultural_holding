from dataclasses import dataclass, field
from typing import Dict, List, Set
import numpy as np


@dataclass
class HarvestData:

    # Планирование
    days: np.ndarray
    days_count: int
    T_shift_max: int
    T_shift: float
    min_harvest_tons: float
    min_load_ratio: float
    terminal_days: int
    tau_F: float
    tau_W: float
    tau_P: float
    M_big: float

    # ID сущностей
    field_ids: List[int] = field(default_factory=list)
    comb_ids: List[int] = field(default_factory=list)
    truck_ids: List[int] = field(default_factory=list)
    elev_ids: List[int] = field(default_factory=list)
    point_ids: List[int] = field(default_factory=list)
    wh_ids: List[int] = field(default_factory=list)

    # Поля
    field_type: Dict[int, int] = field(default_factory=dict)
    field_yield: Dict[int, float] = field(default_factory=dict)
    field_warehouse: Dict[int, int] = field(default_factory=dict)
    field_loss_rate: Dict[int, float] = field(default_factory=dict)
    field_max_storage: Dict[int, int] = field(default_factory=dict)
    field_min_interval: Dict[int, int] = field(default_factory=dict)

    # Комбайны
    comb_productivity: Dict[int, float] = field(default_factory=dict)
    comb_cost: Dict[int, float] = field(default_factory=dict)
    comb_maintenance: Dict[int, Set[int]] = field(default_factory=dict)

    # Грузовики
    truck_capacity: Dict[int, float] = field(default_factory=dict)
    truck_cost_km: Dict[int, float] = field(default_factory=dict)
    truck_speed: Dict[int, float] = field(default_factory=dict)

    # Элеваторы
    elev_capacity: Dict[int, float] = field(default_factory=dict)
    elev_drying_cost: Dict[int, float] = field(default_factory=dict)
    elev_storage_cost: Dict[int, float] = field(default_factory=dict)
    elev_initial: Dict[int, float] = field(default_factory=dict)
    elev_offload: Dict[int, np.ndarray] = field(default_factory=dict)

    # Пункты
    point_capacity: Dict[int, float] = field(default_factory=dict)
    point_storage_cost: Dict[int, float] = field(default_factory=dict)
    point_loss: Dict[int, float] = field(default_factory=dict)
    point_initial: Dict[int, float] = field(default_factory=dict)

    # Склады
    wh_capacity: Dict[int, float] = field(default_factory=dict)
    wh_drying_cost: Dict[int, float] = field(default_factory=dict)
    wh_storage_cost: Dict[int, float] = field(default_factory=dict)
    wh_initial: Dict[int, float] = field(default_factory=dict)

    # Матрица расстояний
    dist: Dict[tuple, float] = field(default_factory=dict)



import json
import numpy as np
from pathlib import Path

def preprocess(raw: dict) -> HarvestData:
    config = raw['config']
    plan = config['planning']
    penalties = config['penalties']

    days = np.arange(1, plan['days_count'] + 1, dtype=np.int32)


    field_ids = [f['id'] for f in raw['fields']]
    comb_ids = [c['id'] for c in raw['combiners']]
    truck_ids = [t['id'] for t in raw['trucks']]
    elev_ids = [e['id'] for e in raw['elevators']]
    point_ids = [p['id'] for p in raw['points']]
    wh_ids = [w['id'] for w in raw['warehouses']]

    return HarvestData(
        days=days, days_count=plan['days_count'], 
        T_shift=plan['T_shift_hours'], T_shift_max=plan['T_shift_max'],
        min_harvest_tons=plan['min_harvest_tons'], min_load_ratio=plan['min_load_ratio'],
        terminal_days=plan['terminal_days'],
        tau_F=plan['tau_F_hours'], tau_W=plan['tau_W_hours'],
        tau_P=plan['tau_P_hours'], M_big=penalties['M_big'],
        field_ids=field_ids, comb_ids=comb_ids, truck_ids=truck_ids,
        elev_ids=elev_ids, point_ids=point_ids, wh_ids=wh_ids,
        field_type={f['id']: f['type'] for f in raw['fields']},
        field_yield={f['id']: f['area_km2'] * f['yield_t_km2'] for f in raw['fields']},
        field_warehouse={f['id']: f['warehouse_id'] for f in raw['fields'] if f['type'] == 3},
        field_loss_rate={f['id']: f.get('loss_rate', 0.0) for f in raw['fields']}, 
        field_max_storage={f['id']: f.get('max_storage_days') for f in raw['fields']},
        field_min_interval={f['id']: f.get('min_interval_days') for f in raw['fields']},
        comb_productivity={c['id']: c['productivity_t_hour'] for c in raw['combiners']},
        comb_cost={c['id']: c['cost_per_ton'] for c in raw['combiners']},
        comb_maintenance={c['id']: set(c.get('maintenance_days', [])) for c in raw['combiners']},
        truck_capacity={t['id']: t['capacity_ton'] for t in raw['trucks']},
        truck_cost_km={t['id']: t['cost_per_km'] for t in raw['trucks']},
        truck_speed={t['id']: t['avg_speed_kmh'] for t in raw['trucks']},
        elev_capacity={e['id']: e['capacity_ton'] for e in raw['elevators']},
        elev_drying_cost={e['id']: e['drying_cost_per_t'] for e in raw['elevators']},
        elev_storage_cost={e['id']: e['storage_cost_per_t_day'] for e in raw['elevators']},
        elev_initial={e['id']: e['initial_stock_ton'] for e in raw['elevators']},
        elev_offload={e['id']: np.array(e['daily_offload_plan'], dtype=np.float32) for e in raw['elevators']},
        point_capacity={p['id']: p['capacity_ton'] for p in raw['points']},
        point_storage_cost={p['id']: p['storage_cost_per_t_day'] for p in raw['points']},
        point_loss={p['id']: p['loss_rate_per_day'] for p in raw['points']},
        point_initial={p['id']: p['initial_stock_ton'] for p in raw['points']},
        wh_capacity={w['id']: w['capacity_ton'] for w in raw['warehouses']},
        wh_drying_cost={w['id']: w['drying_cost_per_t'] for w in raw['warehouses']},
        wh_storage_cost={w['id']: w['storage_cost_per_t_day'] for w in raw['warehouses']},
        wh_initial={w['id']: w['initial_stock_ton'] for w in raw['warehouses']},
        dist={(d['from_type'], d['from_id'], d['to_type'], d['to_id']): d['distance_km'] for d in raw['distances']}
    )


import json
import numpy as np
from dataclasses import asdict

class HarvestEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, np.ndarray): return o.tolist()
        if isinstance(o, set): return sorted(list(o))
        if isinstance(o, np.generic): return o.item()
        return super().default(o)

def save_harvest_data(data: HarvestData, path: str) -> None:
    ctx = asdict(data)

    ctx['dist'] = [
        {"from_type": k[0], "from_id": k[1], "to_type": k[2], "to_id": k[3], "distance_km": v}
        for k, v in ctx['dist'].items()
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ctx, f, indent=2, ensure_ascii=False, cls=HarvestEncoder)
    print(f"Контекст сохранён: {path}")

import json
import numpy as np
from pathlib import Path
from typing import Dict, Any


INT_KEY_FIELDS = [
    "comb_cost", "comb_productivity", "comb_maintenance",
    "truck_capacity", "truck_cost_km", "truck_speed",
    "elev_capacity", "elev_drying_cost", "elev_storage_cost", "elev_initial",
    "point_capacity", "point_storage_cost", "point_loss", "point_initial",
    "wh_capacity", "wh_drying_cost", "wh_storage_cost", "wh_initial",
    "field_type", "field_yield", "field_warehouse", "field_loss_rate",
    "field_max_storage", "field_min_interval"
]


INT_LIST_FIELDS = [
    "field_ids", "comb_ids", "truck_ids", "elev_ids", "point_ids", "wh_ids"
]

def load_harvest_data(path: str | Path) -> HarvestData:

    path = Path(path)
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    ctx: Dict[str, Any] = {}


    for key in INT_KEY_FIELDS:
        if key not in raw:
            raise KeyError(f"Отсутствует обязательное поле: {key}")
        
        val = raw[key]
        if not isinstance(val, dict):
            raise TypeError(f"Поле {key} должно быть dict, получено {type(val)}")
        

        try:
            ctx[key] = {int(k): v for k, v in val.items()}
        except ValueError as e:
            raise ValueError(f"Невалидный ключ в поле {key}: ожидался int. Ошибка: {e}")


    for key in INT_LIST_FIELDS:
        if key not in raw:
            raise KeyError(f"Отсутствует обязательное поле: {key}")
            
        val = raw[key]
        if not isinstance(val, list):
            raise TypeError(f"Поле {key} должно быть list, получено {type(val)}")
            
        try:
            ctx[key] = [int(x) for x in val]
        except ValueError as e:
            raise ValueError(f"Невалидный элемент в списке {key}: ожидался int. Ошибка: {e}")


    if "days" not in raw: raise KeyError("Отсутствует поле days")
    ctx["days"] = np.array(raw["days"], dtype=np.int32)

    if "dist" in raw:
        if not isinstance(raw["dist"], list):
            raise TypeError("Поле dist должно быть списком объектов")
        ctx["dist"] = {
            (d['from_type'], d['from_id'], d['to_type'], d['to_id']): d['distance_km']
            for d in raw["dist"]
        }


    processed_keys = set(INT_KEY_FIELDS) | set(INT_LIST_FIELDS) | {"days", "dist"}
    for key, val in raw.items():
        if key not in processed_keys:
            ctx[key] = val



    return HarvestData(**ctx)

def count_variables(data: HarvestData) -> int:
    T = len(data.days)
    n_fields = len(data.field_ids)
    n_combs = len(data.comb_ids)
    n_trucks = len(data.truck_ids)
    n_elevs = len(data.elev_ids)
    n_points = len(data.point_ids)
    n_whs = len(data.wh_ids)


    f_type3 = sum(1 for fid in data.field_ids if data.field_type[fid] == 3)
    f_type12 = sum(1 for fid in data.field_ids if data.field_type[fid] in (1, 2))
    f_type2 = sum(1 for fid in data.field_ids if data.field_type[fid] == 2)

    n = 0
    n += n_fields * n_combs * T * 2               # 1.1 h + 1.2 a
    n += n_fields * T                             # 1.2b u
    n += f_type3 * T                              # 1.3 q
    n += f_type12 * n_elevs * T                   # 1.3a
    n += f_type12 * n_points * T                  # 1.3b
    n += f_type3 * T * n_trucks                   # 1.4 z
    n += f_type12 * n_elevs * T * n_trucks        # 1.4a
    n += f_type12 * n_points * T * n_trucks       # 1.4b
    n += n_whs * T * 2                            # 1.5 S_w + 1.6 overflow
    n += n_whs * n_elevs * T * (1 + n_trucks)     # 1.7 f + 1.8 y
    n += n_whs * n_points * T * (1 + n_trucks)    # 1.9 g + 1.10 yP
    n += n_points * n_elevs * T * (1 + n_trucks)  # 1.11 t_pe + 1.12 w_pe
    n += n_elevs * T * 2                          # 1.13 S_e + 1.14 offload
    n += n_points * T                             # 1.15 S_p
    n += n_fields                                 # 1.16 unharvested
    n += n_elevs * T                              # 1.18 shortfall
    n += f_type2 * T * 2                          # 1.19 S_f + 1.20 b

    max_idle_days = 1
    window = max_idle_days + 1
    n += n_fields * max(0, T - window + 2)        # 1.21 idle_penalty

    # Мягкие переменные
    n += n_combs * T                              # combine_overtime
    n += n_trucks * T                             # truck_overtime
    n += n_fields * n_combs * T                   # h_shortage

    return n



from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class NormalizedSolution:

    variables: Dict[str, float]  
    status: str                  
    objective: float             
    solve_time: float = 0.0      
    mip_gap: float = 0.0         
    solver_name: str = "unknown" 
    metadata: Dict = field(default_factory=dict)  
    
    def get(self, name: str, default: float = 0.0) -> float:

        return self.variables.get(name, default)
    
    def filter(self, prefix: str, threshold: float = 1e-4) -> Dict[str, float]:

        return {k: v for k, v in self.variables.items() 
                if k.startswith(prefix) and v > threshold}
    
    @property
    def is_feasible(self) -> bool:

        return self.status.upper() in ("OPTIMAL", "FEASIBLE", "FEASIBLE_FOUND")
    

from abc import ABC, abstractmethod
from pathlib import Path
from model_general import NormalizedSolution

class SolutionAdapter(ABC):

    
    @abstractmethod
    def load(self, path: str | Path) -> NormalizedSolution:

        pass
    
    @staticmethod
    @abstractmethod
    def supports_format(path: str | Path) -> bool:

        pass


from pathlib import Path
from typing import List, Type
from solution_adapters import CuOptAdapter
from solution_adapters import SolFileAdapter

class SolutionAdapterFactory:

    
    _adapters: List[Type[SolutionAdapter]] = [
        CuOptAdapter,
        SolFileAdapter,

    ]
    
    @classmethod
    def get_adapter(cls, path: str | Path) -> SolutionAdapter:

        path = Path(path)
        
        for adapter_cls in cls._adapters:
            if adapter_cls.supports_format(path):
                return adapter_cls()
        
        raise ValueError(
            f"Неизвестный формат решения: {path}\n"
            f"Поддерживаемые: {[a.__name__ for a in cls._adapters]}"
        )
    
    @classmethod
    def register_adapter(cls, adapter_cls: Type[SolutionAdapter]):

        cls._adapters.append(adapter_cls)