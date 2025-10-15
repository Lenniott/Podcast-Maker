#!/usr/bin/env python3
"""
Podcast Generator Service

A simple Flask web service that takes a script with david: and janis: speakers
and generates podcast audio using Google's Gemini TTS API.
"""

import base64
import mimetypes
import os
import re
import struct
from flask import Flask, request, jsonify, send_file
from google import genai
from google.genai import types
import tempfile
import uuid

app = Flask(__name__)

def save_binary_file(file_name, data):
    """Save binary data to file"""
    with open(file_name, "wb") as f:
        f.write(data)
    print(f"File saved to: {file_name}")

def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Generates a WAV file header for the given audio data and parameters.

    Args:
        audio_data: The raw audio data as a bytes object.
        mime_type: Mime type of the audio data.

    Returns:
        A bytes object representing the WAV file header.
    """
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size  # 36 bytes for header fields before data chunk size

    # http://soundfile.sapp.org/doc/WaveFormat/
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",          # ChunkID
        chunk_size,       # ChunkSize (total file size - 8 bytes)
        b"WAVE",          # Format
        b"fmt ",          # Subchunk1ID
        16,               # Subchunk1Size (16 for PCM)
        1,                # AudioFormat (1 for PCM)
        num_channels,     # NumChannels
        sample_rate,      # SampleRate
        byte_rate,        # ByteRate
        block_align,      # BlockAlign
        bits_per_sample,  # BitsPerSample
        b"data",          # Subchunk2ID
        data_size         # Subchunk2Size (size of audio data)
    )
    return header + audio_data

def parse_audio_mime_type(mime_type: str) -> dict[str, int | None]:
    """Parses bits per sample and rate from an audio MIME type string.

    Assumes bits per sample is encoded like "L16" and rate as "rate=xxxxx".

    Args:
        mime_type: The audio MIME type string (e.g., "audio/L16;rate=24000").

    Returns:
        A dictionary with "bits_per_sample" and "rate" keys. Values will be
        integers if found, otherwise None.
    """
    bits_per_sample = 16
    rate = 24000

    # Extract rate from parameters
    parts = mime_type.split(";")
    for param in parts: # Skip the main type part
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate_str = param.split("=", 1)[1]
                rate = int(rate_str)
            except (ValueError, IndexError):
                # Handle cases like "rate=" with no value or non-integer value
                pass # Keep rate as default
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass # Keep bits_per_sample as default if conversion fails

    return {"bits_per_sample": bits_per_sample, "rate": rate}

def generate_podcast_audio(script_text: str):
    """Generate podcast audio from script text"""
    
    # Validate API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required")
    
    client = genai.Client(api_key=api_key)
    
    model = "gemini-2.5-flash-preview-tts"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=f"Read aloud in a warm, welcoming tone:\n{script_text}"),
            ],
        ),
    ]
    
    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        response_modalities=["audio"],
        speech_config=types.SpeechConfig(
            multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                speaker_voice_configs=[
                    types.SpeakerVoiceConfig(
                        speaker="david",
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name="Zephyr"
                            )
                        ),
                    ),
                    types.SpeakerVoiceConfig(
                        speaker="janis",
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name="Puck"
                            )
                        ),
                    ),
                ]
            ),
        ),
    )

    # Create temporary file to store audio
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
    temp_file.close()
    
    audio_data = bytearray()
    
    try:
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if (
                chunk.candidates is None
                or chunk.candidates[0].content is None
                or chunk.candidates[0].content.parts is None
            ):
                continue
                
            if (chunk.candidates[0].content.parts[0].inline_data and 
                chunk.candidates[0].content.parts[0].inline_data.data):
                
                inline_data = chunk.candidates[0].content.parts[0].inline_data
                data_buffer = inline_data.data
                file_extension = mimetypes.guess_extension(inline_data.mime_type)
                
                if file_extension is None:
                    file_extension = ".wav"
                    data_buffer = convert_to_wav(inline_data.data, inline_data.mime_type)
                
                # Append audio data
                audio_data.extend(data_buffer)
        
        # Write all audio data to file
        with open(temp_file.name, 'wb') as f:
            f.write(audio_data)
            
        return temp_file.name
        
    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
        raise e

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "podcast-generator"})

@app.route('/generate', methods=['POST'])
def generate_podcast():
    """Generate podcast audio from script"""
    try:
        data = request.get_json()
        
        if not data or 'script' not in data:
            return jsonify({"error": "Script text is required"}), 400
        
        script_text = data['script']
        
        if not script_text.strip():
            return jsonify({"error": "Script cannot be empty"}), 400
        
        # Validate that script contains david: and janis: speakers
        if 'david:' not in script_text.lower() or 'janis:' not in script_text.lower():
            return jsonify({
                "error": "Script must contain both 'david:' and 'janis:' speakers"
            }), 400
        
        # Generate audio
        audio_file_path = generate_podcast_audio(script_text)
        
        # Send the audio file and clean up after response
        def remove_file(response):
            try:
                if os.path.exists(audio_file_path):
                    os.unlink(audio_file_path)
            except:
                pass
            return response
        
        response = send_file(
            audio_file_path,
            as_attachment=True,
            download_name=f'podcast_{uuid.uuid4().hex[:8]}.wav',
            mimetype='audio/wav'
        )
        
        # Register cleanup callback
        response.call_on_close(lambda: remove_file(response))
        return response
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        # Clean up temp file on error
        if 'audio_file_path' in locals() and os.path.exists(audio_file_path):
            try:
                os.unlink(audio_file_path)
            except:
                pass
        return jsonify({"error": f"Failed to generate podcast: {str(e)}"}), 500

@app.route('/example', methods=['GET'])
def get_example():
    """Get example script format"""
    example_script = """david: Hello! Welcome to our podcast. Today we're going to discuss some exciting topics.
janis: That's right, David. We have a lot of interesting content planned for our listeners.
david: So Janis, what's the first topic you'd like to cover today?
janis: Well, I think we should start with the basics of our service and how it works."""
    
    return jsonify({
        "example_script": example_script,
        "format": "Each line should start with 'david:' or 'janis:' followed by the text for that speaker"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
