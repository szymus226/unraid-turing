FROM python:3.12-slim

# Czcionka Inter (licencja OFL) do rysowania ekranów.
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-inter \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/unraid-lcd
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

ENV LCD_KONFIGURACJA=/config \
    LCD_DEV=/dev-host \
    LCD_PROC=/host/proc \
    PYTHONUNBUFFERED=1

EXPOSE 8765
VOLUME ["/config"]
CMD ["uvicorn", "app.serwer:app", "--host", "0.0.0.0", "--port", "8765", "--no-access-log"]
