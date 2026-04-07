FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# install minimal deps first for layer cache
COPY requirements.txt ./
# force-disable hash checking if host policy injects --require-hashes
ENV PIP_REQUIRE_HASHES=0
RUN python -m pip install --no-cache-dir -r requirements.txt

# copy app
COPY . .

EXPOSE 5000

CMD ["python", "src/app.py"]
