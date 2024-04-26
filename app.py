import os
import torch
import argparse
import gradio as gr
import sys
#from zipfile import ZipFile
from melo.api import TTS

# Init EN/ZH baseTTS and ToneConvertor
from OpenVoice import se_extractor
from OpenVoice.api import ToneColorConverter
import devicetorch
device = devicetorch.get(torch)
ckpt_converter = 'checkpoints/converter'
tone_color_converter = ToneColorConverter(f'{ckpt_converter}/config.json', device=device)
tone_color_converter.load_ckpt(f'{ckpt_converter}/checkpoint.pth')


#languages = ["EN_NEWEST", "EN", "ES", "FR", "ZH", "JP", "KR"]
en = ["EN-Default", "EN-US", "EN-BR", "EN_INDIA", "EN-AU"]

LANG = sys.argv[1].strip()
print(f"LANG={LANG}")


#def predict(prompt, style, audio_file_pth, mic_file_path, use_mic, language):
def predict(prompt, audio_file_pth, mic_file_path, use_mic, language, speed):
    # initialize a empty info
    text_hint = ''

    print(f"language = {language}")
    lang_code = language
#    lang_code = language
    if language.startswith("EN"):
       lang_code = "EN"
    tts_model = TTS(language=lang_code, device=device)

    speaker_key = language.lower().replace('_', '-')
    source_se = torch.load(f'checkpoints/base_speakers/ses/{speaker_key}.pth', map_location=device)

    if use_mic == True:
        if mic_file_path is not None:
            speaker_wav = mic_file_path
        else:
            text_hint += f"[ERROR] Please record your voice with Microphone, or uncheck Use Microphone to use reference audios\n"
            gr.Warning(
                "Please record your voice with Microphone, or uncheck Use Microphone to use reference audios"
            )
            return (
                text_hint,
                None,
                None,
            )

    else:
        speaker_wav = audio_file_pth

    if len(prompt) < 2:
        text_hint += f"[ERROR] Please give a longer prompt text \n"
        gr.Warning("Please give a longer prompt text")
        return (
            text_hint,
            None,
            None,
        )
    
    # note diffusion_conditioning not used on hifigan (default mode), it will be empty but need to pass it to model.inference
    try:
        target_se, wavs_folder = se_extractor.get_se(speaker_wav, tone_color_converter, target_dir='processed', max_length=60., vad=True)
        # os.system(f'rm -rf {wavs_folder}')
    except Exception as e:
        text_hint += f"[ERROR] Get target tone color error {str(e)} \n"
        gr.Warning(
            "[ERROR] Get target tone color error {str(e)} \n"
        )
        return (
            text_hint,
            None,
            None,
        )

    output_dir = os.path.abspath("output")
    src_path = f'{output_dir}/tmp.wav'

    #speed = 1.0
    print(f"speed = {speed}")

    #tts_model.tts_to_file(prompt, speaker_id, src_path, speaker=style, language=language)
    speaker_ids = tts_model.hps.data.spk2id
    print(f"Speaker_ids= {speaker_ids}, language={language}, speaker_key={speaker_key}")
    speaker_id = speaker_ids[language]

    tts_model.tts_to_file(prompt, speaker_id, src_path, speed=speed)

    save_path = f'{output_dir}/output.wav'
    # Run the tone color converter
    encode_message = "@MyShell"
    tone_color_converter.convert(
        audio_src_path=src_path, 
        src_se=source_se, 
        tgt_se=target_se, 
        output_path=save_path,
        message=encode_message)

    text_hint += f'''Get response successfully \n'''

    return (
        text_hint,
        save_path,
        speaker_wav,
    )


examples = [
    [
        "今天天气真好，我们一起出去吃饭吧。",
#        'default',
        "examples/speaker0.mp3",
        None,
        False,
        "ZH",
    ],
    [
        "お前はもう死んでいる",
#        'default',
        "examples/speaker0.mp3",
        None,
        False,
        "JP",
    ],
    [
        "오빤 강남 스타일",
#        'default',
        "examples/speaker0.mp3",
        None,
        False,
        "KR",
    ],
    [
        "This audio is generated by open voice with a half-performance model.",
#        'whispering',
        "examples/speaker1.mp3",
        None,
        False,
        "EN-BR"
    ],
    [
        "He hoped there would be stew for dinner, turnips and carrots and bruised potatoes and fat mutton pieces to be ladled out in thick, peppered, flour-fattened sauce.",
#        'sad',
        "examples/speaker2.mp3",
        None,
        False,
        "EN-BR"
    ],
]

with gr.Blocks(analytics_enabled=False) as demo:

#    with gr.Row():
#        gr.HTML(wrapped_markdown_content)

    with gr.Row():
        with gr.Column():
            input_text_gr = gr.Textbox(
                label="Text Prompt",
                info="One or two sentences at a time is better. Up to 200 text characters.",
                value="He hoped there would be stew for dinner, turnips and carrots and bruised potatoes and fat mutton pieces to be ladled out in thick, peppered, flour-fattened sauce.",
            )
            #style_gr = gr.Dropdown(
            #    label="Style",
            #    info="Select a style of output audio for the synthesised speech. (Chinese only support 'default' now)",
            #    choices=['default', 'whispering', 'cheerful', 'terrified', 'angry', 'sad', 'friendly'],
            #    max_choices=1,
            #    value="default",
            #)
            ref_gr = gr.Audio(
                label="Reference Audio",
                info="Click on the ✎ button to upload your own target speaker audio",
                type="filepath",
                value="examples/speaker0.mp3",
            )
            mic_gr = gr.Audio(
                source="microphone",
                type="filepath",
                info="Use your microphone to record audio",
                label="Use Microphone for Reference",
            )
            use_mic_gr = gr.Checkbox(
                label="Use Microphone",
                value=False,
                info="Notice: Microphone input may not work properly under traffic",
            )
            speed = gr.Slider(
                label="Speed",
                minimum=0.1,
                maximum=3.0,
                value=1.0,
            )
            #language = gr.Radio(['EN-Newest', 'EN-US', 'EN-BR', 'EN_INDIA', 'EN-AU', 'EN-Default', 'ES', 'FR', 'ZH', 'JP', 'KR'], label='Language', value='EN-Newest')
            if LANG.startswith("EN"):
                language = gr.Radio(['EN-US', 'EN-BR', 'EN_INDIA', 'EN-AU', 'EN-Default'], label='Language', value='EN-Default')
            else:
                language = gr.Radio([LANG], value=LANG, visible=False)

            tts_button = gr.Button("Send", elem_id="send-btn", visible=True)


        with gr.Column():
            out_text_gr = gr.Text(label="Info")
            audio_gr = gr.Audio(label="Synthesised Audio", autoplay=True)
            ref_audio_gr = gr.Audio(label="Reference Audio Used")

#            gr.Examples(examples,
#                        label="Examples",
#                        #inputs=[input_text_gr, style_gr, ref_gr, mic_gr, use_mic_gr, language],
#                        inputs=[input_text_gr, ref_gr, mic_gr, use_mic_gr, language],
#                        outputs=[out_text_gr, audio_gr, ref_audio_gr],
#                        fn=predict,
#                        cache_examples=False,)
            #tts_button.click(predict, [input_text_gr, style_gr, ref_gr, mic_gr, use_mic_gr, language], outputs=[out_text_gr, audio_gr, ref_audio_gr])
            tts_button.click(predict, [input_text_gr, ref_gr, mic_gr, use_mic_gr, language, speed], outputs=[out_text_gr, audio_gr, ref_audio_gr])

demo.queue()  
demo.launch(debug=True, show_api=True)
