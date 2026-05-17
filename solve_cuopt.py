from cuopt_sh_client import CuOptServiceSelfHostClient
from config import TIME_LIMIT
import json
from config import DATA_FILE, HARVEST_FILE, TIME_LIMIT
from model_cuopt_h import build_cuopt_problem
from model_general import preprocess, count_variables, save_harvest_data

print("Запуск построения модели...")

with open(DATA_FILE, 'r', encoding='utf-8') as f:
    raw = json.load(f)

print("Файл с параметрами агрохолдинга загружен...")

data = preprocess(raw)

print("Файл обработан в формат HarvestData...")

save_harvest_data(data, HARVEST_FILE)

print("Файл HarvestData сохранён")

n = count_variables(data)
problem_data, var_index = build_cuopt_problem(data, n)

print(f"Модель построена: {len(problem_data['variable_names'])} переменных, {len(problem_data['csr_constraint_matrix']['offsets'])-1} ограничений.")


print("\nСоздание клиента NVIDIA cuOpt Managed Service...")
client = CuOptServiceSelfHostClient(ip="localhost", port="5000", polling_timeout=TIME_LIMIT)

print("\nОтправка задачи в локальный NVIDIA cuOpt Server...")
# 1. Первичный вызов
client.get_LP_solve(problem_data, response_type="dict")