"""STR8-N UTIL MEMORY — PC backup, restore, load and offload."""
from pathlib import Path
import sys
from memory_tool import main

if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1] in ('backup','verify','plan','restore','load','offload') and '--agent' not in sys.argv:
        sys.argv += ['--agent', str(Path(__file__).resolve().parents[1]/'BUILD/str8n-copyright-r2/memory-agent-build')]
    main()
