"""
从 MP4 视频提取音频为 MP3
用法：python extract_audio.py <视频路径> [输出MP3路径]
"""
import sys
import os
import av
from av.audio.resampler import AudioResampler


def mp4_to_mp3(src, dst):
    inp = av.open(src)

    # 创建重采样器：输出 44100Hz / 16bit / 立体声
    resampler = AudioResampler(
        format="s16",
        layout="stereo",
        rate=44100,
    )

    out = av.open(dst, mode="w")
    out_stream = out.add_stream("libmp3lame", rate=44100)
    out_stream.options = {"b": "192k"}

    for frame in inp.decode(audio=0):
        for resampled in resampler.resample(frame):
            for packet in out_stream.encode(resampled):
                out.mux(packet)

    # flush encoder
    for packet in out_stream.encode():
        out.mux(packet)

    out.close()
    inp.close()
    print(f"✅ 已生成: {dst}  大小: {os.path.getsize(dst)//1024} KB")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python extract_audio.py <video.mp4> [output.mp3]")
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + ".mp3"
    mp4_to_mp3(src, dst)
