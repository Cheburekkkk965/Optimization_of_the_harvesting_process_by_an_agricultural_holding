
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, Optional

import numpy as np
from model_general import HarvestData, NormalizedSolution
from matplotlib.ticker import FuncFormatter

import warnings
warnings.filterwarnings('ignore', message='Glyph.*missing from font')

HAS_MATPLOTLIB = False
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    print("matplotlib не установлен. Графики не будут построены.")


def generate_plots(metrics: Dict, data: HarvestData, solution: NormalizedSolution, output_dir: str):

    if not HAS_MATPLOTLIB:
        print("Пропуск генерации графиков: matplotlib не установлен")
        return
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    print("Генерация графиков...")
    
    # 1. Динамика уборки по дням
    plot_harvest_dynamics(metrics, data, solution, output_dir)
    
    # 2. Потоки хранилищ (inflow/outflow)
    plot_storage_flows(metrics, data, output_dir)
    
    plot_resource_utilization(metrics, data, solution, output_dir)
    plot_truck_routes(metrics, data, output_dir)
    plot_type2_dynamics(metrics, data, solution, output_dir)
    plot_elevator_balance(metrics, data, output_dir)
    
    print(f"Графики сохранены в: {output_dir}/")
# plots.py — НОВЫЙ подход: линии вместо столбцов

def plot_harvest_dynamics(metrics: Dict,  HarvestData, solution: NormalizedSolution, output_dir: str):


    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    import numpy as np
    
    harvest_by_day = metrics.get('harvest_by_day', {})
    comb_daily = metrics.get('comb_daily', {})
    
    if not harvest_by_day:
        print(" Нет данных для harvest_dynamics")
        return
    

    days: list[int] = sorted(int(d) for d in harvest_by_day.keys())
    total_daily: list[float] = [harvest_by_day[d] for d in days]
    
    fig, ax = plt.subplots(figsize=(14, 6), dpi=150)
    

    ax.plot(days, total_daily, marker='o', linewidth=3, color='#2E86AB', 
           label='Всего убрано', zorder=10)
    ax.fill_between(days, total_daily, alpha=0.2, color='#2E86AB')
    

    n_combs = 0
    if comb_daily:
        n_combs = len(comb_daily)

        if n_combs <= 12:
            cmap = plt.get_cmap('Set3')
        elif n_combs <= 20:
            cmap = plt.get_cmap('tab20')
        else:
            cmap = plt.get_cmap('rainbow')
        

        sorted_combs = sorted(
            comb_daily.items(),
            key=lambda x: sum(d.get('harvest_tons', 0) for d in x[1]),
            reverse=True
        )
        
        for idx, (k, daily) in enumerate(sorted_combs):
            values = [d.get('harvest_tons', 0) for d in daily]
            if sum(values) < 1:  
                continue
            
            color = cmap(idx / n_combs)
            ax.plot(days, values, linewidth=1.5, alpha=0.7, 
                   label=f"K{k}", linestyle='--')
    

    total_harvest = sum(total_daily)
    avg_daily = total_harvest / len(days) if days else 0
    
    ax.set_title(f"Динамика уборки по дням\n"
                f"Всего: {total_harvest:,.1f} т | Среднее: {avg_daily:,.1f} т/день", 
                fontsize=12, fontweight='bold')
    ax.set_xlabel("День", fontsize=10)
    ax.set_ylabel("Тонн убрано", fontsize=10)
    

    ax.set_xticks(days)

    
    # Легенда
    ncol = min(3, (n_combs + 2) // 2) if comb_daily else 1
    ax.legend(fontsize=8, ncol=ncol, frameon=True, shadow=True, loc='upper right')
    
    ax.grid(axis='y', linestyle=':', alpha=0.4)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:,.0f}'))
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/01_harvest_with_combines.png", bbox_inches='tight', dpi=150)
    plt.close()
    print(f"   ✓ 01_harvest_with_combines.png (общая + {len(comb_daily)} комбайнов)")

def plot_truck_routes(metrics: Dict,  data: HarvestData, output_dir: str):

    import matplotlib.pyplot as plt
    
    truck_daily = metrics.get('truck_daily', {})
    
    if not truck_daily:
        print("Нет данных для truck_routes")
        return
    

    days = [int(d) for d in (data.days.tolist() if hasattr(data.days, 'tolist') else data.days)]
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), dpi=150, sharex=True)
    

    sorted_trucks = sorted(
        truck_daily.items(),
        key=lambda x: sum(d.get('trips', 0) for d in x[1]),
        reverse=True
    )
    
    n_trucks = len(sorted_trucks)
    if n_trucks <= 10:
        cmap = plt.get_cmap('Pastel1')
    elif n_trucks <= 20:
        cmap = plt.get_cmap('tab20')
    else:
        cmap = plt.get_cmap('gist_rainbow')
    

    total_trips_all_days = [0] * len(days)
    
    for idx, (m, daily) in enumerate(sorted_trucks):
        trips = [d.get('trips', 0) for d in daily]
        total = sum(trips)
        if total < 1:
            continue
        
        color = cmap(idx / n_trucks)
        ax1.plot(days, trips, linewidth=1.5, marker='o', markersize=3, 
                label=f"M{m} (всего {total} рейсов)", alpha=0.8)
        
        for i, t in enumerate(trips):
            total_trips_all_days[i] += t
    

    ax1.plot(days, total_trips_all_days, linewidth=3, color='black', 
            linestyle='-', label='ВСЕГО рейсов', zorder=10)
    
    ax1.set_ylabel("Рейсов/день", fontsize=10)
    ax1.set_title(f"Рейсы грузовиков по дням\n"
                 f"Всего рейсов за период: {sum(total_trips_all_days)}", 
                 fontsize=12, fontweight='bold')
    
    ncol = min(2, (n_trucks + 1) // 3)
    ax1.legend(fontsize=7, ncol=ncol, frameon=True, loc='upper right')
    ax1.grid(axis='y', linestyle=':', alpha=0.4)
    

    ax1.set_xticks(days)  
    ax1.set_xticklabels(days, rotation=45, ha='right', fontsize=8)
    

    has_overtime = False
    for m, daily in sorted_trucks[:10]:  # Топ-10
        overtime = [d.get('overtime_hours', 0) for d in daily]
        if any(ot > 0.1 for ot in overtime):
            ax2.plot(days, overtime, marker='o', linewidth=1.5, 
                    label=f"M{m}", markersize=3)
            has_overtime = True
    
    ax2.axhline(y=0, color='gray', linestyle='-', linewidth=0.5)
    ax2.set_xlabel("День", fontsize=10)
    ax2.set_ylabel("Переработка, часов", fontsize=10)
    ax2.set_title(f"Переработка грузовиков (сверх {int(data.T_shift)}ч)", 
                 fontweight='bold', fontsize=12)
    ax2.grid(axis='y', linestyle=':', alpha=0.4)
    

    ax2.set_xticks(days)
    ax2.set_xticklabels(days, rotation=45, ha='right', fontsize=8)
    
    if has_overtime:
        ax2.legend(fontsize=8, frameon=True)
    else:
        ax2.text(0.5, 0.5, "Переработки нет", ha='center', va='center', 
                fontsize=10, color='green', transform=ax2.transAxes)
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/02_truck_routes.png", bbox_inches='tight', dpi=150)
    plt.close()
    print(f"   ✓ 02_truck_routes.png ({n_trucks} грузовиков)")

def plot_storage_flows(metrics: Dict, data: HarvestData, output_dir: str, limit: int = 6):

    
    chart_data = metrics.get('storage_chart_data', {})
    if not chart_data:
        print("ВНИМАНИЕ: chart_data пуст! Проверь _compute_storage_charts в metrics.py")
        return
    

    non_empty_count = sum(1 for d in chart_data.values() if d.get('inflow') or d.get('outflow') or d.get('stock'))
    if non_empty_count == 0:
        print("ВНИМАНИЕ: Все графики хранилищ пустые (inflow=outflow=stock=0)")
        print("   Это значит, что решение не содержит перевозок или метрики не рассчитаны.")

        for stype, title, color in [
            ('warehouse', "Склад", '#27AE60'),
            ('elevator', "Элеватор", '#2980B9'),
            ('point', "ПП", '#16A085')
        ]:
            items = {k: v for k, v in chart_data.items() if k.startswith(f'{stype}_')}
            for name in list(items.keys())[:1]:
                fig, ax = plt.subplots(figsize=(10, 4), dpi=150)
                ax.text(0.5, 0.5, "Нет данных\n(перевозки = 0)", 
                       ha='center', va='center', fontsize=14, color='gray')
                ax.set_title(f"{title}: {name}", fontsize=11)
                ax.axis('off')
                plt.savefig(f"{output_dir}/02_{name}_flows.png", bbox_inches='tight', dpi=150)
                plt.close()
                print(f"   ✓ 02_{name}_flows.png (пустой)")
        return
    
    def _plot_group(items: Dict, title: str, prefix: str, color_in: str, color_out: str, color_stock: str):
        if not items:
            print(f" {title}: нет объектов для отображения")
            return
        
        plotted = 0
        for i, (name, d) in enumerate(list(items.items())[:limit]):
            days = d.get('days', [])
            inflow = d.get('inflow', [])
            outflow = d.get('outflow', [])
            stock = d.get('stock', [])
            
            if not days:
                print(f" {name}: нет данных о днях")
                continue
            
            total_in = sum(inflow) if inflow else 0
            total_out = sum(outflow) if outflow else 0
            final_stock = stock[-1] if stock else 0
            
            if total_in == 0 and total_out == 0 and final_stock == 0:
                print(f" {name}: все значения нулевые")
                # Всё равно создаём график, но с пометкой
                fig, ax = plt.subplots(figsize=(10, 4), dpi=150)
                ax.text(0.5, 0.5, "Нет активности", ha='center', va='center', 
                       fontsize=12, color='gray', alpha=0.7)
                ax.set_title(f"{title}: {name}")
                plt.savefig(f"{output_dir}/02_{prefix}_{name.split('_')[-1]}_flows.png", 
                           bbox_inches='tight', dpi=150)
                plt.close()
                continue
            

            fig, ax1 = plt.subplots(figsize=(12, 5), dpi=150)
            

            width = 0.35
            x = np.arange(len(days))
            ax1.bar(x - width/2, inflow, width, label='Поступило', 
                   color=color_in, alpha=0.8, edgecolor='white')
            ax1.bar(x + width/2, outflow, width, label='Уехало', 
                   color=color_out, alpha=0.8, edgecolor='white')
            
            ax1.set_xlabel("День", fontsize=10)
            ax1.set_ylabel("Тонн/день", fontsize=10, color='black')
            ax1.tick_params(axis='y', labelcolor='black')
            ax1.set_xticks(x)
            ax1.set_xticklabels(days, rotation=45, ha='right')
            

            has_stock = any(s > 0 for s in stock) if stock else False
            if has_stock:
                ax2 = ax1.twinx()  # Создаём вторую ось
                ax2.plot(x, stock, color=color_stock, linewidth=2.5, marker='o', 
                        markersize=4, label='Запас на конец дня')
                ax2.set_ylabel("Запас, тонн", fontsize=10, color=color_stock)
                ax2.tick_params(axis='y', labelcolor=color_stock)
                

                lines1, labels1 = ax1.get_legend_handles_labels()
                lines2, labels2 = ax2.get_legend_handles_labels()
                ax1.legend(lines1 + lines2, labels1 + labels2, 
                          loc='upper left', frameon=True, shadow=True)
            else:

                ax1.legend(loc='upper left', frameon=True, shadow=True)
            

            ax1.set_title(f"{title}: {name}\n"
                         f"Всего поступило: {total_in:,.1f} т | "
                         f"Уехало: {total_out:,.1f} т | "
                         f"Остаток: {final_stock:,.1f} т", 
                         fontsize=11, fontweight='bold')
            
            ax1.grid(axis='y', linestyle=':', alpha=0.4)
            plt.tight_layout()
            
            fname = f"{output_dir}/02_{prefix}_{name.split('_')[-1]}_flows.png"
            plt.savefig(fname, bbox_inches='tight', dpi=150)
            plt.close()
            plotted += 1
        
        if plotted > 0:
            print(f"    02_{prefix}_*_flows.png ({plotted} из {len(items)})")
        else:
            print(f"    02_{prefix}_*: все графики пустые")
    

    _plot_group(
        {k: v for k, v in chart_data.items() if k.startswith('warehouse_')},
        "Склад", "wh", '#27AE60', '#E67E22', '#2C3E50'
    )
    _plot_group(
        {k: v for k, v in chart_data.items() if k.startswith('elevator_')},
        "Элеватор", "elev", '#2980B9', '#F39C12', '#8E44AD'
    )
    _plot_group(
        {k: v for k, v in chart_data.items() if k.startswith('point_')},
        "ПП", "point", '#16A085', '#D35400', '#C0392B'
    )



def plot_resource_utilization(metrics: Dict, data: HarvestData, solution: NormalizedSolution, output_dir: str):

    import matplotlib.pyplot as plt
    import numpy as np
    
    comb_daily = metrics.get('comb_daily', {})
    truck_daily = metrics.get('truck_daily', {})
    
    if not comb_daily and not truck_daily:
        print("Нет данных для resource_utilization")
        return
    

    days = [int(d) for d in (data.days.tolist() if hasattr(data.days, 'tolist') else data.days)]
    x = np.arange(len(days))  
    

    if comb_daily:
        fig, axes = plt.subplots(2, 1, figsize=(12, 8), dpi=150, sharex=True)
        

        ax1 = axes[0]
        bottom = [0] * len(days)
        
        n_combs = len(comb_daily)
        if n_combs <= 10:
            cmap = plt.get_cmap('Set3')
        elif n_combs <= 20:
            cmap = plt.get_cmap('tab20')
        else:
            cmap = plt.get_cmap('rainbow')
        
        colors = [cmap(i / n_combs) for i in range(n_combs)]
        sorted_combs = sorted(comb_daily.items(), 
                             key=lambda x: sum(d.get('harvest_tons', 0) for d in x[1]), 
                             reverse=True)
        
        for idx, (k, daily) in enumerate(sorted_combs):
            values = [d.get('harvest_tons', 0) for d in daily]
            if sum(values) < 1: 
                continue
            color = colors[idx % len(colors)]

            ax1.bar(days, values, bottom=bottom, label=f"K{k}", 
                   color=color, alpha=0.85, edgecolor='white', linewidth=0.5)
            bottom = [b + v for b, v in zip(bottom, values)]
        
        ax1.set_ylabel("Тонн/день", fontsize=10)
        ax1.set_title("Выработка комбайнов по дням", fontweight='bold', fontsize=12)
        ax1.legend(fontsize=8, ncol=min(3, (n_combs+1)//2), frameon=True, loc='upper right')
        ax1.grid(axis='y', linestyle=':', alpha=0.4)
        

        ax1.set_xticks(days)  
        ax1.set_xticklabels(days, rotation=45, ha='right', fontsize=8)
        

        ax2 = axes[1]
        plotted = 0
        
        for k, daily in sorted_combs:
            overtime = [d.get('overtime_hours', 0) for d in daily]
            total_ot = sum(overtime)
            
            if total_ot > 0.001:
                color = colors[sorted_combs.index((k, daily)) % len(colors)]

                ax2.plot(days, overtime, marker='o', label=f"K{k}", 
                        color=color, linewidth=2, markersize=4, alpha=0.9)
                plotted += 1
        
        if plotted == 0:
            ax2.plot(days, [0]*len(days), 'k--', alpha=0.3, label='переработка = 0')
        
        ax2.set_ylim(0, max(4.5, ax2.get_ylim()[1]))
        ax2.axhline(y=0, color='gray', linestyle='-', linewidth=0.5)
        ax2.axhline(y=8, color='orange', linestyle=':', linewidth=1, label=f'норма (8ч)')
        
        ax2.set_xlabel("День", fontsize=10)
        ax2.set_ylabel("Переработка, часов", fontsize=10)
        ax2.set_title(f"Переработка комбайнов (сверх 8ч)", fontweight='bold', fontsize=12)
        ax2.grid(axis='y', linestyle=':', alpha=0.4)
        

        ax2.set_xticks(days)
        ax2.set_xticklabels(days, rotation=45, ha='right', fontsize=8)
        
        if plotted > 0:
            ax2.legend(fontsize=8, ncol=min(3, plotted), loc='upper right', frameon=True)
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/03_comb_utilization.png", bbox_inches='tight', dpi=150)
        plt.close()
        print(f"   ✓ 03_comb_utilization.png ({n_combs} комбайнов, {plotted} с переработкой)")
    

    if truck_daily:
        fig, axes = plt.subplots(2, 1, figsize=(12, 8), dpi=150, sharex=True)
        
        ax1 = axes[0]
        bottom = [0] * len(days)
        
        n_trucks = len(truck_daily)
        if n_trucks <= 10:
            cmap = plt.get_cmap('Pastel1')
        elif n_trucks <= 20:
            cmap = plt.get_cmap('tab20')
        else:
            cmap = plt.get_cmap('gist_rainbow')
        
        colors = [cmap(i / n_trucks) for i in range(n_trucks)]
        sorted_trucks = sorted(truck_daily.items(), 
                              key=lambda x: sum(d.get('trips', 0) for d in x[1]), 
                              reverse=True)
        
        for idx, (m, daily) in enumerate(sorted_trucks):
            trips = [d.get('trips', 0) for d in daily]
            total = sum(trips)
            if total < 1:
                continue
            
            color = colors[idx % len(colors)]
            ax1.bar(days, trips, bottom=bottom, label=f"M{m}", 
                   color=color, alpha=0.85, edgecolor='white', linewidth=0.5)
            bottom = [b + v for b, v in zip(bottom, trips)]
        
        ax1.set_ylabel("Рейсов/день", fontsize=10)
        ax1.set_title("Рейсы грузовиков по дням", fontweight='bold', fontsize=12)
        

        ax1.set_xticks(days)
        ax1.set_xticklabels(days, rotation=45, ha='right', fontsize=8)
        
        ncol = min(3, (n_trucks + 1) // 2)
        ax1.legend(fontsize=8, ncol=ncol, frameon=True, loc='upper right')
        ax1.grid(axis='y', linestyle=':', alpha=0.4)
        

        ax2 = axes[1]
        for m, daily in sorted_trucks[:10]:
            overtime = [d.get('overtime_hours', 0) for d in daily]
            if any(ot > 0.1 for ot in overtime):
                ax2.plot(days, overtime, marker='o', label=f"M{m}", linewidth=1.5, markersize=3)
        
        ax2.axhline(y=0, color='gray', linestyle='-', linewidth=0.5)
        

        ax2.set_xticks(days)
        ax2.set_xticklabels(days, rotation=45, ha='right', fontsize=8)
        
        ax2.set_xlabel("День", fontsize=10)
        ax2.set_ylabel("Переработка, часов", fontsize=10)
        ax2.set_title(f"Переработка грузовиков (сверх {int(data.T_shift)}ч)", fontweight='bold', fontsize=12)
        ax2.grid(axis='y', linestyle=':', alpha=0.4)
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/04_truck_utilization.png", bbox_inches='tight', dpi=150)
        plt.close()
        print(f"   ✓ 04_truck_utilization.png ({n_trucks} грузовиков)")


def plot_type2_dynamics(metrics: Dict, data: HarvestData, sol: NormalizedSolution, output_dir: str):

    import matplotlib.pyplot as plt
    import numpy as np
    
    dynamics = metrics.get('type2_field_dynamics', {})
    if not dynamics:
        print(" Нет данных type2_field_dynamics")
        return
    
    print(f"Генерация графиков для полей типа 2: {list(dynamics.keys())}")
    

    for field_id, d in dynamics.items():

        min_int = data.field_min_interval.get(field_id, 0)
        max_storage = data.field_max_storage.get(field_id, 0)
        

        days = np.array([int(day) for day in d['days']])
        stock_end = np.array(d['stock_end'])
        harvest = np.array(d['harvest'])
        outflow = np.array(d['outflow'])
        losses = np.array(d['losses'])
        

        removal_days = days[outflow > 0.1]
        

        violations = []
        if len(removal_days) > 1 and min_int > 1:
            for i in range(1, len(removal_days)):
                gap = removal_days[i] - removal_days[i-1]
                if gap < min_int:
                    violations.append((removal_days[i-1], removal_days[i], gap))
        

        fig, axes = plt.subplots(3, 1, figsize=(14, 12), 
                                gridspec_kw={'height_ratios': [2, 1, 1], 'hspace': 0.15})
        

        ax1 = axes[0]
        ax1.fill_between(days, stock_end, 0, alpha=0.3, color='blue', label='Запас на поле')
        ax1.plot(days, stock_end, 'b-o', label='Остаток (конец дня)', linewidth=2, markersize=4)
        ax1.plot(days, outflow, 'g-s', label='Вывоз', linewidth=2, markersize=5)
        ax1.plot(days, harvest, 'orange', marker='^', label='Уборка', linewidth=2, markersize=4, linestyle='--')
        ax1.plot(days, losses, 'r:', label='Потери', linewidth=1.5)
        
        for day in removal_days:
            ax1.axvline(x=day, color='green', linestyle=':', alpha=0.5, linewidth=1)
        
        ax1.set_ylabel('Тонны', fontweight='bold')
        ax1.set_title(f"Поле {field_id} (тип 2)\nmin_int={min_int-1} дн, max_storage={max_storage} дн, потери={d['loss_rate_pct']}%/день", 
                     fontweight='bold', pad=10)
        ax1.legend(loc='upper right', fontsize=9)
        ax1.grid(alpha=0.3)
        _set_integer_xticks(ax1, days)
        

        ax2 = axes[1]
        if sol is not None:
            try:
                b_flags = [sol.get(f"b_{field_id}_{t}", 0.0) for t in days]
                ax2.bar(days, b_flags, color='purple', alpha=0.6, edgecolor='black')
                ax2.set_ylabel('Флаг b', fontweight='bold')
                ax2.set_ylim(-0.1, 1.1)
                ax2.grid(alpha=0.3, axis='y')
                _set_integer_xticks(ax2, days)
            except Exception as e:
                ax2.text(0.5, 0.5, f"Ошибка чтения флагов:\n{str(e)}", 
                        ha='center', va='center', transform=ax2.transAxes, fontsize=10)
                ax2.set_ylim(0, 1)
                _set_integer_xticks(ax2, days)
        else:
            ax2.text(0.5, 0.5, "Флаг b недоступен\n(sol=None)", 
                    ha='center', va='center', transform=ax2.transAxes, fontsize=10)
            ax2.set_ylim(0, 1)
            _set_integer_xticks(ax2, days)
        

        ax3 = axes[2]
        if len(removal_days) > 1:
            gaps = np.diff(removal_days)
            ax3.bar(removal_days[1:], gaps, color='red' if violations else 'green', 
                    alpha=0.7, edgecolor='black', width=0.6)
            ax3.axhline(y=min_int, color='red', linestyle='--', linewidth=2, 
                       label=f'Мин. интервал ({min_int} дн)')
            ax3.set_xlabel('День', fontweight='bold')
            ax3.set_ylabel('Интервал (дней)', fontweight='bold')
            ax3.set_ylim(0, max(gaps.max()+1, min_int+2))
            ax3.legend()
            ax3.grid(alpha=0.3, axis='y')
            _set_integer_xticks(ax3, days)
        else:
            ax3.text(0.5, 0.5, "Менее 2 вывозов\nневозможно проверить интервал", 
                    ha='center', va='center', transform=ax3.transAxes)
            ax3.set_ylim(0, 5)
            _set_integer_xticks(ax3, days)

        status_text = f"Вывозов: {len(removal_days)} | "
        if violations:
            status_text += f"Нарушений min_int: {len(violations)}"
            for v in violations[:3]:
                status_text += f"\n   Дни {v[0]}→{v[1]}: интервал={v[2]} < {min_int}"
        else:
            status_text += "min_int соблюдается"
        
        fig.text(0.02, 0.02, status_text, fontsize=9, verticalalignment='bottom',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        

        plt.tight_layout()
        out_filename = f"type2_field_{field_id}_diagnostics.png"
        plt.savefig(f"{output_dir}/{out_filename}", dpi=150, bbox_inches='tight')
        plt.close()
        

        print(f"   {out_filename} | Вывозов: {len(removal_days)} | {'OK' if not violations else f'WARN ({len(violations)} нарушений)'}")
    
    print(f" Сгенерировано графиков для {len(dynamics)} полей типа 2.")



def _set_integer_xticks(ax, days: np.ndarray, max_labels: int = 20):
    """
    Устанавливает явные целочисленные тики на оси X.
    Если дней много → показывает каждый N-й, чтобы не сливались.
    """
    if len(days) <= max_labels:
        ax.set_xticks(days)
        ax.set_xticklabels(days, rotation=45, ha='right', fontsize=8)
    else:
        step = max(1, len(days) // max_labels)
        ax.set_xticks(days[::step])
        ax.set_xticklabels([str(d) for d in days[::step]], rotation=45, ha='right', fontsize=8)


def plot_elevator_balance(metrics: Dict,  HarvestData, output_dir: str):

    import matplotlib.pyplot as plt
    import numpy as np
    
    elev_bal = metrics.get('elev_balance', {})
    if not elev_bal:
        print(" Нет данных elev_balance для графика")
        return
    
    n_elev = len(elev_bal)
    n_cols = 2
    n_rows = (n_elev + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, 5 * n_rows), squeeze=False)
    fig.suptitle('Баланс элеваторов: План vs Факт отгрузки + Shortfall', 
                 fontsize=16, fontweight='bold', y=1.02)
    

    colors = {
        'in_total': '#95A5A6',    # Серый фон для прихода
        'offload': '#27AE60',     # Насыщенный зелёный для факта
        'plan': '#E74C3C',        # Яркий красный для плана
        'shortfall': '#F39C12',   # Оранжевый для shortfall
        'stock': '#34495E',       # Тёмный для остатка
        'grid': '#ECF0F1'
    }
    
    for idx, (e_id, d) in enumerate(elev_bal.items()):
        row, col = divmod(idx, n_cols)
        ax = axes[row, col]
        

        days = np.array([int(day) for day in d['days']])
        plan = np.array(d['plan_offload'])
        offload = np.array(d['offload'])
        shortfall = np.array(d['shortfall'])
        stock = np.array(d['stock_end'])
        total_in = np.array(d['total_in'])
        

        ax.fill_between(days, 0, total_in, color=colors['in_total'], alpha=0.15, 
                       label='Приход (сумма)', zorder=1)
        ax.plot(days, total_in, color=colors['in_total'], linewidth=0.8, alpha=0.4, zorder=2)
        

        if np.any(plan > 0.1):
            ax.plot(days, plan, color=colors['plan'], linestyle='--', linewidth=3, 
                   marker='o', markersize=4, markevery=max(1, len(days)//10),
                   label='План отгрузки', zorder=5)
        
        ax.plot(days, offload, color=colors['offload'], linestyle='-', linewidth=3, 
               marker='s', markersize=4, markevery=max(1, len(days)//10),
               label='Факт отгрузки', zorder=6)
        

        if np.any(shortfall > 0.1):
            ax.fill_between(days, offload, plan, where=(plan > offload),
                           color=colors['shortfall'], alpha=0.5, 
                           label=f'Недоотгрузка (max: {shortfall.max():.1f} т)', 
                           zorder=4, hatch='///')
            peak_days = days[(shortfall > shortfall.max() * 0.8) & (shortfall > 0.1)]
            peak_vals = shortfall[(shortfall > shortfall.max() * 0.8) & (shortfall > 0.1)]
            if len(peak_days) > 0:
                ax.scatter(peak_days, plan[(shortfall > shortfall.max() * 0.8) & (shortfall > 0.1)], 
                          color=colors['shortfall'], s=80, zorder=7, edgecolors='black', linewidth=1)
        

        ax2 = ax.twinx()
        ax2.plot(days, stock, color=colors['stock'], marker='D', markersize=3, 
                linewidth=2, linestyle=':', label='Остаток на элеваторе', zorder=3)
        ax2.set_ylabel('Остаток, т', color=colors['stock'], fontweight='bold')
        ax2.tick_params(axis='y', labelcolor=colors['stock'])
        ax2.grid(False)
        

        ax.set_title(f"Элеватор #{e_id}\nЁмкость: {d['capacity']:.0f} т", 
                    fontweight='bold', pad=10)
        ax.set_xlabel('День', fontweight='bold')
        ax.set_ylabel('Тонны', fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--', color=colors['grid'], zorder=0)
        ax.set_axisbelow(True)
        
        y_max = max(plan.max() if np.any(plan>0) else 0, 
                   offload.max(), total_in.max(), stock.max()) * 1.15
        ax.set_ylim(0, y_max)

        if len(days) <= 20:
            ax.set_xticks(days)
            ax.set_xticklabels(days, rotation=45, ha='right', fontsize=8)
        else:
            step = max(1, len(days) // 12)  # ~12 подписей максимум
            ax.set_xticks(days[::step])
            ax.set_xticklabels([str(d) for d in days[::step]], rotation=45, ha='right', fontsize=8)
        

        l1, lb1 = ax.get_legend_handles_labels()
        l2, lb2 = ax2.get_legend_handles_labels()
        ax.legend(l1+l2, lb1+lb2, loc='upper left', fontsize=9, framealpha=0.95, 
                 ncol=2, bbox_to_anchor=(0, 1.02))
        

        total_shortfall = shortfall.sum()
        if total_shortfall > 0.1:
            ax.text(0.02, 0.98, f'Σ shortfall: {total_shortfall:.1f} т', 
                   transform=ax.transAxes, fontsize=9, 
                   bbox=dict(boxstyle='round', facecolor=colors['shortfall'], alpha=0.2),
                   verticalalignment='top')
        

    for i in range(n_elev, n_rows * n_cols):
        r, c = divmod(i, n_cols)
        axes[r, c].axis('off')
        
    plt.tight_layout()
    out_path = f"{output_dir}/elevators_balance_dashboard.png"
    plt.savefig(out_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f" График сохранён: {out_path}")