# === Настройки ===
TIME_LIMIT = 2000
BASE_URL = "http://localhost:5000"

# === Пути ===
DATA_FILE = 'data/generated/2.json' # Читаемые сгенерированные данные
HARVEST_FILE = 'data/generated/2h.json' # Нечитаемые сгенерированные данные
MPS_FILE = 'data/generated/mps.mps' # Модель для других солверов
HIGHS_FILE = 'data/results/solution_highs.sol' # Решение по highs

# === Ответ модели ===
STATUS_TEXT = {
    0: "Optimal",
    1: "Feasible", 
    2: "Infeasible",
    3: "Unbounded",
    4: "Error",
    5: "Timeout",
    6: "UserInterrupt",
    7: "NoSolution",
    8: "FeasibleFound", 
}