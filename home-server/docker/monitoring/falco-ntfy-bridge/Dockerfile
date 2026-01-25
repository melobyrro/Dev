FROM python:3.11-slim
WORKDIR /app
RUN apt-get update &&     apt-get install -y --no-install-recommends curl &&     apt-get clean &&     rm -rf /var/lib/apt/lists/* &&     pip install flask requests
COPY app.py /app/
EXPOSE 5001
CMD ["python", "app.py"]
