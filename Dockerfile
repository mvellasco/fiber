FROM pypy:3.10-7.3.15-bookworm

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["gunicorn", "-b", "0.0.0.0:8000", "wsgi:application", "-w", "1"]
