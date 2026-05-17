
import highspy
import sys
from config import MPS_FILE, HIGHS_FILE, TIME_LIMIT

def solve_with_highspy(mps_path: str = "agri_model.mps", sol_path: str = "solution.sol"):
    h = highspy.Highs()
    

    h.setOptionValue("threads", 1)               
    h.setOptionValue("time_limit", TIME_LIMIT)
    h.setOptionValue("mip_rel_gap", 0.1)      
    h.setOptionValue("log_to_console", True)   
    
    print(f"Чтение модели: {mps_path}")
    status = h.readModel(mps_path)
    if status != highspy.HighsStatus.kOk:
        print(f"Ошибка чтения MPS: {status}")
        return False

    print("Запуск решения...")
    h.run()
    
    model_status = h.getModelStatus()
    obj_val = h.getObjectiveValue()
    
    print(f"\nРезультат:")
    print(f"   Статус: {h.modelStatusToString(model_status)}")
    print(f"   Целевая: {obj_val:.2f}")

    if model_status in (highspy.HighsModelStatus.kOptimal, 
                        highspy.HighsModelStatus.kTimeLimit,
                        highspy.HighsModelStatus.kSolutionLimit):
        h.writeSolution(sol_path, 1)
        print(f"Решение сохранено: {sol_path}")
        return True
    else:
        print("Допустимое решение не найдено. Файл .sol не создан.")
        return False

if __name__ == "__main__":
    solve_with_highspy(MPS_FILE, HIGHS_FILE)