set shell := ["bash", "-cu"]

cdm := "cd src/ && "

generate GENERATION_PARAMS_FILE_NAME:
    {{cdm}} python generate.py \
    --params data/generated/{{GENERATION_PARAMS_FILE_NAME}}.json

verify FILE_NAME:
    {{cdm}} python verify.py \
    data/generated/{{FILE_NAME}}.json

server:
    export CUOPT_GIGABYTES_PER_PROC=4; \
    .venv/bin/python -m cuopt_server.cuopt_service

#lstart:
#    export CUOPT_GIGABYTES_PER_PROC=4
#    python -m cuopt_server.cuopt_service > cuopt_server.log 2>&1 &

gpu:
    {{cdm}} python solve_cuopt.py

highs:
    {{cdm}} python solve_highs.py

fetch REQ:
    {{cdm}} python fetch_cuopt.py \
    --job-id {{REQ}} \
    --output data/results/solution_cuopt.json

analyze FOLDER:
    {{cdm}} python analyze.py \
    -r data/results/solution_cuopt.json \
    -o data/cuopt/{{FOLDER}} \
    --export

ansol FOLDER:
    {{cdm}} python analyze.py \
    -r data/results/solution_highs.sol \
    -o data/highs/{{FOLDER}} \
    --export


#proc:
#   ps aux

kill:
    pkill -9 -f cuopt_server.cuopt_service

sol:
    {{cdm}} python sol_to_cuopt.py solution.sol results/highs_solution_full.json


#highs_r:
#    highs agri_model.mps --time_limit 3600 --solution_file mps_sol.sol

#delete REQ_ID:
#   curl -s -X DELETE http://localhost:5000/cuopt/solution/{{REQ_ID}}