import numpy as np

def save_as_mps(var_names, var_types, var_lb, var_ub, obj_coef,
                offsets, indices, values, con_lb, con_ub, 
                output_path, BIG_M=1e9) -> None:
    n_vars = len(var_names)
    n_cons = len(con_lb)
    

    THRESH = BIG_M * 0.1
    

    rows = [] 
    for i, (lb, ub) in enumerate(zip(con_lb, con_ub)):
        if abs(ub - lb) < 1e-6:
            rows.append(('E', lb, i))
        elif lb < -THRESH:
            rows.append(('L', ub, i))
        elif ub > THRESH:
            rows.append(('G', lb, i))
        else:

            rows.append(('G', lb, i))
            rows.append(('L', ub, i))
            
    con_names = [f"R{j:05d}" for j in range(len(rows))]
    

    col_entries = [[] for _ in range(n_vars)]
    for r_idx, (sense, rhs, orig_idx) in enumerate(rows):

        for k in range(offsets[orig_idx], offsets[orig_idx+1]):
            c = indices[k]
            col_entries[c].append((r_idx, values[k]))


    with open(output_path, 'w') as f:
        f.write("NAME          AGRI_HARVEST\n")
        f.write("ROWS\n")
        f.write(" N  OBJ\n")
        for j, (sense, _, _) in enumerate(rows):
            f.write(f" {sense}  {con_names[j]}\n")

        f.write("COLUMNS\n")
        int_idx = [j for j in range(n_vars) if var_types[j] in ('I', 'B')]
        cont_idx = [j for j in range(n_vars) if var_types[j] == 'C']
        
        def write_col(j):
            name = var_names[j]
            c = float(obj_coef[j])
            if abs(c) > 1e-12:
                f.write(f"    {name}  OBJ  {c:.12E}\n")
            for r, v in col_entries[j]:
                f.write(f"    {name}  {con_names[r]}  {float(v):.12E}\n")

        if int_idx:
            f.write("    MARKER    'MARKER'                 'INTORG'\n")
            for j in int_idx: write_col(j)
            f.write("    MARKER    'MARKER'                 'INTEND'\n")
        for j in cont_idx: write_col(j)

        f.write("RHS\n")
        for j, (_, rhs, _) in enumerate(rows):
            if abs(rhs) > 1e-12:
                f.write(f"    RHS1  {con_names[j]}  {rhs:.12E}\n")

        f.write("BOUNDS\n")
        for j in range(n_vars):
            name = var_names[j]
            lb, ub = float(var_lb[j]), float(var_ub[j])
            vtype = var_types[j]
            
            if vtype == 'B':
                f.write(f" BV BND1    {name}\n")
            elif vtype == 'I':
                if lb > 1e-12: f.write(f" LI BND1    {name}  {lb:.12E}\n")
                if ub < THRESH: f.write(f" UI BND1    {name}  {ub:.12E}\n")
            else:
                if lb > 1e-12: f.write(f" LO BND1    {name}  {lb:.12E}\n")
                if ub < THRESH: f.write(f" UP BND1    {name}  {ub:.12E}\n")
                
        f.write("ENDATA\n")
        
    print(f"MPS сохранён: {output_path}")
    print(f"Строк: {len(rows)} | Переменных: {n_vars}")