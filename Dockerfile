FROM python:3.12-slim

ARG WERSJA=0.3.0

# Czcionka Inter (licencja OFL) do rysowania ekranów.
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-inter tzdata \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/unraid-lcd
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

ENV LCD_KONFIGURACJA=/config \
    LCD_DEV=/dev-host \
    LCD_PROC=/host/proc \
    LCD_PORT_PANELU=8766 \
    LCD_WERSJA=${WERSJA} \
    PYTHONUNBUFFERED=1

EXPOSE 8765
VOLUME ["/config"]
CMD ["uvicorn", "app.serwer:app", "--host", "0.0.0.0", "--port", "8765", "--no-access-log"]
