from pathlib import Path
from datetime import datetime
import time


class CrewLogger:

    def __init__(self, session_id=None):

        self.start = time.perf_counter()

        now = datetime.now()

        self.folder = Path("logs") / now.strftime("%Y-%m-%d")
        self.folder.mkdir(parents=True, exist_ok=True)

        self.file = self.folder / f"{now.strftime('%H-%M-%S')}.log"

        self.session_id = session_id

        self._write("=" * 90)
        self._write("CREW ASSISTANT AI")
        self._write("=" * 90)
        self._write(f"Data/Hora : {now:%d/%m/%Y %H:%M:%S}")

        if session_id:
            self._write(f"Sessão    : {session_id}")

        self._write("")

    def _write(self, text=""):

        with open(self.file, "a", encoding="utf-8") as f:
            f.write(text + "\n")

    def user(self, message):

        self._write("-" * 90)
        self._write("PERGUNTA")
        self._write("-" * 90)
        self._write(message)
        self._write()

    def agent(self, name, output):

        self._write("-" * 90)
        self._write(f"AGENTE : {name}")
        self._write("-" * 90)
        self._write(str(output))
        self._write()

    def info(self, text):

        self._write(text)

    def response(self, text):

        self._write("-" * 90)
        self._write("RESPOSTA FINAL")
        self._write("-" * 90)
        self._write(text)
        self._write()

    def finish(self):

        elapsed = time.perf_counter() - self.start

        self._write("-" * 90)
        self._write("ESTATÍSTICAS")
        self._write("-" * 90)
        self._write(f"Tempo total : {elapsed:.2f} segundos")
        self._write("=" * 90)