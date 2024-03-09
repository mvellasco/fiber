FROM python:3.10-slim-buster

RUN apt update && apt install -y libev-dev build-essential

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-m", "fiber.wsgi"]
