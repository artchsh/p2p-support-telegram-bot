# Use Python image
FROM python:3.13

# Set the working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot files
COPY . .

# Link to the github repository
LABEL org.opencontainers.image.source https://github.com/artchsh/p2p-support-telegram-bot

# Run the bot
CMD ["python", "bot.py"]
