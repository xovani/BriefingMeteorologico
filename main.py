import logging
import argparse
from pathlib import Path

import customtkinter as ctk

from gui.main_window import MainWindow
from utils.logger import configure_logging


def main() -> None:
    configure_logging()
    logging.getLogger(__name__).info("Início do programa — briefing com fontes reais")
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    parser = argparse.ArgumentParser(description="Briefing meteorológico educacional")
    parser.add_argument("--verificar-exe", type=Path, help="Verificação automatizada do pacote; grava diagnóstico JSON no caminho indicado")
    args = parser.parse_args()
    if args.verificar_exe:
        from utils.executable_check import verify_executable
        verify_executable(args.verificar_exe)
    else:
        MainWindow().mainloop()


if __name__ == "__main__":
    main()
