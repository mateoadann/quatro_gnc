from rq import SimpleWorker

from app import create_app
from app.queue import get_queue


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        queue = get_queue(for_worker=True)
        # SimpleWorker evita el fork por job y permite reutilizar la sesion de Playwright.
        worker = SimpleWorker([queue], connection=queue.connection)
        worker.work()
