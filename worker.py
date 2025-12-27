from rq import Worker

from app import create_app
from app.queue import get_queue


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        queue = get_queue(for_worker=True)
        worker = Worker([queue], connection=queue.connection)
        worker.work()
