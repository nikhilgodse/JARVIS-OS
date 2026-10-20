# JARVIS OS - Reference Papers

Five verified academic papers that ground this project's design. Each entry
gives the full citation, a BibTeX block, links, a short summary, and exactly
where it connects to JARVIS OS. Every detail here was checked against arXiv,
PMLR and Crossref on 2026-10-19; the links are included so your guide can
verify each one independently.

These are the papers to use in the Literature Review and System Design
chapters of your report.

## Which paper supports which part of the project

| # | Paper | Project area it supports |
|---|-------|--------------------------|
| 1 | JARVIS-1 | The assistant concept itself: memory + planning + acting |
| 2 | ReAct | How an LLM and tools work together (the routing model) |
| 3 | LLM Agent Survey | The architectural framework: profile, memory, planning, action |
| 4 | Whisper | Speech recognition (the voice input pipeline) |
| 5 | GPTQ | Quantization: how a 7B model fits in 6 GB of VRAM |

---

## 1. JARVIS-1: Open-World Multi-task Agents with Memory-Augmented Multimodal Language Models

**Citation (IEEE style):** Z. Wang, S. Cai, A. Liu, Y. Jin, J. Hou,
B. Zhang, H. Lin, Z. He, Z. Zheng, Y. Yang, X. Ma, and Y. Liang, "JARVIS-1:
Open-world multi-task agents with memory-augmented multimodal language
models," arXiv:2311.05997, Nov. 2023, doi: 10.48550/arXiv.2311.05997.

**BibTeX:**

```bibtex
@article{wang2023jarvis1,
  title={JARVIS-1: Open-World Multi-task Agents with Memory-Augmented Multimodal Language Models},
  author={Wang, Zihao and Cai, Shaofei and Liu, Anji and Jin, Yonggang and Hou, Jinbing and Zhang, Bowei and Lin, Haowei and He, Zhaofeng and Zheng, Zilong and Yang, Yaodong and Ma, Xiaojian and Liang, Yitao},
  journal={arXiv preprint arXiv:2311.05997},
  year={2023},
  doi={10.48550/arXiv.2311.05997}
}
```

**Links:** https://arxiv.org/abs/2311.05997

**What it is:** The most complete academic "JARVIS-style" assistant built on
a language model. It perceives input, generates plans with a multimodal
language model, stores experiences in memory, and executes actions through
controllers in an open world (Minecraft). It is a research agent, not a
desktop assistant, but its loop (perceive, plan, remember, act) is the same
loop JARVIS OS implements at a smaller scale.

**How it connects to JARVIS OS:**

- Memory-augmented planning maps to the notes skill plus the bounded
  conversation history in `jarvis/modules/chat.py`.
- The plan-then-dispatch structure maps to `Router.run()` deciding between
  commands, 11 skills, and the LLM in `jarvis/main.py`.
- The paper supports the project's core claim: an LLM is useful as a
  planner and communicator, while execution stays in deterministic,
  verifiable tools.

**Where to cite it:** Introduction (motivation for a personal
JARVIS-style assistant) and System Design (the perceive/plan/act loop).

---

## 2. ReAct: Synergizing Reasoning and Acting in Language Models

**Citation (IEEE style):** S. Yao, J. Zhao, D. Yu, N. Du, I. Shafran,
K. Narasimhan, and Y. Cao, "ReAct: Synergizing reasoning and acting in
language models," in Proc. 11th Int. Conf. Learning Representations (ICLR),
Kigali, Rwanda, 2023. arXiv:2210.03629.

**BibTeX:**

```bibtex
@inproceedings{yao2023react,
  title={ReAct: Synergizing Reasoning and Acting in Language Models},
  author={Yao, Shunyu and Zhao, Jeffrey and Yu, Dian and Du, Nan and Shafran, Izhak and Narasimhan, Karthik and Cao, Yuan},
  booktitle={International Conference on Learning Representations (ICLR)},
  year={2023}
}
```

**Links:** https://arxiv.org/abs/2210.03629 (ICLR 2023 camera-ready)

**What it is:** The paper that showed language models work best when
reasoning and acting are interleaved: the model thinks, calls a tool, reads
the result, and continues. Instead of hallucinating answers, it grounds
itself by interacting with external systems (the paper uses a Wikipedia
API). ReAct is the conceptual ancestor of modern tool-using assistants.

**How it connects to JARVIS OS:**

- The routing pipeline is a ReAct-style split: the LLM interprets and
  communicates, while real effects happen only through declared skills
  (`jarvis/skills/`) that return real results.
- The design rule "the LLM never executes shell code directly, actions go
  through tools with results" comes straight from this line of work.
- Grounding-by-tool-call maps to the weather, websearch and wikipedia
  skills fetching real data instead of letting the model guess.

**Where to cite it:** System Design (why skills are separate from the
model) and Safety (why the model cannot bypass execution guards).

---

## 3. A Survey on Large Language Model based Autonomous Agents

**Citation (IEEE style):** L. Wang, C. Ma, X. Feng, Z. Zhang, H. Yang,
J. Zhang, Z. Chen, J. Tang, X. Chen, Y. Lin, W. X. Zhao, Z. Wei, and
J.-R. Wen, "A survey on large language model based autonomous agents,"
Frontiers of Computer Science, vol. 18, no. 6, 2024, doi:
10.1007/s11704-024-40231-1.

**BibTeX:**

```bibtex
@article{wang2024survey,
  title={A survey on large language model based autonomous agents},
  author={Wang, Lei and Ma, Chen and Feng, Xueyang and Zhang, Zeyu and Yang, Hao and Zhang, Jingsen and Chen, Zhiyuan and Tang, Jiakai and Chen, Xu and Lin, Yankai and Zhao, Wayne Xin and Wei, Zhewei and Wen, Ji-Rong},
  journal={Frontiers of Computer Science},
  volume={18},
  number={6},
  year={2024},
  doi={10.1007/s11704-024-40231-1}
}
```

**Links:** https://doi.org/10.1007/s11704-024-40231-1 and
https://arxiv.org/abs/2308.11432

**What it is:** A widely used survey that proposes a unified framework for
LLM-based agents with four building blocks: profile (who the agent is),
memory (what it remembers), planning (how it decides), and action (what it
executes). It then reviews applications and evaluation methods.

**How it connects to JARVIS OS:**

- Profile: the terse assistant persona defined in `jarvis/modules/chat.py`.
- Memory: notes and the bounded chat history, stored as local JSON.
- Planning: the parser plus the local-replies / skills / LLM decision order.
- Action: the execution layer (`pccontrol`, `apps`, files, scheduler).
- The survey's evaluation chapter supports the project's testing approach
  (task-success tests, failure-path tests, honest reporting).

**Where to cite it:** Literature Review (to define what an LLM agent is)
and System Design (to justify the four-layer architecture).

---

## 4. Robust Speech Recognition via Large-Scale Weak Supervision (Whisper)

**Citation (IEEE style):** A. Radford, J. W. Kim, T. Xu, G. Brockman,
C. McLeavey, and I. Sutskever, "Robust speech recognition via large-scale
weak supervision," in Proc. 40th Int. Conf. Machine Learning (ICML),
PMLR vol. 202, pp. 28492-28518, 2023.

**BibTeX:**

```bibtex
@inproceedings{radford2023robust,
  title={Robust Speech Recognition via Large-Scale Weak Supervision},
  author={Radford, Alec and Kim, Jong Wook and Xu, Tao and Brockman, Greg and McLeavey, Christine and Sutskever, Ilya},
  booktitle={Proceedings of the 40th International Conference on Machine Learning},
  pages={28492--28518},
  year={2023},
  volume={202},
  series={Proceedings of Machine Learning Research},
  publisher={PMLR}
}
```

**Links:** https://proceedings.mlr.press/v202/radford23a.html and
https://arxiv.org/abs/2212.04356

**What it is:** The Whisper model, trained on 680,000 hours of weakly
labeled audio, showed that large-scale speech recognition can be robust
across accents, noise and languages without per-dataset tuning. It is the
standard modern reference for speech-to-text and the leading open-weight
option for running recognition locally.

**How it connects to JARVIS OS:**

- The project's voice input is speech-to-text; Whisper defines the
  state of the art that the browser Web Speech API is compared against.
- It is the recommended local (offline, private) STT provider in roadmap
  Phase 3, replacing the cloud speech service the project currently uses.
- The privacy argument (audio never leaving the machine) is grounded in
  this line of work.

**Where to cite it:** Literature Review (speech recognition) and Future
Work (local speech recognition provider).

---

## 5. GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers

**Citation (IEEE style):** E. Frantar, S. Ashkboos, T. Hoefler, and
D. Alistarh, "GPTQ: Accurate post-training quantization for generative
pre-trained transformers," in Proc. 11th Int. Conf. Learning
Representations (ICLR), Kigali, Rwanda, 2023. arXiv:2210.17323.

**BibTeX:**

```bibtex
@inproceedings{frantar2023gptq,
  title={GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers},
  author={Frantar, Elias and Ashkboos, Saleh and Hoefler, Torsten and Alistarh, Dan},
  booktitle={International Conference on Learning Representations (ICLR)},
  year={2023}
}
```

**Links:** https://arxiv.org/abs/2210.17323

**What it is:** GPTQ introduced one-shot weight quantization that shrinks
large language models to 3 or 4 bits per weight with negligible accuracy
loss, which is what made it practical to run big models on a single GPU.
It is one of the foundational papers behind the "run a useful LLM on
consumer hardware" movement, together with the quantization families used
by llama.cpp/Ollama.

**How it connects to JARVIS OS:**

- The project measured its limits: the 7B model at Q4 needed 5.2 GB of
  VRAM but the GPU has 6 GB total, so 18% spilled to CPU and answers took
  11-20 seconds. Switching to the Q3 quantized model (about 3.9 GB) fits
  fully on the GPU and answers at about 37 tokens per second.
- This is exactly the compression-versus-quality trade-off the paper
  formalizes, applied to a real deployment decision.
- It supports the project's "local AI, no cloud bill, data stays on the
  machine" claim by explaining why small quantized models are viable.

**Where to cite it:** Implementation (why the Q3 model was chosen) and
Results (the measured latency/VRAM comparison).

---

## How to use these in your report

IEEE numeric style example for your Literature Review:

> Building a personal assistant follows the perceive-plan-act loop
> established by memory-augmented agents [1]. The interaction between
> reasoning and tool use is grounded in ReAct [2], and this project
> adopts the profile-memory-planning-action framework from the LLM agent
> survey [3]. Speech input is compared against the Whisper line of work
> [4], and the local model deployment uses 3-4 bit quantization as
> formalized by GPTQ [5].

One-sentence uses you can adapt:

1. "JARVIS-1 [1] demonstrates that LLM agents benefit from memory, which
   this project implements as a local notes store and bounded chat
   history."
2. "Following ReAct [2], the language model in this project proposes and
   explains actions, but all real effects pass through deterministic
   tools."
3. "The architecture follows the unified agent framework of Wang et al.
   [3]: profile, memory, planning and action as separate layers."
4. "Voice input relies on cloud speech recognition today, with Whisper
   [4] identified as the local offline replacement for privacy."
5. "The choice of a 3-bit quantized 7B model follows the compression
   trade-offs established by GPTQ [5], measured on the target laptop's
   6 GB GPU."

Note: cite these as related work and design grounding. The project does
not claim to replicate or outperform any of them; it applies their ideas
to a personal Windows assistant with honest, measured results.
