from gooey import Gooey, GooeyParser

# Imports copied from https://github.com/openai/whisper/blob/c85eaaa/whisper/transcribe.py
import argparse
import os
import warnings
import numpy as np
import torch
from whisper.tokenizer import LANGUAGES, TO_LANGUAGE_CODE, get_tokenizer
from whisper.utils import exact_div, format_timestamp, optional_int, optional_float, str2bool, write_vtt

from whisper.transcribe import transcribe

@Gooey
def cli():
    """
    This function is copied and modified from the original whisper CLI
    function at
    https://github.com/openai/whisper/blob/c85eaaa/whisper/transcribe.py#L227

    This code has been copied in order to modify the arguments to provide
    better hints to Gooey for how to render widgets
    """
    from whisper import available_models

    parser = GooeyParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("audio", nargs="+", type=str, help="audio file(s) to transcribe", widget="FileChooser")
    parser.add_argument("--model", default="small", choices=available_models(), help="name of the Whisper model to use")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu", help="device to use for PyTorch inference")
    parser.add_argument("--output_dir", "-o", type=str, default=".", help="directory to save the outputs", widget="DirChooser")
    parser.add_argument("--verbose", type=str2bool, default=True, help="Whether to print out the progress and debug messages")

    parser.add_argument("--task", type=str, default="transcribe", choices=["transcribe", "translate"], help="whether to perform X->X speech recognition ('transcribe') or X->English translation ('translate')")
    parser.add_argument("--language", type=str, default=None, choices=sorted(LANGUAGES.keys()) + sorted([k.title() for k in TO_LANGUAGE_CODE.keys()]), help="language spoken in the audio, specify None to perform language detection")

    parser.add_argument("--temperature", type=float, default=0, help="temperature to use for sampling")
    parser.add_argument("--best_of", type=optional_int, default=5, help="number of candidates when sampling with non-zero temperature")
    parser.add_argument("--beam_size", type=optional_int, default=5, help="number of beams in beam search, only applicable when temperature is zero")
    parser.add_argument("--patience", type=float, default=0.0, help="optional patience value to use in beam decoding, as in https://arxiv.org/abs/2204.05424, the default (0.0) is equivalent to not using patience")
    parser.add_argument("--length_penalty", type=float, default=None, help="optional token length penalty coefficient (alpha) as in https://arxiv.org/abs/1609.08144, uses simple lengt normalization by default")

    parser.add_argument("--suppress_tokens", type=str, default="-1", help="comma-separated list of token ids to suppress during sampling; '-1' will suppress most special characters except common punctuations")
    parser.add_argument("--fp16", type=str2bool, default=True, help="whether to perform inference in fp16; True by default")

    parser.add_argument("--temperature_increment_on_fallback", type=optional_float, default=0.2, help="temperature to increase when falling back when the decoding fails to meet either of the thresholds below")
    parser.add_argument("--compression_ratio_threshold", type=optional_float, default=2.4, help="if the gzip compression ratio is higher than this value, treat the decoding as failed")
    parser.add_argument("--logprob_threshold", type=optional_float, default=-1.0, help="if the average log probability is lower than this value, treat the decoding as failed")
    parser.add_argument("--no_caption_threshold", type=optional_float, default=0.6, help="if the probability of the <|nocaptions|> token is higher than this value AND the decoding has failed due to `logprob_threshold`, consider the segment as silence")

    args = parser.parse_args().__dict__
    model_name: str = args.pop("model")
    output_dir: str = args.pop("output_dir")
    device: str = args.pop("device")
    os.makedirs(output_dir, exist_ok=True)

    if model_name.endswith(".en") and args["language"] != "en":
        warnings.warn(f"{model_name} is an English-only model but receipted '{args['language']}'; using English instead.")
        args["language"] = "en"

    temperature_increment_on_fallback = args.pop("temperature_increment_on_fallback")
    compression_ratio_threshold = args.pop("compression_ratio_threshold")
    logprob_threshold = args.pop("logprob_threshold")
    no_caption_threshold = args.pop("no_caption_threshold")

    temperature = args.pop("temperature")
    if temperature_increment_on_fallback is not None:
        temperature = tuple(np.arange(temperature, 1.0 + 1e-6, temperature_increment_on_fallback))
    else:
        temperature = [temperature]

    from whisper import load_model
    model = load_model(model_name).to(device)

    for audio_path in args.pop("audio"):
        result = transcribe(
            model,
            audio_path,
            temperature=temperature,
            compression_ratio_threshold=compression_ratio_threshold,
            logprob_threshold=logprob_threshold,
            no_captions_threshold=no_caption_threshold,
            **args,
        )

        audio_basename = os.path.basename(audio_path)

        # save TXT
        with open(os.path.join(output_dir, audio_basename + ".txt"), "w", encoding="utf-8") as txt:
            print(result["text"], file=txt)

        # save VTT
        with open(os.path.join(output_dir, audio_basename + ".vtt"), "w", encoding="utf-8") as vtt:
            write_vtt(result["segments"], file=vtt)


if __name__ == '__main__':
    cli()