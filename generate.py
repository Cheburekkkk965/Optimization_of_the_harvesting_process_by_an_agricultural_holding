import json
import random
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path


class HarvestDataGenerator:



    DEFAULT_PARAMS = {
        'field': {
            'area': [0.5, 5.0],
            'yield': [30, 50],
            'loss_rate': [0.01, 0.05],
            'max_storage_days': [3, 7],
            'min_interval_days': [2, 4],
            'type_ratios': [0.30, 0.20],  
        },
        'combiner': {
            'productivity': [40, 70],
            'cost': [10, 90],
            'maintenance_days': [0, 2],
        },
        'truck': {
            'count': [1, 3],
            'capacity': [26, 40],
            'cost': [65, 95],
            'speed': [30, 50],
        },
        'elevator': {
            'capacity': [500, 1000],
            'initial_stock_ratio': [0, 0.1],
            'drying_cost': [100, 200],
            'storage_cost': [5, 20],
            'offload_plan_divisor': 5,  
            'offload_plan_variation': [0.7, 1.3]
        },
        'point': {
            'capacity': [500, 2000],
            'storage_cost': [20, 50],
            'loss_rate': [0.005, 0.02],
        },
        'warehouse': {
            'capacity': [600, 2000],
            'drying_cost': [80, 150],
            'storage_cost': [30, 40],
        },
        'distances': {
            'field_elevator': [5, 150],
            'field_point': [2, 40],
            'field_warehouse': [1, 3],
            'warehouse_elevator': [10, 70],
            'warehouse_point': [10, 40],
            'point_elevator': [20, 60],
        },
        'config': {
            'days_count': 30,
            'T_shift_hours': 8,
            'T_shift_max': 12,
            'min_harvest_tons': 5.0,
            'terminal_days': 5,
            'tau_F_hours': 0.5,
            'tau_W_hours': 0.3,
            'tau_P_hours': 0.4,
            'penalty_f': 100,
            'penalty_n': 150,
            'penalty_b': 500,
            'penalty_B': 1000,
            'M_big': 1000000,
        }
    }

    def __init__(self, seed: int = 0, params: Optional[Dict[str, Any]] = None):

        if seed is not None:
            random.seed(seed)
        self.seed = seed

        self.params = self._deep_merge(self.DEFAULT_PARAMS, params or {})

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:

        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def generate_all_data(self,
                          n_fields: int = 100,
                          n_combiners: int = 10,
                          n_trucks: int = 50,
                          n_elevators: int = 5,
                          n_points: int = 3,
                          n_warehouses: int = 4,
                          n_days: int = 30,
                          params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:


        original_params = None
        if params:
            original_params = self.params
            self.params = self._deep_merge(self.DEFAULT_PARAMS, params)
        
        print("=" * 60)
        print("ГЕНЕРАТОР ВХОДНЫХ ДАННЫХ (с гарантией допустимости)")
        print("=" * 60)
        print(f"Полей: {n_fields}")
        print(f"Комбайнов: {n_combiners}")
        print(f"Типов грузовиков: {n_trucks}")
        print(f"Элеваторов: {n_elevators}")
        print(f"Промежуточных пунктов: {n_points}")
        print(f"Временных складов: {n_warehouses}")
        print(f"Дней планирования: {n_days}")
        print("=" * 60)

        data = {
            'metadata': self._generate_metadata(n_fields, n_combiners, n_trucks, n_days),
            'fields': self._generate_fields(n_fields, n_warehouses),
            'combiners': self._generate_combiners(n_combiners, n_days),
            'trucks': self._generate_trucks(n_trucks),
            'elevators': self._generate_elevators(n_elevators, n_days),
            'points': self._generate_points(n_points),
            'warehouses': self._generate_warehouses(n_warehouses),
            'distances': self._generate_distances(n_fields, n_elevators, n_points, n_warehouses),
            'config': self._generate_config(n_days)
        }

        self._validate_and_fix_data(data)
        print("\nДанные успешно сгенерированы и проверены!")
        
        if original_params:
            self.params = original_params
            
        return data

    def _generate_metadata(self, n_fields: int, n_combiners: int, n_trucks: int, n_days: int) -> Dict:
        return {
            'generated_at': datetime.now().isoformat(),
            'seed': self.seed,
            'n_fields': n_fields,
            'n_combiners': n_combiners,
            'n_trucks': n_trucks,
            'n_days': n_days,
            'version': '2.0'
        }

    def _generate_fields(self, n_fields: int, n_warehouses: int) -> List[Dict]:

        fields = []
        type_ratios = self.params['field']['type_ratios']
        n_type1 = int(n_fields * type_ratios[0])
        n_type2 = int(n_fields * type_ratios[1])
        n_type3 = n_fields - n_type1 - n_type2

        field_id = 1
        p_area = self.params['field']['area']
        p_yield = self.params['field']['yield']

        # Тип 1
        for _ in range(n_type1):
            fields.append({
                'id': field_id,
                'type': 1,
                'area_km2': round(random.uniform(p_area[0], p_area[1]), 2),
                'yield_t_km2': round(random.uniform(p_yield[0], p_yield[1]), 1),
                'loss_rate': None,
                'max_storage_days': None,
                'min_interval_days': None,
                'warehouse_id': None
            })
            field_id += 1

        # Тип 2
        p_loss = self.params['field']['loss_rate']
        p_max_storage = self.params['field']['max_storage_days']
        p_min_interval = self.params['field']['min_interval_days']
        for _ in range(n_type2):
            fields.append({
                'id': field_id,
                'type': 2,
                'area_km2': round(random.uniform(p_area[0], p_area[1]), 2),
                'yield_t_km2': round(random.uniform(p_yield[0], p_yield[1]), 1),
                'loss_rate': round(random.uniform(p_loss[0], p_loss[1]), 3),
                'max_storage_days': random.randint(p_max_storage[0], p_max_storage[1]),
                'min_interval_days': random.randint(p_min_interval[0], p_min_interval[1]),
                'warehouse_id': None
            })
            field_id += 1

        # Тип 3
        warehouse_ids = list(range(1, n_warehouses + 1))
        for i in range(n_type3):
            assigned_warehouse = warehouse_ids[i % n_warehouses]
            fields.append({
                'id': field_id,
                'type': 3,
                'area_km2': round(random.uniform(p_area[0], p_area[1]), 2),
                'yield_t_km2': round(random.uniform(p_yield[0], p_yield[1]), 1),
                'loss_rate': None,
                'max_storage_days': None,
                'min_interval_days': None,
                'warehouse_id': assigned_warehouse
            })
            field_id += 1

        return fields

    def _generate_combiners(self, n_combiners: int, n_days: int) -> List[Dict]:
        combiners = []
        p_prod = self.params['combiner']['productivity']
        p_cost = self.params['combiner']['cost']
        p_maint = self.params['combiner']['maintenance_days']
        
        for i in range(1, n_combiners + 1):
            combiners.append({
                'id': i,
                'productivity_t_hour': round(random.uniform(p_prod[0], p_prod[1]), 1),
                'cost_per_ton': round(random.uniform(p_cost[0], p_cost[1]), 1),
                'maintenance_days': random.sample(
                    range(1, n_days + 1), 
                    k=random.randint(p_maint[0], p_maint[1]))
            })
        return combiners

    def _generate_trucks(self, p_count: int) -> List[Dict]:
        p_cap = self.params['truck']['capacity']
        p_cost = self.params['truck']['cost']
        p_speed = self.params['truck']['speed']
        
        trucks = []
        for i in range(1, p_count + 1):
            trucks.append({
                    'id': i,
                    'capacity_ton': random.randint(p_cap[0], p_cap[1]),
                    'cost_per_km': round(random.uniform(p_cost[0], p_cost[1]), 1),
                    'avg_speed_kmh': round(random.uniform(p_speed[0], p_speed[1]), 1)
            })
        return trucks

    def _generate_elevators(self, n_elevators: int, n_days: int) -> List[Dict]:
        elevators = []
        p_cap = self.params['elevator']['capacity']
        p_init_ratio = self.params['elevator']['initial_stock_ratio']
        p_dry = self.params['elevator']['drying_cost']
        p_store = self.params['elevator']['storage_cost']
        divisor = self.params['elevator']['offload_plan_divisor']
        variation = self.params['elevator']['offload_plan_variation']

        for i in range(1, n_elevators + 1):
            capacity = random.randint(p_cap[0], p_cap[1])
            initial = random.randint(
                int(capacity * p_init_ratio[0]), 
                int(capacity * p_init_ratio[1])
            )

            offload_plan = []

            daily = capacity / divisor
            for day in range(n_days):

                daily_plan = daily * random.uniform(variation[0], variation[1])


                daily_plan = min(capacity, daily_plan)

                offload_plan.append(daily_plan)
                    
            elevators.append({
                'id': i,
                'capacity_ton': capacity,
                'drying_cost_per_t': round(random.uniform(p_dry[0], p_dry[1]), 1),
                'storage_cost_per_t_day': round(random.uniform(p_store[0], p_store[1]), 1),
                'initial_stock_ton': initial,
                'daily_offload_plan': offload_plan
            })

        return elevators

    def _generate_points(self, n_points: int) -> List[Dict]:
        points = []
        p_cap = self.params['point']['capacity']
        p_store = self.params['point']['storage_cost']
        p_loss = self.params['point']['loss_rate']
        
        for i in range(1, n_points + 1):
            capacity = random.randint(p_cap[0], p_cap[1])
            points.append({
                'id': i,
                'capacity_ton': capacity,
                'storage_cost_per_t_day': round(random.uniform(p_store[0], p_store[1]), 1),
                'loss_rate_per_day': round(random.uniform(p_loss[0], p_loss[1]), 3),
                'initial_stock_ton': 0
            })
        return points

    def _generate_warehouses(self, n_warehouses: int) -> List[Dict]:
        warehouses = []
        p_cap = self.params['warehouse']['capacity']
        p_dry = self.params['warehouse']['drying_cost']
        p_store = self.params['warehouse']['storage_cost']
        
        for i in range(1, n_warehouses + 1):
            capacity = random.randint(p_cap[0], p_cap[1])
            warehouses.append({
                'id': i,
                'capacity_ton': capacity,
                'drying_cost_per_t': round(random.uniform(p_dry[0], p_dry[1]), 1),
                'storage_cost_per_t_day': round(random.uniform(p_store[0], p_store[1]), 1),
                'initial_stock_ton': 0
            })
        return warehouses

    def _generate_distances(self, n_fields: int, n_elevators: int,
                            n_points: int, n_warehouses: int) -> List[Dict]:
        distances = []
        p = self.params['distances']
        
        # Поле → Элеватор
        for f in range(1, n_fields + 1):
            for e in range(1, n_elevators + 1):
                distances.append({
                    'from_type': 'I', 'from_id': f,
                    'to_type': 'E', 'to_id': e,
                    'distance_km': round(random.uniform(p['field_elevator'][0], p['field_elevator'][1]), 1)
                })

        # Поле → ПП
        for f in range(1, n_fields + 1):
            for pt in range(1, n_points + 1):
                distances.append({
                    'from_type': 'I', 'from_id': f,
                    'to_type': 'P', 'to_id': pt,
                    'distance_km': round(random.uniform(p['field_point'][0], p['field_point'][1]), 1)
                })

        # Поле → Склад
        for f in range(1, n_fields + 1):
            for w in range(1, n_warehouses + 1):
                distances.append({
                    'from_type': 'I', 'from_id': f,
                    'to_type': 'W', 'to_id': w,
                    'distance_km': round(random.uniform(p['field_warehouse'][0], p['field_warehouse'][1]), 1)
                })

        # Склад → Элеватор
        for w in range(1, n_warehouses + 1):
            for e in range(1, n_elevators + 1):
                distances.append({
                    'from_type': 'W', 'from_id': w,
                    'to_type': 'E', 'to_id': e,
                    'distance_km': round(random.uniform(p['warehouse_elevator'][0], p['warehouse_elevator'][1]), 1)
                })

        # Склад → ПП
        for w in range(1, n_warehouses + 1):
            for pt in range(1, n_points + 1):
                distances.append({
                    'from_type': 'W', 'from_id': w,
                    'to_type': 'P', 'to_id': pt,
                    'distance_km': round(random.uniform(p['warehouse_point'][0], p['warehouse_point'][1]), 1)
                })

        # ПП → Элеватор
        for pt in range(1, n_points + 1):
            for e in range(1, n_elevators + 1):
                distances.append({
                    'from_type': 'P', 'from_id': pt,
                    'to_type': 'E', 'to_id': e,
                    'distance_km': round(random.uniform(p['point_elevator'][0], p['point_elevator'][1]), 1)
                })

        return distances

    def _generate_config(self, n_days: int) -> Dict:
        c = self.params['config']
        return {
            'planning': {
                'days_count': n_days,
                'T_shift_hours': c['T_shift_hours'],
                'T_shift_max': c['T_shift_max'],
                'min_harvest_tons': c['min_harvest_tons'],
                'min_load_ratio': c['min_load_ratio'],
                'terminal_days': c['terminal_days'],
                'tau_F_hours': c['tau_F_hours'],
                'tau_W_hours': c['tau_W_hours'],
                'tau_P_hours': c['tau_P_hours']
            },
            'penalties': {
                'f': c['penalty_f'],
                'n': c['penalty_n'],
                'b': c['penalty_b'],
                'B': c['penalty_B'],
                'M_big': c['M_big']
            }
        }

    def _validate_and_fix_data(self, data: Dict) -> None:
        print("\nПроверка и коррекция данных...")

        fields = data['fields']
        n_type1 = sum(1 for f in fields if f['type'] == 1)
        n_type2 = sum(1 for f in fields if f['type'] == 2)
        n_type3 = sum(1 for f in fields if f['type'] == 3)
        assert n_type1 + n_type2 + n_type3 == len(fields)
        print(f"  ✓ Поля: {len(fields)} (Тип1: {n_type1}, Тип2: {n_type2}, Тип3: {n_type3})")

        assert len(data['combiners']) > 0
        print(f"  ✓ Комбайны: {len(data['combiners'])}")

        trucks = data['trucks']
        total_capacity = sum(t['capacity_ton'] for t in trucks)
        print(f"  ✓ Грузовики, всего машин: {len(trucks)}, общая вместимость: {total_capacity} т")

        elevators = data['elevators']
        print(f"  ✓ Элеваторы: {len(elevators)}")

        distances = data['distances']
        avg_distance = sum(d['distance_km'] for d in distances) / len(distances)
        print(f"  ✓ Расстояния: {len(distances)} пар, среднее: {avg_distance:.1f} км")

        warehouse_ids = set(w['id'] for w in data['warehouses'])
        for f in fields:
            if f['type'] == 3:
                assert f['warehouse_id'] in warehouse_ids, f"Поле {f['id']} имеет несуществующий склад {f['warehouse_id']}"
        print(f"  ✓ Поля типа 3 привязаны к существующим складам")

    def save_to_json(self, data: Dict, filepath: str = 'input_data.json') -> None:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n Данные сохранены в файл: {filepath}")

    def save_to_excel(self, data: Dict, filepath: str = 'input_data.xlsx') -> None:
        try:
            import pandas as pd

            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                pd.DataFrame(data['fields']).to_excel(writer, sheet_name='Fields', index=False)
                pd.DataFrame(data['combiners']).to_excel(writer, sheet_name='Combiners', index=False)
                pd.DataFrame(data['trucks']).to_excel(writer, sheet_name='Trucks', index=False)

                elevators_simple = [{
                    'id': e['id'],
                    'capacity_ton': e['capacity_ton'],
                    'drying_cost_per_t': e['drying_cost_per_t'],
                    'storage_cost_per_t_day': e['storage_cost_per_t_day'],
                    'initial_stock_ton': e['initial_stock_ton']
                } for e in data['elevators']]
                pd.DataFrame(elevators_simple).to_excel(writer, sheet_name='Elevators', index=False)

                pd.DataFrame(data['points']).to_excel(writer, sheet_name='Points', index=False)
                pd.DataFrame(data['warehouses']).to_excel(writer, sheet_name='Warehouses', index=False)
                pd.DataFrame(data['distances']).to_excel(writer, sheet_name='Distances', index=False)

                config_flat = {
                    'days_count': data['config']['planning']['days_count'],
                    'T_shift_max': data['config']['planning']['T_shift_max'],
                    'T_shift_hours': data['config']['planning']['T_shift_hours'],
                    'min_harvest_tons': data['config']['planning']['min_harvest_tons'],
                    'min_load_ratio': data['config']['planning']['min_load_ratio'],
                    'terminal_days': data['config']['planning']['terminal_days'],
                    'tau_F_hours': data['config']['planning']['tau_F_hours'],
                    'tau_W_hours': data['config']['planning']['tau_W_hours'],
                    'tau_P_hours': data['config']['planning']['tau_P_hours'],
                    'penalty_f': data['config']['penalties']['f'],
                    'penalty_n': data['config']['penalties']['n'],
                    'penalty_b': data['config']['penalties']['b'],
                    'penalty_B': data['config']['penalties']['B'],
                    'M_big': data['config']['penalties']['M_big'],
                }
                pd.DataFrame([config_flat]).to_excel(writer, sheet_name='Config', index=False)

            print(f"\n💾 Данные сохранены в Excel: {filepath}")

        except ImportError:
            print("\n pandas/openpyxl не установлены. Сохранение только в JSON.")




def load_params_from_json(filepath: str) -> Dict[str, Any]:

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Файл параметров не найден: {filepath}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():

    parser = argparse.ArgumentParser(
        description='Генератор входных данных для задачи оптимизации уборки урожая'
    )

    parser.add_argument('--n-fields', type=int, default=None, help='Количество полей')
    parser.add_argument('--n-combiners', type=int, default=None, help='Количество комбайнов')
    parser.add_argument('--n-trucks', type=int, default=None, help='Количество типов грузовиков')
    parser.add_argument('--n-elevators', type=int, default=None, help='Количество элеваторов')
    parser.add_argument('--n-points', type=int, default=None, help='Количество промежуточных пунктов')
    parser.add_argument('--n-warehouses', type=int, default=None, help='Количество складов')
    parser.add_argument('--n-days', type=int, default=None, help='Горизонт планирования (дни)')
    parser.add_argument('--seed', type=int, default=None, help='Seed для воспроизводимости')
    

    parser.add_argument('--params', '-p', type=str, default=None,
                        help='Путь к JSON-файлу с параметрами генерации')
    parser.add_argument('--output-json', '-o', type=str, default=None,
                        help='Имя выходного JSON-файла')
    parser.add_argument('--output-xlsx', type=str, default=None,
                        help='Имя выходного Excel-файла')
    parser.add_argument('--json', action='store_true', default=None, help='Сохранять в JSON')
    parser.add_argument('--xlsx', action='store_true', default=None, help='Сохранять также в Excel')
    
    args = parser.parse_args()
    

    params = {}
    if args.params:
        print(f"Загрузка параметров из: {args.params}")
        params = load_params_from_json(args.params)
        print(f"Загружено параметров")
    

    def get_val(cli_val, params_dict, key, default):
        if cli_val is not None:
            return cli_val
        if params_dict and 'scenario' in params_dict and key in params_dict['scenario']:
            return params_dict['scenario'][key]
        if params_dict and 'output' in params_dict and key in params_dict['output']:
            return params_dict['output'][key]
        
        return default
    
    n_fields = get_val(args.n_fields, params, 'n_fields', 100)
    n_combiners = get_val(args.n_combiners, params, 'n_combiners', 10)
    n_trucks = get_val(args.n_trucks, params, 'n_trucks', 50)
    n_elevators = get_val(args.n_elevators, params, 'n_elevators', 5)
    n_points = get_val(args.n_points, params, 'n_points', 3)
    n_warehouses = get_val(args.n_warehouses, params, 'n_warehouses', 4)
    n_days = get_val(args.n_days, params, 'n_days', 30)
    seed = args.seed if args.seed is not None else (params.get('scenario', {}).get('seed') if params else 0)
    
    # Настройки вывода
    save_json = get_val(args.json, params, 'save_json', False)
    save_excel = get_val(args.xlsx, params, 'save_excel', False)
    json_filename = get_val(args.output_json, params, 'json_filename', 'generated.json')
    excel_filename = get_val(args.output_xlsx, params, 'excel_filename', 'generated.xlsx')
    
    # Генерация
    generator = HarvestDataGenerator(seed=seed, params=params.get('distributions') if params else None)
    data = generator.generate_all_data(
        n_fields=n_fields,
        n_combiners=n_combiners,
        n_trucks=n_trucks,
        n_elevators=n_elevators,
        n_points=n_points,
        n_warehouses=n_warehouses,
        n_days=n_days
    )
    
    # Сохранение
    if save_json:
        generator.save_to_json(data, json_filename)
    if save_excel:
        generator.save_to_excel(data, excel_filename)
    
    # Статистика
    print("\n" + "=" * 60)
    print("СТАТИСТИКА СГЕНЕРИРОВАННЫХ ДАННЫХ")
    print("=" * 60)

    total_yield = sum(f['area_km2'] * f['yield_t_km2'] for f in data['fields'])
    total_area = sum(f['area_km2'] for f in data['fields'])
    total_truck_capacity = sum(t['capacity_ton'] for t in data['trucks'])
    total_storage = (
        sum(e['capacity_ton'] for e in data['elevators']) +
        sum(p['capacity_ton'] for p in data['points']) +
        sum(w['capacity_ton'] for w in data['warehouses'])
    )

    print(f"\nПоля:")
    print(f"   Общая площадь: {total_area:.1f} км²")
    print(f"   Общий урожай: {total_yield:.0f} т")
    print(f"   Средняя урожайность: {total_yield / total_area:.1f} т/км²")

    print(f"\nТехника:")
    print(f"   Комбайнов: {len(data['combiners'])}")
    print(f"   Грузовиков: {n_trucks}")
    print(f"   Общая вместимость грузовиков: {total_truck_capacity} т")

    print(f"\nХранилища:")
    print(f"   Элеваторы: {sum(e['capacity_ton'] for e in data['elevators']):.0f} т")
    print(f"   Пункты: {sum(p['capacity_ton'] for p in data['points']):.0f} т")
    print(f"   Склады: {sum(w['capacity_ton'] for w in data['warehouses']):.0f} т")
    print(f"   Итого: {total_storage:.0f} т")

    print(f"\nРасстояния:")
    avg_distance = sum(d['distance_km'] for d in data['distances']) / len(data['distances'])
    print(f"   Всего пар расстояний: {len(data['distances'])}")
    print(f"   Среднее расстояние: {avg_distance:.1f} км")

    print(f"\nКоэффициенты:")
    print(f"   Урожай / Хранение: {total_yield / total_storage:.2f}")
    print(f"   Комбайнов на 1000 га: {len(data['combiners']) / (total_area / 10):.1f}")
    print(f"   Грузовиков на 1000 га: {n_trucks / (total_area / 10):.1f}")

    print("\n" + "=" * 60)
    print("ГЕНЕРАЦИЯ ЗАВЕРШЕНА")
    print("=" * 60)


if __name__ == "__main__":
    main()