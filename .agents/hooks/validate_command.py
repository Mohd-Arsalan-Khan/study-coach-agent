import sys
import json

def main():
    try:
        input_data = sys.stdin.read()
        if not input_data:
            sys.exit(0)
            
        args = json.loads(input_data)
        cmd = args.get("CommandLine", "").lower()
        
        destructive_patterns = [
            "rm -rf",
            "del /s",
            "del /q",
            "format ",
            "drop table",
            "mkfs"
        ]
        
        for pattern in destructive_patterns:
            if pattern in cmd:
                print(f"Error: Destructive command detected ('{pattern}')", file=sys.stderr)
                sys.exit(1)
                
        sys.exit(0)
    except Exception as e:
        print(f"Hook error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
