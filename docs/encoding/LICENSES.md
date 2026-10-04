# Encoding model — licences of every asset (checked 2026-10-04)

The rule for this work: every dataset, stimulus and model must allow **commercial use** (CC0, PDDL, CC BY, CC BY-SA,
MIT, Apache-2.0, BSD, public domain), with **no signed agreement, registration or non-commercial clause**. Each entry
below was checked by hand at its source on the date above. The machine-readable list is
[`out/encoding/MANIFEST.json`](../../out/encoding/MANIFEST.json); `tests/test_sensory.py` checks that it covers every
file in `out/encoding/` and every model the server downloads (same commit, same sha256).

## Used

### fMRI data
| asset | licence | checked where | notes |
|---|---|---|---|
| **Emo-FilM** fMRI, OpenNeuro [ds004892](https://openneuro.org/datasets/ds004892) (Morgenroth et al. 2025, *Sci Data*) | **CC0** | `dataset_description.json` → `"License": "CC0"`; OpenNeuro's own terms (no data-use agreement, no login) | we use the authors' preprocessed BOLD in MNI (`derivatives/preprocessing/*_space-MNI_desc-ppres_bold.nii.gz`) for the three films below, 30 participants |
| **The Alice dataset**, OpenNeuro [ds002322](https://openneuro.org/datasets/ds002322) (Bhattasali et al. 2020, LREC) | **CC0** | `dataset_description.json` → `"License": "CC0"` | preprocessed BOLD in MNI (SPM8), `code/annotations.tsv` (word onsets), the stimulus audio. 23 runs preprocessed; one (sub-53) is truncated on OpenNeuro (gzip length error after two downloads), so 22 are used |

### Stimuli (the features are computed from them, so their own licence counts too)
| asset | licence | checked where | notes |
|---|---|---|---|
| **Big Buck Bunny** (Blender Foundation 2008) | **CC BY 3.0** | [peach.blender.org/about](https://peach.blender.org/about/); Emo-FilM's `code/FilmInfo.txt` | file: [BigBuckBunny_640x360.m4v](https://download.blender.org/peach/bigbuckbunny_movies/BigBuckBunny_640x360.m4v.zip). Attribution: © copyright 2008, Blender Foundation / www.bigbuckbunny.org |
| **Sintel** (Blender Foundation 2010) | **CC BY 3.0** | [durian.blender.org/sharing](https://durian.blender.org/sharing/); `FilmInfo.txt` | file: [Sintel.2010.720p.mkv](https://download.blender.org/durian/movies/Sintel.2010.720p.mkv.zip). Attribution: © copyright Blender Foundation / durian.blender.org |
| **Tears of Steel** (Blender Foundation 2012) | **CC BY 3.0** (the film) | [mango.blender.org/sharing](https://mango.blender.org/sharing/); `FilmInfo.txt` | file: [tears_of_steel_720p.mov](https://download.blender.org/demo/movies/ToS/tears_of_steel_720p.mov). Only the picture is used; the separate soundtrack files are CC BY-ND (`copyright.txt` there) and are not used. Attribution: (CC) Blender Foundation / mango.blender.org |
| Lewis Carroll, *Alice's Adventures in Wonderland* (1865), chapter 1 | **public domain** | [Project Gutenberg #11](https://www.gutenberg.org/ebooks/11) | the words the participants heard (onsets from the dataset) |
| LibriVox recording read by Kristen McQuillin ([LibriVox #200](https://librivox.org/alices-adventures-in-wonderland-by-lewis-carroll/)) | **public domain** | [LibriVox: copyright and public domain](https://wiki.librivox.org/index.php/Copyright_and_Public_Domain) | only its loudness envelope, as a nuisance regressor (the dataset spells the reader "McQuillan") |

The films' cut (start / end in each file) is the experiment's own sheet,
`code/BBL_experiment_Movies_without_credits_exp_files.xlsx`; the downloaded files have exactly the lengths listed
there (9:56, 14:48, 12:14).

### Atlas (our 214 regions, as `atlas_subject.py`)
| asset | licence | checked where | notes |
|---|---|---|---|
| Schaefer 2018, 200 parcels / 7 networks, FSL MNI152 2 mm | **MIT** | [CBIG LICENSE.md](https://github.com/ThomasYeoLab/CBIG/blob/master/LICENSE.md); nilearn's fetcher docstring ("License: MIT") | the 200 cortical regions |
| Harvard-Oxford subcortical, maxprob thr25 2 mm (FSL) | **CC BY-SA 4.0** | [FSL licence page](https://fsl.fmrib.ox.ac.uk/fsl/docs/license.html): "released under the CC BY-SA 4.0 licence" | the 14 deep nuclei. Older FSL releases (5.0) put the atlases under the FSL licence (non-commercial); the current terms are CC BY-SA 4.0. ShareAlike: our derived files (below) are CC BY-SA 4.0 too |

### Models
| asset | licence | checked where | notes |
|---|---|---|---|
| OpenCLIP ViT-B-32, LAION-2B s34B b79K | **MIT** | [model card](https://huggingface.co/laion/CLIP-ViT-B-32-laion2B-s34B-b79K) (`license: mit`) | upstream weights |
| its int8 ONNX export: [`onnx/model_int8.onnx` @ de693d0](https://huggingface.co/onnx-community/CLIP-ViT-B-32-laion2B-s34B-b79K-ONNX/resolve/de693d0c5a5b263ae94ece9bf751e0cda14305d8/onnx/model_int8.onnx) | **MIT** | repo card (`license: mit`) | sha256 `2ac8410f…aee9b`; the server downloads it once, cuts out the image tower (89 MB) and deletes the rest. The **same** file computed the training features |
| all-MiniLM-L6-v2, its own int8 ONNX: [`onnx/model_quint8_avx2.onnx` @ 1110a24](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/onnx/model_quint8_avx2.onnx) and [`tokenizer.json`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/tokenizer.json) | **Apache-2.0** | [model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) (`license: apache-2.0`) | sha256 `b941bf19…0fd21` / `be50c362…72037`; training features and runtime |

No Whisper / audio model is used (audio was optional; the films' sound and the story's voice are not encoded).
No torch is used anywhere: features, fits and runtime all run on onnxruntime + numpy.

### Software
| package | licence | where |
|---|---|---|
| [onnxruntime](https://github.com/microsoft/onnxruntime/blob/main/LICENSE) 1.30.0 | MIT | runtime |
| [onnx](https://github.com/onnx/onnx/blob/main/LICENSE) 1.23.1 | Apache-2.0 | runtime, once (cuts the image tower) |
| [tokenizers](https://github.com/huggingface/tokenizers/blob/main/LICENSE) 0.23.2 | Apache-2.0 | runtime |
| [nilearn](https://github.com/nilearn/nilearn/blob/main/LICENSE) 0.14 | BSD-3-Clause | training only (atlas fetch / resampling) |
| numpy, scipy, nibabel, Pillow, ffmpeg | BSD / MIT / HPND / LGPL | already in the project; ffmpeg only decodes the films offline |

### Ours
`out/encoding/vision.npz`, `text.npz`, `scores.json`, `cv_data.npz` are derived from the above and released as
**CC BY-SA 4.0** (ShareAlike because of the Harvard-Oxford atlas), with the attributions above; described in
[REPORT.md](https://github.com/nocontentinhere4-art/sub-01/blob/main/docs/encoding/REPORT.md).

## Considered and not used

| what | why not |
|---|---|
| **Meta's TRIBE / TRIBE v2** ([d'Ascoli et al. 2025, arXiv:2507.22229](https://arxiv.org/abs/2507.22229); code [facebookresearch/algonauts-2025](https://github.com/facebookresearch/algonauts-2025)) | **CC BY-NC**: never downloaded, run, copied, ported or distilled. Only the public paper was read, for the idea (pretrained text / image features + a learned map to fMRI). Our model is a plain ridge regression; it shares no code, weight or output with TRIBE |
| **Narratives** (OpenNeuro ds002345) | the fMRI is CC0, but `stimuli/README` says the story recordings are "intended for non-profit, **non-commercial** scholarship and research use under fair use": features from them would be non-commercial |
| Emo-FilM's other films | **NonCommercial** (per `code/FilmInfo.txt`): *After The Rain* (CC BY-NC-SA 3.0), *Chatter* (CC BY-NC 3.0), *Spaceman* (CC BY-NC 3.0), *The Secret Number* (CC BY-NC 3.0), *To Claire From Sonny* (CC BY-NC-SA 3.0). The other CC BY / BY-SA films (*Between Viewings, First Bite, Lesson Learned, Payload, Superhero, You Again*) are usable in principle but live on Vimeo, which serves no download without an account from here; the experiment's cut cannot be matched without the exact file |
| BOLD5000 (ds001499) | CC0 data, but its images come from ImageNet (non-commercial terms) and SUN (unclear); its COCO images carry per-image Flickr licences, many NonCommercial. Also only T1w / fsnative derivatives. Not used |
| Natural Scenes Dataset (NSD), HCP (movie data), CNeuroMod (Friends / movies) | signed data-use agreements / registration, and copyrighted stimuli |
| Le Petit Prince fMRI | the text and its recordings are not public domain everywhere (US copyright until 2039) |
| LIRIS-ACCEDE (the films' source collection) | download needs a signed agreement |
| OpenAI CLIP weights | MIT, but the model card restricts deployment ("out of scope"); the LAION-trained OpenCLIP weights carry no such note |
