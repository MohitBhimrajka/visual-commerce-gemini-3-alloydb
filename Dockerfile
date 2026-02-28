FROM python:3.12-slim

WORKDIR /app

# Copy everything
COPY . .

# Install all dependencies in one layer
RUN pip install --no-cache-dir \
    -r agents/vision-agent/requirements.txt \
    -r agents/supplier-agent/requirements.txt \
    -r frontend/requirements.txt \
    google-genai

EXPOSE 8080

CMD ["sh", "deploy/start.sh"]
