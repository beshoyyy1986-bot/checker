FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# libatomic1: node driver بتاع Playwright نفسه محتاج libatomic.so.1
# وصور python:3.11-slim الحديثة مش بتيجي فيها — من غير السطر ده البناء
# بيقفل بـ: error while loading shared libraries: libatomic.so.1
RUN apt-get update \
    && apt-get install -y --no-install-recommends libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# تثبيت متصفح Chromium + مكتبات النظام المطلوبة لـ Playwright
# (ده اللي بياخد سكرين شوت حقيقي لصفحة الـ OTP فى بوابة Kashier)
RUN python -m playwright install --with-deps chromium

COPY . .

# مجلد البيانات الدائم (لو اربط Volume على /data)
RUN mkdir -p /data

CMD ["python", "-u", "bot.py"]
