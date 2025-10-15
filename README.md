# Podcast Generator Service

A simple Docker service that converts text scripts into podcast audio using Google's Gemini TTS API. The service expects scripts with `david:` and `janis:` speakers and generates realistic multi-speaker audio.

## Features

- RESTful API for script-to-audio conversion
- Multi-speaker support (David and Janis voices)
- Docker containerization for easy deployment
- Health check endpoints
- Example script format

## Prerequisites

- Docker and Docker Compose
- Google Gemini API key

## Setup

1. **Get a Gemini API Key**
   - Visit [Google AI Studio](https://aistudio.google.com/)
   - Create an API key for Gemini

2. **Configure Environment**
   ```bash
   cp env.example .env
   # Edit .env and add your actual API key
   ```

3. **Build and Run with Docker Compose**
   ```bash
   docker-compose up --build
   ```

4. **Or Build and Run with Docker**
   ```bash
   docker build -t podcast-generator .
   docker run -p 5000:5000 -e GEMINI_API_KEY=your_api_key_here podcast-generator
   ```

## API Usage

### Health Check
```bash
curl http://localhost:8080/
```

### Generate Podcast
```bash
curl -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "script": "david: Hello! Welcome to our podcast.\njanis: Thanks for having me, David!"
  }' \
  --output podcast.wav
```

### Get Example Script
```bash
curl http://localhost:8080/example
```

## Script Format

Scripts must follow this format with `david:` and `janis:` speakers:

```
david: Hello! Welcome to our podcast. Today we're going to discuss some exciting topics.
janis: That's right, David. We have a lot of interesting content planned for our listeners.
david: So Janis, what's the first topic you'd like to cover today?
janis: Well, I think we should start with the basics of our service and how it works.
```

## API Endpoints

- `GET /` - Health check
- `POST /generate` - Generate podcast audio from script
- `GET /example` - Get example script format

## Response Format

### Success (200)
Returns a WAV audio file as download.

### Error (400/500)
```json
{
  "error": "Error message describing what went wrong"
}
```

## Docker Commands

```bash
# Build the image
docker build -t podcast-generator .

# Run the container
docker run -p 8080:5000 -e GEMINI_API_KEY=your_key podcast-generator

# Run with docker-compose
docker-compose up

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

## Development

To run locally without Docker:

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_api_key
python app.py
```

## Notes

- The service uses Google's Gemini 2.5 Pro TTS model
- David uses the "Zephyr" voice
- Janis uses the "Puck" voice
- Generated audio is in WAV format
- The service automatically cleans up temporary files
