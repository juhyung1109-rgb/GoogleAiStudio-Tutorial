# To run this code you need to install the following dependencies:
# pip install google-genai

import mimetypes
import os
import re
import struct
from google import genai
from google.genai import types


def save_binary_file(file_name, data):
    f = open(file_name, "wb")
    f.write(data)
    f.close()
    print(f"File saved to to: {file_name}")


def generate():
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    model = "gemini-3.1-flash-tts-preview"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text="""Read the following transcript based on the audio profile.

# Audio Profile
warm

## Scene:
A professional TV news studio breaking a shocking tech industry announcement.

## Sample Context:
The news anchor is delivering an urgent breaking news report with a fast-paced, enthusiastic, and astonished tone about Google's disruptive pricing.

## Transcript:
[urgent] 속보입니다! 구글이 차세대 인공지능 모델, '제미나이 4.0 Pro'를 전격 공개했습니다. [excited] 그런데 성능보다 더 전 세계를 충격에 빠뜨린 건 바로 가격입니다. [amazed] 기존 모델 대비 무려 90% 이상 파격적으로 인하된, 그야말로 '역대급 헐값' 수준으로 책정되었다는 소식인데요! [confident] 업계에서는 AI 시장의 판도를 완전히 뒤흔들 게임 체인저가 등장했다며 술렁이고 있습니다."""),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        response_modalities=[
            "audio",
        ],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Kore"
                )
            )
        ),
    )

    audio_chunks = bytearray()
    mime_type = None

    print("음성 생성 중...")
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        if chunk.parts is None:
            continue
        if chunk.parts[0].inline_data and chunk.parts[0].inline_data.data:
            inline_data = chunk.parts[0].inline_data
            mime_type = inline_data.mime_type
            audio_chunks.extend(inline_data.data)
        else:
            if text := chunk.text:
                print(text)

    if audio_chunks and mime_type:
        output_file = "output.wav"
        wav_data = convert_to_wav(bytes(audio_chunks), mime_type)
        save_binary_file(output_file, wav_data)
        print(f"완성된 음성 파일이 저장되었습니다: {output_file}")

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


if __name__ == "__main__":
    generate()


