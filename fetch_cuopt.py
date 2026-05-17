

import argparse
import json
import sys
from pathlib import Path
from cuopt_sh_client import CuOptServiceSelfHostClient 

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--job-id", required=True, help="Job ID задачи")
    p.add_argument("--url", default="http://localhost:5000", help="Базовый URL cuOpt")
    p.add_argument("--output", default="solution_full.json", help="Путь для сохранения")
    args = p.parse_args()


    host = args.url.replace("http://", "").replace("https://", "").split(":")[0]
    port = int(args.url.split(":")[-1].split("/")[0])


    client = CuOptServiceSelfHostClient(ip=host, port=port, polling_timeout=120)
    result = client.repoll(args.job_id, response_type="dict")  


    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"Решение сохранено: {output.resolve()} ({output.stat().st_size / 1024:.1f} KB)")
    return 0

if __name__ == "__main__":
    sys.exit(main())