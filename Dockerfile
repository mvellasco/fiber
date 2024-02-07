FROM pypy:3

RUN apt-get update && apt-get install -y --no-install-recommends \
                pypy-lib \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["gunicorn", "-b", "0.0.0.0:8000", "wsgi:application"]
