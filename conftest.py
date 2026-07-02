import os
import sys

# Zapewnia, że pakiety najwyższego poziomu (core, geo, connectors, ...) są
# importowalne przy uruchamianiu pytest z katalogu repozytorium.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
