import json
from pathlib import Path
from model_general import NormalizedSolution
from model_general import SolutionAdapter

class CuOptAdapter(SolutionAdapter):
    
    def load(self, path: str | Path) -> NormalizedSolution:
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        

        solver_resp = raw.get('response', raw)
        if isinstance(solver_resp, dict):
            solver_resp = solver_resp.get('solver_response', solver_resp)
            
        solution = solver_resp.get('solution', solver_resp) if isinstance(solver_resp, dict) else {}
        

        variables = {}
        if isinstance(solution, dict) and 'vars' in solution:
            variables = {str(k): float(v) for k, v in solution['vars'].items()}
        elif isinstance(solver_resp, dict) and 'vars' in solver_resp:
            variables = {str(k): float(v) for k, v in solver_resp['vars'].items()}

        stats = solution.get('milp_statistics', {}) if isinstance(solution, dict) else {}
        status_code = int(solver_resp.get('status', -1)) if isinstance(solver_resp, dict) else -1
        
        status_map = {0: "OPTIMAL", 1: "FEASIBLE", 8: "FEASIBLE_FOUND", 2: "INFEASIBLE", 5: "TIMEOUT"}
        
        return NormalizedSolution(
            variables=variables,
            status=status_map.get(status_code, f"CODE_{status_code}"),
            objective=float(solution.get('primal_objective', 0)),
            solve_time=float(solution.get('solver_time', 0)),
            mip_gap=float(stats.get('mip_gap', 0)),
            solver_name="cuopt",
            metadata={
                'nodes': stats.get('num_nodes'),
                'iterations': stats.get('num_simplex_iterations'),
                'presolve_time': stats.get('presolve_time'),
            }
        )
    
    @staticmethod
    def supports_format(path: str | Path) -> bool:
        p = Path(path)
        if p.suffix.lower() != '.json':
            return False
        try:
            with open(p, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            

            keys = set(raw.keys())
            if 'response' in keys and isinstance(raw['response'], dict):
                keys.update(raw['response'].keys())
                

            return any(k in keys for k in ['solver_response', 'vars', 'primal_solution', 'solution'])
        except Exception:
            return False

import re
from pathlib import Path
from typing import Union, Dict

import re
from pathlib import Path
from typing import Union, Dict, List
import re
from pathlib import Path

class SolFileAdapter(SolutionAdapter):

    
    STATUS_MAP = {
        "optimal": "OPTIMAL",
        "infeasible": "INFEASIBLE",
        "unbounded": "UNBOUNDED",
        "time limit reached": "TIMEOUT",
        "iteration limit reached": "TIMEOUT",
        "solution limit reached": "TIMEOUT",
        "unknown": "UNKNOWN"
    }

    def load(self, path: str | Path) -> NormalizedSolution:
        path = Path(path)
        variables = {}
        status = "UNKNOWN"
        objective = 0.0
        
        in_columns = False
        
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue


                if line.startswith("Columns"):
                    in_columns = True
                    continue
                elif line.startswith("Rows"):
                    in_columns = False
                    continue
                

                if line.startswith("Model status:"):
                    raw_status = line.split(":", 1)[1].strip().lower()
                    status = self.STATUS_MAP.get(raw_status, raw_status.upper())
                    continue
                    
                if line.startswith("Objective value:"):
                    try:
                        objective = float(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                    continue


                if in_columns:

                    if "Index" in line and "Name" in line:
                        continue
                        
                    parts = line.split()
                    if len(parts) >= 6 and parts[-2] in ("Integer", "Continuous"):
                        name = parts[-1]
                        primal_str = parts[-3]  # Primal всегда перед Type
                        try:
                            variables[name] = float(primal_str)
                        except ValueError:
                            # HiGHS может писать '-' или 'inf'
                            if primal_str.lower() in ("inf", "+inf", "-inf"):
                                variables[name] = float(primal_str)
                            continue

        return NormalizedSolution(
            variables=variables,
            status=status,
            objective=objective,
            solve_time=0.0,  
            solver_name="highs",
            metadata={}
        )

    @staticmethod
    def supports_format(path: str | Path) -> bool:
        return Path(path).suffix.lower() == ".sol"