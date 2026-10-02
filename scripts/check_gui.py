"""Manual GUI smoke test: main.py, real worker, heartbeat and actual exports."""
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gui.main_window import MainWindow
from tkinter import filedialog

original_mainloop = MainWindow.mainloop
failures = []


def smoke_mainloop(window):
    ticks = [0]
    def heartbeat():
        if window.busy:
            ticks[0] += 1
        if not window.closed:
            window.after(100, heartbeat)

    def verify():
        if window.busy:
            window.after(200, verify)
            return
        try:
            assert window.report, 'Relatório não gerado'
            assert ticks[0] >= 3, 'Heartbeat insuficiente durante consultas'
            assert window.analyze_button.cget('state') == 'normal'
            assert 'DADOS SIMULADOS' not in window.report
            directory = ROOT / 'manual_results'
            directory.mkdir(exist_ok=True)
            dialog = filedialog.asksaveasfilename
            try:
                for suffix in ('.txt', '.md'):
                    path = directory / ('gui_briefing' + suffix)
                    filedialog.asksaveasfilename = lambda **kwargs: str(path)
                    window.save_report()
                    assert 'BRIEFING METEOROLÓGICO' in path.read_text(encoding='utf-8')
            finally:
                filedialog.asksaveasfilename = dialog
            print(f'GUI main.py: OK; relatório real: OK; heartbeat={ticks[0]}; salvar TXT/Markdown: OK', flush=True)
        except Exception as exc:
            failures.append(str(exc))
        finally:
            window.close()

    def callback_error(exc_type, exc_value, traceback):
        failures.append(f'{exc_type.__name__}: {exc_value}')
        window.close()

    def timeout():
        failures.append('Timeout na verificação da GUI')
        window.close()

    window.report_callback_exception = callback_error
    window.route.delete('1.0', 'end')
    window.route.insert('1.0', 'SBSP DCT SBGR')
    window.after(100, heartbeat)
    window.after(300, window.analyze)
    window.after(600, verify)
    window.after(120000, timeout)
    original_mainloop(window)


if __name__ == '__main__':
    MainWindow.mainloop = smoke_mainloop
    runpy.run_path(str(ROOT / 'main.py'), run_name='__main__')
    if failures:
        print('Falhas:', failures)
        raise SystemExit(1)
