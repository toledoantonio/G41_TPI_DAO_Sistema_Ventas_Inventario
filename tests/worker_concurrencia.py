"""Proceso aislado para verificar dos instancias de la aplicación contra SQLite."""

import json
import sys

from backend.patterns.estados_bulto import ErrorDominio
from backend.services.sistema import Sistema


if __name__ == "__main__":
    sistema = Sistema(sys.argv[1])
    print("LISTO", flush=True)
    if sys.stdin.readline().strip() != "VENDER":
        raise SystemExit("No se recibió la señal de venta.")
    try:
        sistema.registrar_venta(int(sys.argv[2]), [(int(sys.argv[3]), 6)], [("EFECTIVO", "900")])
        resultado = True
    except ErrorDominio:
        resultado = False
    print(json.dumps({"confirmada": resultado}), flush=True)
