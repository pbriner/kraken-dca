FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 krakenuser && \
    chown -R krakenuser:krakenuser /app

# Copy application files
COPY main.py /app/
COPY config.json /app/

# Set ownership
RUN chown krakenuser:krakenuser /app/main.py /app/config.json

# Switch to non-root user
USER krakenuser

# Make main.py executable
RUN chmod +x /app/main.py

# Run application
CMD ["python3", "-u", "/app/main.py"]
