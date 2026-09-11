#!/usr/bin/env python3
import urllib.request
import json
import sys

def main():
    try:
        req = urllib.request.Request("https://mod.fuming.name/api/simulator/status")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            
            minute = data.get("fuse_metrics", {}).get("minute_count", 0)
            max_minute = data.get("fuse_metrics", {}).get("max_per_minute", 20)
            day = data.get("fuse_metrics", {}).get("day_count", 0)
            max_day = data.get("fuse_metrics", {}).get("max_per_day", 5000)
            
            status = data.get("status", "UNKNOWN")
            service = data.get("service", "UNKNOWN")
            last_cycle = data.get("last_cycle_status", "UNKNOWN")
            
            print(f"[Simulator Status]")
            print(f"Service: {service}")
            print(f"Status: {status}")
            print(f"Last Cycle: {last_cycle}")
            print(f"Rate Limit: {minute}/{max_minute} (Day: {day}/{max_day})")
            
            if minute >= 18:
                print(f"\n⚠️ WARNING: Rate limit near cap ({minute}/{max_minute}). Publishing now may trigger DEGRADED status!")
                sys.exit(1) # exit 1 on warning so make fails
    except Exception as e:
        print(f"[Error querying simulator] {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
