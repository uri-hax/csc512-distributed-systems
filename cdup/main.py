import argparse
import os
import sys
from .detect_type_1 import find_clones_inverted_index_step_by_step

def main():
    parser = argparse.ArgumentParser(description="CDUP: Simple Code Duplication Detector")
    parser.add_argument("path", help="Path to the directory or file to scan")
    parser.add_argument("--types", nargs="+", type=int, default=[1], 
                        help="Types of clones to detect (e.g., --types 1 2). Default is 1.")
    parser.add_argument("--show-sequence", action="store_true", 
                        help="Show the code content of the duplicated sequence.")
    
    args = parser.parse_args()

    if not os.path.exists(args.path):
        print(f"Error: Path '{args.path}' does not exist.")
        sys.exit(1)

    # Collect C files
    files = []
    if os.path.isfile(args.path):
        if args.path.endswith(('.c', '.h')):
            files.append(args.path)
    else:
        for root, _, filenames in os.walk(args.path):
            for filename in filenames:
                if filename.endswith(('.c', '.h')):
                    files.append(os.path.join(root, filename))

    if not files:
        print("No C/H files found to scan.")
        return

    print(f"Scanning {len(files)} files for clones...\n")

    if 1 in args.types:
        print("--- Running Type I Clone Detection ---")
        
        for filepath in files:
            print(f"\nAnalyzing File: {filepath}")
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                find_clones_inverted_index_step_by_step(content)
            except Exception as e:
                print(f"Error reading {filepath}: {e}")

if __name__ == "__main__":
    main()