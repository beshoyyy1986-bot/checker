FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright: لازم نشغّل المتصفح نفسه + مكتبات النظام (fonts/libs)
# جواها الـ image، لإن مكتبة playwright البايثون لوحدها مش بتجيب Chromium.
# من غير السطر ده bot.py هيفشل بـ:
#   BrowserType.launch: Executable doesn't exist at /root/.cache/ms-playwright/...
#
# libatomic1: node driver بتاع playwright نفسه محتاج libatomic.so.1
# وصور python:3.11-slim الحديثة بقت مش بتيجي فيها — من غير السطر ده
# البناء بيقفل بـ:
#   error while loading shared libraries: libatomic.so.1: cannot open shared object file
#   Build Failed: process "/bin/sh -c playwright install --with-deps chromium" ... exit code: 127
RUN apt-get update \
    && apt-get install -y --no-install-recommends libatomic1 \
    && rm -rf /var/lib/apt/lists/*

RUN playwright install --with-deps chromium

COPY . .

# مجلد البيانات الدائم (لو اربط Volume على /data)
RUN mkdir -p /data

CMD ["python", "bot.py"]
