FROM python:3.9.2-slim-buster as builder
WORKDIR /app

COPY . /app
RUN pip install --upgrade pip
RUN pip install --no-cache-dir --progress-bar off .

FROM gcr.io/distroless/python3:nonroot

COPY --from=builder /app /app
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin/eth-validator-watcher /usr/local/bin/eth-validator-watcher

ENV PYTHONPATH=/usr/local/lib/python3.9/site-packages

ENTRYPOINT [ "python", "/usr/local/bin/eth-validator-watcher" ] 
