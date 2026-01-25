
FROM python:3.11-slim

WORKDIR /code

# Install system dependencies if needed (e.g. for some python packages)
# RUN apt-get update && apt-get install -y gcc

# Copy requirements first to leverage Docker cache
COPY ./requirements.txt /code/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy the rest of the application
COPY ./app /code/app

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
