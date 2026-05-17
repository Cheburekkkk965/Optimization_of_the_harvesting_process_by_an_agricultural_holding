
import csv
import sys
import argparse
from pathlib import Path
from types import NoneType
from typing import Dict

import pandas as pd
from model_general import SolutionAdapterFactory, HarvestData, NormalizedSolution, load_harvest_data
from metrics import MetricsCalculator, print_input_summary
from plots import generate_plots  
from config import HARVEST_FILE


HAS_MATPLOTLIB = False
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    print("matplotlib не установлен. Графики не будут построены.")

def fmt(num: float, decimals: int = 1) -> str:
    return f"{num:,.{decimals}f}"

def print_report(metrics: Dict, data: 'HarvestData', solution: NormalizedSolution):
    objective = solution.objective
    sep = "=" * 100
    print(f"\n{sep}")
    print(f"SOLUTION REPORT | Статус: {solution.status} | Целевая: {fmt(objective)} руб.")
    print(f"{sep}\n")

    costs = metrics['costs']
    total = sum(costs.values())
    print(f"Подсчитано метриками: {fmt(total)}")
    print(f"{sep}\n")
    
    # 1. Затраты
    print("1️ОБЩИЕ ЗАТРАТЫ")
    print(f"   {'Статья':<30} {'Сумма (руб.)':>20} {'%':>7}")
    print(f"   {'-'*30} {'-'*20} {'-'*7}")
    
    cost_items = []

    # Штрафы
    for key, name in [
        ('harvesting', "Уборка комбайнами"),
        ('truck_cost', "Транспорт"),
        ('penalty_combine_overtime', "Переработка комбайнов"),
        ('penalty_truck_overtime', "Перепробег грузовиков"),
        ('penalty_unharvested', "Неубранный урожай"),
        ('penalty_shortfall', "Недоотгрузка элев."),
        ('penalty_overflow', "Переполнение складов"),
        ('storage_wh', "Хранение на складах"),
        ('storage_point', "Хранение на промежуточных"),
        ('storage_elev', "Хранение на элеваторах"),
        ('drying_wh', "Сушка на складах"),
        ('drying_elev', "Сушка на элеваторах"),
        ('penalty_idle', "Неравномерность"),
        ('penalty_field_loss_type2', "Потери на полях второго типа"),
        ('penalty_point_loss', "Потери на промежуточных пунктах"),
        ('penalty_terminal_wh', "Остатки на складах (терминал)"),
        ('penalty_terminal_elev', "Остатки на элеваторах (терминал)"),
        ('penalty_terminal_point', "Остатки на ПП (терминал)"),
        ('penalty_terminal_field_loss', "Потери на полях тип 2 (терминал)"),
        ('penalty_terminal_point_loss', "Потери на ПП (терминал)"),
    ]:
        cost_items.append((name, costs.get(key, 0)))
    
    for name, val in cost_items:
        pct = (val / total * 100) if total > 0 else 0
        print(f"    {name:<30} {fmt(val):>20} {pct:>7.3f}%")
    
    print(f"   {'-'*40} {'-'*20} {'-'*7}")
    print(f"   {'ИТОГО':<30} {fmt(total, 2):>20} {total / objective * 100.0:>7.3f}% относительно реальной")
    
    # 2. Уборка
    h = metrics['harvest']
    print("2️УБОРКА УРОЖАЯ")
    print(f"  План:           {fmt(h['planned_total']):>12} т")
    print(f"  Убрано:         {fmt(h['harvested_total']):>12} т")
    print(f"  Выполнение:     {h['completion_pct']:>11.1f}%\n")
    
    # 3. Поля (топ-10)
    print("3️ТОП-10 ПОЛЕЙ ПО УБОРКЕ")
    print(f"   {'Поле':<6} {'Тип':<4} {'План':>10} {'Убрано':>12} {'%':>6}")
    for row in metrics['field_harvest_table'][:10]:
        print(f"   {row['field_id']:<6} {row['type']:<4} "
              f"{fmt(row['planned']):>10} {fmt(row['harvested']):>12} {row['completion_pct']:>5.1f}%")
    print()

def _flatten_summary(d, parent_key='', sep=' | '):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_summary(v, new_key, sep))
        else:
            if isinstance(v, float):
                val = f"{v:,.2f}"
            elif isinstance(v, int):
                val = f"{v:,}"
            else:
                val = str(v)
            items.append({'Параметр': new_key, 'Значение': val})
    return items

def _format_num(val, decimals=2):
    if val is None:
        return ""
    try:
        return f"{float(val):,.{decimals}f}"
    except (ValueError, TypeError):
        return str(val)

def export_to_excel(metrics: Dict, data: HarvestData, solution: NormalizedSolution, output_dir: str):
    try:
        import pandas as pd
    except ImportError:
        print("pandas не установлен")
        return
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    excel_path = f"{output_dir}/dashboard.xlsx"
    

    COST_LABELS = {
        'harvesting': 'Уборка комбайнами',
        'truck_cost': 'Транспорт (ГСМ/км)',
        'penalty_unharvested': 'Штраф: неубранный урожай',
        'penalty_idle': 'Штраф: простой/неравномерность',
        'penalty_h_shortage': 'Штраф: недовыработка комбайна',
        'penalty_overflow': 'Штраф: переполнение складов',
        'penalty_shortfall': 'Штраф: недоотгрузка элеваторов',
        'penalty_combine_overtime': 'Штраф: переработка комбайнов',
        'penalty_truck_overtime': 'Штраф: переработка грузовиков',
        'penalty_terminal_wh': 'Штраф: остатки на складах',
        'penalty_terminal_elev': 'Штраф: остатки на элеваторах',
        'penalty_terminal_point': 'Штраф: остатки на ПП',
        'storage_wh': 'Хранение на складах',
        'storage_elev': 'Хранение на элеваторах',
        'storage_point': 'Хранение на ПП',
        'drying_wh': 'Сушка на складах',
        'drying_elev': 'Сушка на элеваторах',
        'penalty_field_loss_type2': 'Штраф за потери на полях второго типа',
        'penalty_point_loss': 'Штраф за потери на промежуточных пунктах',
        'penalty_terminal_wh': "Остатки на складах (терминал)",
        'penalty_terminal_elev': "Остатки на элеваторах (терминал)",
        'penalty_terminal_point': "Остатки на ПП (терминал)",
        'penalty_terminal_field_loss': "Потери на полях тип 2 (терминал)",
        'penalty_terminal_point_loss': "Потери на ПП (терминал)",
    }

    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        
        summary = pd.DataFrame([
            ['Статус', solution.status],
            ['Целевая (руб.)', f"{solution.objective:,.2f}"],
            ['MIP Gap', f"{solution.mip_gap:.2%}"],
            ['Время решения (сек)', f"{solution.solve_time:.1f}"],
            ['Всего убрано (т)', f"{metrics['harvest']['harvested_total']:,.1f}"],
            ['План (т)', f"{metrics['harvest']['planned_total']:,.1f}"],
            ['Выполнение', f"{metrics['harvest']['completion_pct']:.1f}%"],
            ['Неубрано (т)', f"{metrics['harvest']['planned_total'] - metrics['harvest']['harvested_total']:,.1f}"],
        ], columns=['Показатель', 'Значение'])
        summary.to_excel(writer, sheet_name='Summary', index=False)
        

        total_costs = sum(v for v in metrics['costs'].values() if v > 0.5)
        costs_data = []
        for k, v in metrics['costs'].items():
            if v > 0.5:  
                label = COST_LABELS.get(k, k.replace('_', ' ').title())
                pct = (v / total_costs * 100) if total_costs > 0 else 0.0
                costs_data.append({'Статья затрат': label, 'Сумма (руб.)': v, '% от итога': round(pct, 1)})
                
        costs_df = pd.DataFrame(costs_data).sort_values('Сумма (руб.)', ascending=False)

        costs_df = pd.concat([costs_df, pd.DataFrame([{
            'Статья затрат': 'ИТОГО', 
            'Сумма (руб.)': total_costs, 
            '% от итога': 100.0
        }])], ignore_index=True)
        costs_df.to_excel(writer, sheet_name='Costs', index=False)

        fields = pd.DataFrame(metrics['field_harvest_table'])
        fields = fields.rename(columns={
            'field_id': 'Поле', 'type': 'Тип', 'warehouse': 'Склад',
            'planned': 'План (т)', 'harvested': 'Убрано (т)',
            'completion_pct': 'Выполнение (%)', 'remaining': 'Остаток (т)'
        })
        fields.to_excel(writer, sheet_name='Fields', index=False)
        

        type_summary = pd.DataFrame([
            {
                'Тип': t,
                'Описание': {1: "Прямая отгрузка", 2: "Хранение на поле", 3: "Через склад"}[t],
                'Полей': metrics['field_type_summary'][t]['count'],
                'План (т)': metrics['field_type_summary'][t]['planned'],
                'Убрано (т)': metrics['field_type_summary'][t]['harvested'],
                'Выполнение (%)': metrics['field_type_summary'][t]['completion_pct']
            }
            for t in [1, 2, 3]
        ])
        type_summary.to_excel(writer, sheet_name='By Type', index=False)
        

        routes = metrics.get('routes_by_volume', [])
        if routes:
            routes_df = pd.DataFrame([
                {
                    'Маршрут': route,
                    'Рейсов': d['trips'],
                    'Тонн': f"{d['tons']:.2f}",
                    'Всего км': f"{d['km']:.1f}",
                    'Расстояние маршрута км': f"{d['km']/d['trips']:.1f}" if d['trips'] > 0 else 0
                }
                for route, d in routes
            ])
            routes_df.to_excel(writer, sheet_name='Routes', index=False)
        else:
            pd.DataFrame({'Сообщение': ['Нет данных о маршрутах']}).to_excel(writer, sheet_name='Routes', index=False)
            

        elev_inflow = pd.DataFrame([
            {
                'Элеватор': f"E{e}",
                'Всего (т)': metrics['elev_inflow_by_source'][e]['total'],
                'Тип 1 (т)': metrics['elev_inflow_by_source'][e][1],
                'Тип 1 (%)': f"{metrics['elev_inflow_by_source'][e]['1_pct']:.1f}%",
                'Тип 2 (т)': metrics['elev_inflow_by_source'][e][2],
                'Тип 2 (%)': f"{metrics['elev_inflow_by_source'][e]['2_pct']:.1f}%",
                'Тип 3 (т)': metrics['elev_inflow_by_source'][e][3],
                'Тип 3 (%)': f"{metrics['elev_inflow_by_source'][e]['3_pct']:.1f}%",
            }
            for e in data.elev_ids
        ])
        elev_inflow.to_excel(writer, sheet_name='Elev Inflow', index=False)
        

        daily_harvest = pd.DataFrame([
            {'День': day, 'Убрано (т)': metrics['harvest_by_day'].get(day, 0)}
            for day in sorted(metrics['harvest_by_day'].keys())
        ])
        daily_harvest.to_excel(writer, sheet_name='Daily Harvest', index=False)
        


        if 'elev_balance' in metrics:
            for e_id, e_data in metrics['elev_balance'].items():
                df = pd.DataFrame({
                    'День': e_data['days'],
                    'Остаток на начало дня': e_data['stock_start'],
                    'Приход с полей': e_data['in_field'],
                    'Приход со складов': e_data['in_wh'],
                    'Приход с ПП': e_data['in_point'],
                    'Общий приход': e_data['total_in'],
                    'Отгрузка по плану': e_data['plan_offload'],
                    'Отгрузка по факту': e_data['offload'],
                    'Остаток на конец дня': e_data['stock_end'],
                    'Сверка баланса': e_data['balance_check']
                }).round(2)  
                
                sheet_name = f"Элеватор_{e_id}"[:31]
                df.to_excel(writer, sheet_name=sheet_name, index=False)


        point_daily = metrics.get('point_daily', {})
        for p_id, p_data in point_daily.items():
            df = pd.DataFrame({
                'День': p_data['days'],
                'Остаток на начало дня': p_data['stock_start'],
                'Приход с полей': p_data['in_field'],
                'Приход со складов': p_data['in_wh'],
                'Общий приход': p_data['total_in'],
                'Отгрузка': p_data['outflow'],
                'Остаток на конец дня': p_data['stock_end'],
                'Потери (т)': p_data['losses']
            }).round(2)
            
            sheet_name = f"ПП_{p_id}"[:31]
            df.to_excel(writer, sheet_name=sheet_name, index=False)


        warehouse_daily = metrics.get('warehouse_daily', {})
        for w_id, w_data in warehouse_daily.items():
            df = pd.DataFrame({
                'День': w_data['days'],
                'Остаток на начало дня': w_data['stock_start'],
                'Всего пришло': w_data['total_in'],
                'Всего ушло': w_data['total_out'],
                'Остаток на конец дня': w_data['stock_end']
            }).round(2)
            
            sheet_name = f"Склад_{w_id}"[:31]
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        

        comb_data = []
        for k, daily in metrics.get('comb_daily', {}).items():
            for d in daily:
                comb_data.append({
                    'Комбайн': f"K{k}", 'День': d['day'],
                    'Выработка (т)': f"{d['harvest_tons']:.2f}",
                    'Переработка (ч)': f"{d['overtime_hours']:.2f}",
                    'Нарушение': '❌' if d['shift_violated'] else '✅'
                })
        if comb_data:
            pd.DataFrame(comb_data).to_excel(writer, sheet_name='Combines', index=False)
        

        truck_data = []
        for m, daily in metrics.get('truck_daily', {}).items():
            for d in daily:
                truck_data.append({
                    'Грузовик': f"M{m}", 'День': d['day'],
                    'Рейсов': d['trips'],
                    'Переработка (ч)': f"{d['overtime_hours']:.2f}",
                    'Нарушение': '❌' if d['shift_violated'] else '✅'
                })
        if truck_data:
            pd.DataFrame(truck_data).to_excel(writer, sheet_name='Trucks', index=False)


        input_flat = _flatten_summary(metrics.get('input_summary', {}))
        if input_flat:
            pd.DataFrame(input_flat).to_excel(writer, sheet_name='Input Data', index=False)


        elev_bal = metrics.get('elev_balance', {})
        if elev_bal:
            for eid, edata in elev_bal.items():
                df_elev = pd.DataFrame({
                    'День': edata['days'],
                    'Приход со складов (т)': edata['in_wh'],
                    'Приход с ПП (т)': edata['in_point'],
                    'Приход с полей (т)': edata['in_field'],
                    'Всего пришло (т)': edata['total_in'],
                    'Отгрузка offload (т)': edata['offload'],
                    'Остаток начало (т)': edata['stock_start'],
                    'Остаток конец (т)': edata['stock_end'],
                    'Проверка баланса (т)': edata['balance_check']
                })
                sheet_name = f"Elev_{eid}_Balance"[:31]
                df_elev.to_excel(writer, sheet_name=sheet_name, index=False)
    
    print(f"Excel: {excel_path} ({len(writer.sheets)} листов)")



def main():
    parser = argparse.ArgumentParser(description="Solver-Agnostic Analyzer")
    parser.add_argument('-r', '--response', required=True, help='Файл с решением (любой формат)')
    parser.add_argument('-o', '--output', default='reports', help='Папка для отчётов')
    parser.add_argument('--export', action='store_true', help='Экспорт в CSV')
    parser.add_argument('--no-plots', action='store_true', help='Без графиков')
    args = parser.parse_args()
    
    # 1. Загрузка данных
    print(f"Загрузка контекста: {HARVEST_FILE}")
    data = load_harvest_data(HARVEST_FILE)

    
    # 2. Автовыбор адаптера и загрузка решения
    print(f"Определение формата решения: {args.response}")
    adapter = SolutionAdapterFactory.get_adapter(args.response)
    print(f"Используется адаптер: {adapter.__class__.__name__}")
    
    solution = adapter.load(args.response)
    print(f"Решение: {solution.status} | Целевая: {solution.objective:,.0f} | "
          f"Время: {solution.solve_time:.1f}s | Gap: {solution.mip_gap:.2%}")
    
    if not solution.is_feasible:
        print(f"Предупреждение: решение не оптимально ({solution.status})")
    
    # 3. Расчёт метрик 
    print("Расчёт метрик...")
    calc = MetricsCalculator(data, solution)
    metrics = calc.compute_all()
    
    # 4. Вывод и экспорт 
    print_report(metrics, data, solution) 
    
    if args.export:
        export_to_excel(metrics, data, solution, args.output)
        
    if not args.no_plots:
        generate_plots(metrics, data, solution, args.output)

    print("\n" + "="*60)
    print("ВХОДНЫЕ ДАННЫЕ ЗАДАЧИ")
    print("="*60)
    print_input_summary(metrics.get('input_summary', {}))
    print("="*60 + "\n")
    print("field_loss_rate:")
    for fid in sorted(data.field_loss_rate.keys()):
        a=data.field_loss_rate[fid]
        if type(a) == NoneType or type(a)==int: 
            a=0.0
        print(f"   Поле {fid:<3} → {a:.4f} ({a*100:.2f}%/день)")

    print(f"\n Анализ завершён")

if __name__ == "__main__":
    sys.exit(main())