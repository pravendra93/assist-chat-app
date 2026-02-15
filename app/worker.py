from app.core.celery_app import celery_app
import app.tasks.background # Ensure tasks are registered

if __name__ == "__main__":
    celery_app.start()
